# MCP Monitor

## Overview

The MCPMonitor is a utility for monitoring and debugging Model Context Protocol (MCP) communication between clients and servers. It provides a flexible interface for inspecting messages, testing connections, and diagnosing issues in MCP implementations.

## Features

- Connect to MCP servers using multiple transport types
- Send and receive MCP messages with detailed logging
- Perform client initialization and authentication
- List available tools and resources
- Invoke MCP tools for testing
- Support for both newline-delimited and binary length-prefixed message formats
- Auto-detection of message format
- Detailed error reporting and debugging

## Installation

The MCPMonitor is included in the MCP PyPI client package:

```bash
pip install mcp-pypi
```

## Usage Examples

### Basic Monitoring

```python
import asyncio
from mcp_pypi.utils.mcp_monitor import MCPMonitor

async def main():
    # Create monitor instance
    monitor = MCPMonitor(
        server_host="api.example.com",
        server_port=9000,
        debug=True
    )
    
    # Connect to server
    connected = await monitor.connect()
    if not connected:
        print("Failed to connect to server")
        return
    
    try:
        # Initialize connection
        initialized = await monitor.initialize("my-client-id")
        if not initialized:
            print("Failed to initialize client")
            return
        
        # List available tools
        tools = await monitor.list_tools()
        print(f"Available tools: {tools}")
        
        # Send a custom message
        message = {
            "type": "request",
            "method": "get_status",
            "params": {}
        }
        await monitor.send_message(message)
        
        # Receive response
        response = await monitor.receive_message()
        print(f"Response: {response}")
        
    finally:
        # Disconnect
        await monitor.disconnect()

asyncio.run(main())
```

### Using Different Transport Types

```python
from mcp_pypi.utils.mcp_monitor import MCPMonitor

# WebSocket transport
ws_monitor = MCPMonitor(
    server_host="ws.example.com",
    server_port=443,
    transport_type="websocket",
    transport_options={
        "headers": {"Authorization": "Bearer token123"},
        "ping_interval": 15.0
    },
    debug=True
)

# HTTP transport with long-polling
http_monitor = MCPMonitor(
    server_host="api.example.com",
    server_port=443,
    transport_type="http",
    transport_options={
        "base_url": "https://api.example.com/mcp",
        "long_polling": True,
        "polling_interval": 5.0
    },
    debug=True
)

# SSE transport
sse_monitor = MCPMonitor(
    server_host="events.example.com",
    server_port=443,
    transport_type="sse",
    transport_options={
        "event_filter": "package_update"
    },
    debug=True
)
```

### Tool Invocation

```python
import asyncio
from mcp_pypi.utils.mcp_monitor import MCPMonitor

async def test_tool_invocation():
    monitor = MCPMonitor(
        server_host="api.example.com",
        server_port=9000,
        debug=True
    )
    
    await monitor.connect()
    await monitor.initialize("test-client")
    
    # List available tools
    tools = await monitor.list_tools()
    
    # Find a specific tool
    package_info_tool = next((t for t in tools if t.get("name") == "get_package_info"), None)
    
    if package_info_tool:
        # Invoke the tool
        result = await monitor.invoke_tool(
            tool_name="get_package_info",
            parameters={"package_name": "requests"}
        )
        print(f"Tool result: {result}")
    
    await monitor.disconnect()

asyncio.run(test_tool_invocation())
```

### Resource Management

```python
import asyncio
from mcp_pypi.utils.mcp_monitor import MCPMonitor

async def test_resource_management():
    monitor = MCPMonitor(
        server_host="api.example.com",
        server_port=9000,
        debug=True
    )
    
    await monitor.connect()
    await monitor.initialize("test-client")
    
    # List available resources
    resources = await monitor.list_resources()
    print(f"Available resources: {resources}")
    
    # List resource templates
    templates = await monitor.list_resource_templates()
    print(f"Resource templates: {templates}")
    
    # Get a specific resource
    resource = await monitor.get_resource("package_info", {"name": "requests"})
    print(f"Resource content: {resource}")
    
    await monitor.disconnect()

asyncio.run(test_resource_management())
```

## API Reference

### Constructor

```python
MCPMonitor(
    server_host: str,
    server_port: int,
    transport_type: str = "auto",
    transport_options: Optional[Dict[str, Any]] = None,
    message_format: str = "auto",
    debug: bool = False
)
```

**Parameters:**

- `server_host` - Hostname or IP address of the MCP server
- `server_port` - Port number of the MCP server
- `transport_type` - Transport type to use ("binary", "newline", "http", "websocket", "sse", or "auto")
- `transport_options` - Additional options for the transport
- `message_format` - Message format to use ("binary", "newline", or "auto")
- `debug` - Enable debug logging

### Methods

#### `connect()`

Connects to the MCP server.

```python
async def connect() -> bool
```

**Returns:** Boolean indicating success

#### `disconnect()`

Disconnects from the MCP server.

```python
async def disconnect() -> bool
```

**Returns:** Boolean indicating success

#### `send_message(message)`

Sends a message to the MCP server.

```python
async def send_message(message: Dict[str, Any]) -> bool
```

**Parameters:**
- `message` - Dictionary containing the message to send

**Returns:** Boolean indicating success

#### `receive_message()`

Receives a message from the MCP server.

```python
async def receive_message() -> Optional[Dict[str, Any]]
```

**Returns:** Received message as a dictionary, or None if no message received

#### `initialize(client_id, client_version=None)`

Initializes the MCP client.

```python
async def initialize(
    client_id: str,
    client_version: Optional[str] = None
) -> bool
```

**Parameters:**
- `client_id` - Client identifier
- `client_version` - Client version (optional)

**Returns:** Boolean indicating success

#### `list_tools()`

Lists available tools on the MCP server.

```python
async def list_tools() -> List[Dict[str, Any]]
```

**Returns:** List of available tools

#### `list_resources()`

Lists available resources on the MCP server.

```python
async def list_resources() -> List[Dict[str, Any]]
```

**Returns:** List of available resources

#### `list_resource_templates()`

Lists available resource templates on the MCP server.

```python
async def list_resource_templates() -> List[Dict[str, Any]]
```

**Returns:** List of available resource templates

#### `invoke_tool(tool_name, parameters)`

Invokes a tool on the MCP server.

```python
async def invoke_tool(
    tool_name: str,
    parameters: Dict[str, Any]
) -> Optional[Dict[str, Any]]
```

**Parameters:**
- `tool_name` - Name of the tool to invoke
- `parameters` - Parameters for the tool invocation

**Returns:** Tool result as a dictionary, or None if invocation failed

#### `get_resource(resource_name, parameters)`

Gets a resource from the MCP server.

```python
async def get_resource(
    resource_name: str,
    parameters: Dict[str, Any]
) -> Optional[Dict[str, Any]]
```

**Parameters:**
- `resource_name` - Name of the resource to get
- `parameters` - Parameters for the resource request

**Returns:** Resource content as a dictionary, or None if request failed

## Message Formats

The MCPMonitor supports two message formats:

### Binary Format

The binary format uses a length-prefixed protocol with a 4-byte unsigned integer (big-endian) prefix followed by the JSON-encoded message.

### Newline Format

The newline format uses JSON-encoded messages separated by newline characters (`\n`).

### Auto-detection

When `message_format` is set to "auto", the monitor will attempt to determine the format based on the first byte received:
- If the first byte is `{` (ASCII 123), it will use the newline format
- Otherwise, it will use the binary format

## Troubleshooting

### Common Issues

1. **Connection Refused**: Check if the server is running and the host/port are correct.
2. **Timeout**: Increase the timeout value in transport options.
3. **Authentication Failure**: Verify client ID and credentials.
4. **Message Format Mismatch**: Explicitly set the message format instead of using auto-detection.
5. **Transport Error**: Try a different transport type.

### Debugging

Enable debug mode to see detailed logs:

```python
monitor = MCPMonitor(
    server_host="api.example.com",
    server_port=9000,
    debug=True  # Enable debug logging
)
```

## Advanced Usage

### Custom Message Handling

```python
import asyncio
from mcp_pypi.utils.mcp_monitor import MCPMonitor

async def custom_message_handler():
    monitor = MCPMonitor(
        server_host="api.example.com",
        server_port=9000,
        debug=True
    )
    
    await monitor.connect()
    
    try:
        # Custom protocol sequence
        await monitor.send_message({"type": "handshake", "version": "1.0"})
        handshake_response = await monitor.receive_message()
        
        if handshake_response and handshake_response.get("status") == "ok":
            session_id = handshake_response.get("session_id")
            
            await monitor.send_message({
                "type": "authenticate",
                "session_id": session_id,
                "credentials": {
                    "api_key": "your-api-key"
                }
            })
            
            auth_response = await monitor.receive_message()
            if auth_response and auth_response.get("status") == "authenticated":
                print("Authentication successful")
                
                # Continue with application logic
                await monitor.send_message({
                    "type": "subscribe",
                    "channels": ["updates", "alerts"]
                })
                
                # Process incoming messages
                while True:
                    message = await monitor.receive_message()
                    if not message:
                        break
                    
                    message_type = message.get("type")
                    if message_type == "update":
                        print(f"Update received: {message.get('data')}")
                    elif message_type == "alert":
                        print(f"Alert received: {message.get('data')}")
            else:
                print("Authentication failed")
        else:
            print("Handshake failed")
    
    finally:
        await monitor.disconnect()

asyncio.run(custom_message_handler())
```

### Extending MCPMonitor

You can extend the MCPMonitor class to add custom functionality:

```python
from mcp_pypi.utils.mcp_monitor import MCPMonitor
from typing import Dict, Any, Optional, List

class EnhancedMCPMonitor(MCPMonitor):
    def __init__(self, *args, **kwargs):
        self.message_history = []
        self.max_history = kwargs.pop("max_history", 100)
        super().__init__(*args, **kwargs)
    
    async def send_message(self, message: Dict[str, Any]) -> bool:
        # Record message in history
        self.message_history.append({"direction": "outgoing", "message": message})
        if len(self.message_history) > self.max_history:
            self.message_history.pop(0)
        
        return await super().send_message(message)
    
    async def receive_message(self) -> Optional[Dict[str, Any]]:
        message = await super().receive_message()
        
        if message:
            # Record message in history
            self.message_history.append({"direction": "incoming", "message": message})
            if len(self.message_history) > self.max_history:
                self.message_history.pop(0)
        
        return message
    
    def get_message_history(self) -> List[Dict[str, Any]]:
        """Get the message history."""
        return self.message_history
    
    async def replay_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Replay a sequence of messages."""
        for message_entry in messages:
            if message_entry["direction"] == "outgoing":
                await self.send_message(message_entry["message"])
```

## Integration with Testing Frameworks

### Pytest Example

```python
import pytest
import asyncio
from mcp_pypi.utils.mcp_monitor import MCPMonitor

@pytest.fixture
async def mcp_monitor():
    monitor = MCPMonitor(
        server_host="localhost",
        server_port=9000,
        debug=True
    )
    
    connected = await monitor.connect()
    assert connected, "Failed to connect to MCP server"
    
    yield monitor
    
    await monitor.disconnect()

@pytest.mark.asyncio
async def test_tool_invocation(mcp_monitor):
    # Initialize client
    initialized = await mcp_monitor.initialize("test-client")
    assert initialized, "Failed to initialize client"
    
    # Invoke tool
    result = await mcp_monitor.invoke_tool(
        tool_name="get_package_info",
        parameters={"package_name": "requests"}
    )
    
    assert result is not None
    assert "name" in result
    assert result["name"] == "requests"
```

## Conclusion

The MCPMonitor utility provides a comprehensive toolkit for working with MCP servers, troubleshooting communication issues, and testing MCP applications. Its flexible design supports multiple transport types and message formats, making it adaptable to various MCP implementations and use cases. 