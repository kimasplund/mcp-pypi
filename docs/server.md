# JSON-RPC Server Documentation

The MCP-PyPI package includes a full JSON-RPC 2.0 compliant server that provides access to all PyPI client functionality. This document describes the server features, configuration options, and available endpoints.

## Server Modes

The server can be run in two different modes:

### HTTP Mode (Default)

In HTTP mode, the server listens for JSON-RPC requests over HTTP on the specified host and port.

```bash
# Start the server on the default port (8000)
pypi-mcp serve

# Start on a specific port
pypi-mcp serve --port 8001

# Bind to a different interface
pypi-mcp serve --host 0.0.0.0 --port 8001
```

### STDIN Mode

In STDIN mode, the server reads JSON-RPC requests from standard input and writes responses to standard output. This mode is designed for integration with the MCP protocol.

```bash
# Start in STDIN mode
pypi-mcp serve --stdin
```

## Features

### Automatic Port Selection

If the specified port is busy, the server will automatically scan for an available port by incrementing the port number (e.g., 8000, 8001, 8002, etc.). This helps prevent "address already in use" errors and ensures the server can start even if the default port is occupied.

### Tool Discovery

The server implements the JSON-RPC "describe" method, which returns information about all available tools and their parameters. This makes it easier for clients to discover the server's capabilities.

### JSON-RPC 2.0 Compliance

All responses follow the [JSON-RPC 2.0 specification](https://www.jsonrpc.org/specification), including proper error handling and response formatting.

### Error Handling

The server provides standardized error responses with appropriate error codes, making it easier to handle errors in client applications.

### Caching

Server responses are cached for improved performance using the PyPI client's caching mechanisms.

## Configuration Options

The server can be configured with the following command-line options:

| Option | Default | Description |
|--------|---------|-------------|
| `--host`, `-h` | `127.0.0.1` | Host to bind to |
| `--port`, `-p` | `8000` | Port to listen on |
| `--verbose`, `-v` | `False` | Enable verbose logging |
| `--log-file` | `None` | Log file path |
| `--cache-dir` | System default | Cache directory path |
| `--cache-ttl` | `3600` | Cache TTL in seconds |
| `--stdin` | `False` | Read JSON-RPC requests from stdin |

## Available Methods

The server exposes the following JSON-RPC methods:

### Core Methods

| Method | Description | Parameters |
|--------|-------------|------------|
| `ping` | Simple connectivity check | None |
| `describe` | Get information about available tools | None |

### Package Information Methods

| Method | Description | Parameters |
|--------|-------------|------------|
| `get_package_info` | Get detailed package information | `package_name` |
| `get_latest_version` | Get latest version of a package | `package_name` |
| `check_package_exists` | Check if a package exists | `package_name` |
| `get_package_metadata` | Get package metadata | `package_name`, `version` (optional) |
| `get_package_releases` | Get all releases of a package | `package_name` |
| `get_release_urls` | Get download URLs for a package | `package_name`, `version` |
| `get_documentation_url` | Get documentation URL for a package | `package_name`, `version` (optional) |

### Dependency Methods

| Method | Description | Parameters |
|--------|-------------|------------|
| `get_dependencies` | Get dependencies for a package | `package_name`, `version` (optional) |
| `get_dependency_tree` | Get a dependency tree | `package_name`, `version` (optional), `depth` (optional) |

### Statistics Methods

| Method | Description | Parameters |
|--------|-------------|------------|
| `get_package_stats` | Get download statistics | `package_name`, `version` (optional), `periods` (optional) |

### Search and Feed Methods

| Method | Description | Parameters |
|--------|-------------|------------|
| `search_packages` | Search for packages on PyPI | `query`, `page` (optional) |
| `get_newest_packages` | Get newest packages on PyPI | `limit` (optional) |
| `get_latest_updates` | Get latest package updates | `limit` (optional) |
| `get_project_releases` | Get recent project releases | `package_name` |

### Utilities

| Method | Description | Parameters |
|--------|-------------|------------|
| `compare_versions` | Compare package versions | `package_name`, `version1`, `version2` |
| `check_requirements_file` | Check a requirements file for outdated packages | `file_path`, `format` (optional, 'json' or 'table') |

### check_requirements_file

Check a requirements file for outdated packages.

**Parameters:**
- `file_path`: Path to the requirements file to check

This method supports both `requirements.txt` files and `pyproject.toml` files. For `pyproject.toml` files, it can detect dependencies from:
- PEP 621 project metadata (`project.dependencies`)
- Poetry (`tool.poetry.dependencies`)
- PDM (`tool.pdm.dependencies`)
- Flit (`tool.flit.metadata.requires`)

**Example:**
```json
{
  "jsonrpc": "2.0",
  "method": "check_requirements_file",
  "params": {
    "file_path": "requirements.txt"
  },
  "id": 7
}
```

**Example with JSON format:**
```bash
curl -X POST http://localhost:8000/rpc -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0",
  "method": "check_requirements_file",
  "params": {
    "file_path": "requirements.txt",
    "format": "json"
  },
  "id": 7
}'
```

**Example with pyproject.toml:**
```bash
curl -X POST http://localhost:8000/rpc -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0",
  "method": "check_requirements_file",
  "params": {
    "file_path": "pyproject.toml"
  },
  "id": 7
}'
```

## Making Requests

### HTTP Mode

You can make requests to the server using any HTTP client that supports JSON-RPC. Here are some examples using `curl`:

```bash
# Make a ping request
curl -X POST http://localhost:8000/rpc -H "Content-Type: application/json" -d '{"jsonrpc": "2.0", "method": "ping", "id": 1}'

# Check if a package exists
curl -X POST http://localhost:8000/rpc -H "Content-Type: application/json" -d '{"jsonrpc": "2.0", "method": "check_package_exists", "params": {"package_name": "requests"}, "id": 2}'

# Get the latest version of a package
curl -X POST http://localhost:8000/rpc -H "Content-Type: application/json" -d '{"jsonrpc": "2.0", "method": "get_latest_version", "params": {"package_name": "flask"}, "id": 3}'

# Check requirements file with JSON format
curl -X POST http://localhost:8000/rpc -H "Content-Type: application/json" -d '{"jsonrpc": "2.0", "method": "check_requirements_file", "params": {"file_path": "requirements.txt", "format": "json"}, "id": 4}'

# Discover available tools
curl -X POST http://localhost:8000/rpc -H "Content-Type: application/json" -d '{"jsonrpc": "2.0", "method": "describe", "id": 5}'
```

### STDIN Mode

In STDIN mode, you can send JSON-RPC requests directly to the server's standard input:

```bash
echo '{"jsonrpc": "2.0", "method": "ping", "id": 1}' | pypi-mcp serve --stdin
```

## Integration with MCP

You can integrate the PyPI client with the MCP protocol by adding it to your MCP configuration:

```json
{
  "mcpServers": {
    "PYPI_MCP": {
      "command": "pypi-mcp",
      "args": ["serve", "--stdin"]
    }
  }
}
```

This will make all PyPI client functionality available through the MCP protocol.

## Error Handling

The server uses the following error codes in accordance with the JSON-RPC 2.0 specification:

| Code | Message | Meaning |
|------|---------|---------|
| -32700 | Parse error | Invalid JSON was received |
| -32600 | Invalid Request | The JSON sent is not a valid Request object |
| -32601 | Method not found | The method does not exist / is not available |
| -32602 | Invalid params | Invalid method parameter(s) |
| -32603 | Internal error | Internal JSON-RPC error |
| -32000 to -32099 | Server error | Reserved for implementation-defined server errors |

In addition, the server defines the following custom error codes:

| Code | Message | Meaning |
|------|---------|---------|
| -32001 | Not found | Package or resource not found |
| -32002 | Network error | Error communicating with PyPI |
| -32003 | Permission error | Insufficient permissions |
| -32004 | File error | Error accessing or reading a file | 