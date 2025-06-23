# MCP-PyPI API Documentation

This document describes the API for accessing package information from the Python Package Index (PyPI) through the Model Context Protocol.

## Table of Contents

1. [Overview](#overview)
2. [Core Features](#core-features)
3. [Architecture](#architecture)
4. [Methods and Endpoints](#methods-and-endpoints)
5. [Configuration](#configuration)
6. [Error Handling](#error-handling)
7. [Caching](#caching)
8. [Advanced Usage](#advanced-usage)
9. [Integration Examples](#integration-examples)

## Overview

The MCP PyPI client provides a modern, asynchronous interface for interacting with the Python Package Index. It enables applications to search for packages, retrieve package metadata, analyze dependencies, and track download statistics through a standardized API.

The implementation follows a microservice architecture, with a clear separation between the client interface, transport mechanisms, and data models. This design supports easy extension and customization while maintaining compatibility with the broader MCP ecosystem.

## Core Features

- **Package Information**: Retrieve detailed information about packages
- **Version Management**: Get latest versions, all releases, and compare versions
- **Dependency Analysis**: Analyze package dependencies and build dependency trees
- **Statistics**: Access download statistics for packages
- **Search Capabilities**: Search for packages with advanced filtering
- **Documentation Access**: Retrieve documentation URLs and resources
- **Requirements Analysis**: Check requirements files for outdated packages

## Architecture

The MCP PyPI client is structured around the following components:

### Core Components

- **PyPIClient**: Main entry point providing access to all client functionality
- **Transport Layer**: Handles communication with PyPI servers via multiple protocols
- **Data Models**: Type-annotated models for representing PyPI data
- **Cache Manager**: Optional caching layer for improved performance
- **Error Handlers**: Standardized error handling and reporting

### Transport Integrations

The client supports multiple transport mechanisms for MCP communication:

- **HTTP/HTTPS**: RESTful API communication with PyPI 
- **WebSocket**: Real-time updates for package changes (when available)
- **Server-Sent Events (SSE)**: One-way notification stream for package updates
- **Binary & Newline**: Lower-level transports for direct communication

## Methods and Endpoints

The MCP PyPI client exposes the following core methods:

### Package Information Methods

- `get_package_info(package_name: str) -> PackageInfo`
  - Retrieves comprehensive information about a package
  - Includes metadata, current version, homepage, documentation links

- `get_latest_version(package_name: str) -> str`
  - Returns the latest stable version of a package
  - Filters pre-releases unless explicitly requested

- `get_package_releases(package_name: str) -> List[str]`
  - Returns all version numbers for a package
  - Ordered from newest to oldest

- `get_project_releases(package_name: str) -> Dict[str, datetime]`
  - Returns version numbers with their release timestamps
  - Useful for understanding release cadence

- `get_package_metadata(package_name: str, version: Optional[str] = None) -> Dict[str, Any]`
  - Returns detailed metadata for a specific package version
  - Includes maintainers, classifiers, and platform information

- `get_documentation_url(package_name: str) -> str`
  - Returns the URL to the package's documentation
  - Falls back to project homepage if documentation URL is not specified

### Dependency Methods

- `get_dependency_tree(package_name: str, version: Optional[str] = None, depth: int = 1) -> Dict[str, Any]`
  - Builds a hierarchical representation of package dependencies
  - Controls depth to limit the size of large dependency trees
  - Identifies circular dependencies and version conflicts

- `check_requirements_file(file_path: str, format: str = "table") -> Dict[str, Any]`
  - Analyzes requirements files for outdated packages
  - Supports requirements.txt and pyproject.toml formats
  - Identifies security vulnerabilities (when integrated with security databases)

- `compare_versions(package_name: str, version1: str, version2: str) -> Dict[str, Any]`
  - Compares two versions of a package
  - Reports added, removed, and modified dependencies

### Statistics Methods

- `get_package_stats(package_name: str, version: Optional[str] = None) -> Dict[str, Any]`
  - Retrieves download statistics for a package
  - Provides daily, weekly, and monthly download trends

### Search and Feed Methods

- `search_packages(query: str, page: int = 1) -> Dict[str, Any]`
  - Searches for packages matching the query
  - Supports pagination for large result sets
  - Includes relevancy scores for results

- `get_newest_packages() -> List[Dict[str, Any]]`
  - Returns recently added packages to PyPI
  - Useful for discovery and monitoring

- `get_latest_updates() -> List[Dict[str, Any]]`
  - Returns recently updated packages
  - Includes version change information

### Utility Methods

- `check_package_exists(package_name: str) -> bool`
  - Verifies if a package exists on PyPI
  - Useful for validation before other operations

## Configuration

The MCP PyPI client is configurable through the `PyPIClientConfig` class, which supports:

### Basic Configuration

```python
from mcp_pypi.core.models import PyPIClientConfig

config = PyPIClientConfig(
    user_agent="MyApp/1.0",
    timeout=30.0,
    cache_ttl=3600,  # 1 hour
    max_retries=3,
    proxy_url=None,
    verify_ssl=True
)
```

### Advanced Configuration

```python
from mcp_pypi.core.models import PyPIClientConfig
from mcp_pypi.utils.cache import RedisCache
import aiohttp

# Custom session
session = aiohttp.ClientSession()

# Redis-based cache
cache = RedisCache(
    host="localhost",
    port=6379,
    db=0,
    prefix="pypi_cache:",
    ttl=3600
)

config = PyPIClientConfig(
    user_agent="MyApp/1.0",
    timeout=30.0,
    cache=cache,
    session=session,
    max_retries=3,
    retry_backoff=0.5,
    mirror_url="https://custom-pypi-mirror.example.com/simple",
    include_prereleases=False,
    json_api_url="https://custom-pypi-mirror.example.com/pypi"
)
```

## Error Handling

The client implements standardized error handling through error codes and descriptive messages:

### Standard Error Codes

| Code | Description | Example |
|------|-------------|---------|
| 1000 | Package not found | Package "nonexistent-pkg" not found on PyPI |
| 1001 | Version not found | Version "9.9.9" not found for package "requests" |
| 1002 | Invalid package name | Package name contains invalid characters |
| 1003 | PyPI service error | PyPI service returned a 500 error |
| 1004 | Network error | Connection timeout after 30 seconds |
| 1005 | Parse error | Unable to parse JSON response |
| 1006 | Cache error | Failed to retrieve from cache |
| 1007 | File error | Requirements file not found or inaccessible |

### Error Handling Example

```python
from mcp_pypi.core import PyPIClient
from mcp_pypi.exceptions import PackageNotFoundError, VersionNotFoundError

client = PyPIClient()

try:
    package_info = await client.get_package_info("requests")
    latest_version = await client.get_latest_version("requests")
except PackageNotFoundError as e:
    print(f"Package error: {e}")
except VersionNotFoundError as e:
    print(f"Version error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Caching

The client includes a flexible caching system to improve performance and reduce load on PyPI servers:

### Cache Backends

- **Memory Cache**: Default in-memory LRU cache
- **File Cache**: Persistent file-based cache
- **Redis Cache**: Distributed cache using Redis
- **Custom Cache**: Support for custom cache implementations

### Caching Configuration

```python
from mcp_pypi.core import PyPIClient
from mcp_pypi.utils.cache import FileCache

# File-based cache
cache = FileCache(
    directory="/tmp/pypi-cache",
    ttl=3600,  # 1 hour
    max_size=1024 * 1024 * 100  # 100 MB
)

client = PyPIClient(cache=cache)
```

### Cache Control

```python
# Skip cache for this request
latest_version = await client.get_latest_version("requests", use_cache=False)

# Force refresh cache
package_info = await client.get_package_info("django", refresh_cache=True)

# Clear entire cache
await client.clear_cache()

# Clear cache for a specific package
await client.clear_cache_for_package("numpy")
```

## Advanced Usage

### Custom Transport

```python
from mcp_pypi.core import PyPIClient
from utils.transports import WebSocketTransport

# Create a WebSocket transport
transport = WebSocketTransport(
    subprotocols=["pypi-json"],
    ping_interval=30.0,
    debug=True
)

# Initialize client with custom transport
client = PyPIClient(transport=transport)

# Connect to a PyPI-compatible WebSocket server
await client.connect("ws://pypi-ws.example.com/ws", 443)

# Use the client as normal
package_info = await client.get_package_info("requests")
```

### Batch Operations

```python
from mcp_pypi.core import PyPIClient

client = PyPIClient()

# Batch check latest versions
packages = ["requests", "django", "numpy", "pandas"]
results = await client.batch_get_latest_versions(packages)

# Batch check dependencies
deps = await client.batch_get_dependencies(packages)

# Process results
for package, result in results.items():
    if isinstance(result, Exception):
        print(f"Error for {package}: {result}")
    else:
        print(f"{package}: {result}")
```

### Events and Monitoring

```python
from mcp_pypi.core import PyPIClient
from mcp_pypi.utils.events import PyPIEventListener

client = PyPIClient()
listener = PyPIEventListener(client)

# Subscribe to package updates
await listener.subscribe(["django", "requests", "numpy"])

# Register event handlers
@listener.on_package_update
async def handle_update(package_name, old_version, new_version):
    print(f"{package_name} updated from {old_version} to {new_version}")

@listener.on_package_release
async def handle_release(package_name, version):
    print(f"New release: {package_name} {version}")

# Start listening (runs in background)
await listener.start()

# Later, stop listening
await listener.stop()
```

## Integration Examples

### Integration with FastAPI

```python
from fastapi import FastAPI, HTTPException, Depends
from mcp_pypi.core import PyPIClient

app = FastAPI(title="PyPI API Gateway")
client = PyPIClient()

@app.get("/packages/{package_name}")
async def get_package(package_name: str):
    try:
        return await client.get_package_info(package_name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/packages/{package_name}/versions/latest")
async def get_latest_version(package_name: str):
    try:
        version = await client.get_latest_version(package_name)
        return {"package": package_name, "latest_version": version}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/packages/{package_name}/dependencies")
async def get_dependencies(package_name: str, depth: int = 1):
    try:
        return await client.get_dependency_tree(package_name, depth=depth)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
```

### Integration with MCP Server

```python
from mcp.server import MCPServer
from mcp_pypi.server.tools import register_pypi_tools

# Create MCP server
server = MCPServer(
    host="0.0.0.0",
    port=8080,
    debug=True
)

# Register PyPI tools with the MCP server
register_pypi_tools(server)

# Start the server
server.start()
```

### CLI Integration

```python
import typer
from mcp_pypi.core import PyPIClient
from rich.console import Console
from rich.table import Table
import asyncio

app = typer.Typer()
console = Console()

@app.command()
def search(query: str, page: int = 1):
    """Search for packages on PyPI."""
    async def _search():
        client = PyPIClient()
        results = await client.search_packages(query, page=page)
        
        table = Table(title=f"Search results for '{query}'")
        table.add_column("Package")
        table.add_column("Version")
        table.add_column("Description")
        
        for pkg in results["packages"]:
            table.add_row(
                pkg["name"],
                pkg["version"],
                pkg["description"][:50] + "..." if len(pkg["description"]) > 50 else pkg["description"]
            )
        
        console.print(table)
    
    asyncio.run(_search())

@app.command()
def info(package_name: str):
    """Get information about a package."""
    async def _info():
        client = PyPIClient()
        info = await client.get_package_info(package_name)
        
        console.print(f"[bold]{info['name']}[/bold] {info['version']}")
        console.print(f"[italic]{info['description']}[/italic]")
        console.print(f"Homepage: {info['home_page']}")
        console.print(f"Author: {info['author']}")
        console.print(f"License: {info['license']}")
        
    asyncio.run(_info())

if __name__ == "__main__":
    app() 