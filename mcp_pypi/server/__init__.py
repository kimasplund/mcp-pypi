#!/usr/bin/env python
"""MCP-PyPI package server.

This module provides server implementation for PyPI package management through the
Model Context Protocol (MCP), including tools for package information, dependency
tracking, and other PyPI-related operations.
"""

import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Set, Literal

from mcp.server import FastMCP
from mcp.types import GetPromptResult, PromptMessage, TextContent

from mcp_pypi.core import PyPIClient
from mcp_pypi.core.models import (
    PyPIClientConfig,
    PackageInfo,
    VersionInfo,
    DependencyTreeResult,
    SearchResult,
    StatsResult,
    ExistsResult,
    MetadataResult,
    ReleasesInfo,
    ReleasesFeed,
    DocumentationResult,
    PackageRequirementsResult,
    VersionComparisonResult,
    PackagesFeed,
    UpdatesFeed,
    DependenciesResult,
    ErrorResult,
)

# Protocol version for MCP
PROTOCOL_VERSION = "2025-06-18"

logger = logging.getLogger("mcp-pypi.server")


class PyPIMCPServer:
    """A fully compliant MCP server for PyPI functionality."""

    def __init__(
        self,
        config: Optional[PyPIClientConfig] = None,
        host: str = "127.0.0.1",
        port: int = 8143,
    ):
        """Initialize the MCP server with PyPI client."""
        self.config = config or PyPIClientConfig()
        self.client = PyPIClient(self.config)
        
        # Initialize FastMCP server
        self.mcp_server = FastMCP("PyPI MCP Server")
        
        # Set the host and port in the FastMCP settings
        self.mcp_server.settings.host = host
        self.mcp_server.settings.port = port
        
        # Configure protocol version
        self.protocol_version = PROTOCOL_VERSION
        logger.info(f"Using protocol version: {self.protocol_version}")
        
        # Register all tools, resources, and prompts
        self._register_tools()
        self._register_resources()
        self._register_prompts()
        
        logger.info("PyPI MCP Server initialization complete")
    
    def configure_client(self, config: PyPIClientConfig):
        """Configure the PyPI client with new settings."""
        self.config = config
        self.client = PyPIClient(config)
        logger.info("PyPI client reconfigured")
    
    def _register_tools(self):
        """Register all PyPI tools with the MCP server."""
        
        @self.mcp_server.tool()
        async def search_packages(query: str, limit: int = 10) -> SearchResult:
            """Search for packages on PyPI.
            
            Args:
                query: Search query string
                limit: Maximum number of results to return (default: 10, max: 100)
            
            Returns:
                SearchResult with list of matching packages
            """
            try:
                return await self.client.search(query, limit=min(limit, 100))
            except Exception as e:
                logger.error(f"Error searching packages: {e}")
                return SearchResult(
                    query=query,
                    packages=[],
                    total=0,
                    error=ErrorResult(message=str(e), code="search_error")
                )
        
        @self.mcp_server.tool()
        async def get_package_info(package_name: str) -> PackageInfo:
            """Get detailed information about a specific package.
            
            Args:
                package_name: Name of the package
            
            Returns:
                PackageInfo with comprehensive package details
            """
            try:
                return await self.client.get_package_info(package_name)
            except Exception as e:
                logger.error(f"Error getting package info: {e}")
                return PackageInfo(
                    name=package_name,
                    version="",
                    summary="",
                    error=ErrorResult(message=str(e), code="package_info_error")
                )
        
        @self.mcp_server.tool()
        async def get_latest_version(package_name: str) -> VersionInfo:
            """Get the latest version of a package.
            
            Args:
                package_name: Name of the package
            
            Returns:
                VersionInfo with the latest version details
            """
            try:
                return await self.client.get_latest_version(package_name)
            except Exception as e:
                logger.error(f"Error getting latest version: {e}")
                return VersionInfo(
                    package_name=package_name,
                    version="",
                    error=ErrorResult(message=str(e), code="version_error")
                )
        
        @self.mcp_server.tool()
        async def get_dependencies(package_name: str, version: Optional[str] = None) -> DependenciesResult:
            """Get dependencies for a package.
            
            Args:
                package_name: Name of the package
                version: Specific version (optional, defaults to latest)
            
            Returns:
                DependenciesResult with install and dev dependencies
            """
            try:
                return await self.client.get_dependencies(package_name, version)
            except Exception as e:
                logger.error(f"Error getting dependencies: {e}")
                return DependenciesResult(
                    package=package_name,
                    version=version or "latest",
                    install_requires=[],
                    extras_require={},
                    error=ErrorResult(message=str(e), code="dependencies_error")
                )
        
        @self.mcp_server.tool()
        async def get_dependency_tree(
            package_name: str,
            version: Optional[str] = None,
            max_depth: int = 3
        ) -> DependencyTreeResult:
            """Get the full dependency tree for a package.
            
            Args:
                package_name: Name of the package
                version: Specific version (optional, defaults to latest)
                max_depth: Maximum depth to traverse (default: 3)
            
            Returns:
                DependencyTreeResult with nested dependency structure
            """
            try:
                return await self.client.get_dependency_tree(package_name, version, max_depth)
            except Exception as e:
                logger.error(f"Error getting dependency tree: {e}")
                return DependencyTreeResult(
                    package=package_name,
                    version=version or "latest",
                    tree={},
                    error=ErrorResult(message=str(e), code="dependency_tree_error")
                )
        
        @self.mcp_server.tool()
        async def get_package_stats(package_name: str) -> StatsResult:
            """Get download statistics for a package.
            
            Args:
                package_name: Name of the package
            
            Returns:
                StatsResult with download counts and trends
            """
            try:
                return await self.client.get_package_stats(package_name)
            except Exception as e:
                logger.error(f"Error getting package stats: {e}")
                return StatsResult(
                    package_name=package_name,
                    downloads={},
                    error=ErrorResult(message=str(e), code="stats_error")
                )
        
        @self.mcp_server.tool()
        async def check_package_exists(package_name: str) -> ExistsResult:
            """Check if a package exists on PyPI.
            
            Args:
                package_name: Name of the package
            
            Returns:
                ExistsResult indicating whether the package exists
            """
            try:
                return await self.client.check_package_exists(package_name)
            except Exception as e:
                logger.error(f"Error checking package existence: {e}")
                return ExistsResult(
                    package_name=package_name,
                    exists=False,
                    error=ErrorResult(message=str(e), code="exists_error")
                )
        
        @self.mcp_server.tool()
        async def get_package_metadata(
            package_name: str,
            version: Optional[str] = None
        ) -> MetadataResult:
            """Get metadata for a package.
            
            Args:
                package_name: Name of the package
                version: Specific version (optional, defaults to latest)
            
            Returns:
                MetadataResult with package metadata
            """
            try:
                return await self.client.get_package_metadata(package_name, version)
            except Exception as e:
                logger.error(f"Error getting package metadata: {e}")
                return MetadataResult(
                    package_name=package_name,
                    version=version or "latest",
                    metadata={},
                    error=ErrorResult(message=str(e), code="metadata_error")
                )
        
        @self.mcp_server.tool()
        async def list_package_versions(package_name: str) -> ReleasesInfo:
            """List all available versions of a package.
            
            Args:
                package_name: Name of the package
            
            Returns:
                ReleasesInfo with all available versions
            """
            try:
                return await self.client.list_package_versions(package_name)
            except Exception as e:
                logger.error(f"Error listing package versions: {e}")
                return ReleasesInfo(
                    package_name=package_name,
                    releases=[],
                    error=ErrorResult(message=str(e), code="versions_error")
                )
        
        @self.mcp_server.tool()
        async def compare_versions(
            package_name: str,
            version1: str,
            version2: str
        ) -> VersionComparisonResult:
            """Compare two versions of a package.
            
            Args:
                package_name: Name of the package
                version1: First version to compare
                version2: Second version to compare
            
            Returns:
                VersionComparisonResult with comparison details
            """
            try:
                return await self.client.compare_versions(package_name, version1, version2)
            except Exception as e:
                logger.error(f"Error comparing versions: {e}")
                return VersionComparisonResult(
                    package_name=package_name,
                    version1=version1,
                    version2=version2,
                    comparison="error",
                    error=ErrorResult(message=str(e), code="comparison_error")
                )
        
        @self.mcp_server.tool()
        async def check_requirements_txt(file_path: str) -> PackageRequirementsResult:
            """Check packages from a requirements.txt file.
            
            Args:
                file_path: Path to requirements.txt file
            
            Returns:
                PackageRequirementsResult with package status information
            """
            try:
                return await self.client.check_requirements_txt(file_path)
            except Exception as e:
                logger.error(f"Error checking requirements.txt: {e}")
                return PackageRequirementsResult(
                    file_path=file_path,
                    requirements=[],
                    error=ErrorResult(message=str(e), code="requirements_error")
                )
        
        @self.mcp_server.tool()
        async def check_pyproject_toml(file_path: str) -> PackageRequirementsResult:
            """Check packages from a pyproject.toml file.
            
            Args:
                file_path: Path to pyproject.toml file
            
            Returns:
                PackageRequirementsResult with package status information
            """
            try:
                return await self.client.check_pyproject_toml(file_path)
            except Exception as e:
                logger.error(f"Error checking pyproject.toml: {e}")
                return PackageRequirementsResult(
                    file_path=file_path,
                    requirements=[],
                    error=ErrorResult(message=str(e), code="pyproject_error")
                )
        
        @self.mcp_server.tool()
        async def get_package_documentation(package_name: str) -> DocumentationResult:
            """Get documentation links for a package.
            
            Args:
                package_name: Name of the package
            
            Returns:
                DocumentationResult with documentation URLs
            """
            try:
                return await self.client.get_package_documentation(package_name)
            except Exception as e:
                logger.error(f"Error getting package documentation: {e}")
                return DocumentationResult(
                    package_name=package_name,
                    documentation_url=None,
                    error=ErrorResult(message=str(e), code="documentation_error")
                )
        
        @self.mcp_server.tool()
        async def get_package_changelog(
            package_name: str,
            version: Optional[str] = None
        ) -> str:
            """Get changelog for a package.
            
            Args:
                package_name: Name of the package
                version: Specific version (optional, defaults to latest)
            
            Returns:
                Changelog text or error message
            """
            try:
                result = await self.client.get_package_changelog(package_name, version)
                return result if isinstance(result, str) else "No changelog available"
            except Exception as e:
                logger.error(f"Error getting package changelog: {e}")
                return f"Error getting changelog: {str(e)}"
        
        @self.mcp_server.tool()
        async def check_vulnerabilities(
            package_name: str,
            version: Optional[str] = None
        ) -> Dict[str, Any]:
            """Check for known vulnerabilities in a package.
            
            Args:
                package_name: Name of the package
                version: Specific version (optional, defaults to latest)
            
            Returns:
                Dictionary with vulnerability information
            """
            try:
                result = await self.client.check_vulnerabilities(package_name, version)
                return result if isinstance(result, dict) else {"error": str(result)}
            except Exception as e:
                logger.error(f"Error checking vulnerabilities: {e}")
                return {"error": f"Error checking vulnerabilities: {str(e)}"}
    
    def _register_resources(self):
        """Register PyPI resources with the MCP server."""
        
        @self.mcp_server.resource("pypi://recent-releases")
        async def get_recent_releases() -> str:
            """Get recent package releases from PyPI."""
            try:
                feed = await self.client.get_releases_feed()
                if isinstance(feed, ReleasesFeed):
                    releases = []
                    for release in feed.releases[:20]:  # Limit to 20 recent releases
                        releases.append(
                            f"- {release.package} {release.version} "
                            f"(by {release.author}, {release.published})"
                        )
                    return "Recent PyPI Releases:\n\n" + "\n".join(releases)
                return "No recent releases available"
            except Exception as e:
                logger.error(f"Error getting recent releases: {e}")
                return f"Error getting recent releases: {str(e)}"
        
        @self.mcp_server.resource("pypi://new-packages")
        async def get_new_packages() -> str:
            """Get newly created packages on PyPI."""
            try:
                feed = await self.client.get_packages_feed()
                if isinstance(feed, PackagesFeed):
                    packages = []
                    for pkg in feed.packages[:20]:  # Limit to 20 new packages
                        packages.append(
                            f"- {pkg.name} (by {pkg.author}, {pkg.created})"
                        )
                    return "New PyPI Packages:\n\n" + "\n".join(packages)
                return "No new packages available"
            except Exception as e:
                logger.error(f"Error getting new packages: {e}")
                return f"Error getting new packages: {str(e)}"
        
        @self.mcp_server.resource("pypi://updated-packages")
        async def get_updated_packages() -> str:
            """Get recently updated packages on PyPI."""
            try:
                feed = await self.client.get_updates_feed()
                if isinstance(feed, UpdatesFeed):
                    updates = []
                    for update in feed.updates[:20]:  # Limit to 20 updates
                        updates.append(
                            f"- {update.package} {update.version} "
                            f"(updated {update.updated})"
                        )
                    return "Recently Updated PyPI Packages:\n\n" + "\n".join(updates)
                return "No recent updates available"
            except Exception as e:
                logger.error(f"Error getting package updates: {e}")
                return f"Error getting package updates: {str(e)}"
    
    def _register_prompts(self):
        """Register prompts with the MCP server."""
        
        @self.mcp_server.prompt()
        async def analyze_dependencies() -> GetPromptResult:
            """Analyze package dependencies and suggest improvements."""
            return GetPromptResult(
                description="Analyze package dependencies for security and compatibility",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=(
                                "Please analyze the dependencies of the specified package and:\n"
                                "1. Check for security vulnerabilities\n"
                                "2. Identify outdated dependencies\n"
                                "3. Suggest version updates\n"
                                "4. Check for dependency conflicts\n"
                                "5. Recommend best practices for dependency management"
                            )
                        )
                    )
                ]
            )
        
        @self.mcp_server.prompt()
        async def package_comparison() -> GetPromptResult:
            """Compare multiple packages and recommend the best option."""
            return GetPromptResult(
                description="Compare packages and provide recommendations",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=(
                                "Please compare the specified packages based on:\n"
                                "1. Download statistics and popularity\n"
                                "2. Maintenance status and last update\n"
                                "3. Documentation quality\n"
                                "4. Dependencies and size\n"
                                "5. Community support and issues\n"
                                "Provide a recommendation on which package to use."
                            )
                        )
                    )
                ]
            )
    
    def run(self, transport: Literal["stdio", "http"] = "stdio"):
        """Run the MCP server.
        
        Args:
            transport: Transport method to use:
                - "stdio": Direct process communication
                - "http": HTTP server with both SSE (/sse) and streamable-http (/mcp) endpoints
        """
        if transport == "stdio":
            self.mcp_server.run(transport="stdio")
        elif transport == "http":
            # When running HTTP mode, both SSE and streamable-http endpoints are available
            logger.info(f"Starting HTTP server on {self.mcp_server.settings.host}:{self.mcp_server.settings.port}")
            logger.info(f"SSE endpoint: http://{self.mcp_server.settings.host}:{self.mcp_server.settings.port}/sse")
            logger.info(f"Streamable-HTTP endpoint: http://{self.mcp_server.settings.host}:{self.mcp_server.settings.port}/mcp")
            self.mcp_server.run(transport="sse")  # This actually starts the full HTTP server
        else:
            raise ValueError(f"Unknown transport: {transport}. Use 'stdio' or 'http'")
    
    async def run_async(self, transport: Literal["stdio", "http"] = "stdio"):
        """Run the MCP server asynchronously.
        
        Args:
            transport: Transport method to use:
                - "stdio": Direct process communication  
                - "http": HTTP server with both SSE (/sse) and streamable-http (/mcp) endpoints
        """
        if transport == "stdio":
            await self.mcp_server.run_stdio_async()
        elif transport == "http":
            # When running HTTP mode, both SSE and streamable-http endpoints are available
            logger.info(f"Starting HTTP server on {self.mcp_server.settings.host}:{self.mcp_server.settings.port}")
            logger.info(f"SSE endpoint: http://{self.mcp_server.settings.host}:{self.mcp_server.settings.port}/sse")
            logger.info(f"Streamable-HTTP endpoint: http://{self.mcp_server.settings.host}:{self.mcp_server.settings.port}/mcp")
            await self.mcp_server.run_sse_async()  # This actually starts the full HTTP server
        else:
            raise ValueError(f"Unknown transport: {transport}. Use 'stdio' or 'http'")


# Re-export the server class
__all__ = ["PyPIMCPServer"]