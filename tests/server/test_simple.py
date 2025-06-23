"""
Basic tests for the MCP server implementation.
"""

import pytest
import sys
from unittest.mock import MagicMock, AsyncMock, patch

# Mock the mcp module since it's not installed
sys.modules["mcp"] = MagicMock()
sys.modules["mcp.server"] = MagicMock()
sys.modules["mcp.types"] = MagicMock()
sys.modules["mcp.server.fastmcp"] = MagicMock()
sys.modules["mcp.server.stdio"] = MagicMock()

# Now we can import our module
from mcp_pypi.server import PyPIMCPServer
from mcp_pypi.core.models import PyPIClientConfig


@pytest.fixture
def mock_client():
    """Create a mock PyPI client for testing."""
    client = AsyncMock()

    # Add necessary mock methods
    client.get_package_info = AsyncMock(return_value={"info": {"name": "test-package"}})
    client.get_latest_version = AsyncMock(return_value={"version": "1.0.0"})
    client.close = AsyncMock()

    return client


@pytest.fixture
def mock_mcp_server():
    """Create a mock FastMCP server instance."""
    server = MagicMock()
    server.tool = MagicMock(return_value=lambda func: func)
    server.resource = MagicMock(return_value=lambda func: func)
    server.prompt = MagicMock(return_value=lambda func: func)
    server.start = AsyncMock()

    return server


@patch("mcp_pypi.server.FastMCP")
def test_init(mock_fastmcp):
    """Test that the server initializes correctly."""
    # Setup the mock
    mock_fastmcp_instance = MagicMock()
    mock_fastmcp.return_value = mock_fastmcp_instance

    # Create the server
    config = PyPIClientConfig()
    server = PyPIMCPServer(config)

    # Verify
    assert server.config == config
    assert server.mcp_server == mock_fastmcp_instance
    mock_fastmcp.assert_called_once_with("PyPI MCP Server")


@patch("mcp_pypi.server.FastMCP")
@patch("mcp_pypi.core.PyPIClient")
def test_register_tools(mock_client_class, mock_fastmcp):
    """Test that tools are registered correctly."""
    # Setup mocks
    mock_client_instance = AsyncMock()
    mock_client_class.return_value = mock_client_instance

    mock_fastmcp_instance = MagicMock()
    mock_fastmcp.return_value = mock_fastmcp_instance
    mock_fastmcp_instance.tool = MagicMock(return_value=lambda func: func)

    # Create server
    server = PyPIMCPServer()

    # Verify tool registration
    assert mock_fastmcp_instance.tool.call_count > 0


@patch("mcp_pypi.server.FastMCP")
@patch("mcp_pypi.core.PyPIClient")
def test_register_resources(mock_client_class, mock_fastmcp):
    """Test that resources are registered correctly."""
    # Setup mocks
    mock_client_instance = AsyncMock()
    mock_client_class.return_value = mock_client_instance

    mock_fastmcp_instance = MagicMock()
    mock_fastmcp.return_value = mock_fastmcp_instance
    mock_fastmcp_instance.resource = MagicMock(return_value=lambda func: func)

    # Create server
    server = PyPIMCPServer()

    # Verify resource registration
    assert mock_fastmcp_instance.resource.call_count == 3  # We have 3 resources


@patch("mcp_pypi.server.FastMCP")
@patch("mcp_pypi.core.PyPIClient")
def test_register_prompts(mock_client_class, mock_fastmcp):
    """Test that prompts are registered correctly."""
    # Setup mocks
    mock_client_instance = AsyncMock()
    mock_client_class.return_value = mock_client_instance

    mock_fastmcp_instance = MagicMock()
    mock_fastmcp.return_value = mock_fastmcp_instance
    mock_fastmcp_instance.prompt = MagicMock(return_value=lambda func: func)

    # Create server
    server = PyPIMCPServer()

    # Verify prompt registration
    assert mock_fastmcp_instance.prompt.call_count == 3  # We have 3 prompts


@pytest.mark.asyncio
async def test_start_http_server():
    """Test that the HTTP server starts correctly."""
    # Create mocks directly
    mock_client = AsyncMock()
    mock_mcp_server = MagicMock()
    mock_mcp_server.start = AsyncMock()

    # Create server and manually set the mocks
    server = PyPIMCPServer()
    server.client = mock_client
    server.mcp_server = mock_mcp_server

    # Start the server
    await server.start_http_server()

    # Verify
    mock_mcp_server.start.assert_called_once()
    mock_client.close.assert_called_once()


@patch("mcp_pypi.server.FastMCP")
def test_get_fastmcp_app(mock_fastmcp):
    """Test that the FastMCP app is returned correctly."""
    # Setup mock
    mock_fastmcp_instance = MagicMock()
    mock_fastmcp.return_value = mock_fastmcp_instance

    # Create server
    server = PyPIMCPServer()

    # Get the app
    app = server.get_fastmcp_app()

    # Verify
    assert app == mock_fastmcp_instance
