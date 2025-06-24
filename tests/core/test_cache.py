"""Tests for the cache manager."""

import asyncio
import json
import os
import tempfile
import time
import uuid
from pathlib import Path

import pytest

from mcp_pypi.core.cache import AsyncCacheManager
from mcp_pypi.core.models import PyPIClientConfig


@pytest.fixture
def config():
    """Create a test configuration with a temporary cache directory."""
    cache_dir = tempfile.mkdtemp(prefix="mcp_pypi_test_cache_")
    config = PyPIClientConfig(cache_dir=cache_dir)
    yield config

    # Cleanup
    for file in Path(cache_dir).glob("*"):
        try:
            file.unlink()
        except:
            pass
    try:
        Path(cache_dir).rmdir()
    except:
        pass


@pytest.fixture
def cache_manager(config):
    """Create a cache manager with the test configuration."""
    return AsyncCacheManager(config)


@pytest.mark.asyncio
async def test_cache_get_set(cache_manager):
    """Test setting and getting cache entries."""
    # Create test data
    key = f"test-key-{uuid.uuid4()}"
    data = {"test": "data", "number": 123}

    # Set cache
    await cache_manager.set(key, data)

    # Get cache
    cached_data = await cache_manager.get(key)

    # Verify data
    assert cached_data == data

    # Test non-existent key
    non_existent = await cache_manager.get(f"non-existent-{uuid.uuid4()}")
    assert non_existent is None


@pytest.mark.asyncio
async def test_cache_expiration(cache_manager, config):
    """Test cache expiration based on TTL."""
    # Set a short TTL
    original_ttl = config.cache_ttl
    config.cache_ttl = 1  # 1 second

    # Create test data
    key = f"test-key-{uuid.uuid4()}"
    data = {"test": "data", "number": 123}

    # Set cache
    await cache_manager.set(key, data)

    # Get cache immediately
    cached_data = await cache_manager.get(key)
    assert cached_data == data

    # Wait for expiration
    await asyncio.sleep(1.5)

    # Get cache after expiration
    expired_data = await cache_manager.get(key)
    assert expired_data is None

    # Restore original TTL
    config.cache_ttl = original_ttl


@pytest.mark.asyncio
async def test_cache_etag(cache_manager):
    """Test getting and setting ETags."""
    # Create test data
    key = f"test-key-{uuid.uuid4()}"
    data = {"test": "data", "number": 123}
    etag = "test-etag-12345"

    # Set cache with ETag
    await cache_manager.set(key, data, etag)

    # Get ETag
    cached_etag = await cache_manager.get_etag(key)

    # Verify ETag
    assert cached_etag == etag

    # Test non-existent key
    non_existent = await cache_manager.get_etag(f"non-existent-{uuid.uuid4()}")
    assert non_existent is None


@pytest.mark.asyncio
async def test_cache_clear(cache_manager):
    """Test clearing the cache."""
    # Create test data
    key1 = f"test-key-1-{uuid.uuid4()}"
    key2 = f"test-key-2-{uuid.uuid4()}"
    data = {"test": "data", "number": 123}

    # Set cache entries
    await cache_manager.set(key1, data)
    await cache_manager.set(key2, data)

    # Verify entries exist
    assert await cache_manager.get(key1) == data
    assert await cache_manager.get(key2) == data

    # Clear cache
    await cache_manager.clear()

    # Verify entries are gone
    assert await cache_manager.get(key1) is None
    assert await cache_manager.get(key2) is None


@pytest.mark.asyncio
async def test_cache_pruning(cache_manager, config):
    """Test cache pruning when it exceeds the maximum size."""
    # Set a small max size
    original_max_size = config.cache_max_size
    config.cache_max_size = 1000  # 1 KB

    # Create a large data item
    large_data = {
        "large": "x" * 2000
    }  # This should be larger than 1 KB when serialized
    key = f"test-key-{uuid.uuid4()}"

    # Set data, triggering pruning
    await cache_manager.set(key, large_data)

    # Get cache size
    size = await cache_manager.get_cache_size()

    # Size should be less than or equal to 80% of max size (pruning target)
    assert size <= config.cache_max_size * 0.8

    # Restore original max size
    config.cache_max_size = original_max_size


@pytest.mark.asyncio
async def test_cache_stats(cache_manager):
    """Test getting cache statistics."""
    # Create test data
    keys = [f"test-key-{i}-{uuid.uuid4()}" for i in range(5)]
    data = {"test": "data", "number": 123}

    # Set cache entries
    for key in keys:
        await cache_manager.set(key, data)

    # Get stats
    stats = await cache_manager.get_cache_stats()

    # Verify stats
    assert stats["file_count"] == 5
    assert stats["total_size_bytes"] > 0
    assert stats["total_size_mb"] > 0
