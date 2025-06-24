"""Tests for the MCP server implementation."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import GetPromptResult, Resource

from mcp_pypi.core.models import PyPIClientConfig
from mcp_pypi.server import PyPIMCPServer


@pytest.fixture
def mock_pypi_client():
    """Create a mock PyPI client."""
    with patch("mcp_pypi.server.PyPIClient", autospec=True) as mock:
        client_instance = mock.return_value
        client_instance.get_package_info = AsyncMock()
        client_instance.get_latest_version = AsyncMock()
        client_instance.get_package_releases = AsyncMock()
        client_instance.get_dependencies = AsyncMock()
        client_instance.check_package_exists = AsyncMock()
        client_instance.get_package_metadata = AsyncMock()
        client_instance.get_newest_packages = AsyncMock()
        client_instance.get_latest_updates = AsyncMock()
        client_instance.search_packages = AsyncMock()
        client_instance.get_dependency_tree = AsyncMock()
        client_instance.check_requirements_file = AsyncMock()
        client_instance.compare_versions = AsyncMock()
        client_instance.get_project_releases = AsyncMock()
        client_instance.get_package_stats = AsyncMock()
        client_instance.close = AsyncMock()
        yield client_instance


@pytest.fixture
def mock_fastmcp():
    """Create a mock FastMCP server."""
    with patch("mcp_pypi.server.FastMCP", autospec=True) as mock:
        mcp_instance = mock.return_value
        mcp_instance.tool = MagicMock()
        mcp_instance.resource = MagicMock()
        mcp_instance.prompt = MagicMock()
        mcp_instance.start = AsyncMock()
        mcp_instance.run_io = AsyncMock()
        yield mcp_instance


@pytest.mark.asyncio
async def test_pypi_mcp_server_init(mock_pypi_client, mock_fastmcp):
    """Test PyPIMCPServer initialization."""
    server = PyPIMCPServer()

    # Check that FastMCP was initialized with correct name
    from mcp_pypi.server import FastMCP

    FastMCP.assert_called_once_with("PyPI MCP Server")


@pytest.mark.asyncio
async def test_register_tools(mock_pypi_client, mock_fastmcp):
    """Test that tools are registered."""
    server = PyPIMCPServer()

    # Verify the decorator was called for each tool
    assert mock_fastmcp.tool.call_count > 0


@pytest.mark.asyncio
async def test_register_resources(mock_pypi_client, mock_fastmcp):
    """Test that resources are registered."""
    server = PyPIMCPServer()

    # Verify the decorator was called for each resource
    assert mock_fastmcp.resource.call_count > 0


@pytest.mark.asyncio
async def test_register_prompts(mock_pypi_client, mock_fastmcp):
    """Test that prompts are registered."""
    server = PyPIMCPServer()

    # Verify the decorator was called for each prompt
    assert mock_fastmcp.prompt.call_count > 0


@pytest.mark.asyncio
async def test_http_server(mock_pypi_client, mock_fastmcp):
    """Test starting the HTTP server."""
    server = PyPIMCPServer()

    # Call the start_http_server method
    await server.start_http_server(host="localhost", port=8000)

    # Verify that FastMCP.start was called with the correct arguments
    mock_fastmcp.start.assert_called_once_with(host="localhost", port=8000)

    # Verify that client.close was called
    mock_pypi_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_stdin_server(mock_pypi_client, mock_fastmcp):
    """Test stdin processing."""
    with patch("mcp_pypi.server.stdio_server") as mock_stdio:
        # Mock the context manager
        mock_stdio.return_value.__aenter__.return_value = (MagicMock(), MagicMock())

        server = PyPIMCPServer()

        # Call the process_stdin method
        await server.process_stdin()

        # Verify that FastMCP.run_io was called
        mock_fastmcp.run_io.assert_called_once()

        # Verify that client.close was called
        mock_pypi_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_get_fastmcp_app(mock_pypi_client, mock_fastmcp):
    """Test getting the FastMCP app."""
    server = PyPIMCPServer()

    # Call the get_fastmcp_app method
    app = server.get_fastmcp_app()

    # Verify that the FastMCP instance is returned
    assert app == mock_fastmcp


@pytest.mark.asyncio
async def test_tool_execution(mock_pypi_client):
    """Test tool execution through the MCP server."""
    # Mock the FastMCP tool decorator to capture the registered function
    tool_func = None

    def mock_tool_decorator():
        def decorator(func):
            nonlocal tool_func
            tool_func = func
            return func

        return decorator

    with patch("mcp_pypi.server.FastMCP", autospec=True) as mock_fastmcp:
        # Setup the tool decorator to capture the function
        mock_instance = mock_fastmcp.return_value
        mock_instance.tool = mock_tool_decorator

        # Set up mock response for get_package_info
        mock_pypi_client.get_package_info.return_value = {
            "name": "test-package",
            "version": "1.0.0",
        }

        # Create the server to register the tools
        server = PyPIMCPServer()

        # Execute the captured tool function
        if tool_func:
            result = await tool_func("test-package")

            # Verify that the client method was called
            mock_pypi_client.get_package_info.assert_called_once_with("test-package")

            # Verify the result
            assert result == {"name": "test-package", "version": "1.0.0"}
