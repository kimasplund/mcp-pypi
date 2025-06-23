# MCP PyPI Caching System

The MCP PyPI client implements a flexible, extensible caching system to improve performance, reduce network traffic, and provide offline capabilities. This document describes the caching architecture, available implementations, and usage patterns.

## Cache Architecture

### Core Components

The caching system consists of these primary components:

1. **Cache Protocol** - Interface defining the core caching operations
2. **Base Cache** - Abstract implementation providing common functionality
3. **Cache Implementations** - Concrete caches for various storage backends
4. **Cache Strategies** - Advanced patterns for cache manipulation
5. **Hierarchical Cache** - Composite pattern for layered caching

### Key Features

- **Asynchronous API** - All operations are async/await compatible
- **TTL Support** - Time-based expiration for all cached items
- **Namespacing** - Isolation of cache entries by purpose
- **Statistics** - Runtime metrics for cache performance analysis
- **Serialization** - Support for various data serialization formats
- **Eviction Policies** - LRU and other strategies for memory management
- **Events** - Notification system for cache operations

## Cache Implementations

### MemoryCache

An in-memory LRU cache suitable for high-speed, temporary storage of data.

```python
from mcp_pypi.utils.cache import MemoryCache

# Create a memory cache with 1000 item limit and 5 minute TTL
cache = MemoryCache(
    max_size=1000,
    ttl=300,
    namespace="package_metadata"
)

# Basic operations
await cache.set("key", value)
result = await cache.get("key")
exists = await cache.has("key")
await cache.delete("key")
await cache.clear()
```

#### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `max_size` | Maximum number of items to store | 1000 |
| `ttl` | Default time-to-live in seconds | 3600 |
| `namespace` | Namespace prefix for keys | None |
| `event_bus` | Optional event bus for notifications | None |

### FileCache

Persistent cache that stores serialized data on the filesystem.

```python
from mcp_pypi.utils.cache import FileCache

# Create a file cache with JSON serialization
cache = FileCache(
    directory=".cache/pypi",
    ttl=3600,
    namespace="package_info",
    serializer="json"  # or "pickle"
)
```

#### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `directory` | Path to store cache files | ".cache" |
| `ttl` | Default time-to-live in seconds | 86400 |
| `namespace` | Namespace prefix for keys | None |
| `serializer` | Data serialization format ("json" or "pickle") | "json" |
| `event_bus` | Optional event bus for notifications | None |

### RedisCache

Distributed cache implementation using Redis (requires optional `aioredis` dependency).

```python
from mcp_pypi.utils.cache import RedisCache

# Create a Redis cache connected to local Redis instance
cache = RedisCache(
    url="redis://localhost:6379/0",
    ttl=3600,
    namespace="pypi"
)
```

#### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `url` | Redis connection URL | "redis://localhost:6379/0" |
| `ttl` | Default time-to-live in seconds | 3600 |
| `namespace` | Namespace prefix for keys | None |
| `serializer` | Data serialization format ("json" or "pickle") | "json" |
| `event_bus` | Optional event bus for notifications | None |

## Advanced Caching Strategies

### StaleWhileRevalidateStrategy

Cache decorator that implements the stale-while-revalidate pattern, allowing usage of stale cache entries while asynchronously refreshing the data.

```python
from mcp_pypi.utils.cache import MemoryCache, StaleWhileRevalidateStrategy

# Create base cache
base_cache = MemoryCache(ttl=300)

# Define refresh callback
async def refresh_data(key, old_value):
    # Fetch fresh data from source
    fresh_data = await fetch_from_source(key)
    return fresh_data

# Create stale-while-revalidate wrapper
cache = StaleWhileRevalidateStrategy(
    cache=base_cache,
    stale_ttl=3600,  # Allow stale data for up to 1 hour
    background_refresh=True,
    refresh_callback=refresh_data
)

# Usage is the same as regular cache
value = await cache.get("my_key")  # May trigger background refresh
```

### HierarchicalCache

Composite cache that delegates operations to multiple underlying caches in a defined order, typically from fastest to slowest.

```python
from mcp_pypi.utils.cache import MemoryCache, FileCache, HierarchicalCache

# Create individual caches
memory_cache = MemoryCache(max_size=100, ttl=300)
file_cache = FileCache(directory=".cache/pypi", ttl=86400)

# Create hierarchical cache (memory first, then file)
cache = HierarchicalCache(
    caches=[memory_cache, file_cache],
    ttl=3600,
    write_strategy="write-through"
)

# Usage automatically handles the cascade between cache levels
await cache.set("key", value)  # Written to both caches
result = await cache.get("key")  # Checked in memory first, then file
```

#### Write Strategies

- **Write-through** - Write to all caches immediately
- **Write-back** - Write to fastest cache, then asynchronously to slower caches
- **Write-around** - Write to slower caches, skipping fastest cache

## Factory Functions

The cache system provides factory functions to create caches from configuration:

```python
from mcp_pypi.utils.cache import create_cache_from_config

# Configuration dictionary
config = {
    "type": "hierarchical",
    "ttl": 3600,
    "namespace": "pypi",
    "write_strategy": "write-through",
    "caches": [
        {
            "type": "memory",
            "max_size": 1000,
            "ttl": 300
        },
        {
            "type": "file",
            "directory": ".cache/pypi",
            "ttl": 86400,
            "serializer": "json"
        }
    ]
}

# Create cache from config
cache = create_cache_from_config(config)
```

## Integration with MCP PyPI Client

The PyPI client uses caching automatically for appropriate resources:

```python
from mcp_pypi import PyPIClient
from mcp_pypi.utils.cache import MemoryCache, FileCache, HierarchicalCache

# Create a cache
cache = HierarchicalCache(
    caches=[
        MemoryCache(max_size=100),
        FileCache(directory=".cache/pypi")
    ]
)

# Create client with custom cache
client = PyPIClient(cache=cache)

# Cache is used automatically for appropriate operations
package_info = await client.get_package_info("requests")  # Cached
```

### Configurable Cache TTLs

You can configure specific TTLs for different types of PyPI data:

```python
from mcp_pypi import PyPIClient
from mcp_pypi.utils.cache import MemoryCache

client = PyPIClient(
    cache=MemoryCache(),
    cache_ttls={
        "package_info": 3600,  # 1 hour for package metadata
        "releases": 600,       # 10 minutes for release lists
        "download_stats": 86400 # 1 day for download statistics
    }
)
```

## Performance Considerations

- **MemoryCache** is fastest but limited by available memory
- **FileCache** is slower but persists between application restarts
- **RedisCache** allows for distributed caching across multiple processes/servers
- **HierarchicalCache** with memory+file provides good balance of speed and persistence

## Events and Monitoring

The cache system emits events for monitoring and debugging:

```python
from mcp_pypi.utils.cache import MemoryCache
from mcp_pypi.utils.events import EventBus

# Create event bus
event_bus = EventBus()

# Create cache with event bus
cache = MemoryCache(event_bus=event_bus)

# Subscribe to cache events
@event_bus.subscribe("cache:hit")
async def on_cache_hit(event):
    print(f"Cache hit: {event.data['key']}")

@event_bus.subscribe("cache:miss")
async def on_cache_miss(event):
    print(f"Cache miss: {event.data['key']}")
```

Available events:
- `cache:hit` - Cache hit occurred
- `cache:miss` - Cache miss occurred
- `cache:set` - Item set in cache
- `cache:delete` - Item deleted from cache
- `cache:expire` - Item expired from cache
- `cache:clear` - Cache cleared

## Statistics

All cache implementations track operational statistics:

```python
from mcp_pypi.utils.cache import MemoryCache

cache = MemoryCache()

# After some operations
stats = cache.get_stats()
print(f"Hits: {stats['hits']}, Misses: {stats['misses']}")
print(f"Hit ratio: {stats['hit_ratio']:.2f}")

# Reset statistics
cache.reset_stats()
```

Available statistics:
- `hits` - Number of cache hits
- `misses` - Number of cache misses
- `sets` - Number of cache sets
- `deletes` - Number of cache deletes
- `expires` - Number of expired items
- `clears` - Number of cache clears
- `hit_ratio` - Ratio of hits to total lookups 