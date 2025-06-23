#!/usr/bin/env python
"""
Standalone benchmark script to compare disk-based and hybrid caching implementations.

This script implements simplified versions of the Cache and HybridCache classes
for benchmark purposes without depending on the rest of the MCP-PyPI codebase.

Usage:
    python standalone_cache_benchmark.py
"""

import os
import time
import json
import hashlib
import random
import tempfile
import statistics
import shutil
import threading
import re
import argparse
from typing import Dict, Any, List, Tuple, Optional, Union, Pattern
from enum import Enum
from collections import OrderedDict
from functools import wraps


class EvictionStrategy(Enum):
    """Enumeration of cache eviction strategies."""

    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live


class Cache:
    """A simplified disk-based cache implementation for benchmarking."""

    def __init__(
        self, cache_dir: str, ttl: int = 3600, max_size: int = 10 * 1024 * 1024
    ):
        """Initialize the cache."""
        self.cache_dir = cache_dir
        self.ttl = ttl
        self.max_size = max_size

        # Create cache directory if it doesn't exist
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, key: str) -> str:
        """Get the file path for a cache entry."""
        filename = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, filename)

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from the cache."""
        path = self._get_cache_path(key)

        if not os.path.exists(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            # Check if cache entry has expired
            if cache_data.get("expires_at", 0) < time.time():
                try:
                    os.remove(path)
                except OSError:
                    pass
                return None

            return cache_data.get("value")
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Store a value in the cache."""
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

            return True
        except (OSError, Exception):
            # Clean up the temporary file if it exists
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            return False

    def clear(self) -> None:
        """Clear all entries from the cache."""
        for filename in os.listdir(self.cache_dir):
            file_path = os.path.join(self.cache_dir, filename)
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass

    def invalidate(self, key: str) -> bool:
        """Invalidate a specific cache entry."""
        path = self._get_cache_path(key)
        if os.path.exists(path):
            try:
                os.remove(path)
                return True
            except OSError:
                pass
        return False


class HybridCache(Cache):
    """
    A hybrid cache implementation that combines in-memory and disk-based caching.

    This cache provides improved performance through memory caching while maintaining
    persistence through file-based caching.
    """

    def __init__(
        self,
        cache_dir: str,
        ttl: int = 3600,
        max_size: int = 10 * 1024 * 1024,
        memory_max_size: int = 1024,
        eviction_strategy: EvictionStrategy = EvictionStrategy.LRU,
    ):
        """Initialize the hybrid cache."""
        super().__init__(cache_dir, ttl, max_size)

        self.memory_max_size = memory_max_size
        self.eviction_strategy = eviction_strategy

        # In-memory cache using OrderedDict for LRU capability
        self._memory_cache: Dict[str, Dict[str, Any]] = OrderedDict()

        # LFU counters when using LFU strategy
        self._access_counts: Dict[str, int] = {}

        # Thread lock for thread safety
        self._lock = threading.RLock()

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
        """Retrieve a value from the cache."""
        with self._lock:
            # Try to get from memory cache first
            if key in self._memory_cache:
                cache_data = self._memory_cache[key]

                # Check if the memory cache entry has expired
                if cache_data.get("expires_at", 0) < time.time():
                    # Remove from memory cache
                    self._memory_cache.pop(key, None)
                    self._access_counts.pop(key, None)
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
        """Store a value in both memory and disk cache."""
        with self._lock:
            self._metrics["sets"] += 1

            # Add to memory cache
            self._add_to_memory_cache(key, value, ttl)

            # Add to disk cache
            return super().set(key, value, ttl)

    def invalidate(self, key: str) -> bool:
        """Invalidate a specific cache entry in both memory and disk cache."""
        with self._lock:
            self._metrics["invalidations"] += 1

            # Remove from memory cache
            memory_removed = key in self._memory_cache
            if memory_removed:
                self._memory_cache.pop(key, None)
                self._access_counts.pop(key, None)

            # Remove from disk cache
            disk_removed = super().invalidate(key)

            return memory_removed or disk_removed

    def clear(self) -> None:
        """Clear all entries from both memory and disk cache."""
        with self._lock:
            # Clear memory cache
            self._memory_cache.clear()
            self._access_counts.clear()

            # Clear disk cache
            super().clear()

    def _add_to_memory_cache(self, key: str, value: Any, ttl: Optional[int]) -> None:
        """Add an entry to the in-memory cache."""
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
        self._access_counts[key] = 1

        # Perform eviction if needed
        if len(self._memory_cache) > self.memory_max_size:
            self._evict_from_memory_cache()

    def _update_access_metrics(self, key: str) -> None:
        """Update access metrics for a cache entry."""
        if key in self._memory_cache:
            # Update last access time for LRU
            self._memory_cache[key]["last_access"] = time.time()

            # Update access count for LFU
            self._access_counts[key] = self._access_counts.get(key, 0) + 1

            # If using LRU, move the key to the end of the OrderedDict
            if self.eviction_strategy == EvictionStrategy.LRU:
                value = self._memory_cache.pop(key)
                self._memory_cache[key] = value

    def _evict_from_memory_cache(self) -> None:
        """Evict entries from the memory cache based on the eviction strategy."""
        if not self._memory_cache:
            return

        if self.eviction_strategy == EvictionStrategy.LRU:
            # LRU: Remove the first item (oldest used)
            self._memory_cache.popitem(last=False)

        elif self.eviction_strategy == EvictionStrategy.LFU:
            # LFU: Remove the least frequently used item
            min_count = float("inf")
            min_key = None

            for key, count in self._access_counts.items():
                if count < min_count and key in self._memory_cache:
                    min_count = count
                    min_key = key

            if min_key:
                self._memory_cache.pop(min_key, None)
                self._access_counts.pop(min_key, None)

        else:  # EvictionStrategy.TTL
            # TTL: Remove the item closest to expiration
            current_time = time.time()
            closest_to_expire = None
            min_time_left = float("inf")

            for key, data in self._memory_cache.items():
                time_left = data.get("expires_at", 0) - current_time
                if 0 < time_left < min_time_left:
                    min_time_left = time_left
                    closest_to_expire = key

            # If found an item to expire, remove it
            if closest_to_expire:
                self._memory_cache.pop(closest_to_expire, None)
                self._access_counts.pop(closest_to_expire, None)
            else:
                # Fallback to LRU if no unexpired item found
                self._memory_cache.popitem(last=False)


def generate_random_data(size_kb: int) -> Dict[str, Any]:
    """Generate random data of the specified size in kilobytes."""
    data = {
        "id": str(random.randint(1, 1000000)),
        "name": "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=20)),
        "data": "".join(
            random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=size_kb * 128)
        ),
        "timestamp": time.time(),
        "attributes": {
            "attr1": random.random(),
            "attr2": random.randint(1, 100),
            "attr3": "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=10)),
        },
    }
    return data


def benchmark_set_get(
    cache, num_items: int = 100, data_size_kb: int = 1
) -> Tuple[float, float, float]:
    """Benchmark setting and getting items from the cache."""
    # Generate test data
    test_data = [
        (f"key_{i}", generate_random_data(data_size_kb)) for i in range(num_items)
    ]

    # Measure set performance
    start_time = time.time()
    for key, value in test_data:
        cache.set(key, value)
    set_time = time.time() - start_time

    # Measure get performance (cache hit)
    start_time = time.time()
    for key, _ in test_data:
        result = cache.get(key)
        assert result is not None, f"Cache miss for key {key}"
    get_hit_time = time.time() - start_time

    # Measure get performance (cache miss)
    start_time = time.time()
    for i in range(num_items):
        result = cache.get(f"nonexistent_key_{i}")
        assert result is None, f"Unexpected cache hit for nonexistent key"
    get_miss_time = time.time() - start_time

    return set_time, get_hit_time, get_miss_time


def benchmark_eviction(cache, num_items: int = 1000, data_size_kb: int = 1) -> float:
    """Benchmark cache eviction for a large number of items."""
    # Set cache size limit smaller than what we'll insert
    if isinstance(cache, HybridCache):
        cache.memory_max_size = num_items // 2

    # Set up timer
    start_time = time.time()

    # Set many items
    for i in range(num_items):
        cache.set(f"key_{i}", generate_random_data(data_size_kb))

    # Measure how long it takes to clear half the items
    cache.clear()

    return time.time() - start_time


def benchmark_real_world_usage(
    cache,
    num_operations: int = 1000,
    read_write_ratio: float = 0.8,
    unique_keys_ratio: float = 0.2,
) -> float:
    """
    Benchmark a real-world usage pattern with a mix of reads and writes.
    """
    # Generate a pool of keys
    unique_keys = int(num_operations * unique_keys_ratio)
    key_pool = [f"key_{i}" for i in range(unique_keys)]

    # Set up timer
    start_time = time.time()

    # Perform operations
    for i in range(num_operations):
        # Choose a random key from the pool
        key = random.choice(key_pool)

        # Decide whether to read or write based on the ratio
        if random.random() < read_write_ratio and cache.get(key) is None:
            # This is a read, but the key doesn't exist yet, so write it
            cache.set(key, generate_random_data(1))
        elif random.random() < read_write_ratio:
            # This is a read and the key might exist
            cache.get(key)
        else:
            # This is a write
            cache.set(key, generate_random_data(1))

    return time.time() - start_time


def benchmark_all(
    cache_dir: str = None, num_runs: int = 3, print_results: bool = True
) -> Dict[str, Dict[str, float]]:
    """Run all benchmarks multiple times and return average results."""
    if cache_dir is None:
        cache_dir = tempfile.mkdtemp()

    # Create cache instances
    regular_cache = Cache(
        cache_dir=os.path.join(cache_dir, "regular"),
        ttl=3600,
        max_size=10 * 1024 * 1024,
    )
    hybrid_lru_cache = HybridCache(
        cache_dir=os.path.join(cache_dir, "hybrid_lru"),
        ttl=3600,
        max_size=10 * 1024 * 1024,
        memory_max_size=1000,
        eviction_strategy=EvictionStrategy.LRU,
    )
    hybrid_lfu_cache = HybridCache(
        cache_dir=os.path.join(cache_dir, "hybrid_lfu"),
        ttl=3600,
        max_size=10 * 1024 * 1024,
        memory_max_size=1000,
        eviction_strategy=EvictionStrategy.LFU,
    )

    results = {"regular": {}, "hybrid_lru": {}, "hybrid_lfu": {}}

    # Run benchmarks multiple times to get stable results
    for run in range(num_runs):
        if print_results:
            print(f"Run {run + 1}/{num_runs}")

        # Clear caches
        regular_cache.clear()
        hybrid_lru_cache.clear()
        hybrid_lfu_cache.clear()

        # Benchmark 1: Set/Get small items
        if print_results:
            print("Benchmarking set/get (small items)...")

        r_set_time, r_get_hit_time, r_get_miss_time = benchmark_set_get(
            regular_cache, num_items=100, data_size_kb=1
        )
        h_lru_set_time, h_lru_get_hit_time, h_lru_get_miss_time = benchmark_set_get(
            hybrid_lru_cache, num_items=100, data_size_kb=1
        )
        h_lfu_set_time, h_lfu_get_hit_time, h_lfu_get_miss_time = benchmark_set_get(
            hybrid_lfu_cache, num_items=100, data_size_kb=1
        )

        results.setdefault("regular", {}).setdefault("set_small", []).append(r_set_time)
        results.setdefault("regular", {}).setdefault("get_hit_small", []).append(
            r_get_hit_time
        )
        results.setdefault("regular", {}).setdefault("get_miss_small", []).append(
            r_get_miss_time
        )

        results.setdefault("hybrid_lru", {}).setdefault("set_small", []).append(
            h_lru_set_time
        )
        results.setdefault("hybrid_lru", {}).setdefault("get_hit_small", []).append(
            h_lru_get_hit_time
        )
        results.setdefault("hybrid_lru", {}).setdefault("get_miss_small", []).append(
            h_lru_get_miss_time
        )

        results.setdefault("hybrid_lfu", {}).setdefault("set_small", []).append(
            h_lfu_set_time
        )
        results.setdefault("hybrid_lfu", {}).setdefault("get_hit_small", []).append(
            h_lfu_get_hit_time
        )
        results.setdefault("hybrid_lfu", {}).setdefault("get_miss_small", []).append(
            h_lfu_get_miss_time
        )

        # Benchmark 2: Set/Get large items
        if print_results:
            print("Benchmarking set/get (large items)...")

        r_set_time, r_get_hit_time, r_get_miss_time = benchmark_set_get(
            regular_cache, num_items=20, data_size_kb=100
        )
        h_lru_set_time, h_lru_get_hit_time, h_lru_get_miss_time = benchmark_set_get(
            hybrid_lru_cache, num_items=20, data_size_kb=100
        )
        h_lfu_set_time, h_lfu_get_hit_time, h_lfu_get_miss_time = benchmark_set_get(
            hybrid_lfu_cache, num_items=20, data_size_kb=100
        )

        results.setdefault("regular", {}).setdefault("set_large", []).append(r_set_time)
        results.setdefault("regular", {}).setdefault("get_hit_large", []).append(
            r_get_hit_time
        )
        results.setdefault("regular", {}).setdefault("get_miss_large", []).append(
            r_get_miss_time
        )

        results.setdefault("hybrid_lru", {}).setdefault("set_large", []).append(
            h_lru_set_time
        )
        results.setdefault("hybrid_lru", {}).setdefault("get_hit_large", []).append(
            h_lru_get_hit_time
        )
        results.setdefault("hybrid_lru", {}).setdefault("get_miss_large", []).append(
            h_lru_get_miss_time
        )

        results.setdefault("hybrid_lfu", {}).setdefault("set_large", []).append(
            h_lfu_set_time
        )
        results.setdefault("hybrid_lfu", {}).setdefault("get_hit_large", []).append(
            h_lfu_get_hit_time
        )
        results.setdefault("hybrid_lfu", {}).setdefault("get_miss_large", []).append(
            h_lfu_get_miss_time
        )

        # Benchmark 3: Eviction performance
        if print_results:
            print("Benchmarking eviction performance...")

        r_eviction_time = benchmark_eviction(
            regular_cache, num_items=500, data_size_kb=1
        )
        h_lru_eviction_time = benchmark_eviction(
            hybrid_lru_cache, num_items=500, data_size_kb=1
        )
        h_lfu_eviction_time = benchmark_eviction(
            hybrid_lfu_cache, num_items=500, data_size_kb=1
        )

        results.setdefault("regular", {}).setdefault("eviction", []).append(
            r_eviction_time
        )
        results.setdefault("hybrid_lru", {}).setdefault("eviction", []).append(
            h_lru_eviction_time
        )
        results.setdefault("hybrid_lfu", {}).setdefault("eviction", []).append(
            h_lfu_eviction_time
        )

        # Benchmark 4: Real-world usage pattern
        if print_results:
            print("Benchmarking real-world usage pattern...")

        r_real_world_time = benchmark_real_world_usage(
            regular_cache, num_operations=1000
        )
        h_lru_real_world_time = benchmark_real_world_usage(
            hybrid_lru_cache, num_operations=1000
        )
        h_lfu_real_world_time = benchmark_real_world_usage(
            hybrid_lfu_cache, num_operations=1000
        )

        results.setdefault("regular", {}).setdefault("real_world", []).append(
            r_real_world_time
        )
        results.setdefault("hybrid_lru", {}).setdefault("real_world", []).append(
            h_lru_real_world_time
        )
        results.setdefault("hybrid_lfu", {}).setdefault("real_world", []).append(
            h_lfu_real_world_time
        )

    # Calculate averages for all benchmarks
    avg_results = {
        cache_type: {
            test_name: statistics.mean(values) if isinstance(values, list) else values
            for test_name, values in tests.items()
        }
        for cache_type, tests in results.items()
    }

    # Print results
    if print_results:
        print("\n==== Cache Benchmark Results ====")
        for cache_type, tests in avg_results.items():
            print(f"\n{cache_type.upper()} CACHE:")
            for test_name, avg_time in tests.items():
                print(f"  {test_name}: {avg_time:.6f} seconds")

        # Print comparison (hybrid vs regular)
        print("\n==== Performance Comparison ====")
        for test_name in avg_results["regular"].keys():
            regular_time = avg_results["regular"][test_name]
            lru_time = avg_results["hybrid_lru"][test_name]
            lfu_time = avg_results.get("hybrid_lfu", {}).get(test_name, lru_time)

            lru_speedup = regular_time / lru_time if lru_time > 0 else float("inf")
            lfu_speedup = regular_time / lfu_time if lfu_time > 0 else float("inf")

            print(f"{test_name}:")
            print(
                f"  HybridCache (LRU) is {lru_speedup:.2f}x faster than regular Cache"
            )
            if "hybrid_lfu" in avg_results and test_name in avg_results["hybrid_lfu"]:
                print(
                    f"  HybridCache (LFU) is {lfu_speedup:.2f}x faster than regular Cache"
                )

    return avg_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Benchmark Cache vs HybridCache performance"
    )
    parser.add_argument("--runs", type=int, default=3, help="Number of benchmark runs")
    parser.add_argument(
        "--cache-dir", type=str, default=None, help="Cache directory to use"
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    # Run benchmarks
    results = benchmark_all(
        cache_dir=args.cache_dir, num_runs=args.runs, print_results=not args.json
    )

    # Output as JSON if requested
    if args.json:
        print(json.dumps(results, indent=2))
