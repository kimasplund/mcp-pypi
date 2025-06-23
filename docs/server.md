# Enhanced MCP-PyPI Server

This document provides detailed information about the enhanced MCP-PyPI server implementation that supports multiple transport mechanisms and configuration options.

## Overview

The enhanced server (`enhanced_mcp_server.py`) provides a unified interface for running the MCP-PyPI server with different transport mechanisms:

- **STDIO**: Standard input/output for command-line and subprocess communication
- **HTTP**: RESTful and long-polling HTTP communication
- **WebSocket**: Full-duplex communication over a single TCP connection
- **SSE**: Server-Sent Events for real-time server-to-client streaming

This flexibility allows the server to integrate with various client environments and communication patterns.

## Usage

### Basic Usage

To start the server with default settings (STDIO transport):

```bash
python enhanced_mcp_server.py
```

To specify a different transport type:

```bash
python enhanced_mcp_server.py --transport http --host 127.0.0.1 --port 8143
```

### Command-Line Arguments

The server supports the following command-line arguments:

#### Transport Options

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--transport`, `-t` | string | `stdio` | Transport type to use (`stdio`, `http`, `websocket`, `sse`) |
| `--host` | string | `127.0.0.1` | Hostname to bind to (for network transports) |
| `--port` | int | `8143` | Port number to listen on (for network transports) |
| `--message-format` | string | `auto` | Message format for STDIO transport (`auto`, `binary`, `newline`) |
| `--timeout` | float | `30.0` | Operation timeout in seconds |

#### Protocol Options

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--protocol-version` | string | (latest) | MCP protocol version to use |

#### Cache Options

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--cache-dir` | string | None | Directory for caching PyPI data |
| `--cache-ttl` | int | `3600` | Cache TTL in seconds |

#### Debug Options

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--debug`, `-d` | flag | `False` | Enable debug logging |
| `--log-level` | string | `INFO` | Set logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

## Transport Types

### STDIO Transport

The STDIO transport uses standard input and output streams for communication. This is ideal for command-line tools and integration with systems that can spawn subprocesses.

Example usage:

```bash
python enhanced_mcp_server.py --transport stdio --message-format binary
```

The STDIO transport supports two message formats:
- `binary`: Length-prefixed binary format (more efficient)
- `newline`: Newline-delimited JSON format (more human-readable)
- `auto`: Auto-detect the format based on incoming messages

### HTTP Transport

The HTTP transport provides RESTful API access to the MCP-PyPI server. This is suitable for web applications and services that communicate over HTTP.

Example usage:

```bash
python enhanced_mcp_server.py --transport http --host 0.0.0.0 --port 8080
```

The HTTP server provides the following endpoints:
- `POST /`: Main endpoint for JSON-RPC requests and responses

### WebSocket Transport

The WebSocket transport enables full-duplex communication over a single TCP connection. This is ideal for real-time applications that require bidirectional messaging.

Example usage:

```bash
python enhanced_mcp_server.py --transport websocket --host 0.0.0.0 --port 8765
```

### SSE Transport

The Server-Sent Events (SSE) transport provides a streaming connection for server-to-client communication. This is suitable for applications that need real-time updates from the server.

Example usage:

```bash
python enhanced_mcp_server.py --transport sse --host 0.0.0.0 --port 8090
```

The SSE server provides the following endpoints:
- `GET /events`: SSE endpoint for event streaming
- `POST /message`: Endpoint for sending messages to the server

## Protocol Version Negotiation

The server supports protocol version negotiation to ensure compatibility between clients and servers. You can specify the protocol version to use with the `--protocol-version` argument:

```bash
python enhanced_mcp_server.py --protocol-version 2025-03-26
```

If not specified, the server will use the latest supported version and negotiate with clients based on their requested version.

## Cache Configuration

The server supports caching PyPI data to improve performance and reduce load on the PyPI servers. You can configure the cache directory and TTL:

```bash
python enhanced_mcp_server.py --cache-dir /tmp/pypi-cache --cache-ttl 7200
```

## Debug and Logging

For troubleshooting and development, you can enable debug mode and set the logging level:

```bash
python enhanced_mcp_server.py --debug --log-level DEBUG
```

This will output detailed information about transport initialization, message handling, and server operations.

## Integration Examples

### Integration with FastAPI

You can integrate the MCP-PyPI server with a FastAPI application:

```python
from fastapi import FastAPI
from enhanced_mcp_server import EnhancedMCPServer

app = FastAPI()
mcp_server = EnhancedMCPServer(transport_type="http")

@app.on_event("startup")
async def startup():
    # Start the MCP server
    await mcp_server.start()

@app.on_event("shutdown")
async def shutdown():
    # Clean up resources
    await mcp_server.server.client.close()
```

### Integration with WebSocket Service

You can integrate the MCP-PyPI server with a WebSocket service:

```python
import asyncio
import websockets
from enhanced_mcp_server import EnhancedMCPServer

async def main():
    # Initialize server
    server = EnhancedMCPServer(
        transport_type="websocket",
        host="0.0.0.0",
        port=8765,
        debug=True
    )
    
    # Start the server
    await server.start()

# Run the server
asyncio.run(main())
```

## Implementation Details

The enhanced server provides several key features:

1. **Transport Abstraction**: Unified interface for all transport types
2. **Fallback Mechanisms**: Built-in methods with fallback to manual implementations
3. **Flexible Configuration**: Extensive command-line options for all aspects of the server
4. **Protocol Version Management**: Support for different MCP protocol versions
5. **Error Handling**: Comprehensive error handling and reporting
6. **Logging**: Detailed logging for troubleshooting

The server first attempts to use the built-in methods provided by FastMCP (if available) and falls back to manual implementations using our transport classes when necessary.

## Debugging Tips

If you encounter issues with the server:

1. Enable debug mode with `--debug` and set log level to `DEBUG`
2. Check the server logs for transport initialization messages
3. Verify that the correct transport type is being used
4. Ensure that required dependencies are installed for the selected transport
5. Check for port conflicts when using network transports

## Required Dependencies

The enhanced server requires the following dependencies:

- `fastmcp`: For core MCP server functionality
- `mcp_pypi`: For PyPI client implementation
- `uvicorn`: For HTTP and SSE servers
- `websockets`: For WebSocket server
- `fastapi`: For HTTP and SSE APIs 