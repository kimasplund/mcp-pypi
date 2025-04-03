"""
MCP server implementation for mcp-pypi.
This module provides a fully compliant MCP server using the official MCP Python SDK.
"""

import logging
import sys
from typing import Dict, Any, Optional, Union, cast

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
        async def check_requirements_file(file_path: str) -> Union[PackageRequirementsResult, ErrorResult]:
            """Check a requirements file for outdated packages."""
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

    async def start_http_server(self, host: str = "127.0.0.1", port: int = 8000):
        """Start an HTTP server."""
        try:
            await self.mcp_server.start(host=host, port=port)
        finally:
            await self.client.close()

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
