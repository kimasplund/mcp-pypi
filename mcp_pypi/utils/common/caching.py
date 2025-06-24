"""
Caching utilities for MCP-PyPI.

This module provides utilities for caching API responses and function results
to reduce API calls and improve performance.
"""

import hashlib
import json
import logging
import os
import re
import shutil
import threading
import time
from collections import OrderedDict
from enum import Enum
from functools import wraps
from typing import (Any, Callable, Dict, List, Optional, Pattern, TypeVar,
                    Union, cast)

from mcp_pypi.utils.common.constants import (DEFAULT_CACHE_DIR,
                                             DEFAULT_CACHE_MAX_SIZE,
                                             DEFAULT_CACHE_TTL)

# Set up logging
logger = logging.getLogger(__name__)

# Type variables for function signatures
T = TypeVar("T")
R = TypeVar("R")

# Global cache instances
_cache = None
_hybrid_cache = None


class EvictionStrategy(Enum):
    """Enumeration of cache eviction strategies."""

    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live


class Cache:
    """A disk-based cache implementation for storing API responses and function results."""

    def __init__(
        self,
        cache_dir: str = DEFAULT_CACHE_DIR,
        ttl: int = DEFAULT_CACHE_TTL,
        max_size: int = DEFAULT_CACHE_MAX_SIZE,
    ):
        """Initialize the cache.

        Args:
            cache_dir: Directory to store cache files
            ttl: Time-to-live for cache entries in seconds
            max_size: Maximum cache size in bytes
        """
        self.cache_dir = cache_dir
        self.ttl = ttl
        self.max_size = max_size

        # Create cache directory if it doesn't exist
        os.makedirs(self.cache_dir, exist_ok=True)
        logger.debug("Cache initialized at %s", self.cache_dir)

        # Perform initial cleanup if needed
        self._cleanup_cache_if_needed()

    def _get_cache_path(self, key: str) -> str:
        """Get the file path for a cache entry.

        Args:
            key: Cache key

        Returns:
            The file path for the cache entry
        """
        # Use a hash to ensure the filename is valid
        filename = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, filename)

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from the cache.

        Args:
            key: Cache key

        Returns:
            The cached value, or None if not found or expired
        """
        path = self._get_cache_path(key)

        if not os.path.exists(path):
            logger.debug("Cache miss for key %s", key)
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            # Check if cache entry has expired
            if cache_data.get("expires_at", 0) < time.time():
                logger.debug("Cache expired for key %s", key)
                try:
                    os.remove(path)
                except OSError as e:
                    logger.exception("Error removing cache file: %s", e)
                return None

            logger.debug("Cache hit for key %s", key)
            return cache_data.get("value")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Error reading cache file %s: %s", path, e)
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Store a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds, or None to use the default

        Returns:
            True if the value was cached successfully, False otherwise
        """
        if ttl is None:
            ttl = self.ttl

        path = self._get_cache_path(key)
        temp_path = f"{path}.tmp"

        try:
            # Write to temporary file first for atomic operations
            cache_data = {
                "value": value,
                "expires_at": time.time() + ttl,
                "created_at": time.time(),
            }

            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f)

            # Move the temporary file to the final path (atomic operation)
            shutil.move(temp_path, path)

            logger.debug("Cached value for key %s", key)

            # Trigger cleanup if needed
            self._cleanup_cache_if_needed()
            return True
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to cache value for key %s: %s", key, e)
            # Clean up the temporary file if it exists
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            return False

    def _get_cache_size(self) -> int:
        """Get the total size of the cache in bytes.

        Returns:
            The total size of all cache files in bytes
        """
        total_size = 0
        for filename in os.listdir(self.cache_dir):
            file_path = os.path.join(self.cache_dir, filename)
            if os.path.isfile(file_path):
                total_size += os.path.getsize(file_path)
        return total_size

    def _get_cache_entries(self) -> List[Dict[str, Any]]:
        """Get all cache entries with their metadata.

        Returns:
            List of cache entries with metadata
        """
        entries = []
        for filename in os.listdir(self.cache_dir):
            file_path = os.path.join(self.cache_dir, filename)
            if os.path.isfile(file_path):
                try:
                    stat = os.stat(file_path)
                    with open(file_path, "r", encoding="utf-8") as f:
                        try:
                            entry_data = json.load(f)
                            entries.append(
                                {
                                    "path": file_path,
                                    "size": stat.st_size,
                                    "created_at": entry_data.get(
                                        "created_at", stat.st_mtime
                                    ),
                                    "expires_at": entry_data.get("expires_at", 0),
                                }
                            )
                        except json.JSONDecodeError:
                            # Handle corrupted cache files
                            entries.append(
                                {
                                    "path": file_path,
                                    "size": stat.st_size,
                                    "created_at": stat.st_mtime,
                                    "expires_at": 0,  # Mark as expired
                                }
                            )
                except OSError:
                    # Skip files that can't be accessed
                    continue
        return entries

    def _cleanup_cache_if_needed(self) -> None:
        """Check if cache cleanup is needed and perform it if necessary."""
        cache_size = self._get_cache_size()
        if cache_size > self.max_size:
            logger.info(
                "Cache size (%s bytes) exceeds limit (%s bytes). Cleaning up...",
                cache_size,
                self.max_size,
            )
            self._cleanup_cache()

    def _cleanup_cache(self) -> None:
        """Remove oldest cache entries until the cache is under the size limit."""
        entries = self._get_cache_entries()

        # First, remove expired entries
        current_time = time.time()
        for entry in entries[:]:
            if entry["expires_at"] < current_time:
                try:
                    os.remove(entry["path"])
                    entries.remove(entry)
                    logger.debug("Removed expired cache entry: %s", entry["path"])
                except OSError as e:
                    logger.exception("Error removing cache file: %s", e)

        # If still over size limit, remove oldest entries
        if sum(entry["size"] for entry in entries) > self.max_size:
            # Sort by creation time (oldest first)
            entries.sort(key=lambda e: e["created_at"])

            # Remove entries until we're under the limit
            current_size = sum(entry["size"] for entry in entries)
            for entry in entries:
                if current_size <= self.max_size:
                    break

                try:
                    os.remove(entry["path"])
                    current_size -= entry["size"]
                    logger.debug("Removed old cache entry: %s", entry["path"])
                except OSError as e:
                    logger.exception("Error removing cache file: %s", e)

    def clear(self) -> None:
        """Clear all entries from the cache."""
        for filename in os.listdir(self.cache_dir):
            file_path = os.path.join(self.cache_dir, filename)
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                except OSError as e:
                    logger.exception("Error removing cache file: %s", e)

        logger.info("Cache cleared")

    def invalidate(self, key: str) -> bool:
        """Invalidate a specific cache entry.

        Args:
            key: Cache key to invalidate

        Returns:
            True if the entry was invalidated successfully, False otherwise
        """
        path = self._get_cache_path(key)
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.debug("Invalidated cache entry for key %s", key)
                return True
            except OSError as e:
                logger.exception("Error removing cache file: %s", e)
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache.

        Returns:
            Dictionary with cache statistics
        """
        entries = self._get_cache_entries()
        current_time = time.time()

        return {
            "total_entries": len(entries),
            "total_size": sum(entry["size"] for entry in entries),
            "active_entries": sum(
                1 for entry in entries if entry["expires_at"] > current_time
            ),
            "expired_entries": sum(
                1 for entry in entries if entry["expires_at"] <= current_time
            ),
            "max_size": self.max_size,
            "ttl": self.ttl,
            "cache_dir": self.cache_dir,
        }


class HybridCache(Cache):
    """
    A hybrid cache implementation that combines in-memory and disk-based caching.

    This cache provides improved performance through memory caching while maintaining
    persistence through file-based caching. It also adds thread safety and additional
    features like multiple eviction strategies and enhanced metrics.
    """

    # pylint: disable=too-many-arguments
    # pylint: disable=R0917
    def __init__(
        self,
        cache_dir: str = DEFAULT_CACHE_DIR,
        ttl: int = DEFAULT_CACHE_TTL,
        max_size: int = DEFAULT_CACHE_MAX_SIZE,
        memory_max_size: int = 1024,
        eviction_strategy: EvictionStrategy = EvictionStrategy.LRU,
    ):
        """Initialize the hybrid cache.

        Args:
            cache_dir: Directory to store cache files
            ttl: Time-to-live for cache entries in seconds
            max_size: Maximum cache size in bytes for disk cache
            memory_max_size: Maximum number of items in the memory cache
            eviction_strategy: Strategy to use for cache eviction
        """
        super().__init__(cache_dir, ttl, max_size)
        self._memory_cache = OrderedDict()  # LRU cache by default
        self._access_count = {}  # For LFU strategy
        self.memory_max_size = memory_max_size
        self.eviction_strategy = eviction_strategy  # Set inside __init__
        self._lock = threading.RLock()  # Use recursive lock for thread safety

        # Metrics
        self._metrics = {
            "memory_hits": 0,
            "memory_misses": 0,
            "disk_hits": 0,
            "disk_misses": 0,
            "sets": 0,
            "invalidations": 0,
        }

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from the cache.

        First checks the in-memory cache, then falls back to the disk cache.

        Args:
            key: Cache key

        Returns:
            The cached value, or None if not found or expired
        """
        with self._lock:
            # Try to get from memory cache first
            if key in self._memory_cache:
                cache_data = self._memory_cache[key]

                # Check if the memory cache entry has expired
                if cache_data.get("expires_at", 0) < time.time():
                    # Remove from memory cache
                    self._memory_cache.pop(key, None)
                    self._access_count.pop(key, None)
                    self._metrics["memory_misses"] += 1
                else:
                    # Update access metrics for the entry
                    self._update_access_metrics(key)

                    self._metrics["memory_hits"] += 1
                    return cache_data.get("value")

            # Memory cache miss, try disk cache
            self._metrics["memory_misses"] += 1

            # Get from disk cache
            result = super().get(key)

            if result is not None:
                # Found in disk cache, add to memory cache
                self._metrics["disk_hits"] += 1
                self._add_to_memory_cache(key, result, None)
                return result

            self._metrics["disk_misses"] += 1
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Store a value in both memory and disk cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds, or None to use the default

        Returns:
            True if the value was cached successfully, False otherwise
        """
        with self._lock:
            self._metrics["sets"] += 1

            # Add to memory cache
            self._add_to_memory_cache(key, value, ttl)

            # Add to disk cache
            return super().set(key, value, ttl)

    def invalidate(self, key: str) -> bool:
        """Invalidate a specific cache entry in both memory and disk cache.

        Args:
            key: Cache key to invalidate

        Returns:
            True if the entry was invalidated successfully, False otherwise
        """
        with self._lock:
            self._metrics["invalidations"] += 1

            # Remove from memory cache
            memory_removed = key in self._memory_cache
            if memory_removed:
                self._memory_cache.pop(key, None)
                self._access_count.pop(key, None)

            # Remove from disk cache
            disk_removed = super().invalidate(key)

            return memory_removed or disk_removed

    def invalidate_pattern(self, pattern: Union[str, Pattern]) -> int:
        """Invalidate all cache entries matching a pattern.

        Args:
            pattern: Regex pattern to match cache keys against

        Returns:
            Number of invalidated entries
        """
        with self._lock:
            if isinstance(pattern, str):
                pattern = re.compile(pattern)

            # Find matching keys in memory cache
            memory_keys = [k for k in self._memory_cache.keys() if pattern.search(k)]

            # Remove matching keys from memory cache
            for key in memory_keys:
                self._memory_cache.pop(key, None)
                self._access_count.pop(key, None)

            # Store the actual file paths to remove
            disk_paths_to_remove = []
            disk_keys = []

            # First, get all cache entries
            entries = self._get_cache_entries()

            # For each entry, load it to check if the key matches the pattern
            for entry in entries:
                file_path = entry["path"]
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        try:
                            entry_data = json.load(f)
                            # The disk cache doesn't store the key, so we need to get it
                            # from the filename. We reverse-engineer the key by checking
                            # if the hash matches
                            if (
                                entry_data
                                and entry_data.get("expires_at", 0) > time.time()
                            ):
                                for key in memory_keys:
                                    if file_path.endswith(
                                        hashlib.md5(key.encode()).hexdigest()
                                    ):
                                        disk_paths_to_remove.append(file_path)
                                        disk_keys.append(key)
                                        break
                        except json.JSONDecodeError:
                            # Skip invalid JSON files
                            pass
                except OSError:
                    # Skip files that can't be accessed
                    pass

            # Remove matching files from disk
            for file_path in disk_paths_to_remove:
                try:
                    os.remove(file_path)
                except OSError:
                    # Skip files that can't be removed
                    pass

            # For additional invalidation, use individual invalidate calls
            # which is more reliable for key-based invalidation
            for key in memory_keys:
                super().invalidate(key)

            self._metrics["invalidations"] += len(set(memory_keys))
            return len(set(memory_keys))

    def clear(self) -> None:
        """Clear all entries from both memory and disk cache."""
        with self._lock:
            # Clear memory cache
            self._memory_cache.clear()
            self._access_count.clear()

            # Clear disk cache
            super().clear()

    def get_enhanced_stats(self) -> Dict[str, Any]:
        """Get enhanced statistics about the cache.

        Returns:
            Dictionary with detailed cache statistics
        """
        with self._lock:
            # Get basic stats
            stats = super().get_stats()

            # Add memory cache stats
            total_requests = (
                self._metrics["memory_hits"] + self._metrics["memory_misses"]
            )
            memory_hit_ratio = (
                self._metrics["memory_hits"] / total_requests
                if total_requests > 0
                else 0
            )

            total_disk_requests = (
                self._metrics["disk_hits"] + self._metrics["disk_misses"]
            )
            disk_hit_ratio = (
                self._metrics["disk_hits"] / total_disk_requests
                if total_disk_requests > 0
                else 0
            )

            overall_hit_ratio = (
                (self._metrics["memory_hits"] + self._metrics["disk_hits"])
                / (total_requests)
                if total_requests > 0
                else 0
            )

            stats.update(
                {
                    "memory_entries": len(self._memory_cache),
                    "memory_max_size": self.memory_max_size,
                    "eviction_strategy": self.eviction_strategy.value,
                    # Hit/miss statistics
                    "memory_hits": self._metrics["memory_hits"],
                    "memory_misses": self._metrics["memory_misses"],
                    "disk_hits": self._metrics["disk_hits"],
                    "disk_misses": self._metrics["disk_misses"],
                    "memory_hit_ratio": memory_hit_ratio,
                    "disk_hit_ratio": disk_hit_ratio,
                    "overall_hit_ratio": overall_hit_ratio,
                    # Operation counts
                    "sets": self._metrics["sets"],
                    "invalidations": self._metrics["invalidations"],
                }
            )

            return stats

    def _add_to_memory_cache(self, key: str, value: Any, ttl: Optional[int]) -> None:
        """Add an entry to the in-memory cache.

        Also handles eviction when the cache is full.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds, or None to use the default
        """
        if ttl is None:
            ttl = self.ttl

        # Create cache entry
        cache_data = {
            "key": key,
            "value": value,
            "expires_at": time.time() + ttl,
            "created_at": time.time(),
            "last_access": time.time(),
        }

        # If key already exists, remove it to update its position in the OrderedDict
        if key in self._memory_cache:
            self._memory_cache.pop(key)

        # Add to memory cache
        self._memory_cache[key] = cache_data

        # Initialize or reset access count for LFU
        self._access_count[key] = 1

        # Perform eviction if needed
        if len(self._memory_cache) > self.memory_max_size:
            self._evict_from_memory_cache()

    def _update_access_metrics(self, key: str) -> None:
        """Update access metrics for a cache entry.

        Args:
            key: Cache key
        """
        if key in self._memory_cache:
            # Update last access time for LRU
            self._memory_cache[key]["last_access"] = time.time()

            # Update access count for LFU
            self._access_count[key] = self._access_count.get(key, 0) + 1

            # If using LRU, move the key to the end of the OrderedDict
            if self.eviction_strategy == EvictionStrategy.LRU:
                value = self._memory_cache.pop(key)
                self._memory_cache[key] = value

    def _evict_from_memory_cache(self) -> None:
        """Evict entries from memory cache based on the chosen strategy."""
        if not self._memory_cache:
            return

        with self._lock:
            if len(self._memory_cache) <= self.memory_max_size:
                return

            # Handle different eviction strategies
            if self.eviction_strategy == EvictionStrategy.LRU:
                # LRU strategy is handled by OrderedDict
                self._memory_cache.popitem(last=False)  # Remove oldest item (first in)
            elif self.eviction_strategy == EvictionStrategy.LFU:
                # LFU strategy: remove least frequently accessed item
                least_used_key = min(self._access_count.items(), key=lambda x: x[1])[0]
                del self._memory_cache[least_used_key]
                del self._access_count[least_used_key]
            elif self.eviction_strategy == EvictionStrategy.TTL:
                # TTL strategy: remove item closest to expiry
                current_time = time.time()
                closest_to_expiry = min(
                    self._memory_cache.items(),
                    key=lambda x: x[1].get("expires_at", current_time) - current_time,
                )
                del self._memory_cache[closest_to_expiry[0]]
                if closest_to_expiry[0] in self._access_count:
                    del self._access_count[closest_to_expiry[0]]

    def _handle_error(self, e: Exception, message: str) -> None:
        """Helper method to handle exceptions."""
        logger.exception("%s: %s", message, e)


def get_cache() -> Cache:
    """Get the global cache instance.

    Returns:
        The global Cache instance
    """
    # pylint: disable=global-statement
    global _cache
    if _cache is None:
        _cache = Cache()
    return _cache


def get_hybrid_cache() -> HybridCache:
    """Get the global hybrid cache instance.

    Returns:
        The global HybridCache instance
    """
    # pylint: disable=global-statement
    global _hybrid_cache
    if _hybrid_cache is None:
        _hybrid_cache = HybridCache()
    return _hybrid_cache


def cached(
    ttl: Optional[int] = None,
    key_prefix: str = "",
    cache_instance: Optional[Cache] = None,
) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """Decorator to cache function results.

    Args:
        ttl: Time-to-live for cache entries in seconds, or None to use the default
        key_prefix: Prefix for cache keys
        cache_instance: Cache instance to use, or None to use the global cache

    Returns:
        Decorator function
    """

    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> R:
            # Get the cache to use
            cache = cache_instance or get_cache()

            # Generate a cache key based on the function name, arguments, and prefix
            func_name = func.__module__ + "." + func.__qualname__
            key_parts = [key_prefix, func_name]

            # Add positional arguments to the key
            for arg in args:
                try:
                    key_parts.append(str(arg))
                except Exception:
                    # If we can't stringify the argument, use its hash
                    key_parts.append(str(hash(arg)))

            # Add keyword arguments to the key (sorted by key for consistency)
            for k, v in sorted(kwargs.items()):
                try:
                    key_parts.append(f"{k}={v}")
                except Exception:
                    key_parts.append(f"{k}={hash(v)}")

            cache_key = "::".join(key_parts)

            # Try to get the result from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cast(R, cached_result)

            # Call the function and cache the result
            result = func(*args, **kwargs)
            try:
                cache.set(cache_key, result, ttl)
            except Exception as e:
                logger.warning("Failed to cache result for %s: %s", func_name, e)

            return result

        return wrapper

    return decorator


def hybrid_cached(
    ttl: Optional[int] = None,
    key_prefix: str = "",
    cache_instance: Optional[HybridCache] = None,
    eviction_strategy: Optional[EvictionStrategy] = None,
) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """Decorator to cache function results using hybrid caching.

    Args:
        ttl: Time-to-live for cache entries in seconds, or None to use the default
        key_prefix: Prefix for cache keys
        cache_instance: Cache instance to use, or None to use the global cache
        eviction_strategy: Strategy to use for cache eviction

    Returns:
        Decorator function
    """

    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> R:
            # Get the cache to use
            cache = cache_instance or get_cache()

            # Ensure we're using a HybridCache
            if not isinstance(cache, HybridCache):
                logger.warning(
                    "hybrid_cached used with non-hybrid cache, falling back to standard cache"
                )
            elif eviction_strategy is not None:
                # We're modifying the eviction_strategy in __init__, so this is okay
                # pylint: disable=attribute-defined-outside-init
                cache.eviction_strategy = eviction_strategy

            # Generate a cache key based on the function name, arguments, and prefix
            func_name = func.__module__ + "." + func.__qualname__
            key_parts = [key_prefix, func_name]

            # Add positional arguments to the key
            for arg in args:
                try:
                    key_parts.append(str(arg))
                except Exception:
                    # If we can't stringify the argument, use its hash
                    key_parts.append(str(hash(arg)))

            # Add keyword arguments to the key (sorted by key for consistency)
            for k, v in sorted(kwargs.items()):
                try:
                    key_parts.append(f"{k}={v}")
                except Exception:
                    key_parts.append(f"{k}={hash(v)}")

            cache_key = "::".join(key_parts)

            # Try to get the result from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cast(R, cached_result)

            # Call the function and cache the result
            result = func(*args, **kwargs)
            try:
                cache.set(cache_key, result, ttl)
            except Exception as e:
                logger.warning("Failed to cache result for %s: %s", func_name, e)

            return result

        return wrapper

    return decorator


def cache_keygen(*args: Any, **kwargs: Any) -> str:
    """Generate a cache key from arbitrary arguments.

    This function can be used to generate consistent cache keys
    outside of the @cached decorator context.

    Args:
        *args: Positional arguments to include in the key
        **kwargs: Keyword arguments to include in the key

    Returns:
        A string that can be used as a cache key
    """
    key_parts = []

    # Add prefix if provided
    if "prefix" in kwargs:
        prefix = kwargs.pop("prefix")
        key_parts.append(str(prefix))

    # Add positional arguments
    for arg in args:
        try:
            key_parts.append(str(arg))
        except Exception:
            key_parts.append(str(hash(arg)))

    # Add keyword arguments (sorted)
    for k, v in sorted(kwargs.items()):
        try:
            key_parts.append(f"{k}={v}")
        except Exception:
            key_parts.append(f"{k}={hash(v)}")

    return "::".join(key_parts)


def invalidate_cached_call(
    func: Callable,
    *args: Any,
    key_prefix: str = "",
    cache_instance: Optional[Cache] = None,
    **kwargs: Any,
) -> bool:
    """Invalidate a cached function call.

    Args:
        func: The function whose cache to invalidate
        *args: The positional arguments of the call to invalidate
        key_prefix: The prefix used when caching
        cache_instance: Cache instance to use, or None to use the global cache
        **kwargs: The keyword arguments of the call to invalidate

    Returns:
        True if the cache entry was invalidated successfully, False otherwise
    """
    # Get the cache to use
    cache = cache_instance or get_cache()

    # Generate the same cache key as the @cached decorator
    func_name = func.__module__ + "." + func.__qualname__
    key_parts = [key_prefix, func_name]

    # Add positional arguments to the key
    for arg in args:
        try:
            key_parts.append(str(arg))
        except Exception:
            key_parts.append(str(hash(arg)))

    # Add keyword arguments to the key (sorted by key for consistency)
    for k, v in sorted(kwargs.items()):
        try:
            key_parts.append(f"{k}={v}")
        except Exception:
            key_parts.append(f"{k}={hash(v)}")

    cache_key = "::".join(key_parts)
    return cache.invalidate(cache_key)
