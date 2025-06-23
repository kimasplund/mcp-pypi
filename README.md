# MCP-PyPI

A Model Context Protocol (MCP) server for providing PyPI package information through standardized AI agent interfaces.

## Overview

MCP-PyPI is a server that implements the Model Context Protocol (MCP), allowing AI assistants like Claude to access real-time Python package information from PyPI. It enables AI agents to search for packages, check dependencies, analyze version information, and much more.

## Features

- **MCP Server**: Fully compliant MCP server with multiple transport options
- **PyPI Integration**: Real-time access to the Python Package Index
- **Tool Integration**: Easily integrable with Claude and other MCP-compatible AI assistants
- **Multiple Transport Types**: Supports HTTP, SSE, WebSocket, and STDIO communication
- **Advanced Caching**: High-performance hybrid memory/disk caching system with multiple eviction strategies
- **Pydantic Models**: Strong typing with Pydantic for request/response validation

## Installation

### Basic Installation

```bash
pip install mcp-pypi
```

### With Transport-Specific Dependencies

For HTTP transport:
```bash
pip install "mcp-pypi[http]"
```

For WebSocket transport:
```bash
pip install "mcp-pypi[websocket]"
```

For all transports and development tools:
```bash
pip install "mcp-pypi[http,websocket,sse,dev]"
```

## Running the Server

MCP-PyPI provides several ways to run the server:

### Command-line Interface

Using the typer-based CLI:

```bash
# HTTP/SSE transport (default)
mcp-pypi-server run

# STDIO transport (for direct Claude integration)
mcp-pypi-server run --stdin

# With verbose logging
mcp-pypi-server run --verbose

# Specify host and port
mcp-pypi-server run --host 0.0.0.0 --port 8144
```

### Advanced Server Runner

Using the advanced server runner with more transport options:

```bash
# Run with HTTP transport
mcp-pypi-run --transport http --host 0.0.0.0 --port 8143

# Run with WebSocket transport
mcp-pypi-run --transport ws --host 127.0.0.1 --port 8144 

# Run with STDIO transport
mcp-pypi-run --transport stdio

# Run with all available transports
mcp-pypi-run --transport all --host 127.0.0.1 --port 8143

# With debug logging
mcp-pypi-run --transport http --debug
```

### Traditional JSON-RPC Server

For classic JSON-RPC over HTTP:

```bash
# Start the JSON-RPC server
mcp-pypi-rpc
```

## Configuration

### Server Configuration File (.mcp.json)

Create a `.mcp.json` file in your project directory to configure MCP servers:

```json
{
  "version": "2025-03-26",
  "mcpServers": {
    "pypi-http-server": {
      "type": "http",
      "url": "http://127.0.0.1:8143/messages/",
      "protocolVersion": "2025-03-26",
      "description": "PyPI MCP server over HTTP"
    },
    "pypi-ws-server": {
      "type": "websocket",
      "url": "ws://127.0.0.1:8144/ws",
      "protocolVersion": "2025-03-26",
      "description": "PyPI MCP server over WebSocket"
    },
    "pypi-stdio-server": {
      "type": "stdio",
      "command": "mcp-pypi-server run --stdin",
      "protocolVersion": "2025-03-26",
      "description": "PyPI MCP server over STDIO"
    }
  }
}
```

### Environment Variables

The server behavior can be controlled with environment variables:

- `MCP_PYPI_HOST`: Host to bind to (default: 127.0.0.1)
- `MCP_PYPI_PORT`: Port to listen on (default: 8143)
- `MCP_PYPI_LOG_LEVEL`: Log level (default: INFO)
- `MCP_PYPI_CACHE_DIR`: Cache directory path
- `MCP_PYPI_CACHE_TTL`: Cache TTL in seconds (default: 3600)
- `MCP_PYPI_CACHE_TYPE`: Cache type to use (default: "disk", also available: "hybrid")
- `MCP_PYPI_CACHE_MEMORY_SIZE`: Maximum number of items to keep in memory cache (default: 1024)
- `MCP_PYPI_CACHE_EVICTION`: Eviction strategy for hybrid cache (default: "lru", also available: "lfu", "ttl")
- `MCP_PYPI_USER_AGENT`: User agent for PyPI requests

## Claude Integration

To use with Claude, reference the MCP server in your conversation:

```
Use the pypi-http-server MCP tool to help me find information about Python packages.
```

For direct STDIO integration with Claude:

```
I need you to use MCP to access Python package information. Please run the following command and connect to the server:

mcp-pypi-server run --stdin
```

## Available Tools

- **Package Information**
  - `get_package_info`: Get detailed information about a Python package
  - `get_latest_version`: Get the latest version of a package
  - `get_package_metadata`: Get package metadata from PyPI
  - `check_package_exists`: Check if a package exists on PyPI
  - `get_documentation_url`: Get documentation URL for a package

- **Package Releases**
  - `get_package_releases`: Get all releases of a package
  - `get_project_releases`: Get project releases with timestamps
  - `get_newest_packages`: Get newest packages on PyPI
  - `get_latest_updates`: Get latest package updates on PyPI

- **Dependencies**
  - `get_dependency_tree`: Get the dependency tree for a package
  - `check_requirements_file`: Check a requirements file for outdated packages

- **Search and Stats**
  - `search_packages`: Search for packages on PyPI
  - `get_package_stats`: Get download statistics for a package
  - `compare_versions`: Compare two package versions

## Troubleshooting

### Common Issues

- **Port already in use**: Try a different port with `--port` option
- **Connection refused**: Ensure the server is running and accessible
- **Timeout errors**: Consider increasing timeouts or checking connectivity
- **CORS issues**: If accessing from a browser, ensure CORS headers are properly set

### Debugging

Enable verbose logging for more detailed output:

```bash
mcp-pypi-server run --verbose
# or
mcp-pypi-run --transport http --debug
```

## License

Commercial

## Author

Kim Asplund (kim.asplund@gmail.com)

## Advanced Usage

### Caching System

MCP-PyPI includes an advanced caching system to improve performance and reduce load on the PyPI servers. Two caching implementations are available:

#### Disk Cache (Default)

The traditional disk-based cache stores API responses and function results in files. It provides:

- Persistent storage across server restarts
- TTL-based expiration
- Size-based cleanup
- Thread-safe operation

To use the disk cache in your code:

```python
from mcp_pypi.utils.common.caching import Cache, cached

# Create a cache instance with custom parameters
cache = Cache(
    cache_dir="/path/to/cache",
    ttl=3600,  # 1 hour
    max_size=1024 * 1024 * 100  # 100 MB
)

# Use the cache directly
cache.set("my_key", {"some": "data"})
result = cache.get("my_key")

# Or use the decorator
@cached(ttl=1800)  # 30 minutes
def some_function(arg1, arg2):
    # Function will only be called if result not in cache
    return expensive_operation(arg1, arg2)
```

#### Hybrid Cache (Advanced)

The hybrid cache combines in-memory and disk-based caching for optimal performance:

- Fast in-memory access for frequently used data
- Persistent disk storage for durability
- Multiple eviction strategies (LRU, LFU, TTL)
- Thread-safe operation with fine-grained locking
- Enhanced metrics and statistics
- Pattern-based invalidation

To use the hybrid cache in your code:

```python
from mcp_pypi.utils.common.caching import HybridCache, hybrid_cached, EvictionStrategy

# Create a hybrid cache with custom parameters
cache = HybridCache(
    cache_dir="/path/to/cache",
    ttl=3600,  # 1 hour
    max_size=1024 * 1024 * 100,  # 100 MB disk cache
    memory_max_size=1000,  # 1000 items in memory
    eviction_strategy=EvictionStrategy.LRU  # Least Recently Used
)

# Use the cache directly
cache.set("my_key", {"some": "data"})
result = cache.get("my_key")

# Use pattern-based invalidation
cache.invalidate_pattern(r"^prefix_.*")

# Get detailed stats
stats = cache.get_enhanced_stats()

# Or use the decorator with a specific eviction strategy
@hybrid_cached(ttl=1800, eviction_strategy=EvictionStrategy.LFU)
def some_function(arg1, arg2):
    # Function will only be called if result not in cache
    return expensive_operation(arg1, arg2)
```

#### Configuring Cache in Server

To configure the cache type when running the server:

```bash
# Use hybrid cache with LRU eviction
MCP_PYPI_CACHE_TYPE=hybrid MCP_PYPI_CACHE_EVICTION=lru mcp-pypi-server run

# Use hybrid cache with custom memory size
MCP_PYPI_CACHE_TYPE=hybrid MCP_PYPI_CACHE_MEMORY_SIZE=2048 mcp-pypi-server run
```
