"""
Cache management for the MCP-PyPI client.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mcp_pypi.core.models import ErrorCode, PyPIClientConfig, format_error

logger = logging.getLogger("mcp-pypi.cache")


class AsyncCacheManager:
    """Async cache manager for API responses."""

    def __init__(self, config: PyPIClientConfig):
        """Initialize the cache manager.

        Args:
            config: The client configuration
        """
        self.config = config
        self._cache_lock = asyncio.Lock()

        # Ensure cache directory exists
        os.makedirs(self.config.cache_dir, exist_ok=True)

    async def _get_cache_path(self, key: str) -> Path:
        """Get the cache file path for a key."""
        hashed_key = hashlib.sha256(key.encode()).hexdigest()
        return Path(self.config.cache_dir) / hashed_key

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached data if it exists and is not expired.

        Args:
            key: The cache key

        Returns:
            The cached data or None if not found or expired
        """
        cache_path = await self._get_cache_path(key)

        if cache_path.exists():
            try:
                async with self._cache_lock:
                    with cache_path.open("r") as f:
                        data = json.load(f)

                # Check if cache is expired
                # Use custom TTL if stored, otherwise use default
                ttl = (
                    data.get("ttl")
                    if data.get("ttl") is not None
                    else self.config.cache_ttl
                )
                if time.time() - data.get("timestamp", 0) < ttl:
                    # Update access time
                    os.utime(cache_path, None)
                    return data.get("content")
                else:
                    logger.debug(f"Cache expired for {key} (TTL: {ttl}s)")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Cache error for {key}: {e}")
            except PermissionError as e:
                logger.warning(f"Permission error accessing cache for {key}: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error reading cache for {key}: {e}")

        return None

    async def set(
        self,
        key: str,
        data: Dict[str, Any],
        etag: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> None:
        """Cache response data with timestamp and etag.

        Args:
            key: The cache key
            data: The data to cache
            etag: Optional ETag for conditional requests
            ttl: Optional TTL in seconds (overrides default TTL)
        """
        try:
            # Estimate the size of the serialized data
            cache_data = {
                "timestamp": time.time(),
                "content": data,
                "etag": etag,
                "ttl": ttl,  # Store custom TTL if provided
            }
            serialized = json.dumps(cache_data)
            estimated_size = len(serialized.encode("utf-8"))

            # If estimated size is larger than 80% of max cache size, don't cache it
            if estimated_size > self.config.cache_max_size * 0.8:
                logger.warning(
                    f"Data for key {key} is too large ({estimated_size} bytes) to cache (limit: {int(self.config.cache_max_size * 0.8)} bytes)"
                )
                return

            # Check cache directory size before storing
            await self._prune_cache_if_needed()

            cache_path = await self._get_cache_path(key)

            async with self._cache_lock:
                with cache_path.open("w") as f:
                    json.dump(cache_data, f)

            logger.debug(f"Cached data for {key}")
        except (PermissionError, OSError) as e:
            logger.warning(f"Failed to cache data for {key}: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error caching data for {key}: {e}")

    async def get_etag(self, key: str) -> Optional[str]:
        """Get the ETag for a cached response.

        Args:
            key: The cache key

        Returns:
            The ETag or None if not found
        """
        cache_path = await self._get_cache_path(key)

        if cache_path.exists():
            try:
                async with self._cache_lock:
                    with cache_path.open("r") as f:
                        data = json.load(f)
                return data.get("etag")
            except (json.JSONDecodeError, KeyError, PermissionError):
                pass

        return None

    async def clear(self) -> None:
        """Clear all cached data."""
        try:
            async with self._cache_lock:
                for file_path in Path(self.config.cache_dir).glob("*"):
                    if file_path.is_file():
                        file_path.unlink()
            logger.info("Cache cleared")
        except Exception as e:
            logger.warning(f"Failed to clear cache: {e}")

    async def get_cache_size(self) -> int:
        """Get the current size of the cache in bytes."""
        try:
            total_size = 0
            async with self._cache_lock:
                for file_path in Path(self.config.cache_dir).glob("*"):
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
            return total_size
        except Exception as e:
            logger.warning(f"Failed to get cache size: {e}")
            return 0

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache."""
        try:
            file_count = 0
            total_size = 0
            oldest_timestamp = time.time()
            newest_timestamp = 0

            async with self._cache_lock:
                for file_path in Path(self.config.cache_dir).glob("*"):
                    if file_path.is_file():
                        file_count += 1
                        file_size = file_path.stat().st_size
                        total_size += file_size

                        # Try to get file timestamp
                        try:
                            with file_path.open("r") as f:
                                data = json.load(f)
                                timestamp = data.get("timestamp", 0)
                                oldest_timestamp = min(oldest_timestamp, timestamp)
                                newest_timestamp = max(newest_timestamp, timestamp)
                        except:
                            # If we can't read the file, use the file mtime
                            mtime = file_path.stat().st_mtime
                            oldest_timestamp = min(oldest_timestamp, mtime)
                            newest_timestamp = max(newest_timestamp, mtime)

            # Avoid division by zero if cache is empty
            if file_count == 0:
                avg_size = 0
                oldest_timestamp = 0
                newest_timestamp = 0
            else:
                avg_size = total_size / file_count

            return {
                "file_count": file_count,
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024),
                "avg_file_size_bytes": avg_size,
                "oldest_timestamp": oldest_timestamp,
                "newest_timestamp": newest_timestamp,
                "cache_dir": self.config.cache_dir,
                "max_size_bytes": self.config.cache_max_size,
                "max_size_mb": self.config.cache_max_size / (1024 * 1024),
                "ttl_seconds": self.config.cache_ttl,
            }
        except Exception as e:
            logger.warning(f"Failed to get cache stats: {e}")
            return {"error": str(e), "cache_dir": self.config.cache_dir}

    async def _prune_cache_if_needed(self) -> None:
        """Prune cache if it exceeds the maximum size."""
        try:
            cache_size = await self.get_cache_size()

            if cache_size > self.config.cache_max_size:
                logger.info(
                    f"Cache size ({cache_size} bytes) exceeds max ({self.config.cache_max_size} bytes), pruning..."
                )
                await self._prune_cache(
                    target_size=int(self.config.cache_max_size * 0.8)
                )
        except Exception as e:
            logger.warning(f"Failed to check/prune cache: {e}")

    async def _prune_cache(self, target_size: int) -> None:
        """Prune the cache to the target size by removing oldest files by access time.

        Args:
            target_size: The target size in bytes
        """
        try:
            # Get all cache files with their access times
            cache_files: List[Tuple[Path, float]] = []

            async with self._cache_lock:
                for file_path in Path(self.config.cache_dir).glob("*"):
                    if file_path.is_file():
                        # Use atime to determine which files were accessed least recently
                        atime = file_path.stat().st_atime
                        cache_files.append((file_path, atime))

            # Sort by access time (oldest first)
            cache_files.sort(key=lambda x: x[1])

            # Get current cache size
            current_size = await self.get_cache_size()
            remaining_size = current_size

            # Remove files until we're under the target size
            async with self._cache_lock:
                for file_path, _ in cache_files:
                    if remaining_size <= target_size:
                        break

                    try:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        remaining_size -= file_size
                        logger.debug(
                            f"Pruned cache file: {file_path.name} ({file_size} bytes)"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to remove cache file {file_path}: {e}")

            logger.info(
                f"Pruned cache from {current_size} bytes to {remaining_size} bytes"
            )
        except Exception as e:
            logger.warning(f"Failed to prune cache: {e}")

    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache (compatibility wrapper).

        This is a wrapper around get_cache_stats for backwards compatibility.
        """
        return await self.get_cache_stats()
