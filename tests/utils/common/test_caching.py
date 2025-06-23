"""
Tests for the caching utilities.
"""

import os
import time
import tempfile
import unittest
import shutil
from unittest import mock
import hashlib

from mcp_pypi.utils.common.caching import (
    Cache,
    cached,
    cache_keygen,
    invalidate_cached_call,
)


class TestCache(unittest.TestCase):
    """Test the Cache class."""

    def setUp(self):
        """Set up a test cache."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = Cache(cache_dir=self.temp_dir, ttl=1, max_size=10240)

    def tearDown(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_cache_path(self):
        """Test generating cache paths."""
        key = "test_key"
        # Compute the actual hash used by the implementation
        actual_hash = hashlib.md5(key.encode()).hexdigest()
        expected_path = os.path.join(self.temp_dir, actual_hash)
        # Access to protected member is okay in tests
        # pylint: disable=protected-access
        self.assertEqual(self.cache._get_cache_path(key), expected_path)

    def test_set_and_get(self):
        """Test setting and getting cache values."""
        key = "test_key"
        value = {"data": "test_value"}

        # Set value
        result = self.cache.set(key, value)
        self.assertTrue(result)

        # Get value
        cached_value = self.cache.get(key)
        self.assertEqual(cached_value, value)

    def test_expiry(self):
        """Test cache entry expiry."""
        key = "test_key"
        value = "test_value"

        # Set value with TTL of 1 second
        self.cache.set(key, value)

        # Verify it's cached
        self.assertEqual(self.cache.get(key), value)

        # Wait for it to expire
        time.sleep(1.1)

        # Verify it's expired
        self.assertIsNone(self.cache.get(key))

    def test_custom_ttl(self):
        """Test setting custom TTL for a cache entry."""
        key = "test_key"
        value = "test_value"

        # Set value with custom TTL of 0.5 seconds
        self.cache.set(key, value, ttl=0.5)

        # Verify it's cached
        self.assertEqual(self.cache.get(key), value)

        # Wait for it to expire
        time.sleep(0.6)

        # Verify it's expired
        self.assertIsNone(self.cache.get(key))

    def test_invalid_json(self):
        """Test handling of invalid JSON in cache file."""
        key = "test_key"
        # pylint: disable=protected-access
        cache_path = self.cache._get_cache_path(key)

        # Create an invalid JSON file
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write("invalid json")

        # Verify we get None and no exception
        self.assertIsNone(self.cache.get(key))

    def test_clear(self):
        """Test clearing the cache."""
        # Add some entries
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")

        # Verify they're cached
        self.assertEqual(self.cache.get("key1"), "value1")
        self.assertEqual(self.cache.get("key2"), "value2")

        # Clear the cache
        self.cache.clear()

        # Verify entries are gone
        self.assertIsNone(self.cache.get("key1"))
        self.assertIsNone(self.cache.get("key2"))

    def test_invalidate(self):
        """Test invalidating a specific cache entry."""
        # Add some entries
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")

        # Invalidate one entry
        result = self.cache.invalidate("key1")
        self.assertTrue(result)

        # Verify it's gone
        self.assertIsNone(self.cache.get("key1"))
        self.assertEqual(self.cache.get("key2"), "value2")

        # Try to invalidate a non-existent entry
        result = self.cache.invalidate("key3")
        self.assertFalse(result)

    def test_cache_size_limit(self):
        """Test cache size limiting mechanism."""
        # Set max size to 100 bytes
        self.cache.max_size = 100

        # Add entries that should exceed the limit
        large_value = "x" * 30  # Each entry will be ~40-50 bytes with metadata
        self.cache.set("key1", large_value)

        # Wait to ensure different creation times
        time.sleep(0.2)

        self.cache.set("key2", large_value)

        # Wait to ensure different creation times
        time.sleep(0.2)

        # This should trigger cleanup and remove key1
        self.cache.set("key3", large_value)

        # Wait to ensure cleanup has completed
        time.sleep(0.2)

        # Check cache size to ensure cleanup occurred
        # pylint: disable=protected-access
        cache_size = self.cache._get_cache_size()
        self.assertLessEqual(cache_size, self.cache.max_size)

        # We can't be certain which entries remain as it depends on exact byte sizes,
        # but we know the cache should contain fewer than 3 entries
        # pylint: disable=protected-access
        entries = self.cache._get_cache_entries()
        self.assertLess(len(entries), 3)

    def test_get_stats(self):
        """Test getting cache statistics."""
        # Add some entries
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2", ttl=0.1)

        # Wait for one to expire
        time.sleep(0.2)

        # Get stats
        stats = self.cache.get_stats()

        # Verify stats
        self.assertEqual(stats["total_entries"], 2)
        self.assertEqual(stats["active_entries"], 1)
        self.assertEqual(stats["expired_entries"], 1)
        self.assertEqual(stats["cache_dir"], self.temp_dir)


class TestCacheDecorator(unittest.TestCase):
    """Test the @cached decorator."""

    def setUp(self):
        """Set up a test cache."""
        self.temp_dir = tempfile.mkdtemp()
        # Mock the global cache to use our test cache
        self.patcher = mock.patch(
            "mcp_pypi.utils.common.caching._cache",
            Cache(cache_dir=self.temp_dir, ttl=1, max_size=10240),
        )
        self.mock_cache = self.patcher.start()

    def tearDown(self):
        """Clean up after tests."""
        self.patcher.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cached_decorator(self):
        """Test the cached decorator."""
        call_count = 0

        @cached()
        def example_function(arg1, arg2=None):
            nonlocal call_count
            call_count += 1
            return f"{arg1}-{arg2}"

        # First call should execute the function
        result1 = example_function("test", arg2="value")
        self.assertEqual(result1, "test-value")
        self.assertEqual(call_count, 1)

        # Second call with same args should use cache
        result2 = example_function("test", arg2="value")
        self.assertEqual(result2, "test-value")
        self.assertEqual(call_count, 1)  # Still 1

        # Call with different args should execute the function
        result3 = example_function("test", arg2="different")
        self.assertEqual(result3, "test-different")
        self.assertEqual(call_count, 2)

    def test_cached_with_prefix(self):
        """Test the cached decorator with a key prefix."""
        call_count = 0

        @cached(key_prefix="prefix1")
        def example_function(arg):
            nonlocal call_count
            call_count += 1
            return arg

        # First call
        example_function("test")
        self.assertEqual(call_count, 1)

        # Should be cached
        example_function("test")
        self.assertEqual(call_count, 1)

        # Different function but same args, different prefix
        @cached(key_prefix="prefix2")
        def another_function(arg):
            nonlocal call_count
            call_count += 1
            return arg

        # Should execute because prefix is different
        another_function("test")
        self.assertEqual(call_count, 2)

    def test_invalidate_cached_call(self):
        """Test invalidating a cached function call."""
        call_count = 0

        @cached()
        def example_function(arg1, arg2=None):
            nonlocal call_count
            call_count += 1
            return f"{arg1}-{arg2}"

        # First call
        example_function("test", arg2="value")
        self.assertEqual(call_count, 1)

        # Invalidate the call
        result = invalidate_cached_call(example_function, "test", arg2="value")
        self.assertTrue(result)

        # Call again, should execute
        example_function("test", arg2="value")
        self.assertEqual(call_count, 2)

    def test_cache_keygen(self):
        """Test the cache key generation function."""
        # Basic key generation
        key1 = cache_keygen("arg1", "arg2", kwarg1="value1")
        self.assertEqual(key1, "arg1::arg2::kwarg1=value1")

        # With prefix
        key2 = cache_keygen("arg1", prefix="prefix")
        self.assertEqual(key2, "prefix::arg1")

        # With non-string arguments
        key3 = cache_keygen(123, [1, 2, 3], {"a": 1})
        # We don't test the exact string, just that it works without error
        self.assertIsInstance(key3, str)


if __name__ == "__main__":
    unittest.main()
