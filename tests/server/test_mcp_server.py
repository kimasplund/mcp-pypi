"""Tests for the MCP server implementation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    with patch("mcp_pypi.server.FastMCP") as mock:
        mcp_instance = mock.return_value
        mcp_instance.tool = MagicMock()
        mcp_instance.resource = MagicMock()
        mcp_instance.prompt = MagicMock()
        mcp_instance.run = MagicMock()
        mcp_instance.run_stdio_async = AsyncMock()
        # Mock the settings attribute
        mcp_instance.settings = MagicMock()
        mcp_instance.settings.host = "127.0.0.1"
        mcp_instance.settings.port = 8143
        yield mock  # Yield the mock class, not the instance


@pytest.mark.asyncio
async def test_pypi_mcp_server_init(mock_pypi_client, mock_fastmcp):
    """Test PyPIMCPServer initialization."""
    server = PyPIMCPServer()

    # Check that FastMCP was initialized with name parameter
    mock_fastmcp.assert_called_once()
    call_kwargs = mock_fastmcp.call_args.kwargs
    assert call_kwargs.get("name") == "PyPI MCP Server"
    assert "description" in call_kwargs


@pytest.mark.asyncio
async def test_register_tools(mock_pypi_client, mock_fastmcp):
    """Test that tools are registered."""
    server = PyPIMCPServer()

    # Verify the decorator was called for each tool
    mcp_instance = mock_fastmcp.return_value
    assert mcp_instance.tool.call_count > 0


@pytest.mark.asyncio
async def test_register_resources(mock_pypi_client, mock_fastmcp):
    """Test that resources are registered."""
    server = PyPIMCPServer()

    # Verify the decorator was called for each resource
    mcp_instance = mock_fastmcp.return_value
    assert mcp_instance.resource.call_count > 0


@pytest.mark.asyncio
async def test_register_prompts(mock_pypi_client, mock_fastmcp):
    """Test that prompts are registered."""
    server = PyPIMCPServer()

    # Verify the decorator was called for each prompt
    mcp_instance = mock_fastmcp.return_value
    assert mcp_instance.prompt.call_count > 0


def test_configure_client(mock_pypi_client, mock_fastmcp):
    """Test client reconfiguration."""
    server = PyPIMCPServer()

    # Create a new config
    new_config = PyPIClientConfig(cache_strategy="memory")

    # Reconfigure the client
    server.configure_client(new_config)

    # Verify the config was updated
    assert server.config == new_config


def test_run_method_exists(mock_pypi_client, mock_fastmcp):
    """Test that run method exists and can be called."""
    server = PyPIMCPServer()

    # Verify run method exists
    assert hasattr(server, "run")
    assert callable(server.run)


@pytest.mark.asyncio
async def test_run_async_method_exists(mock_pypi_client, mock_fastmcp):
    """Test that run_async method exists."""
    server = PyPIMCPServer()

    # Verify run_async method exists
    assert hasattr(server, "run_async")
    assert callable(server.run_async)


def test_mcp_server_attribute(mock_pypi_client, mock_fastmcp):
    """Test that mcp_server attribute is set correctly."""
    server = PyPIMCPServer()
    mcp_instance = mock_fastmcp.return_value

    # Verify the mcp_server attribute is the FastMCP instance
    assert server.mcp_server == mcp_instance
