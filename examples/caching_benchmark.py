#!/usr/bin/env python
"""
Benchmark script to compare the performance of the regular Cache and HybridCache implementations.

This script runs a series of tests to measure the performance of both cache implementations
under different scenarios.

Usage:
    python caching_benchmark.py
"""

import os
import time
import random
import tempfile
import statistics
import json
import argparse
from typing import Dict, Any, List, Tuple

from mcp_pypi.utils.common.caching import (
    Cache,
    HybridCache,
    cached,
    hybrid_cached,
    EvictionStrategy,
)


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

    Args:
        cache: The cache instance to test
        num_operations: Total number of operations to perform
        read_write_ratio: Ratio of reads to total operations (0.8 = 80% reads, 20% writes)
        unique_keys_ratio: Ratio of unique keys to total operations (0.2 = 20% unique keys)
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


def benchmark_decorator_performance(num_calls: int = 1000) -> Tuple[float, float]:
    """Benchmark the performance of both decorators."""
    # Define test functions
    counter1 = 0
    counter2 = 0

    @cached()
    def regular_cached_func(arg):
        nonlocal counter1
        counter1 += 1
        return arg * 2

    @hybrid_cached()
    def hybrid_cached_func(arg):
        nonlocal counter2
        counter2 += 1
        return arg * 2

    # Test regular cached
    start_time = time.time()
    for i in range(num_calls):
        # Use a small set of arguments to ensure caching
        result = regular_cached_func(i % 10)
    regular_time = time.time() - start_time

    # Test hybrid cached
    start_time = time.time()
    for i in range(num_calls):
        # Use a small set of arguments to ensure caching
        result = hybrid_cached_func(i % 10)
    hybrid_time = time.time() - start_time

    # Verify cache worked properly
    assert (
        counter1 <= 10
    ), f"Regular cache didn't work, expected <=10 calls, got {counter1}"
    assert (
        counter2 <= 10
    ), f"Hybrid cache didn't work, expected <=10 calls, got {counter2}"

    return regular_time, hybrid_time


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

    # Benchmark 5: Decorator performance
    if print_results:
        print("Benchmarking decorator performance...")

    regular_decorator_time, hybrid_decorator_time = benchmark_decorator_performance(
        num_calls=1000
    )
    results.setdefault("regular", {})["decorator"] = regular_decorator_time
    results.setdefault("hybrid_lru", {})["decorator"] = hybrid_decorator_time

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
