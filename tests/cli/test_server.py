"""Tests for the RPC server implementation."""

import json
import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from mcp_pypi.cli.server import RPCServer
from mcp_pypi.core import PyPIClient

@pytest.fixture
def mock_client():
    """Create a mock PyPI client."""
    client = AsyncMock(spec=PyPIClient)
    client.get_package_info = AsyncMock()
    client.search_packages = AsyncMock()
    client.get_dependencies = AsyncMock()
    client.get_latest_version = AsyncMock()
    client.check_package_exists = AsyncMock()
    client.close = AsyncMock()
    return client

@pytest.fixture
def rpc_server(mock_client):
    """Create an RPC server instance with a mock client."""
    return RPCServer(client=mock_client)

@pytest.mark.asyncio
async def test_handle_request_invalid_json(rpc_server):
    """Test handling of invalid JSON requests."""
    response = await rpc_server.handle_request("invalid json")
    response_obj = json.loads(response)
    
    assert response_obj["jsonrpc"] == "2.0"
    assert "error" in response_obj
    assert response_obj["error"]["code"] == -32700
    assert "Parse error" in response_obj["error"]["message"]

@pytest.mark.asyncio
async def test_handle_request_invalid_rpc_format(rpc_server):
    """Test handling of requests with invalid RPC format."""
    # Missing jsonrpc version
    response = await rpc_server.handle_request('{"method": "get_package_info"}')
    response_obj = json.loads(response)
    
    assert "error" in response_obj
    assert response_obj["error"]["code"] == -32600
    
    # Missing method
    response = await rpc_server.handle_request('{"jsonrpc": "2.0", "id": 1}')
    response_obj = json.loads(response)
    
    assert "error" in response_obj
    assert response_obj["error"]["code"] == -32600

@pytest.mark.asyncio
async def test_ping_method(rpc_server):
    """Test the ping method."""
    request = {
        "jsonrpc": "2.0",
        "method": "ping",
        "id": 1
    }
    
    response = await rpc_server.handle_request(json.dumps(request))
    response_obj = json.loads(response)
    
    assert response_obj["jsonrpc"] == "2.0"
    assert response_obj["result"] == "pong"
    assert response_obj["id"] == 1

@pytest.mark.asyncio
async def test_describe_method(rpc_server):
    """Test the describe method."""
    with patch("mcp_pypi.cli.main.get_mcp_schema") as mock_schema:
        mock_schema.return_value = {"tools": [{"name": "test_tool"}]}
        
        request = {
            "jsonrpc": "2.0",
            "method": "describe",
            "id": 1
        }
        
        response = await rpc_server.handle_request(json.dumps(request))
        response_obj = json.loads(response)
        
        assert response_obj["jsonrpc"] == "2.0"
        assert "tools" in response_obj["result"]
        assert response_obj["id"] == 1
        mock_schema.assert_called_once()

@pytest.mark.asyncio
async def test_get_package_info_method(rpc_server, mock_client):
    """Test the get_package_info method."""
    mock_data = {
        "info": {
            "name": "test-package",
            "version": "1.0.0",
            "summary": "A test package"
        }
    }
    mock_client.get_package_info.return_value = mock_data
    
    request = {
        "jsonrpc": "2.0",
        "method": "get_package_info",
        "params": {"package_name": "test-package"},
        "id": 1
    }
    
    response = await rpc_server.handle_request(json.dumps(request))
    response_obj = json.loads(response)
    
    assert response_obj["jsonrpc"] == "2.0"
    assert response_obj["result"] == mock_data
    assert response_obj["id"] == 1
    mock_client.get_package_info.assert_called_once_with(package_name="test-package")

@pytest.mark.asyncio
async def test_unknown_method(rpc_server):
    """Test handling of unknown methods."""
    request = {
        "jsonrpc": "2.0",
        "method": "nonexistent_method",
        "id": 1
    }
    
    response = await rpc_server.handle_request(json.dumps(request))
    response_obj = json.loads(response)
    
    assert response_obj["jsonrpc"] == "2.0"
    assert "error" in response_obj
    assert response_obj["error"]["code"] == -32603  # Internal error
    # The message doesn't include the exact error text in the final response
    # as it's logged but not passed through to the client
    assert "Internal error" in response_obj["error"]["message"]
    assert response_obj["id"] == 1

@pytest.mark.asyncio
async def test_method_with_error_response(rpc_server, mock_client):
    """Test handling of methods that return error responses."""
    error_data = {
        "error": {
            "code": "not_found",
            "message": "Package not found"
        }
    }
    mock_client.get_package_info.return_value = error_data
    
    request = {
        "jsonrpc": "2.0",
        "method": "get_package_info",
        "params": {"package_name": "nonexistent-package"},
        "id": 1
    }
    
    response = await rpc_server.handle_request(json.dumps(request))
    response_obj = json.loads(response)
    
    assert response_obj["jsonrpc"] == "2.0"
    assert "error" in response_obj
    assert response_obj["error"]["code"] == -32001  # mapped from "not_found"
    assert "Package not found" in response_obj["error"]["message"]
    assert response_obj["id"] == 1

@pytest.mark.asyncio
async def test_list_params_handling(rpc_server, mock_client):
    """Test handling of list-style parameters."""
    mock_data = {"version": "1.0.0"}
    mock_client.get_latest_version.return_value = mock_data
    
    request = {
        "jsonrpc": "2.0",
        "method": "get_latest_version",
        "params": ["test-package"],  # List-style parameters
        "id": 1
    }
    
    response = await rpc_server.handle_request(json.dumps(request))
    response_obj = json.loads(response)
    
    assert response_obj["jsonrpc"] == "2.0"
    assert response_obj["result"] == mock_data
    assert response_obj["id"] == 1
    mock_client.get_latest_version.assert_called_once_with("test-package")

@pytest.mark.asyncio
async def test_no_params_handling(rpc_server, mock_client):
    """Test handling of no parameters."""
    # Setup mock for a method that doesn't require parameters
    mock_client.get_newest_packages.return_value = [{"name": "package1"}, {"name": "package2"}]
    
    request = {
        "jsonrpc": "2.0",
        "method": "get_newest_packages",
        "id": 1
    }
    
    response = await rpc_server.handle_request(json.dumps(request))
    response_obj = json.loads(response)
    
    assert response_obj["jsonrpc"] == "2.0"
    assert isinstance(response_obj["result"], list)
    assert response_obj["id"] == 1
    mock_client.get_newest_packages.assert_called_once()

@pytest.mark.asyncio
async def test_method_internal_exception(rpc_server, mock_client):
    """Test handling of internal exceptions in method execution."""
    mock_client.get_package_info.side_effect = Exception("Unexpected error")
    
    request = {
        "jsonrpc": "2.0",
        "method": "get_package_info",
        "params": {"package_name": "test-package"},
        "id": 1
    }
    
    response = await rpc_server.handle_request(json.dumps(request))
    response_obj = json.loads(response)
    
    assert response_obj["jsonrpc"] == "2.0"
    assert "error" in response_obj
    assert response_obj["error"]["code"] == -32603  # Internal error
    # The exception message doesn't get passed directly to the client
    assert "Internal error" in response_obj["error"]["message"]
    assert response_obj["id"] == 1

# Test the process_mcp_stdin function
@pytest.mark.asyncio
async def test_process_mcp_stdin():
    """Test processing MCP stdin protocol."""
    mock_client = AsyncMock(spec=PyPIClient)
    mock_server = MagicMock(spec=RPCServer)
    mock_server.handle_request = AsyncMock()
    mock_server.handle_request.return_value = '{"jsonrpc": "2.0", "result": "success", "id": 1}'
    
    with patch('mcp_pypi.cli.server.RPCServer', return_value=mock_server), \
         patch('mcp_pypi.cli.server.PyPIClient', return_value=mock_client), \
         patch('sys.stdin.readline') as mock_readline, \
         patch('builtins.print') as mock_print:
        
        # Set up the mock to return a request and then EOF
        mock_readline.side_effect = [
            '{"jsonrpc": "2.0", "method": "ping", "id": 1}',
            ''  # Empty string indicates EOF
        ]
        
        # Call the function to test
        from mcp_pypi.cli.server import process_mcp_stdin
        await process_mcp_stdin(verbose=True)
        
        # Verify expectations
        mock_server.handle_request.assert_called_once()
        mock_print.assert_called_once_with(
            '{"jsonrpc": "2.0", "result": "success", "id": 1}', 
            flush=True
        )
        mock_client.close.assert_called_once()

@pytest.mark.asyncio
async def test_start_server():
    """Test the HTTP server startup."""
    # Import the actual module to create proper mocks
    from mcp_pypi.cli.server import start_server
    import sys
    
    # Create our client mock
    mock_client = AsyncMock(spec=PyPIClient)
    
    # Create mocks for aiohttp.web components
    mock_app = MagicMock()
    mock_app.on_shutdown = []
    mock_app.router = MagicMock()
    mock_app.router.add_post = MagicMock()
    
    mock_runner = AsyncMock()
    mock_runner.setup = AsyncMock()
    
    mock_site = AsyncMock()
    mock_site.start = AsyncMock()
    
    # Create the web module mock
    mock_web = MagicMock()
    mock_web.Application.return_value = mock_app
    mock_web.AppRunner.return_value = mock_runner
    mock_web.TCPSite.return_value = mock_site
    mock_web.Response = MagicMock()
    
    # Set up patching
    with patch.dict('sys.modules', {'aiohttp.web': mock_web}), \
         patch('mcp_pypi.cli.server.PyPIClient', return_value=mock_client), \
         patch('socket.socket') as mock_socket:
        
        # Set up socket mock
        mock_sock_instance = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_sock_instance
        mock_sock_instance.connect_ex.return_value = 1  # Port is available
        
        # Run the server for a short time then cancel
        task = asyncio.create_task(start_server("localhost", 8000))
        await asyncio.sleep(0.1)  # Give it time to initialize
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    # Verify the expected setup sequence
    assert mock_app.router.add_post.call_count >= 1
    assert len(mock_app.on_shutdown) == 1
    mock_runner.setup.assert_awaited_once()
    mock_site.start.assert_awaited_once()
    
    # Test the shutdown handler
    shutdown_handler = mock_app.on_shutdown[0]
    await shutdown_handler(mock_app)
    mock_client.close.assert_awaited_once() 