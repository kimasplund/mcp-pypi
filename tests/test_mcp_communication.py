#!/usr/bin/env python3
"""
Test suite for MCP communication functionality.
Tests interaction with MCP servers using both live and mock servers.
"""

import asyncio
import json
import logging
import os
import pytest
from pathlib import Path

# Import test utilities
from utils.test_helpers import (
    run_test_with_mock_server,
    MockMCPServer,
    TestServerRunner,
)
from utils.mcp_monitor import MCPMonitor

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("MCP_DEBUG") == "1" else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Test configuration (can be overridden with environment variables)
MCP_HOST = os.environ.get("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.environ.get("MCP_PORT", "5004"))
USE_MOCK = os.environ.get("MCP_USE_MOCK", "1") == "1"

# Create a logger for the tests
logger = logging.getLogger(__name__)


@pytest.fixture
async def mcp_monitor():
    """
    Fixture for MCPMonitor with automatic setup and teardown.
    Connects to an MCP server before running tests and disconnects afterward.
    """
    monitor = MCPMonitor(MCP_HOST, MCP_PORT)
    await monitor.connect()
    yield monitor
    await monitor.disconnect()


@pytest.fixture
async def mock_server():
    """Fixture to provide a running mock MCP server"""
    if not USE_MOCK:
        pytest.skip("Mock server tests disabled")

    server = MockMCPServer()
    port = await server.start()
    yield server
    await server.stop()


# Tests using the mock server
@pytest.mark.asyncio
async def test_connect_to_mock():
    """Test connecting to a mock server"""

    async def test_func(server_port):
        monitor = MCPMonitor("127.0.0.1", server_port)
        connected = await monitor.connect()
        assert connected, "Failed to connect to mock server"

        info = await monitor.initialize()
        assert info, "Failed to get server info"
        assert "server_info" in info, "Server info missing"
        assert "server_version" in info["server_info"], "Server info missing version"

        await monitor.disconnect()
        return True

    result = await run_test_with_mock_server(test_func)
    assert result, "Test with mock server failed"


@pytest.mark.asyncio
async def test_list_tools_from_mock():
    """Test listing tools from a mock server"""

    async def test_func(server_port):
        monitor = MCPMonitor("127.0.0.1", server_port)
        await monitor.connect()
        await monitor.initialize()

        tools = await monitor.list_tools()
        assert tools, "Failed to get tools"
        assert len(tools) > 0, "No tools returned"
        assert any(
            tool["name"] == "test.echo" for tool in tools
        ), "Expected tool not found"

        await monitor.disconnect()
        return True

    result = await run_test_with_mock_server(test_func)
    assert result, "Test with mock server failed"


@pytest.mark.asyncio
async def test_invoke_tool_on_mock():
    """Test invoking a tool on a mock server"""

    async def test_func(server_port):
        monitor = MCPMonitor("127.0.0.1", server_port)
        await monitor.connect()
        await monitor.initialize()

        # Invoke the echo tool
        test_message = "Hello, MCP!"
        result = await monitor.invoke_tool("test.echo", {"message": test_message})
        assert result, "Failed to invoke tool"
        assert "message" in result, "Response missing expected field"
        assert result["message"] == test_message, "Echo response doesn't match input"

        await monitor.disconnect()
        return True

    result = await run_test_with_mock_server(test_func)
    assert result, "Test with mock server failed"


@pytest.mark.asyncio
async def test_error_handling_mock():
    """Test error handling on a mock server"""

    async def test_func(server_port):
        monitor = MCPMonitor("127.0.0.1", server_port)
        await monitor.connect()
        await monitor.initialize()

        # Try to invoke a non-existent tool
        try:
            result = await monitor.invoke_tool("nonexistent.tool", {})
            assert False, "Should have raised an exception for non-existent tool"
        except Exception as e:
            # Expected error
            assert "Tool not found" in str(e), "Unexpected error message"

        await monitor.disconnect()
        return True

    result = await run_test_with_mock_server(test_func)
    assert result, "Test with mock server failed"


# Tests using a real MCP server if available
@pytest.mark.asyncio
async def test_connection(mcp_monitor):
    """Test basic connection to the MCP server"""
    assert mcp_monitor.connected, "Not connected to MCP server"


@pytest.mark.asyncio
async def test_initialization(mcp_monitor):
    """Test initialization of the MCP connection"""
    info = await mcp_monitor.initialize()
    assert info, "Failed to get server info"
    assert "server_info" in info, "Missing server_info in response"
    assert "server_version" in info["server_info"], "Server info missing version"
    assert (
        "protocol_version" in info["server_info"]
    ), "Server info missing protocol version"


@pytest.mark.asyncio
async def test_list_tools(mcp_monitor):
    """Test listing tools from the MCP server"""
    await mcp_monitor.initialize()
    tools = await mcp_monitor.list_tools()
    assert tools, "Failed to get tools"
    assert isinstance(tools, list), "Tools should be a list"

    # Log available tools for debugging
    logger.info(f"Available tools: {[tool['name'] for tool in tools]}")

    # Verify tool structure
    if tools:
        tool = tools[0]
        assert "name" in tool, "Tool missing name"
        assert "description" in tool, "Tool missing description"


@pytest.mark.asyncio
async def test_list_resources(mcp_monitor):
    """Test listing resources from the MCP server"""
    await mcp_monitor.initialize()
    resources = await mcp_monitor.list_resources()

    # Resources might be empty on some servers, so we just check the type
    assert isinstance(resources, list), "Resources should be a list"

    # Log available resources for debugging
    logger.info(f"Available resources: {[res['name'] for res in resources]}")


@pytest.mark.asyncio
async def test_full_communication_flow(mcp_monitor):
    """Test complete communication flow with the MCP server"""
    # Initialize
    info = await mcp_monitor.initialize()
    assert info, "Failed to initialize"

    # List tools
    tools = await mcp_monitor.list_tools()
    assert isinstance(tools, list), "Tools should be a list"

    # Find a simple tool to test if available
    test_tool = None
    for tool in tools:
        if "echo" in tool["name"].lower() or "ping" in tool["name"].lower():
            test_tool = tool
            break

    # If we found a simple tool, try to invoke it
    if test_tool:
        logger.info(f"Testing tool invocation with: {test_tool['name']}")

        # Prepare parameters
        params = {}

        # Handle different parameter requirements
        if "parameters" in test_tool and "properties" in test_tool["parameters"]:
            for param_name, param_info in test_tool["parameters"]["properties"].items():
                # For string parameters, provide a test value
                if param_info.get("type") == "string":
                    params[param_name] = f"Test value for {param_name}"
                # For numeric parameters, provide a test value
                elif param_info.get("type") in ["number", "integer"]:
                    params[param_name] = 42
                # For boolean parameters, provide true
                elif param_info.get("type") == "boolean":
                    params[param_name] = True

        # Invoke the tool
        result = await mcp_monitor.invoke_tool(test_tool["name"], params)
        assert result is not None, f"Failed to invoke tool {test_tool['name']}"
        logger.info(f"Tool result: {result}")
    else:
        logger.warning("No suitable test tool found for invocation test")


@pytest.mark.asyncio
async def test_error_handling(mcp_monitor):
    """Test error handling by attempting to invoke a non-existent tool"""
    await mcp_monitor.initialize()

    # Try to invoke a tool that doesn't exist
    try:
        result = await mcp_monitor.invoke_tool("nonexistent.tool", {})
        assert False, "Should have raised an exception for non-existent tool"
    except Exception as e:
        # We expect an exception for a non-existent tool
        logger.info(f"Expected error received: {str(e)}")
        assert (
            "not found" in str(e).lower() or "invalid" in str(e).lower()
        ), "Unexpected error message"


if __name__ == "__main__":
    import sys

    # When run directly, use pytest to execute the tests
    sys.exit(pytest.main(["-xvs", __file__]))
