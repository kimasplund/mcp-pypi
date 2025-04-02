"""Simple tests for the MCP server implementation."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_pypi_mcp_server_structure():
    """Test that our PyPIMCPServer has the right structure."""
    # Mock the imported modules
    with patch('mcp.server.fastmcp.FastMCP') as mock_fastmcp, \
         patch('mcp_pypi.core.PyPIClient') as mock_client:
        
        # Import our server module
        from mcp_pypi.server import PyPIMCPServer
        
        # Create a mock instance of FastMCP
        mock_fastmcp_instance = MagicMock()
        mock_fastmcp.return_value = mock_fastmcp_instance
        mock_fastmcp_instance.tool = MagicMock(return_value=lambda f: f)
        mock_fastmcp_instance.resource = MagicMock(return_value=lambda f: f)
        mock_fastmcp_instance.prompt = MagicMock(return_value=lambda f: f)
        
        # Create a mock instance of PyPIClient
        mock_client_instance = AsyncMock()
        mock_client.return_value = mock_client_instance
        
        # Create an instance of PyPIMCPServer
        server = PyPIMCPServer()
        
        # Check that it has the expected methods
        assert hasattr(server, 'start_http_server')
        assert hasattr(server, 'process_stdin')
        assert hasattr(server, 'get_fastmcp_app')
        
        # Check that it registered tools, resources, and prompts
        assert mock_fastmcp_instance.tool.call_count > 0
        assert mock_fastmcp_instance.resource.call_count > 0
        assert mock_fastmcp_instance.prompt.call_count > 0 