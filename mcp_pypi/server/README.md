# MCP Server for PyPI Client

This module provides a fully compliant MCP server implementation using the official MCP Python SDK.

## Features

- Full compliance with the Model Context Protocol (MCP) standard
- Implementation of all three MCP primitives:
  - **Tools**: Expose PyPI functionality as callable tools
  - **Resources**: Expose PyPI data as URI-addressable resources
  - **Prompts**: Provide predefined prompt templates for PyPI interactions

## Usage

### CLI Usage

```bash
# Start the server with HTTP endpoint
pypi-mcp mcp-server run

# Start the server in stdin mode for MCP integration
pypi-mcp mcp-server run --stdin

# Use with custom cache settings
pypi-mcp mcp-server run --cache-dir /tmp/pypi-cache --cache-ttl 7200
```

### Python API Usage

```python
from mcp_pypi.server import PyPIMCPServer
from mcp_pypi.core.models import PyPIClientConfig
import asyncio

async def run_server():
    # Create config
    config = PyPIClientConfig()
    
    # Create server
    server = PyPIMCPServer(config)
    
    # HTTP server mode
    await server.start_http_server(host="127.0.0.1", port=8000)
    
    # Or stdin mode
    # await server.process_stdin()

asyncio.run(run_server())
```

### Integration with ASGI Servers

```python
from starlette.applications import Starlette
from starlette.routing import Mount
from mcp_pypi.server import PyPIMCPServer

# Create server
server = PyPIMCPServer()

# Get ASGI app
app = Starlette(
    routes=[
        Mount('/mcp', app=server.get_fastmcp_app())
    ]
)
```

## Available MCP Tools

- `get_package_info`: Get detailed information about a Python package
- `get_latest_version`: Get the latest version of a package
- `get_dependency_tree`: Get the dependency tree for a package
- `search_packages`: Search for packages on PyPI
- `get_package_stats`: Get download statistics for a package
- `check_package_exists`: Check if a package exists on PyPI
- `get_package_metadata`: Get package metadata
- `get_package_releases`: Get all releases of a package
- `get_project_releases`: Get project releases with timestamps
- `get_documentation_url`: Get documentation URL for a package
- `check_requirements_file`: Check a requirements file for outdated packages
- `compare_versions`: Compare two package versions
- `get_newest_packages`: Get newest packages on PyPI
- `get_latest_updates`: Get latest package updates on PyPI

## Available MCP Resources

- `pypi://package/{package_name}`: Package information
- `pypi://stats/{package_name}`: Package download statistics
- `pypi://dependencies/{package_name}`: Package dependencies

## Available MCP Prompts

- `search_packages_prompt`: Create a prompt for searching packages
- `analyze_package_prompt`: Create a prompt for analyzing a package
- `compare_packages_prompt`: Create a prompt for comparing two packages 