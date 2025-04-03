"""
MCP server implementation for mcp-pypi.
This module provides a fully compliant MCP server using the official MCP Python SDK.
"""

import logging
import sys
import socket
from typing import Dict, Any, Optional, Union, cast, Tuple

# Add type ignore comments for missing stubs
from mcp.server.fastmcp import FastMCP  # type: ignore

# Import the correct types from the installed MCP package
from mcp.types import (
    GetPromptResult, PromptMessage, TextContent,
    Resource, Tool, Prompt  # These are available in the installed package
)

from mcp_pypi.core import PyPIClient
from mcp_pypi.core.models import (
    PyPIClientConfig, PackageInfo, VersionInfo, DependencyTreeResult,
    SearchResult, StatsResult, ExistsResult, MetadataResult,
    ReleasesInfo, ReleasesFeed, DocumentationResult, PackageRequirementsResult,
    VersionComparisonResult, PackagesFeed, UpdatesFeed, DependenciesResult,
    ErrorResult
)

logger = logging.getLogger("mcp-pypi.server")


# Define a simple ResourceResponse class since it's not available in the installed package
class ResourceResponse:
    """Response for a resource request."""
    
    def __init__(self, content: str, mime_type: str):
        self.content = content
        self.mime_type = mime_type


class PyPIMCPServer:
    """A fully compliant MCP server for PyPI functionality."""

    def __init__(self, config: Optional[PyPIClientConfig] = None, host: str = "127.0.0.1", port: int = 8143):
        """Initialize the MCP server with PyPI client."""
        self.config = config or PyPIClientConfig()
        self.client = PyPIClient(self.config)
        self.mcp_server = FastMCP("PyPI MCP Server")
        
        # Set the host and port in the FastMCP settings
        self.mcp_server.settings.host = host
        self.mcp_server.settings.port = port

        # Register all tools
        self._register_tools()
        # Register resources
        self._register_resources()
        # Register prompts
        self._register_prompts()

    async def configure_client(self) -> None:
        """Configure the PyPI client with the current settings.
        
        This method is called before executing certain operations that may need
        updated client configuration, such as checking requirements files.
        """
        logger.debug("Configuring PyPI client with current settings")
        # Update User-Agent if needed for better compatibility with PyPI
        self.client.set_user_agent("Mozilla/5.0 (compatible; MCP-PyPI/2.0; +https://asplund.kim)")
        # Any additional client configuration can be added here

    def _register_tools(self):
        """Register all PyPI tools with the MCP server."""

        @self.mcp_server.tool()
        async def get_package_info(package_name: str) -> Union[PackageInfo, ErrorResult]:
            """Get detailed information about a Python package from PyPI."""
            return await self.client.get_package_info(package_name)

        @self.mcp_server.tool()
        async def get_latest_version(package_name: str) -> Union[VersionInfo, ErrorResult]:
            """Get the latest version of a package from PyPI."""
            return await self.client.get_latest_version(package_name)

        @self.mcp_server.tool()
        async def get_dependency_tree(
            package_name: str, version: Optional[str] = None, depth: int = 1
        ) -> Union[DependencyTreeResult, ErrorResult]:
            """Get the dependency tree for a package."""
            return await self.client.get_dependency_tree(package_name, version, depth)

        @self.mcp_server.tool()
        async def search_packages(query: str, page: int = 1) -> Union[SearchResult, ErrorResult]:
            """Search for packages on PyPI."""
            return await self.client.search_packages(query, page)

        @self.mcp_server.tool()
        async def get_package_stats(
            package_name: str, version: Optional[str] = None
        ) -> Union[StatsResult, ErrorResult]:
            """Get download statistics for a package."""
            return await self.client.get_package_stats(package_name, version)

        @self.mcp_server.tool()
        async def check_package_exists(package_name: str) -> Union[ExistsResult, ErrorResult]:
            """Check if a package exists on PyPI."""
            return await self.client.check_package_exists(package_name)

        @self.mcp_server.tool()
        async def get_package_metadata(
            package_name: str, version: Optional[str] = None
        ) -> Union[MetadataResult, ErrorResult]:
            """Get package metadata from PyPI."""
            return await self.client.get_package_metadata(package_name, version)

        @self.mcp_server.tool()
        async def get_package_releases(package_name: str) -> Union[ReleasesInfo, ErrorResult]:
            """Get all releases of a package."""
            return await self.client.get_package_releases(package_name)

        @self.mcp_server.tool()
        async def get_project_releases(package_name: str) -> Union[ReleasesFeed, ErrorResult]:
            """Get project releases with timestamps."""
            return await self.client.get_project_releases(package_name)

        @self.mcp_server.tool()
        async def get_documentation_url(package_name: str) -> Union[DocumentationResult, ErrorResult]:
            """Get documentation URL for a package."""
            return await self.client.get_documentation_url(package_name)

        @self.mcp_server.tool()
        async def check_requirements_file(file_path: str, format: Optional[str] = None) -> Union[PackageRequirementsResult, ErrorResult]:
            """
            Check a requirements file for outdated packages.
            
            This method examines a requirements file (requirements.txt or pyproject.toml) and reports
            which packages are outdated.
            
            Parameters:
                file_path (str): The path to the requirements file
                format (str, optional): Output format, either 'json' or 'table'. Defaults to 'table'.
            
            Returns:
                A dictionary containing:
                - outdated: List of outdated packages with current and latest versions
                - up_to_date: List of up-to-date packages
                
            For pyproject.toml files, dependencies from the following formats are supported:
            - PEP 621 project metadata (project.dependencies)
            - Poetry (tool.poetry.dependencies)
            - PDM (tool.pdm.dependencies)
            - Flit (tool.flit.metadata.requires)
            """
            await self.configure_client()
            return await self.client.check_requirements_file(file_path)

        @self.mcp_server.tool()
        async def compare_versions(
            package_name: str, version1: str, version2: str
        ) -> Union[VersionComparisonResult, ErrorResult]:
            """Compare two package versions."""
            return await self.client.compare_versions(package_name, version1, version2)

        @self.mcp_server.tool()
        async def get_newest_packages() -> Union[PackagesFeed, ErrorResult]:
            """Get newest packages on PyPI."""
            return await self.client.get_newest_packages()

        @self.mcp_server.tool()
        async def get_latest_updates() -> Union[UpdatesFeed, ErrorResult]:
            """Get latest package updates on PyPI."""
            return await self.client.get_latest_updates()

    def _register_resources(self):
        """Register all PyPI resources with the MCP server."""

        @self.mcp_server.resource("pypi://package/{package_name}")
        async def package_resource(package_name: str) -> ResourceResponse:
            """Package information resource."""
            result = await self.client.get_package_info(package_name)
            if "error" in result:
                raise ValueError(result["error"]["message"])
            return ResourceResponse(content=str(result), mime_type="application/json")

        @self.mcp_server.resource("pypi://stats/{package_name}")
        async def package_stats_resource(package_name: str) -> ResourceResponse:
            """Package statistics resource."""
            result = await self.client.get_package_stats(package_name)
            if "error" in result:
                raise ValueError(result["error"]["message"])
            return ResourceResponse(content=str(result), mime_type="application/json")

        @self.mcp_server.resource("pypi://dependencies/{package_name}")
        async def package_dependencies_resource(package_name: str) -> ResourceResponse:
            """Package dependencies resource."""
            result = await self.client.get_dependencies(package_name)
            if "error" in result:
                raise ValueError(result["error"]["message"])
            return ResourceResponse(content=str(result), mime_type="application/json")

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
                            text=(
                                f"Search for Python packages that match '{query}' "
                                "and provide a brief description of each result."
                            ),
                        ),
                    )
                ],
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
                            text=(
                                f"Analyze the Python package '{package_name}'. "
                                "Provide information about its purpose, features, "
                                "dependencies, and popularity."
                            ),
                        ),
                    )
                ],
            )

        @self.mcp_server.prompt()
        async def compare_packages_prompt(
            package1: str, package2: str
        ) -> GetPromptResult:
            """Create a prompt for comparing two packages."""
            return GetPromptResult(
                description=f"Compare '{package1}' and '{package2}' packages",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=(
                                f"Compare the Python packages '{package1}' and '{package2}'. "
                                "Analyze their features, popularity, maintenance status, "
                                "and use cases to determine when to use each one."
                            ),
                        ),
                    )
                ],
            )

    async def start_http_server(self, host: str = "127.0.0.1", port: int = 8143):
        """Start an HTTP server."""
        try:
            # Check if the port is available, try to find another if not
            port = self._find_available_port(host, port)
            
            # Update host and port settings before starting the server
            self.mcp_server.settings.host = host
            self.mcp_server.settings.port = port
            
            logger.info(f"Starting MCP HTTP server on {host}:{port}...")
            
            # Use run_sse_async instead of start which doesn't exist
            await self.mcp_server.run_sse_async()
        finally:
            await self.client.close()
    
    def _find_available_port(self, host: str, port: int, max_attempts: int = 10) -> int:
        """Find an available port, starting from the specified one."""
        original_port = port
        
        for offset in range(max_attempts):
            if offset > 0:
                port = original_port + offset
                logger.info(f"Port {original_port + offset - 1} is in use, trying port {port}...")
            
            # Check if the port is available
            if not self._is_port_in_use(host, port):
                break
        else:
            # If we couldn't find an available port in the range
            error_msg = f"Could not find an available port in range {original_port}-{original_port + max_attempts - 1}"
            logger.error(error_msg)
            raise OSError(error_msg)
        
        return port
    
    @staticmethod
    def _is_port_in_use(host: str, port: int) -> bool:
        """Check if a port is in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex((host, port)) == 0

    async def process_stdin(self):
        """Process stdin for MCP protocol."""
        try:
            # Use the correct method run_stdio_async from FastMCP
            await self.mcp_server.run_stdio_async()
        finally:
            await self.client.close()

    def get_fastmcp_app(self):
        """Get the FastMCP app for mounting to another ASGI server."""
        return self.mcp_server
