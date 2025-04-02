# PyPI MCP Client (mcp-pypi)

A powerful Python client and CLI tool for interacting with the Python Package Index (PyPI). This tool integrates with Claude, Gordon, Cursor, or any other AI assistant that supports the MCP protocol.

## Major Improvements

This is a complete rewrite of the original PyPI MCP server, with many improvements:

- **Modular Architecture**: Organized into logical components for better maintainability
- **True Asynchronous HTTP**: Uses `aiohttp` for efficient, non-blocking requests
- **Improved Caching**: Thread-safe async cache with proper pruning
- **Dependency Injection**: Components can be replaced or mocked for testing
- **Proper Error Handling**: Consistent error handling with descriptive messages
- **Real Package Statistics**: Fetches real download statistics from PyPI
- **Modern CLI**: Rich command-line interface with Typer and Rich
- **Extensive Testing**: Comprehensive test suite for all components
- **Type Safety**: Complete type annotations throughout the codebase
- **Security Challenge Handling**: Gracefully handles PyPI security challenges

## Features

The PyPI MCP client provides the following capabilities:

### Core Features

- **Package Information**: Get detailed information about Python packages
- **Version Management**: Retrieve and compare package versions
- **Download URL Generation**: Generate predictable download URLs
- **Search**: Search for packages on PyPI
- **Dependencies**: Get package dependencies and their details

### Enhanced Features

- **Package Statistics**: Get real download statistics for packages
- **Dependency Visualization**: Generate and visualize dependency trees
- **Documentation Discovery**: Find documentation URLs for packages
- **Requirements Analysis**: Check requirements files for outdated packages
- **Caching**: Efficient local response caching with ETag support
- **User-Agent Configuration**: Proper user-agent with contact information

## Installation

### From PyPI (recommended)

```bash
pip install mcp-pypi
```

### From Source

```bash
git clone https://github.com/kimasplund/mcp-pypi.git
cd mcp-pypi
pip install .
```

For development:

```bash
pip install -e ".[dev]"
```

### Optional Dependencies

Install optional visualization features:

```bash
pip install "mcp-pypi[viz]"
```

For improved search functionality:

```bash
pip install "mcp-pypi[search]"
```

## CLI Usage

The client includes a rich command-line interface:

```bash
# Get package information
pypi-mcp package info requests

# Get the latest version of a package
pypi-mcp package version flask

# Search for packages
pypi-mcp search fastapi

# Check a requirements file for outdated packages
pypi-mcp check-requirements requirements.txt

# See download statistics for a package
pypi-mcp stats downloads numpy

# Show newest packages on PyPI
pypi-mcp feed newest

# Compare versions
pypi-mcp package compare requests 2.28.1 2.28.2

# Clear the cache
pypi-mcp cache clear
```

## Python API Usage

```python
import asyncio
from mcp_pypi.core import PyPIClient
from mcp_pypi.core.models import PyPIClientConfig

async def get_package_info():
    # Create a client with custom configuration
    config = PyPIClientConfig(cache_ttl=3600, max_retries=3)
    client = PyPIClient(config)
    
    try:
        # Get package information
        info = await client.get_package_info("requests")
        print(f"Latest version: {info['info']['version']}")
        
        # Get download statistics
        stats = await client.get_package_stats("requests")
        print(f"Last month downloads: {stats.get('last_month', 0):,}")
        
        # Check dependencies
        deps = await client.get_dependencies("requests")
        print("Dependencies:")
        for dep in deps.get("dependencies", []):
            print(f"  {dep['name']} {dep['version_spec']}")
            
        # Example of searching with proper error handling
        search_result = await client.search_packages("fastapi")
        
        if isinstance(search_result, str) and "Client Challenge" in search_result:
            print("PyPI returned a security challenge page.")
            print("Try using a web browser to search directly.")
        elif isinstance(search_result, dict):
            if "error" in search_result:
                print(f"Search error: {search_result['error']['message']}")
            elif "message" in search_result:
                print(search_result['message'])
            elif "results" in search_result:
                results = search_result["results"]
                print(f"Found {len(results)} packages")
                for pkg in results[:3]:  # Just show first 3
                    print(f"  {pkg.get('name')} - {pkg.get('description', '')[:60]}...")
                    
    finally:
        # Always close the client to release resources
        await client.close()

# Run the async function
asyncio.run(get_package_info())
```

## Error Handling

All tools use standardized error responses with the following error codes:

- `not_found`: Package or resource not found
- `invalid_input`: Invalid parameter value provided
- `network_error`: Error communicating with PyPI
- `parse_error`: Error parsing response from PyPI
- `file_error`: Error accessing or reading a file
- `permission_error`: Insufficient permissions
- `rate_limit_error`: Exceeded PyPI rate limits
- `timeout_error`: Request timed out

### Handling Errors

```python
# Example of proper error handling
async def example_with_error_handling():
    client = PyPIClient()
    try:
        # Try to get info for a package that doesn't exist
        info = await client.get_package_info("this-package-does-not-exist")
        
        # Check for error
        if "error" in info:
            error_code = info["error"]["code"]
            error_message = info["error"]["message"]
            
            if error_code == "not_found":
                print(f"Package not found: {error_message}")
            elif error_code == "network_error":
                print(f"Network issue: {error_message}")
            else:
                print(f"Error ({error_code}): {error_message}")
        else:
            # Process normal response
            print(f"Package found: {info['info']['name']}")
            
    finally:
        await client.close()
```

### Security Challenges

PyPI implements security measures to prevent scraping and abuse. In some cases, PyPI may return a "Client Challenge" page instead of the expected response. The MCP-PyPI client handles these cases in the following ways:

1. For search requests, the client detects the challenge page and returns a structured response with a helpful message.
2. For API endpoints, the client uses proper caching and respects rate limits to minimize the chances of triggering security measures.

When you encounter a security challenge during searches:

```python
search_result = await client.search_packages("flask")

# Handle different response types
if isinstance(search_result, str) and "Client Challenge" in search_result:
    print("Security challenge detected - try direct browser search")
elif isinstance(search_result, dict):
    if "message" in search_result:
        print(search_result["message"])
    elif "results" in search_result:
        # Process normal results
        for pkg in search_result["results"]:
            print(f"{pkg['name']} - {pkg['description']}")
```

## Running Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=mcp_pypi
```

## MCP Server Integration

You can integrate the PyPI client as an MCP server in your workflow:

### JSON-RPC 2.0 Server

The PyPI MCP client includes a full JSON-RPC 2.0 compliant server that can be started in two modes:

1. **HTTP Server Mode**: Exposes the API over HTTP
2. **STDIN Mode**: Reads JSON-RPC requests from standard input (for use with the MCP protocol)

For detailed documentation on the server, see [Server Documentation](docs/server.md).

#### Starting the Server

```bash
# Start the HTTP server on the default port (8000)
pypi-mcp serve

# Start the server on a custom port
pypi-mcp serve --port 8001

# Start the server with verbose logging
pypi-mcp serve --verbose

# Start in STDIN mode for MCP integration
pypi-mcp serve --stdin
```

#### Server Features

- **Automatic Port Selection**: If the specified port is in use, the server automatically scans for an available port
- **Tool Discovery**: The server implements the JSON-RPC "describe" method for tool discovery
- **JSON-RPC 2.0 Compliance**: All responses follow the JSON-RPC 2.0 specification
- **Error Handling**: Proper error responses with standard error codes
- **Caching**: Server responses are cached for improved performance

#### Making Requests to the Server

Example using `curl`:

```bash
# Make a ping request to check if the server is running
curl -X POST http://localhost:8000/rpc -H "Content-Type: application/json" -d '{"jsonrpc": "2.0", "method": "ping", "id": 1}'

# Check if a package exists
curl -X POST http://localhost:8000/rpc -H "Content-Type: application/json" -d '{"jsonrpc": "2.0", "method": "check_package_exists", "params": {"package_name": "requests"}, "id": 2}'

# Get the latest version of a package
curl -X POST http://localhost:8000/rpc -H "Content-Type: application/json" -d '{"jsonrpc": "2.0", "method": "get_latest_version", "params": {"package_name": "flask"}, "id": 3}'

# Discover available tools
curl -X POST http://localhost:8000/rpc -H "Content-Type: application/json" -d '{"jsonrpc": "2.0", "method": "describe", "id": 4}'
```

#### Server Endpoints

The server exposes the following JSON-RPC methods:

- `ping`: Simple connectivity check
- `describe`: Get information about available tools
- `search_packages`: Search for packages on PyPI
- `get_dependencies`: Get dependencies for a package
- `check_package_exists`: Check if a package exists
- `get_package_metadata`: Get package metadata
- `get_package_stats`: Get download statistics
- `get_dependency_tree`: Get a dependency tree
- `get_package_info`: Get detailed package information
- `get_latest_version`: Get the latest version of a package
- And more...

Each method accepts parameters as defined in the tool schema, which can be retrieved using the `describe` method.

## License

MIT

## Author

Kim Asplund (kim.asplund@gmail.com)
GitHub: https://github.com/kimasplund
Website: https://asplund.kim 