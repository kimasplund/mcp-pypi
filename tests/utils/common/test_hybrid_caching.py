"""
Tests for the hybrid caching utilities.
"""

import time
import tempfile
import unittest
import shutil
from unittest import mock
from concurrent.futures import ThreadPoolExecutor

from mcp_pypi.utils.common.caching import (
    HybridCache,
    EvictionStrategy,
    hybrid_cached,
    invalidate_cached_call,
)


class TestHybridCache(unittest.TestCase):
    """Test the HybridCache class."""

    def setUp(self):
        """Set up a test cache."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = HybridCache(
            cache_dir=self.temp_dir,
            ttl=1,
            max_size=10240,
            memory_max_size=10,
            eviction_strategy=EvictionStrategy.LRU,
        )

    def tearDown(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

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

        # Check that we got a memory hit
        stats = self.cache.get_enhanced_stats()
        self.assertEqual(stats["memory_hits"], 1)
        self.assertEqual(stats["memory_misses"], 0)

    def test_memory_to_disk_fallback(self):
        """Test fallback from memory to disk cache."""
        key = "test_key"
        value = "test_value"

        # Set value
        self.cache.set(key, value)

        # Remove from memory cache but keep in disk
        with self.cache._lock:
            self.cache._memory_cache.pop(key)

        # Get value - should retrieve from disk
        cached_value = self.cache.get(key)
        self.assertEqual(cached_value, value)

        # Check stats
        stats = self.cache.get_enhanced_stats()
        self.assertEqual(stats["memory_misses"], 1)
        self.assertEqual(stats["disk_hits"], 1)

        # Next get should be from memory
        cached_value = self.cache.get(key)
        self.assertEqual(cached_value, value)

        # Check updated stats
        stats = self.cache.get_enhanced_stats()
        self.assertEqual(stats["memory_hits"], 1)

    def test_expiry(self):
        """Test cache entry expiry."""
        key = "test_key"
        value = "test_value"

        # Set value with TTL of 0.5 seconds
        self.cache.set(key, value, ttl=0.5)

        # Verify it's cached
        self.assertEqual(self.cache.get(key), value)

        # Wait for it to expire
        time.sleep(0.6)

        # Verify it's expired
        self.assertIsNone(self.cache.get(key))

        # Check that we got memory and disk misses
        stats = self.cache.get_enhanced_stats()
        self.assertTrue(stats["memory_misses"] >= 1)
        self.assertTrue(stats["disk_misses"] >= 1)

    def test_invalidate(self):
        """Test invalidating a specific cache entry."""
        # Add some entries
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")

        # Verify they're cached
        self.assertEqual(self.cache.get("key1"), "value1")
        self.assertEqual(self.cache.get("key2"), "value2")

        # Invalidate one entry
        result = self.cache.invalidate("key1")
        self.assertTrue(result)

        # Verify it's gone
        self.assertIsNone(self.cache.get("key1"))
        self.assertEqual(self.cache.get("key2"), "value2")

    def test_invalidate_pattern(self):
        """Test invalidating cache entries by pattern."""
        # Add entries with a pattern
        self.cache.set("prefix_key1", "value1")
        self.cache.set("prefix_key2", "value2")
        self.cache.set("other_key", "value3")

        # Invalidate by pattern
        count = self.cache.invalidate_pattern(r"^prefix_")
        self.assertEqual(count, 2)

        # Verify pattern matches are gone
        self.assertIsNone(self.cache.get("prefix_key1"))
        self.assertIsNone(self.cache.get("prefix_key2"))
        self.assertEqual(self.cache.get("other_key"), "value3")

    def test_clear(self):
        """Test clearing the cache."""
        # Add some entries
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")

        # Clear the cache
        self.cache.clear()

        # Verify entries are gone
        self.assertIsNone(self.cache.get("key1"))
        self.assertIsNone(self.cache.get("key2"))

        # Verify memory cache is empty
        self.assertEqual(len(self.cache._memory_cache), 0)

    def test_lru_eviction(self):
        """Test LRU eviction strategy."""
        # Set eviction strategy
        self.cache.eviction_strategy = EvictionStrategy.LRU
        self.cache.memory_max_size = 3

        # Add entries
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.set("key3", "value3")

        # All should be in memory
        self.assertEqual(len(self.cache._memory_cache), 3)

        # Access key1 to make it most recently used
        self.cache.get("key1")

        # Add another entry to trigger eviction
        self.cache.set("key4", "value4")

        # key2 should be evicted (least recently used)
        self.assertEqual(len(self.cache._memory_cache), 3)
        self.assertIn("key1", self.cache._memory_cache)
        self.assertIn("key3", self.cache._memory_cache)
        self.assertIn("key4", self.cache._memory_cache)
        self.assertNotIn("key2", self.cache._memory_cache)

        # But key2 should still be in disk cache
        self.assertEqual(self.cache.get("key2"), "value2")

    def test_lfu_eviction(self):
        """Test LFU eviction strategy."""
        # Set eviction strategy
        self.cache.eviction_strategy = EvictionStrategy.LFU
        self.cache.memory_max_size = 3

        # Add entries
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.set("key3", "value3")

        # Access key1 and key2 multiple times
        self.cache.get("key1")
        self.cache.get("key1")
        self.cache.get("key2")

        # Add another entry to trigger eviction
        self.cache.set("key4", "value4")

        # key3 should be evicted (least frequently used)
        self.assertEqual(len(self.cache._memory_cache), 3)
        self.assertIn("key1", self.cache._memory_cache)
        self.assertIn("key2", self.cache._memory_cache)
        self.assertIn("key4", self.cache._memory_cache)
        self.assertNotIn("key3", self.cache._memory_cache)

    def test_ttl_eviction(self):
        """Test TTL-based eviction strategy."""
        # Set eviction strategy
        self.cache.eviction_strategy = EvictionStrategy.TTL
        self.cache.memory_max_size = 3

        # Add entries with different TTLs
        self.cache.set("key1", "value1", ttl=5)
        self.cache.set("key2", "value2", ttl=3)
        self.cache.set("key3", "value3", ttl=1)

        # Add another entry to trigger eviction
        self.cache.set("key4", "value4", ttl=4)

        # key3 should be evicted (closest to expiry)
        self.assertEqual(len(self.cache._memory_cache), 3)
        self.assertIn("key1", self.cache._memory_cache)
        self.assertIn("key2", self.cache._memory_cache)
        self.assertIn("key4", self.cache._memory_cache)
        self.assertNotIn("key3", self.cache._memory_cache)

    def test_thread_safety(self):
        """Test that the cache is thread-safe."""

        # Define a function to run in threads
        def cache_operation(key, value):
            self.cache.set(key, value)
            time.sleep(0.01)  # Introduce some delay
            result = self.cache.get(key)
            return result

        # Run multiple threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(50):
                key = f"key_{i}"
                value = f"value_{i}"
                futures.append(executor.submit(cache_operation, key, value))

            # Check results
            for i, future in enumerate(futures):
                self.assertEqual(future.result(), f"value_{i}")

        # Verify no data corruption
        for i in range(50):
            key = f"key_{i}"
            expected = f"value_{i}"
            self.assertEqual(self.cache.get(key), expected)

    def test_enhanced_stats(self):
        """Test getting enhanced cache statistics."""
        # Add some entries
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")

        # Access entries
        self.cache.get("key1")
        self.cache.get("key1")
        self.cache.get("key2")
        self.cache.get("key3")  # Miss

        # Invalidate an entry
        self.cache.invalidate("key2")

        # Get stats
        stats = self.cache.get_enhanced_stats()

        # Verify stats
        self.assertEqual(stats["memory_entries"], 1)
        self.assertEqual(stats["memory_hits"], 3)
        self.assertEqual(stats["memory_misses"], 1)
        self.assertEqual(stats["sets"], 2)
        self.assertEqual(stats["invalidations"], 1)
        self.assertEqual(stats["eviction_strategy"], EvictionStrategy.LRU.value)

        # Check hit ratios
        self.assertTrue(0 < stats["memory_hit_ratio"] < 1)
        self.assertTrue(0 <= stats["disk_hit_ratio"] <= 1)
        self.assertTrue(0 < stats["overall_hit_ratio"] < 1)


class TestHybridCacheDecorator(unittest.TestCase):
    """Test the @hybrid_cached decorator."""

    def setUp(self):
        """Set up a test cache."""
        self.temp_dir = tempfile.mkdtemp()
        # Create a hybrid cache for testing
        self.test_cache = HybridCache(
            cache_dir=self.temp_dir, ttl=1, max_size=10240, memory_max_size=10
        )
        # Mock the global cache
        self.patcher = mock.patch(
            "mcp_pypi.utils.common.caching._cache", self.test_cache
        )
        self.mock_cache = self.patcher.start()

    def tearDown(self):
        """Clean up after tests."""
        self.patcher.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_hybrid_cached_decorator(self):
        """Test the hybrid_cached decorator."""
        call_count = 0

        @hybrid_cached()
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

        # Check cache stats
        stats = self.test_cache.get_enhanced_stats()
        self.assertEqual(stats["memory_hits"], 1)

    def test_hybrid_cached_with_custom_eviction(self):
        """Test hybrid_cached with custom eviction strategy."""
        call_count = 0

        # Create a test hybrid cache with the specific eviction strategy
        test_specific_cache = HybridCache(
            cache_dir=self.temp_dir,
            eviction_strategy=EvictionStrategy.LFU
        )

        @hybrid_cached(eviction_strategy=EvictionStrategy.LFU, cache_instance=test_specific_cache)
        def example_function(arg):
            nonlocal call_count
            call_count += 1
            return arg

        # Call function multiple times
        example_function("test1")
        example_function("test2")
        example_function("test1")  # Should be from cache

        self.assertEqual(call_count, 2)

        # Verify eviction strategy was set on the specific instance
        self.assertEqual(test_specific_cache.eviction_strategy, EvictionStrategy.LFU)

    def test_invalidate_hybrid_cached_call(self):
        """Test invalidating a hybrid cached function call."""
        call_count = 0

        @hybrid_cached()
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


if __name__ == "__main__":
    unittest.main()
