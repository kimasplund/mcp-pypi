#!/usr/bin/env python3
"""Test with mocked server responses for faster testing."""

import json
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import patch, MagicMock
from mcp_pypi.cli.server import RPCServer

# Sample responses
PING_RESPONSE = {
    "jsonrpc": "2.0",
    "result": "pong",
    "id": 1
}
SCHEMA = {
    "name": "pypi-mcp",
    "version": "2.0.0",
    "description": "Modern Command-line PyPI Client Tools",
    "tools": [
        {
            "name": "get_package_info",
            "description": "Get information about a PyPI package",
            "parameters": {
                "type": "object",
                "properties": {
                    "package_name": {
                        "type": "string",
                        "description": "Name of the package to get information about"
                    }
                },
                "required": ["package_name"]
            }
        }
    ]
}
PACKAGE_INFO_RESULT = {
    "info": {
        "name": "pip",
        "version": "23.1.2",
        "summary": "The PyPA recommended tool for installing Python packages."
    }
}

@pytest.mark.asyncio
async def test_ping_request():
    """Test that the server responds to ping requests."""
    # Create a mock client
    mock_client = MagicMock()
    
    # Create the RPC server with our mock client
    server = RPCServer(mock_client)
    
    # Create a ping request
    ping_request = {
        "jsonrpc": "2.0",
        "method": "ping",
        "id": 1
    }
    
    # Call the handler
    response_json = await server.handle_request(json.dumps(ping_request))
    response = json.loads(response_json)
    
    # Verify the response
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert response["result"] == "pong"

@pytest.mark.asyncio
async def test_describe_request():
    """Test that the server responds to describe requests."""
    # Create a mock client
    mock_client = MagicMock()
    
    # Create the RPC server with our mock client
    server = RPCServer(mock_client)
    
    # Create a describe request
    describe_request = {
        "jsonrpc": "2.0",
        "method": "describe",
        "id": 2
    }
    
    # Mock the get_mcp_schema function
    with patch('mcp_pypi.cli.main.get_mcp_schema', return_value=SCHEMA):
        # Call the handler
        response_json = await server.handle_request(json.dumps(describe_request))
        response = json.loads(response_json)
        
        # Verify the response
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2
        assert "result" in response
        result = response["result"]
        assert "name" in result
        assert "version" in result
        assert "description" in result
        assert "tools" in result
        assert isinstance(result["tools"], list)
        assert len(result["tools"]) > 0

@pytest.mark.asyncio
async def test_package_info_request():
    """Test that the server can execute package info requests."""
    # Create a mock client with a mocked get_package_info method
    mock_client = MagicMock()
    # We'll patch the _dispatch_method directly instead of trying to mock async methods
    
    # Create the RPC server with our mock client
    server = RPCServer(mock_client)
    
    # Create an async mock for the _dispatch_method
    async def mock_dispatch(method, params):
        return PACKAGE_INFO_RESULT
    
    # Patch the dispatch method to return our test data
    with patch.object(server, '_dispatch_method', side_effect=mock_dispatch):
        # Create a get_package_info request
        execute_request = {
            "jsonrpc": "2.0",
            "method": "get_package_info",
            "params": {
                "package_name": "pip"
            },
            "id": 3
        }
        
        # Call the handler
        response_json = await server.handle_request(json.dumps(execute_request))
        response = json.loads(response_json)
        
        # Verify the response
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 3
        assert "result" in response
        result = response["result"]
        assert "info" in result
        assert result["info"]["name"] == "pip"

@pytest.mark.asyncio
async def test_invalid_request():
    """Test that the server handles invalid requests properly."""
    # Create a mock client
    mock_client = MagicMock()
    
    # Create the RPC server with our mock client
    server = RPCServer(mock_client)
    
    # Create an invalid request (missing jsonrpc field)
    invalid_request = {
        "method": "get_package_info",
        "params": {
            "package_name": "pip"
        },
        "id": 4
    }
    
    # Call the handler
    response_json = await server.handle_request(json.dumps(invalid_request))
    response = json.loads(response_json)
    
    # Verify the response contains an error
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 4
    assert "error" in response
    assert response["error"]["code"] == -32600  # Invalid Request

@pytest.mark.asyncio
async def test_unknown_method():
    """Test that the server handles unknown methods properly."""
    # Create a mock client
    mock_client = MagicMock()
    
    # Create the RPC server with our mock client
    server = RPCServer(mock_client)
    
    # Create a request with an unknown method
    unknown_method_request = {
        "jsonrpc": "2.0",
        "method": "unknown_method",
        "id": 5
    }
    
    # Call the handler
    response_json = await server.handle_request(json.dumps(unknown_method_request))
    response = json.loads(response_json)
    
    # Verify the response contains an error
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 5
    assert "error" in response

if __name__ == "__main__":
    pytest.main(["-v", __file__]) 