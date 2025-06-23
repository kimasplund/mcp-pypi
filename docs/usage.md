# MCP-PyPI Server Usage

This document provides detailed instructions on how to use the MCP-PyPI server with different transport protocols.

## Server Options

The MCP-PyPI server supports multiple transport protocols:

- **HTTP**: Standard HTTP transport for web-based clients
- **SSE (Server-Sent Events)**: For real-time streaming of events
- **WebSocket**: For bidirectional communication
- **STDIO**: For command-line tools and integration with other applications

### Starting the Server

You can start the server using the provided `run_mcp_server.py` script:

```bash
# Start with default HTTP transport
python run_mcp_server.py

# Start with WebSocket transport
python run_mcp_server.py --transport ws

# Start with SSE transport
python run_mcp_server.py --transport sse

# Start with STDIO transport (for integration with MCP clients)
python run_mcp_server.py --transport stdio

# Start all transports simultaneously
python run_mcp_server.py --transport all

# Specify host and port
python run_mcp_server.py --host 0.0.0.0 --port 8143

# Enable debug logging
python run_mcp_server.py --debug
```

## Server Configuration

The server is configured through the `.mcp.json` file, which defines server capabilities, transport options, and available tools. You can customize this file for your specific requirements.

## Client Usage

### Testing with Provided Client

The repository includes a test client (`test_mcp_client.py`) that you can use to test the server:

```bash
# Test with HTTP transport
python test_mcp_client.py

# Test with specific URL
python test_mcp_client.py --url http://127.0.0.1:8143

# Test with WebSocket transport
python test_mcp_client.py --url ws://127.0.0.1:8144

# Test with a different package
python test_mcp_client.py --package numpy

# Enable debug logging
python test_mcp_client.py --debug
```

### Client Implementation Example

Here's a simple example of how to implement a client for the MCP-PyPI server:

```python
import asyncio
import json
import logging
import aiohttp

async def test_pypi_mcp_server():
    # Connect to the server
    async with aiohttp.ClientSession() as session:
        # Initialize connection
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "1.1",
                "capabilities": ["invokeTool", "listTools"]
            }
        }
        
        async with session.post("http://127.0.0.1:8143", json=init_request) as response:
            init_result = await response.json()
            print(f"Initialization result: {json.dumps(init_result, indent=2)}")
            
            if "error" in init_result:
                print(f"Initialization failed: {init_result['error']}")
                return
        
        # List available tools
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "listTools",
            "params": {}
        }
        
        async with session.post("http://127.0.0.1:8143", json=tools_request) as response:
            tools_result = await response.json()
            tools = tools_result.get("result", {}).get("tools", [])
            print(f"Available tools: {len(tools)}")
            for tool in tools[:5]:  # Show first 5 tools
                print(f"  - {tool['name']}: {tool['description']}")
        
        # Invoke a tool
        invoke_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "invokeTool",
            "params": {
                "name": "get_latest_version",
                "parameters": {
                    "package_name": "requests"
                }
            }
        }
        
        async with session.post("http://127.0.0.1:8143", json=invoke_request) as response:
            invoke_result = await response.json()
            print(f"Tool result: {json.dumps(invoke_result, indent=2)}")

# Run the test
if __name__ == "__main__":
    asyncio.run(test_pypi_mcp_server())
```

## Available Tools

The MCP-PyPI server provides the following tools:

- `get_package_info`: Get detailed information about a Python package from PyPI
- `get_latest_version`: Get the latest version of a package from PyPI
- `get_dependency_tree`: Get the dependency tree for a package
- `search_packages`: Search for packages on PyPI
- `get_package_stats`: Get download statistics for a package
- `check_package_exists`: Check if a package exists on PyPI
- `get_package_metadata`: Get package metadata from PyPI
- `get_package_releases`: Get all releases of a package
- `get_project_releases`: Get project releases with timestamps
- `get_documentation_url`: Get documentation URL for a package
- `check_requirements_file`: Check a requirements file for outdated packages
- `compare_versions`: Compare two package versions
- `get_newest_packages`: Get newest packages on PyPI
- `get_latest_updates`: Get latest package updates on PyPI

## Prompt Templates

The server provides several prompt templates that can be used to generate prompts for LLM systems:

- `search_packages_prompt`: Create a prompt for searching packages
- `analyze_package_prompt`: Create a prompt for analyzing a package
- `compare_packages_prompt`: Create a prompt for comparing two packages

You can retrieve these prompts using the `getPrompt` method.

## Resources

The server also provides resource endpoints that can be accessed via the `getResource` method:

- `pypi://package/{package_name}`: Package information resource
- `pypi://stats/{package_name}`: Package statistics resource
- `pypi://dependencies/{package_name}`: Package dependencies resource

## Error Handling

The server uses standard JSON-RPC error codes for error responses. Here are some common error codes:

- `-32700`: Parse error
- `-32600`: Invalid request
- `-32601`: Method not found
- `-32602`: Invalid params
- `-32603`: Internal error
- `-32001`: Protocol version not supported

When handling errors, check for the presence of an `error` field in the response:

```python
if "error" in response:
    error = response["error"]
    print(f"Error: {error.get('message')} (code: {error.get('code')})")
    # Handle specific error codes
    if error.get("code") == -32001:
        # Protocol version error
        required_version = error.get("data", {}).get("requiredVersion")
        if required_version:
            print(f"Server requires protocol version: {required_version}")
```

## Advanced Usage

### Using WebSocket Transport

WebSocket provides a persistent connection for bidirectional communication:

```python
import asyncio
import json
import logging
import websockets

async def test_websocket():
    async with websockets.connect("ws://127.0.0.1:8144") as websocket:
        # Initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "1.1",
                "capabilities": ["invokeTool", "listTools"]
            }
        }
        
        await websocket.send(json.dumps(init_request))
        init_response = await websocket.recv()
        print(f"Initialization response: {init_response}")
        
        # List tools
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "listTools",
            "params": {}
        }
        
        await websocket.send(json.dumps(tools_request))
        tools_response = await websocket.recv()
        print(f"Tools response: {tools_response}")

# Run the test
if __name__ == "__main__":
    asyncio.run(test_websocket())
```

### Using SSE Transport

SSE transport is useful for receiving server-sent events:

```python
import asyncio
import json
import aiohttp

async def test_sse():
    # First, make a request to establish SSE connection
    async with aiohttp.ClientSession() as session:
        async with session.get("http://127.0.0.1:8143/sse") as sse_response:
            # Send a request over HTTP
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "1.1",
                    "capabilities": ["invokeTool", "listTools"]
                }
            }
            
            async with session.post("http://127.0.0.1:8143", json=init_request) as response:
                # The response will come through the SSE connection
                async for line in sse_response.content:
                    if line:
                        line = line.decode('utf-8').strip()
                        if line.startswith('data: '):
                            data = line[6:]  # Remove 'data: ' prefix
                            event_data = json.loads(data)
                            if event_data.get('id') == 1:
                                print(f"Received initialization response: {event_data}")
                                break

# Run the test
if __name__ == "__main__":
    asyncio.run(test_sse())
```

### Using STDIO Transport

STDIO transport is useful for integrating with MCP clients that use STDIO for communication:

```python
import asyncio
import json
import subprocess

async def test_stdio():
    # Start the server process
    process = await asyncio.create_subprocess_exec(
        "python", "run_mcp_server.py", "--transport", "stdio",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE
    )
    
    # Initialize
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "1.1",
            "capabilities": ["invokeTool", "listTools"]
        }
    }
    
    # Send the request
    process.stdin.write((json.dumps(init_request) + "\n").encode())
    await process.stdin.drain()
    
    # Read response
    response_line = await process.stdout.readline()
    response = json.loads(response_line)
    print(f"Initialization response: {response}")
    
    # Clean up
    process.terminate()
    await process.wait()

# Run the test
if __name__ == "__main__":
    asyncio.run(test_stdio())
```

## Integration with Other Applications

You can integrate the MCP-PyPI server with other applications by:

1. Using the STDIO transport for direct communication
2. Using the HTTP/WebSocket/SSE transport for network-based communication
3. Mounting the FastMCP app in another ASGI application

### Mounting in an ASGI Application

```python
from fastapi import FastAPI
from mcp_pypi.server import PyPIMCPServer

# Create the FastAPI app
app = FastAPI()

# Create the PyPI MCP server
pypi_server = PyPIMCPServer()

# Get the FastMCP app
fastmcp_app = pypi_server.get_fastmcp_app()

# Mount the FastMCP app
app.mount("/mcp", fastmcp_app)

# Add your own routes
@app.get("/")
async def root():
    return {"message": "Welcome to the PyPI API server"}
```

This will make the MCP server available at the `/mcp` endpoint of your ASGI application. 