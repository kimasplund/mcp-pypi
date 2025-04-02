"""
MCP server implementation for mcp-pypi.
This module provides a fully compliant MCP server using the official MCP Python SDK.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List, Tuple, Union

from mcp.server.fastmcp import FastMCP
from mcp.types import Resource, Tool, Prompt, ResourceResponse, PromptMessage, TextContent, GetPromptResult

from mcp_pypi.core import PyPIClient
from mcp_pypi.core.models import PyPIClientConfig

logger = logging.getLogger("mcp-pypi.server")


class PyPIMCPServer:
    """A fully compliant MCP server for PyPI functionality."""
    
    def __init__(self, config: Optional[PyPIClientConfig] = None):
        """Initialize the MCP server with PyPI client."""
        self.config = config or PyPIClientConfig()
        self.client = PyPIClient(self.config)
        self.mcp_server = FastMCP("PyPI MCP Server")
        
        # Register all tools
        self._register_tools()
        # Register resources
        self._register_resources()
        # Register prompts
        self._register_prompts()
    
    def _register_tools(self):
        """Register all PyPI tools with the MCP server."""
        
        @self.mcp_server.tool()
        async def get_package_info(package_name: str) -> Dict[str, Any]:
            """Get detailed information about a Python package from PyPI."""
            return await self.client.get_package_info(package_name)
        
        @self.mcp_server.tool()
        async def get_latest_version(package_name: str) -> Dict[str, Any]:
            """Get the latest version of a package from PyPI."""
            return await self.client.get_latest_version(package_name)
        
        @self.mcp_server.tool()
        async def get_dependency_tree(package_name: str, version: Optional[str] = None, depth: int = 1) -> Dict[str, Any]:
            """Get the dependency tree for a package."""
            return await self.client.get_dependency_tree(package_name, version, depth)
        
        @self.mcp_server.tool()
        async def search_packages(query: str, page: int = 1) -> Dict[str, Any]:
            """Search for packages on PyPI."""
            return await self.client.search_packages(query, page)
        
        @self.mcp_server.tool()
        async def get_package_stats(package_name: str, version: Optional[str] = None) -> Dict[str, Any]:
            """Get download statistics for a package."""
            return await self.client.get_package_stats(package_name, version)
            
        @self.mcp_server.tool()
        async def check_package_exists(package_name: str) -> Dict[str, Any]:
            """Check if a package exists on PyPI."""
            return await self.client.check_package_exists(package_name)
            
        @self.mcp_server.tool()
        async def get_package_metadata(package_name: str, version: Optional[str] = None) -> Dict[str, Any]:
            """Get package metadata from PyPI."""
            return await self.client.get_package_metadata(package_name, version)
            
        @self.mcp_server.tool()
        async def get_package_releases(package_name: str) -> Dict[str, Any]:
            """Get all releases of a package."""
            return await self.client.get_package_releases(package_name)
            
        @self.mcp_server.tool()
        async def get_project_releases(package_name: str) -> Dict[str, Any]:
            """Get project releases with timestamps."""
            return await self.client.get_project_releases(package_name)
            
        @self.mcp_server.tool()
        async def get_documentation_url(package_name: str) -> Dict[str, Any]:
            """Get documentation URL for a package."""
            return await self.client.get_documentation_url(package_name)
            
        @self.mcp_server.tool()
        async def check_requirements_file(file_path: str) -> Dict[str, Any]:
            """Check a requirements file for outdated packages."""
            return await self.client.check_requirements_file(file_path)
            
        @self.mcp_server.tool()
        async def compare_versions(package_name: str, version1: str, version2: str) -> Dict[str, Any]:
            """Compare two package versions."""
            return await self.client.compare_versions(package_name, version1, version2)
            
        @self.mcp_server.tool()
        async def get_newest_packages() -> Dict[str, Any]:
            """Get newest packages on PyPI."""
            return await self.client.get_newest_packages()
            
        @self.mcp_server.tool()
        async def get_latest_updates() -> Dict[str, Any]:
            """Get latest package updates on PyPI."""
            return await self.client.get_latest_updates()
    
    def _register_resources(self):
        """Register all PyPI resources with the MCP server."""
        
        @self.mcp_server.resource("pypi://package/{package_name}")
        async def package_resource(package_name: str) -> str:
            """Package information resource."""
            result = await self.client.get_package_info(package_name)
            if "error" in result:
                raise ValueError(result["error"]["message"])
            return ResourceResponse(
                content=str(result),
                mime_type="application/json"
            )
        
        @self.mcp_server.resource("pypi://stats/{package_name}")
        async def package_stats_resource(package_name: str) -> str:
            """Package statistics resource."""
            result = await self.client.get_package_stats(package_name)
            if "error" in result:
                raise ValueError(result["error"]["message"])
            return ResourceResponse(
                content=str(result),
                mime_type="application/json"
            )
            
        @self.mcp_server.resource("pypi://dependencies/{package_name}")
        async def package_dependencies_resource(package_name: str) -> str:
            """Package dependencies resource."""
            result = await self.client.get_dependencies(package_name)
            if "error" in result:
                raise ValueError(result["error"]["message"])
            return ResourceResponse(
                content=str(result),
                mime_type="application/json"
            )
    
    def _register_prompts(self):
        """Register all PyPI prompts with the MCP server."""
        
        @self.mcp_server.prompt()
        async def search_packages_prompt(query: str) -> GetPromptResult:
            """Create a prompt for searching packages."""
            return GetPromptResult(
                description=f"Search for Python packages matching '{query}'",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=f"Search for Python packages that match '{query}' and provide a brief description of each result."
                        )
                    )
                ]
            )
            
        @self.mcp_server.prompt()
        async def analyze_package_prompt(package_name: str) -> GetPromptResult:
            """Create a prompt for analyzing a package."""
            return GetPromptResult(
                description=f"Analyze the Python package '{package_name}'",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=f"Analyze the Python package '{package_name}'. Provide information about its purpose, features, dependencies, and popularity."
                        )
                    )
                ]
            )
            
        @self.mcp_server.prompt()
        async def compare_packages_prompt(package1: str, package2: str) -> GetPromptResult:
            """Create a prompt for comparing two packages."""
            return GetPromptResult(
                description=f"Compare '{package1}' and '{package2}' packages",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=f"Compare the Python packages '{package1}' and '{package2}'. Analyze their features, popularity, maintenance status, and use cases to determine when to use each one."
                        )
                    )
                ]
            )
    
    async def start_http_server(self, host: str = "127.0.0.1", port: int = 8000):
        """Start an HTTP server."""
        try:
            await self.mcp_server.start(host=host, port=port)
        finally:
            await self.client.close()
    
    async def process_stdin(self):
        """Process stdin for MCP protocol."""
        import sys
        from mcp.server.stdio import stdio_server
        
        async with stdio_server() as (read_stream, write_stream):
            try:
                await self.mcp_server.run_io(read_stream, write_stream)
            finally:
                await self.client.close()
    
    def get_fastmcp_app(self):
        """Get the FastMCP app for mounting to another ASGI server."""
        return self.mcp_server 