# MCP Transport Implementations

This document provides detailed information about the available transport implementations for the Model Context Protocol (MCP) communication system.

## Overview

The MCP system supports multiple transport mechanisms to accommodate different communication needs and environments. Each transport implementation follows a common interface defined by the `BaseTransport` abstract class, ensuring consistent behavior across different communication channels.

Available transport implementations:

1. **Binary Transport** - Length-prefixed binary message format
2. **Newline Transport** - Newline-delimited JSON messages
3. **HTTP Transport** - RESTful and long-polling HTTP communication
4. **WebSocket Transport** - Full-duplex communication over a single TCP connection
5. **SSE Transport** - Server-Sent Events for real-time server-to-client streaming

## Base Transport Interface

All transport implementations inherit from the `BaseTransport` abstract class, which defines the following interface:

```python
class BaseTransport(ABC):
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if the transport is currently connected."""
        pass

    @abstractmethod
    async def connect(self, host: str, port: int) -> bool:
        """Connect to the server."""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from the server."""
        pass

    @abstractmethod
    async def send_message(self, message: Dict[str, Any]) -> bool:
        """Send a message to the server."""
        pass

    @abstractmethod
    async def receive_message(self) -> Optional[Dict[str, Any]]:
        """Receive a message from the server."""
        pass
```

## Binary Transport

The Binary Transport uses a length-prefixed binary format for sending and receiving messages. Each message is prefixed with a 4-byte unsigned integer representing the message length, followed by the JSON-encoded message payload.

### Features

- Efficient binary encoding
- Message boundaries clearly defined by length prefix
- Suitable for high-throughput applications
- Works well in streaming environments

### Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `receive_timeout` | float | 60.0 | Timeout for receiving messages (seconds) |
| `connect_timeout` | float | 10.0 | Timeout for establishing connection (seconds) |
| `max_message_size` | int | 1048576 | Maximum allowed message size (bytes) |
| `retry_attempts` | int | 3 | Number of connection retry attempts |
| `retry_delay` | float | 1.0 | Delay between retry attempts (seconds) |
| `debug` | bool | False | Enable debug logging |

### Usage Example

```python
from utils.transports.binary import BinaryTransport

# Create the transport
transport = BinaryTransport(
    max_message_size=2*1024*1024,  # 2MB max message size
    debug=True
)

# Connect to the server
await transport.connect("example.com", 8080)

# Send a message
message = {"type": "request", "action": "get_data"}
await transport.send_message(message)

# Receive a response
response = await transport.receive_message()

# Disconnect when done
await transport.disconnect()
```

## Newline Transport

The Newline Transport uses newline-delimited JSON messages for communication. Each message is encoded as a JSON string followed by a newline character (`\n`).

### Features

- Human-readable JSON format
- Simple protocol
- Easy to debug
- Compatible with line-oriented tools and logs

### Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `receive_timeout` | float | 60.0 | Timeout for receiving messages (seconds) |
| `connect_timeout` | float | 10.0 | Timeout for establishing connection (seconds) |
| `max_line_length` | int | 1048576 | Maximum allowed line length (bytes) |
| `retry_attempts` | int | 3 | Number of connection retry attempts |
| `retry_delay` | float | 1.0 | Delay between retry attempts (seconds) |
| `debug` | bool | False | Enable debug logging |

### Usage Example

```python
from utils.transports.newline import NewlineTransport

# Create the transport
transport = NewlineTransport(
    max_line_length=100*1024,  # 100KB max line length
    debug=True
)

# Connect to the server
await transport.connect("example.com", 8080)

# Send a message
message = {"type": "request", "action": "list_items"}
await transport.send_message(message)

# Receive a response
response = await transport.receive_message()

# Disconnect when done
await transport.disconnect()
```

## HTTP Transport

The HTTP Transport uses HTTP/HTTPS for communication with MCP servers. It supports both RESTful request-response patterns and long-polling for near-real-time communication.

### Features

- Works over standard HTTP/HTTPS
- Compatible with firewalls and proxies
- Supports REST API patterns
- Long-polling option for near-real-time updates
- Optional session management

### Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `headers` | Dict[str, str] | None | HTTP headers to include in requests |
| `timeout` | float | 30.0 | Request timeout (seconds) |
| `session_id` | str | None | Session identifier (auto-generated if None) |
| `long_polling` | bool | False | Enable long-polling mode |
| `polling_interval` | float | 0.5 | Interval between polls (seconds) |
| `retry_attempts` | int | 3 | Number of retry attempts for failed requests |
| `retry_delay` | float | 1.0 | Delay between retry attempts (seconds) |
| `debug` | bool | False | Enable debug logging |

### Usage Example

```python
from utils.transports.http import HTTPTransport

# Create the transport with long-polling enabled
transport = HTTPTransport(
    headers={"User-Agent": "MCP Client/1.0"},
    long_polling=True,
    polling_interval=1.0,
    debug=True
)

# Connect to the server
await transport.connect("api.example.com", 443)

# Send a message
message = {"type": "subscription", "channel": "updates"}
await transport.send_message(message)

# Receive messages (will use long-polling)
while True:
    response = await transport.receive_message()
    if response:
        print(f"Received: {response}")

# Disconnect when done
await transport.disconnect()
```

### Direct HTTP Requests

The HTTP Transport also provides a utility method for making direct HTTP requests:

```python
# Make a GET request
response = await transport.make_request(
    method="GET",
    path="/api/resources/123",
    params={"include": "details"}
)

# Make a POST request
response = await transport.make_request(
    method="POST",
    path="/api/resources",
    json={"name": "New Resource", "type": "document"}
)
```

## WebSocket Transport

The WebSocket Transport enables full-duplex communication over a single TCP connection. It maintains a persistent connection and handles automatic reconnection.

### Features

- Full-duplex communication
- Real-time messaging
- Automatic ping/pong keep-alive
- Reconnection with exponential backoff
- Support for subprotocols and custom headers

### Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `subprotocols` | List[str] | None | WebSocket subprotocols to request |
| `headers` | Dict[str, str] | None | HTTP headers for the upgrade request |
| `ping_interval` | float | 20.0 | Interval for sending ping frames (seconds) |
| `ping_timeout` | float | 10.0 | Timeout for ping response (seconds) |
| `max_message_size` | int | 1048576 | Maximum message size (bytes) |
| `retry_attempts` | int | 3 | Number of reconnection attempts |
| `retry_delay` | float | 1.0 | Delay between retry attempts (seconds) |
| `ssl` | bool/SSLContext | None | SSL context or verification flag |
| `debug` | bool | False | Enable debug logging |

### Usage Example

```python
from utils.transports.websocket import WebSocketTransport

# Create the transport
transport = WebSocketTransport(
    subprotocols=["mcp.v1"],
    headers={"Authorization": "Bearer token123"},
    ping_interval=30.0,
    debug=True
)

# Connect to the server
await transport.connect("ws.example.com", 443)

# Send a message
message = {"type": "event", "name": "user.login"}
await transport.send_message(message)

# Receive messages
while True:
    response = await transport.receive_message()
    if response:
        print(f"Received: {response}")
        
    # Check if still connected
    if not transport.is_connected:
        print("Connection lost")
        break

# Disconnect when done
await transport.disconnect()
```

## SSE Transport

The SSE (Server-Sent Events) Transport implements a streaming connection for server-to-client communication. It combines SSE for receiving messages with HTTP for sending messages.

### Features

- Real-time server-to-client updates
- Automatic event parsing
- Automatic reconnection with last event ID tracking
- Works over standard HTTP connections
- Compatible with firewalls and proxies

### Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `headers` | Dict[str, str] | None | HTTP headers to include in requests |
| `retry_attempts` | int | 3 | Number of connection retry attempts |
| `retry_delay` | float | 1.0 | Initial delay between retry attempts (seconds) |
| `event_type` | str | "message" | SSE event type to listen for |
| `ssl` | bool/SSLContext | None | SSL context or verification flag |
| `connect_timeout` | float | 30.0 | Timeout for establishing connection (seconds) |
| `read_timeout` | float | None | Timeout for reading event data (seconds) |
| `outbound_url` | str | None | URL for sending messages |
| `client_id` | str | None | Client identifier (auto-generated if None) |
| `debug` | bool | False | Enable debug logging |

### Usage Example

```python
from utils.transports.sse import SSETransport

# Create the transport
transport = SSETransport(
    headers={"Authorization": "Bearer token123"},
    event_type="update",
    debug=True
)

# Connect to the server
await transport.connect("api.example.com", 443)

# Send a message (uses HTTP POST)
message = {"type": "subscription", "channel": "alerts"}
await transport.send_message(message)

# Receive SSE events
while True:
    event = await transport.receive_message()
    if event:
        print(f"Received event: {event}")

# Disconnect when done
await transport.disconnect()
```

## Selecting a Transport

When choosing a transport implementation, consider the following factors:

1. **Environment constraints**: Firewall rules, proxies, and network limitations
2. **Real-time requirements**: How time-sensitive is your application?
3. **Bandwidth efficiency**: Binary for efficiency, JSON for readability
4. **Communication pattern**: One-way vs bidirectional communication
5. **Error handling requirements**: Reconnection strategies, message delivery guarantees
6. **Debugging needs**: Readability vs performance

### Transport Selection Guide

| Transport | Best For | Limitations |
|-----------|----------|-------------|
| **Binary** | High-performance, low-latency systems | Less human-readable |
| **Newline** | Debugging, simple integrations | Less efficient encoding |
| **HTTP** | RESTful APIs, compatibility with firewalls | Higher latency, more overhead |
| **WebSocket** | Real-time bidirectional communication | May be blocked by some proxies |
| **SSE** | Server-to-client streaming, notifications | One-way (server to client) only |

## Implementation Notes

All transport implementations follow these best practices:

1. **Error handling**: Robust error detection and recovery
2. **Reconnection**: Automatic reconnection with backoff
3. **Timeouts**: Configurable timeouts for all operations
4. **Logging**: Detailed logging for debugging
5. **Resource cleanup**: Proper cleanup of resources on disconnect
6. **Type annotations**: Full type annotations for IDE support
7. **Async/await**: Fully asynchronous implementation for efficient I/O

# MCP-PyPI Transport Options

This document explains the different transport options available in the MCP-PyPI server and how to use them effectively.

## Available Transports

The MCP-PyPI server supports four transport protocols:

1. **HTTP Transport**
2. **WebSocket Transport**
3. **Server-Sent Events (SSE) Transport**
4. **STDIO Transport**

Each transport has its own characteristics, advantages, and use cases.

## HTTP Transport

The HTTP transport is the simplest and most widely supported option. It uses standard HTTP requests and responses for communication.

### Features:
- **Stateless**: Each request-response pair is independent
- **Firewall-friendly**: Works through most firewalls and proxies
- **Widely supported**: Can be used with almost any HTTP client library

### Configuration:
```bash
python run_mcp_server.py --transport http --host 127.0.0.1 --port 8143
```

### Implementation Details:
The HTTP transport is implemented in `utils/transports/http.py` and provides a simple HTTP server for handling JSON-RPC requests. The server uses `aiohttp` for asynchronous HTTP processing.

### Best Practices:
- Use for simple, request-response style interactions
- Set appropriate timeouts for long-running operations
- Consider adding authentication for production deployments

## WebSocket Transport

WebSocket provides a persistent, bidirectional connection between the client and server, allowing for real-time communication.

### Features:
- **Bidirectional**: Both client and server can send messages at any time
- **Persistent connection**: Eliminates connection setup overhead
- **Real-time**: Low-latency communication

### Configuration:
```bash
python run_mcp_server.py --transport ws --host 127.0.0.1 --port 8144
```

### Implementation Details:
The WebSocket transport is implemented in `utils/transports/websocket.py` and provides a WebSocket server for handling JSON-RPC messages. The server uses `websockets` or `aiohttp` for WebSocket processing.

### Best Practices:
- Implement reconnection logic in clients
- Handle WebSocket-specific events (connect, disconnect, error)
- Add heartbeat mechanism for long-lived connections

## Server-Sent Events (SSE) Transport

SSE is a server push technology that allows the server to send updates to the client over a single HTTP connection.

### Features:
- **Server push**: Server can send messages without client request
- **Simple**: Uses standard HTTP
- **Automatic reconnection**: Browsers handle reconnection automatically

### Configuration:
```bash
python run_mcp_server.py --transport sse --host 127.0.0.1 --port 8143
```

### Implementation Details:
The SSE transport is implemented in `utils/transports/sse.py` and provides an SSE server for sending JSON-RPC messages to clients. The server uses `aiohttp` for HTTP and SSE processing.

### Best Practices:
- Use for applications that need real-time updates from the server
- Understand that SSE is unidirectional (server to client only)
- Combine with standard HTTP requests for client-to-server communication

## STDIO Transport

The STDIO transport uses standard input and output streams for communication, making it ideal for integration with command-line tools and other applications.

### Features:
- **Integration-friendly**: Easy to integrate with other applications
- **Process-based**: Communicates between parent and child processes
- **Low overhead**: Minimal processing overhead

### Configuration:
```bash
python run_mcp_server.py --transport stdio
```

### Implementation Details:
The STDIO transport is implemented in `utils/transports/stdio.py` and uses system standard input and output for communication. It supports both direct STDIO mode and subprocess mode.

### Best Practices:
- Use for integration with command-line tools and MCP clients
- Handle signal interruptions properly
- Ensure proper encoding and buffering of input/output

## Using Multiple Transports

The MCP-PyPI server can run multiple transports simultaneously, allowing clients to connect through their preferred transport method.

### Configuration:
```bash
python run_mcp_server.py --transport all --host 0.0.0.0 --port 8143
```

This will start the HTTP and SSE transports on port 8143, and the WebSocket transport on port 8144.

## Transport Selection Guide

| Transport | Use When | Avoid When |
|-----------|----------|------------|
| HTTP      | - You need simple request-response<br>- Maximum compatibility is needed<br>- Working with stateless operations | - You need real-time updates<br>- Connection overhead is a concern |
| WebSocket | - You need bidirectional communication<br>- Real-time updates are required<br>- Low latency is important | - Working through restrictive firewalls<br>- Implementing complex clients |
| SSE       | - Server needs to push updates<br>- Client is a web browser<br>- Simple implementation is desired | - Client needs to send frequent messages<br>- Full bidirectional communication is needed |
| STDIO     | - Integrating with MCP clients<br>- Working with command-line tools<br>- Running as a child process | - Networking is required<br>- Multiple clients need to connect |

## Advanced Transport Configuration

### Custom SSL/TLS Configuration

For HTTP, WebSocket, and SSE transports, you can configure SSL/TLS for secure communication:

```python
import ssl

# Create SSL context
ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
ssl_context.load_cert_chain('server.crt', 'server.key')

# Use with HTTP transport
http_transport = HTTPTransport(
    base_url="https://127.0.0.1:8143",
    server_mode=True,
    host="127.0.0.1",
    port=8143,
    ssl_context=ssl_context
)

# Use with WebSocket transport
ws_transport = WebSocketTransport(
    url="wss://127.0.0.1:8144",
    server_mode=True,
    host="127.0.0.1",
    port=8144,
    ssl_context=ssl_context
)

# Use with SSE transport
sse_transport = SSETransport(
    url="https://127.0.0.1:8143/sse",
    server_mode=True,
    host="127.0.0.1",
    port=8143,
    ssl_context=ssl_context
)
```

### Timeout Configuration

You can configure timeouts for the various transports:

```python
# HTTP transport with custom timeout
http_transport = HTTPTransport(
    base_url="http://127.0.0.1:8143",
    timeout=30.0,  # 30 seconds
    polling_interval=0.5  # Check for responses every 0.5 seconds
)

# WebSocket transport with custom timeout
ws_transport = WebSocketTransport(
    url="ws://127.0.0.1:8144",
    timeout=60.0  # 60 seconds
)
```

### Subprocess Configuration for STDIO Transport

The STDIO transport can be used to communicate with a subprocess:

```python
# STDIO transport with subprocess
stdio_transport = STDIOTransport(
    command=["python", "-m", "some_script.py"],
    working_dir="/path/to/directory",
    env={"PYTHONPATH": "/custom/path"}
)
```

## Troubleshooting

### Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| Connection refused | Check the host and port configuration, and ensure the server is running |
| Protocol version negotiation failed | Use a compatible protocol version in the client initialization |
| Timeout during operation | Increase the timeout configuration for the transport |
| CORS errors with browser clients | Configure proper CORS headers on the server |
| WebSocket connection closed unexpectedly | Implement reconnection logic in the client |

### Debugging Transport Issues

To enable detailed logging for transport debugging:

```bash
python run_mcp_server.py --transport http --debug
```

This will output detailed logs about the transport operations, including incoming and outgoing messages. 