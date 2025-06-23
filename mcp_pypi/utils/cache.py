"""
Cache system for MCP PyPI client.

This module provides a flexible caching system for the MCP PyPI client,
supporting multiple backends and strategies for efficient data retrieval.
"""

import asyncio
import json
import logging
import os
import pickle
import time
import io
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Tuple,
    TypeVar,
    Union,
    cast,
)

T = TypeVar("T")

logger = logging.getLogger("mcp_pypi.cache")


class RestrictedUnpickler(pickle.Unpickler):
    """Restricted unpickler that only allows safe types."""
    
    def find_class(self, module, name):
        # Only allow specific safe types
        ALLOWED_MODULES = {
            'builtins',
            '__builtin__',
            'collections',
            'datetime',
            'mcp_pypi.core.models',  # Allow our own model classes
        }
        
        # Allow basic types
        if module in ALLOWED_MODULES:
            return super().find_class(module, name)
        
        # Allow specific safe classes
        if module == 'mcp_pypi.core.models' and name in [
            'PackageInfo', 'VersionInfo', 'DependenciesResult',
            'SearchResult', 'StatsResult', 'ErrorResult'
        ]:
            return super().find_class(module, name)
            
        raise pickle.UnpicklingError(f"Global '{module}.{name}' is not allowed")


def restricted_loads(data: bytes) -> Any:
    """Load pickle data with restrictions on allowed types."""
    return RestrictedUnpickler(io.BytesIO(data)).load()


class CacheProtocol(Protocol):
    """Protocol defining the interface for all cache implementations."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Retrieve an item from the cache.

        Args:
            key: The cache key to retrieve

        Returns:
            The cached value or None if not found or expired
        """
        ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Store an item in the cache.

        Args:
            key: The cache key
            value: The value to cache
            ttl: Time-to-live in seconds, or None for default

        Returns:
            True if successful, False otherwise
        """
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete an item from the cache.

        Args:
            key: The cache key to delete

        Returns:
            True if deleted, False if not found or error
        """
        ...

    @abstractmethod
    async def clear(self, namespace: Optional[str] = None) -> bool:
        """Clear all items from the cache, optionally within a namespace.

        Args:
            namespace: Optional namespace to restrict clearing to

        Returns:
            True if successful, False otherwise
        """
        ...

    @abstractmethod
    async def has(self, key: str) -> bool:
        """Check if an item exists in the cache and is not expired.

        Args:
            key: The cache key to check

        Returns:
            True if exists and not expired, False otherwise
        """
        ...


class BaseCache(ABC):
    """Base class for all cache implementations."""

    def __init__(self, ttl: int = 3600, namespace: str = "pypi"):
        """Initialize the cache.

        Args:
            ttl: Default time-to-live in seconds
            namespace: Cache namespace for key isolation
        """
        self.ttl = ttl
        self.namespace = namespace
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "clears": 0,
        }

    def _make_key(self, key: str) -> str:
        """Create a namespaced cache key.

        Args:
            key: The original key

        Returns:
            Namespaced key
        """
        return f"{self.namespace}:{key}" if self.namespace else key

    def _parse_key(self, full_key: str) -> Tuple[str, str]:
        """Parse a namespaced key into namespace and key.

        Args:
            full_key: The full namespaced key

        Returns:
            Tuple of (namespace, key)
        """
        if ":" not in full_key:
            return ("", full_key)
        namespace, key = full_key.split(":", 1)
        return (namespace, key)

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve an item from the cache with metrics.

        Args:
            key: The cache key to retrieve

        Returns:
            The cached value or None if not found or expired
        """
        namespaced_key = self._make_key(key)
        value = await self._get(namespaced_key)

        if value is not None:
            self._stats["hits"] += 1
            logger.debug(f"Cache hit: {namespaced_key}")
        else:
            self._stats["misses"] += 1
            logger.debug(f"Cache miss: {namespaced_key}")

        return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Store an item in the cache with metrics.

        Args:
            key: The cache key
            value: The value to cache
            ttl: Time-to-live in seconds, or None for default

        Returns:
            True if successful, False otherwise
        """
        namespaced_key = self._make_key(key)
        effective_ttl = ttl if ttl is not None else self.ttl
        result = await self._set(namespaced_key, value, effective_ttl)

        if result:
            self._stats["sets"] += 1
            logger.debug(f"Cache set: {namespaced_key} (TTL: {effective_ttl}s)")

        return result

    async def delete(self, key: str) -> bool:
        """Delete an item from the cache with metrics.

        Args:
            key: The cache key to delete

        Returns:
            True if deleted, False if not found or error
        """
        namespaced_key = self._make_key(key)
        result = await self._delete(namespaced_key)

        if result:
            self._stats["deletes"] += 1
            logger.debug(f"Cache delete: {namespaced_key}")

        return result

    async def clear(self, namespace: Optional[str] = None) -> bool:
        """Clear all items from the cache, optionally within a namespace.

        Args:
            namespace: Optional namespace to restrict clearing to

        Returns:
            True if successful, False otherwise
        """
        target_namespace = namespace if namespace is not None else self.namespace
        result = await self._clear(target_namespace)

        if result:
            self._stats["clears"] += 1
            logger.debug(f"Cache clear: {target_namespace or 'all'}")

        return result

    async def has(self, key: str) -> bool:
        """Check if an item exists in the cache and is not expired.

        Args:
            key: The cache key to check

        Returns:
            True if exists and not expired, False otherwise
        """
        namespaced_key = self._make_key(key)
        return await self._has(namespaced_key)

    def get_stats(self) -> Dict[str, Union[int, float]]:
        """Get cache usage statistics.

        Returns:
            Dictionary of usage statistics
        """
        stats: Dict[str, Union[int, float]] = {}
        stats.update(self._stats)
        total = stats["hits"] + stats["misses"]
        stats["hit_ratio"] = stats["hits"] / total if total > 0 else 0
        return stats

    def reset_stats(self) -> None:
        """Reset all cache usage statistics."""
        for key in self._stats:
            self._stats[key] = 0

    @abstractmethod
    async def _get(self, key: str) -> Optional[Any]:
        """Retrieve an item from the cache (implementation)."""
        pass

    @abstractmethod
    async def _set(self, key: str, value: Any, ttl: int) -> bool:
        """Store an item in the cache (implementation)."""
        pass

    @abstractmethod
    async def _delete(self, key: str) -> bool:
        """Delete an item from the cache (implementation)."""
        pass

    @abstractmethod
    async def _clear(self, namespace: Optional[str]) -> bool:
        """Clear all items from the cache (implementation)."""
        pass

    @abstractmethod
    async def _has(self, key: str) -> bool:
        """Check if an item exists in the cache (implementation)."""
        pass


class MemoryCache(BaseCache):
    """In-memory LRU cache implementation."""

    def __init__(self, max_size: int = 1000, ttl: int = 3600, namespace: str = "pypi"):
        """Initialize the memory cache.

        Args:
            max_size: Maximum number of entries before LRU eviction
            ttl: Default time-to-live in seconds
            namespace: Cache namespace for key isolation
        """
        super().__init__(ttl, namespace)
        self.max_size = max_size
        self._cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def _get(self, key: str) -> Optional[Any]:
        """Retrieve an item from the memory cache.

        Args:
            key: The cache key to retrieve

        Returns:
            The cached value or None if not found or expired
        """
        async with self._lock:
            if key not in self._cache:
                return None

            value, expiry = self._cache[key]

            # Check if expired
            if expiry < time.time():
                del self._cache[key]
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return value

    async def _set(self, key: str, value: Any, ttl: int) -> bool:
        """Store an item in the memory cache.

        Args:
            key: The cache key
            value: The value to cache
            ttl: Time-to-live in seconds

        Returns:
            True if successful
        """
        expiry = time.time() + ttl

        async with self._lock:
            # If at capacity, remove least recently used item
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._cache.popitem(last=False)

            self._cache[key] = (value, expiry)
            self._cache.move_to_end(key)

        return True

    async def _delete(self, key: str) -> bool:
        """Delete an item from the memory cache.

        Args:
            key: The cache key to delete

        Returns:
            True if deleted, False if not found
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def _clear(self, namespace: Optional[str]) -> bool:
        """Clear all items from the memory cache.

        Args:
            namespace: Optional namespace to restrict clearing to

        Returns:
            True if successful
        """
        async with self._lock:
            if namespace is None:
                self._cache.clear()
            else:
                # Keep only keys not in the target namespace
                keys_to_remove = [
                    k for k in self._cache.keys() if k.startswith(f"{namespace}:")
                ]
                for k in keys_to_remove:
                    del self._cache[k]

        return True

    async def _has(self, key: str) -> bool:
        """Check if an item exists in the memory cache and is not expired.

        Args:
            key: The cache key to check

        Returns:
            True if exists and not expired, False otherwise
        """
        async with self._lock:
            if key not in self._cache:
                return False

            _, expiry = self._cache[key]

            # Check if expired
            if expiry < time.time():
                del self._cache[key]
                return False

            return True


class FileCache(BaseCache):
    """File-based cache implementation."""

    def __init__(
        self,
        directory: Union[str, Path] = ".cache/pypi",
        ttl: int = 3600,
        namespace: str = "pypi",
        serializer: str = "pickle",
    ):
        """Initialize the file cache.

        Args:
            directory: Directory to store cache files
            ttl: Default time-to-live in seconds
            namespace: Cache namespace for key isolation
            serializer: Serialization format ('pickle', 'json')
        """
        super().__init__(ttl, namespace)
        self.directory = Path(directory)
        self.serializer = serializer
        self._ensure_directory()
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    def _ensure_directory(self) -> None:
        """Ensure the cache directory exists."""
        os.makedirs(self.directory, exist_ok=True)

    def _get_path(self, key: str) -> Path:
        """Get the file path for a cache key.

        Args:
            key: The cache key

        Returns:
            Path to the cache file
        """
        # Use a hash to avoid illegal filename characters
        hashed_key = str(hash(key) % 1000000).zfill(6)
        filename = f"{hashed_key}_{key.replace('/', '_').replace(':', '_')}"
        return self.directory / filename

    async def _get_lock(self, key: str) -> asyncio.Lock:
        """Get a lock for a specific cache key.

        Args:
            key: The cache key

        Returns:
            Lock for the key
        """
        async with self._global_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]

    def _serialize(self, value: Any) -> bytes:
        """Serialize a value to bytes.

        Args:
            value: The value to serialize

        Returns:
            Serialized bytes
        """
        if self.serializer == "json":
            return json.dumps({"data": value, "timestamp": time.time()}).encode("utf-8")
        else:  # Default to pickle
            return pickle.dumps({"data": value, "timestamp": time.time()})

    def _deserialize(self, data: bytes) -> Tuple[Any, float]:
        """Deserialize bytes to a value and timestamp.

        Args:
            data: The serialized data

        Returns:
            Tuple of (value, timestamp)
        """
        try:
            if self.serializer == "json":
                parsed = json.loads(data.decode("utf-8"))
            else:  # Default to pickle
                parsed = restricted_loads(data)

            return parsed["data"], parsed["timestamp"]
        except (json.JSONDecodeError, pickle.UnpicklingError, KeyError) as e:
            logger.warning(f"Failed to deserialize cache data: {e}")
            return None, 0

    async def _get(self, key: str) -> Optional[Any]:
        """Retrieve an item from the file cache.

        Args:
            key: The cache key to retrieve

        Returns:
            The cached value or None if not found or expired
        """
        path = self._get_path(key)
        lock = await self._get_lock(key)

        async with lock:
            if not path.exists():
                return None

            try:
                # Read file and deserialize
                data = path.read_bytes()
                value, timestamp = self._deserialize(data)

                # Check if expired
                if value is None or timestamp + self.ttl < time.time():
                    try:
                        path.unlink()
                    except OSError:
                        pass
                    return None

                return value
            except (OSError, EOFError) as e:
                logger.warning(f"Error reading cache file {path}: {e}")
                return None

    async def _set(self, key: str, value: Any, ttl: int) -> bool:
        """Store an item in the file cache.

        Args:
            key: The cache key
            value: The value to cache
            ttl: Time-to-live in seconds

        Returns:
            True if successful, False on error
        """
        path = self._get_path(key)
        lock = await self._get_lock(key)

        async with lock:
            try:
                # Serialize and write
                data = self._serialize(value)
                path.write_bytes(data)
                return True
            except (OSError, pickle.PickleError, TypeError) as e:
                logger.warning(f"Error writing cache file {path}: {e}")
                return False

    async def _delete(self, key: str) -> bool:
        """Delete an item from the file cache.

        Args:
            key: The cache key to delete

        Returns:
            True if deleted, False if not found or error
        """
        path = self._get_path(key)
        lock = await self._get_lock(key)

        async with lock:
            if not path.exists():
                return False

            try:
                path.unlink()
                return True
            except OSError as e:
                logger.warning(f"Error deleting cache file {path}: {e}")
                return False

    async def _clear(self, namespace: Optional[str]) -> bool:
        """Clear all items from the file cache.

        Args:
            namespace: Optional namespace to restrict clearing to

        Returns:
            True if successful, even if no files matched
        """
        async with self._global_lock:
            try:
                # Get all cache files
                files = list(self.directory.glob("*"))

                if namespace is not None:
                    # Only delete files for this namespace
                    files = [
                        f
                        for f in files
                        if f.name.split("_", 1)[1].startswith(f"{namespace}_")
                    ]

                # Delete each file
                for file in files:
                    try:
                        file.unlink()
                    except OSError as e:
                        logger.warning(f"Error deleting cache file {file}: {e}")

                return True
            except OSError as e:
                logger.warning(f"Error clearing cache directory: {e}")
                return False

    async def _has(self, key: str) -> bool:
        """Check if an item exists in the file cache and is not expired.

        Args:
            key: The cache key to check

        Returns:
            True if exists and not expired, False otherwise
        """
        path = self._get_path(key)
        lock = await self._get_lock(key)

        async with lock:
            if not path.exists():
                return False

            try:
                # Read file and deserialize
                data = path.read_bytes()
                _, timestamp = self._deserialize(data)

                # Check if expired
                if timestamp + self.ttl < time.time():
                    try:
                        path.unlink()
                    except OSError:
                        pass
                    return False

                return True
            except (OSError, EOFError) as e:
                logger.warning(f"Error checking cache file {path}: {e}")
                return False


# Optional Redis cache if aioredis is available
try:
    import aioredis  # type: ignore[import-not-found]

    class RedisCache(BaseCache):
        """Redis-based distributed cache implementation."""

        def __init__(
            self,
            host: str = "localhost",
            port: int = 6379,
            db: int = 0,
            password: Optional[str] = None,
            prefix: str = "pypi_cache:",
            ttl: int = 3600,
            namespace: str = "pypi",
            serializer: str = "json",
            pool_size: int = 10,
        ):
            """Initialize the Redis cache.

            Args:
                host: Redis server hostname
                port: Redis server port
                db: Redis database number
                password: Optional Redis password
                prefix: Key prefix for Redis
                ttl: Default time-to-live in seconds
                namespace: Cache namespace for key isolation
                serializer: Serialization format ('pickle', 'json')
                pool_size: Redis connection pool size
            """
            super().__init__(ttl, namespace)
            self.prefix = prefix
            self.serializer = serializer
            self.redis_url = f"redis://{host}:{port}/{db}"
            if password:
                self.redis_url = f"redis://:{password}@{host}:{port}/{db}"
            self.pool_size = pool_size
            self._redis: Optional[aioredis.Redis] = None
            self._lock = asyncio.Lock()

        async def _ensure_connection(self) -> aioredis.Redis:
            """Ensure Redis connection is established.

            Returns:
                Redis client
            """
            if self._redis is None:
                async with self._lock:
                    if self._redis is None:
                        try:
                            self._redis = aioredis.from_url(
                                self.redis_url,
                                max_connections=self.pool_size,
                                decode_responses=False,
                            )
                        except Exception as e:
                            logger.error(f"Failed to connect to Redis: {e}")
                            raise

            return self._redis

        def _make_redis_key(self, key: str) -> str:
            """Create a prefixed Redis key.

            Args:
                key: The cache key

            Returns:
                Prefixed Redis key
            """
            return f"{self.prefix}{key}"

        def _serialize(self, value: Any) -> bytes:
            """Serialize a value to bytes.

            Args:
                value: The value to serialize

            Returns:
                Serialized bytes
            """
            if self.serializer == "json":
                return json.dumps(value).encode("utf-8")
            else:  # Default to pickle
                return pickle.dumps(value)

        def _deserialize(self, data: bytes) -> Any:
            """Deserialize bytes to a value.

            Args:
                data: The serialized data

            Returns:
                Deserialized value
            """
            try:
                if self.serializer == "json":
                    return json.loads(data.decode("utf-8"))
                else:  # Default to pickle
                    return restricted_loads(data)
            except (json.JSONDecodeError, pickle.UnpicklingError) as e:
                logger.warning(f"Failed to deserialize Redis data: {e}")
                return None

        async def _get(self, key: str) -> Optional[Any]:
            """Retrieve an item from the Redis cache.

            Args:
                key: The cache key to retrieve

            Returns:
                The cached value or None if not found
            """
            try:
                redis = await self._ensure_connection()
                redis_key = self._make_redis_key(key)
                data = await redis.get(redis_key)

                if data is None:
                    return None

                return self._deserialize(data)
            except Exception as e:
                logger.warning(f"Error retrieving from Redis: {e}")
                return None

        async def _set(self, key: str, value: Any, ttl: int) -> bool:
            """Store an item in the Redis cache.

            Args:
                key: The cache key
                value: The value to cache
                ttl: Time-to-live in seconds

            Returns:
                True if successful, False on error
            """
            try:
                redis = await self._ensure_connection()
                redis_key = self._make_redis_key(key)
                serialized = self._serialize(value)

                await redis.setex(redis_key, ttl, serialized)
                return True
            except Exception as e:
                logger.warning(f"Error setting in Redis: {e}")
                return False

        async def _delete(self, key: str) -> bool:
            """Delete an item from the Redis cache.

            Args:
                key: The cache key to delete

            Returns:
                True if deleted, False on error
            """
            try:
                redis = await self._ensure_connection()
                redis_key = self._make_redis_key(key)
                result = await redis.delete(redis_key)
                return result > 0
            except Exception as e:
                logger.warning(f"Error deleting from Redis: {e}")
                return False

        async def _clear(self, namespace: Optional[str]) -> bool:
            """Clear all items from the Redis cache.

            Args:
                namespace: Optional namespace to restrict clearing to

            Returns:
                True if successful, False on error
            """
            try:
                redis = await self._ensure_connection()

                if namespace is None:
                    # Get all keys with our prefix
                    pattern = f"{self.prefix}*"
                else:
                    # Get all keys with our prefix and namespace
                    pattern = f"{self.prefix}{namespace}:*"

                # Use scan for efficient key iteration
                cursor = 0
                deleted_keys = 0

                while True:
                    cursor, keys = await redis.scan(cursor, pattern, 100)
                    if keys:
                        deleted_keys += await redis.delete(*keys)

                    # End of scan
                    if cursor == 0:
                        break

                return True
            except Exception as e:
                logger.warning(f"Error clearing Redis cache: {e}")
                return False

        async def _has(self, key: str) -> bool:
            """Check if an item exists in the Redis cache.

            Args:
                key: The cache key to check

            Returns:
                True if exists, False otherwise
            """
            try:
                redis = await self._ensure_connection()
                redis_key = self._make_redis_key(key)
                result = await redis.exists(redis_key)
                return result > 0
            except Exception as e:
                logger.warning(f"Error checking Redis key: {e}")
                return False

except ImportError:
    # Redis support not available
    pass


class CacheStrategy(ABC):
    """Base class for all cache strategies."""

    def __init__(self, cache: BaseCache):
        """Initialize the cache strategy.

        Args:
            cache: The underlying cache to use
        """
        self.cache = cache

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache using this strategy."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in the cache using this strategy."""
        pass


class StaleWhileRevalidateStrategy(CacheStrategy):
    """Strategy that returns stale data while refreshing in background."""

    def __init__(
        self,
        cache: BaseCache,
        stale_ttl: int = 86400,
        background_refresh: bool = True,
        refresh_callback: Optional[Callable[[str, Any], Any]] = None,
    ):
        """Initialize the stale-while-revalidate strategy.

        Args:
            cache: The underlying cache
            stale_ttl: How long to serve stale data (seconds)
            background_refresh: Whether to refresh in background
            refresh_callback: Optional callback for refreshing data
        """
        super().__init__(cache)
        self.stale_ttl = stale_ttl
        self.background_refresh = background_refresh
        self.refresh_callback = refresh_callback
        self._background_tasks: Dict[str, asyncio.Task] = {}

    async def get(self, key: str) -> Optional[Any]:
        """Get a value with stale-while-revalidate behavior.

        Args:
            key: The cache key

        Returns:
            The cached value or None
        """
        value = await self.cache.get(key)

        if value is None:
            return None

        # Check if we should trigger a refresh
        if self.background_refresh and self.refresh_callback:
            self._schedule_refresh(key, value)

        return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in the cache.

        Args:
            key: The cache key
            value: The value to cache
            ttl: Time-to-live in seconds

        Returns:
            True if successful
        """
        return await self.cache.set(key, value, ttl)

    def _schedule_refresh(self, key: str, old_value: Any) -> None:
        """Schedule a background refresh task.

        Args:
            key: The cache key
            old_value: The current cached value
        """
        if key in self._background_tasks and not self._background_tasks[key].done():
            return  # Already refreshing

        if self.refresh_callback:

            async def refresh_task():
                try:
                    assert self.refresh_callback is not None
                    new_value = await self.refresh_callback(key, old_value)
                    if new_value is not None:
                        await self.cache.set(key, new_value)
                except Exception as e:
                    logger.warning(f"Background refresh failed for {key}: {e}")

            self._background_tasks[key] = asyncio.create_task(refresh_task())


class HierarchicalCache(BaseCache):
    """Cache that combines multiple backends in a hierarchy."""

    def __init__(
        self,
        caches: List[BaseCache],
        ttl: int = 3600,
        namespace: str = "pypi",
        write_strategy: str = "write-through",
    ):
        """Initialize the hierarchical cache.

        Args:
            caches: List of caches in order of access (fastest first)
            ttl: Default time-to-live in seconds
            namespace: Cache namespace for key isolation
            write_strategy: 'write-through' or 'write-back'
        """
        super().__init__(ttl, namespace)
        self.caches = caches
        self.write_strategy = write_strategy

        # Set same namespace for all caches
        for cache in self.caches:
            cache.namespace = namespace

    async def _get(self, key: str) -> Optional[Any]:
        """Retrieve from the fastest cache available.

        Args:
            key: The cache key

        Returns:
            The cached value or None
        """
        # Try each cache in order
        value = None
        found_in_index = -1

        for i, cache in enumerate(self.caches):
            cache_value = await cache.get(key)
            if cache_value is not None:
                value = cache_value
                found_in_index = i
                break

        # If found in a slower cache, populate faster caches
        if value is not None and found_in_index > 0:
            for i in range(found_in_index):
                await self.caches[i].set(key, value, self.ttl)

        return value

    async def _set(self, key: str, value: Any, ttl: int) -> bool:
        """Store in caches according to write strategy.

        Args:
            key: The cache key
            value: The value to cache
            ttl: Time-to-live in seconds

        Returns:
            True if successful in at least one cache
        """
        if self.write_strategy == "write-through":
            # Write to all caches
            results = await asyncio.gather(
                *[cache.set(key, value, ttl) for cache in self.caches],
                return_exceptions=True,
            )
            # Return True if at least one succeeded
            return any(r is True for r in results if not isinstance(r, Exception))
        else:  # write-back
            # Write only to fastest cache
            return await self.caches[0].set(key, value, ttl)

    async def _delete(self, key: str) -> bool:
        """Delete from all caches.

        Args:
            key: The cache key to delete

        Returns:
            True if deleted from at least one cache
        """
        results = await asyncio.gather(
            *[cache.delete(key) for cache in self.caches], return_exceptions=True
        )
        # Return True if at least one succeeded
        return any(r is True for r in results if not isinstance(r, Exception))

    async def _clear(self, namespace: Optional[str]) -> bool:
        """Clear all caches.

        Args:
            namespace: Optional namespace to restrict clearing to

        Returns:
            True if cleared at least one cache
        """
        results = await asyncio.gather(
            *[cache.clear(namespace) for cache in self.caches], return_exceptions=True
        )
        # Return True if at least one succeeded
        return any(r is True for r in results if not isinstance(r, Exception))

    async def _has(self, key: str) -> bool:
        """Check if an item exists in any cache.

        Args:
            key: The cache key to check

        Returns:
            True if exists in at least one cache
        """
        for cache in self.caches:
            if await cache.has(key):
                return True
        return False


@dataclass
class CacheStats:
    """Cache statistics collector."""

    cache: BaseCache
    hits: int = 0
    misses: int = 0
    total_access_time_ns: int = 0
    per_method_stats: Dict[str, "MethodStats"] = field(default_factory=dict)

    @property
    def total(self) -> int:
        """Total number of cache accesses."""
        return self.hits + self.misses

    @property
    def hit_ratio(self) -> float:
        """Cache hit ratio."""
        if self.total == 0:
            return 0
        return self.hits / self.total

    @property
    def average_access_time_ms(self) -> float:
        """Average cache access time in milliseconds."""
        if self.total == 0:
            return 0
        return (self.total_access_time_ns / self.total) / 1_000_000

    def reset(self) -> None:
        """Reset all statistics."""
        self.hits = 0
        self.misses = 0
        self.total_access_time_ns = 0
        self.per_method_stats.clear()


@dataclass
class MethodStats:
    """Statistics for a specific method."""

    method: str
    hits: int = 0
    misses: int = 0

    @property
    def total(self) -> int:
        """Total number of method accesses."""
        return self.hits + self.misses

    @property
    def hit_ratio(self) -> float:
        """Method hit ratio."""
        if self.total == 0:
            return 0
        return self.hits / self.total


class CacheEventEmitter:
    """Event emitter for cache events."""

    def __init__(self, cache: BaseCache):
        """Initialize the event emitter.

        Args:
            cache: The cache to instrument
        """
        self.cache = cache
        self._event_handlers: Dict[str, List[Callable]] = {
            "hit": [],
            "miss": [],
            "set": [],
            "delete": [],
            "clear": [],
        }

        # Wrap cache methods
        self._wrap_methods()

    def on(self, event: str):
        """Decorator to register an event handler.

        Args:
            event: Event name ('hit', 'miss', 'set', 'delete', 'clear')

        Returns:
            Decorator function
        """

        def decorator(func):
            if event in self._event_handlers:
                self._event_handlers[event].append(func)
            return func

        return decorator

    async def _emit(self, event: str, *args, **kwargs) -> None:
        """Emit an event to all registered handlers.

        Args:
            event: Event name
            *args: Arguments to pass to handlers
            **kwargs: Keyword arguments to pass to handlers
        """
        for handler in self._event_handlers.get(event, []):
            try:
                result = handler(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.warning(f"Error in cache event handler: {e}")

    def _wrap_methods(self) -> None:
        """Wrap cache methods to emit events."""
        original_get = self.cache.get
        original_set = self.cache.set
        original_delete = self.cache.delete
        original_clear = self.cache.clear

        @wraps(original_get)
        async def wrapped_get(key: str) -> Optional[Any]:
            start = time.time_ns()
            value = await original_get(key)
            duration = time.time_ns() - start

            if value is not None:
                await self._emit("hit", key, value, duration)
            else:
                await self._emit("miss", key, duration)

            return value

        @wraps(original_set)
        async def wrapped_set(key: str, value: Any, ttl: Optional[int] = None) -> bool:
            result = await original_set(key, value, ttl)
            if result:
                await self._emit("set", key, value, ttl)
            return result

        @wraps(original_delete)
        async def wrapped_delete(key: str) -> bool:
            result = await original_delete(key)
            if result:
                await self._emit("delete", key)
            return result

        @wraps(original_clear)
        async def wrapped_clear(namespace: Optional[str] = None) -> bool:
            result = await original_clear(namespace)
            if result:
                await self._emit("clear", namespace)
            return result

        # Replace methods
        self.cache.get = wrapped_get
        self.cache.set = wrapped_set
        self.cache.delete = wrapped_delete
        self.cache.clear = wrapped_clear


def create_cache_from_config(config: Dict[str, Any]) -> BaseCache:
    """Create a cache instance from configuration.

    Args:
        config: Configuration dictionary

    Returns:
        Configured cache instance
    """
    cache_type = config.get("type", "memory").lower()
    ttl = config.get("ttl", 3600)
    namespace = config.get("namespace", "pypi")

    if cache_type == "memory":
        max_size = config.get("max_size", 1000)
        return MemoryCache(max_size=max_size, ttl=ttl, namespace=namespace)

    elif cache_type == "file":
        directory = config.get("file_path", ".cache/pypi")
        serializer = config.get("serializer", "pickle")
        return FileCache(
            directory=directory, ttl=ttl, namespace=namespace, serializer=serializer
        )

    elif cache_type == "redis":
        # Check if Redis is available
        if "RedisCache" not in globals():
            raise ImportError("Redis cache requires aioredis package")

        redis_url = config.get("redis_url")
        if redis_url:
            # Parse Redis URL for host, port, etc.
            from urllib.parse import urlparse

            parsed = urlparse(redis_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 6379
            password = parsed.password
            path = parsed.path.lstrip("/") if parsed.path else "0"
            db = int(path)
        else:
            # Use individual settings
            host = config.get("host", "localhost")
            port = config.get("port", 6379)
            password = config.get("password")
            db = config.get("db", 0)

        prefix = config.get("prefix", "pypi_cache:")
        serializer = config.get("serializer", "json")
        pool_size = config.get("pool_size", 10)

        return RedisCache(
            host=host,
            port=port,
            db=db,
            password=password,
            prefix=prefix,
            ttl=ttl,
            namespace=namespace,
            serializer=serializer,
            pool_size=pool_size,
        )

    elif cache_type == "hierarchical":
        cache_configs = config.get("caches", [])
        write_strategy = config.get("write_strategy", "write-through")

        if not cache_configs:
            # Default to memory + file
            caches = [
                MemoryCache(ttl=ttl, namespace=namespace),
                FileCache(ttl=ttl, namespace=namespace),
            ]
        else:
            caches = [
                create_cache_from_config({**c, "namespace": namespace})
                for c in cache_configs
            ]

        return HierarchicalCache(
            caches=cast(List[BaseCache], caches), ttl=ttl, namespace=namespace, write_strategy=write_strategy
        )

    else:
        raise ValueError(f"Unknown cache type: {cache_type}")
