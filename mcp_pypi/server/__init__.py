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
from typing import Dict, Any, List, Optional, Union, Set, Literal, cast

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
        
        # Initialize FastMCP server with enhanced description
        self.mcp_server = FastMCP(
            name="PyPI MCP Server",
            description="""🐍 Python Package Intelligence for AI Agents

Access PyPI's 500,000+ packages with powerful discovery and analysis tools. 
Perfect for finding libraries, managing dependencies, and keeping projects secure.

Key capabilities:
• 🔍 Smart package search and discovery
• 📊 Download statistics and popularity metrics  
• 🔗 Deep dependency analysis
• 🛡️ Security vulnerability scanning
• 📋 Requirements file auditing
• 🚀 Version tracking and updates"""
        )
        
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
            """🔍 Search PyPI to discover Python packages for any task.
            
            Find the perfect library from 500,000+ packages. Returns ranked results
            with names, descriptions, and versions to help you choose the best option.
            
            Args:
                query: Search terms (e.g. "web scraping", "machine learning")
                limit: Maximum results (default: 10, max: 100)
            
            Returns:
                SearchResult with packages sorted by relevance
            
            Examples:
                query="data visualization" → matplotlib, plotly, seaborn
                query="testing framework" → pytest, unittest, nose2
            """
            try:
                # Note: PyPI search API doesn't support limit parameter directly
                # We'll get results and truncate if needed
                result = await self.client.search_packages(query)
                if not result.get("error") and limit < 100:
                    # Limit the results if specified
                    results = result.get("results", [])
                    if len(results) > limit:
                        result["results"] = results[:limit]
                        result["total"] = limit
                return result
            except Exception as e:
                logger.error(f"Error searching packages: {e}")
                return {
                    "query": query,
                    "packages": [],
                    "total": 0,
                    "error": {"message": str(e), "code": "search_error"}
                }
        
        @self.mcp_server.tool()
        async def get_package_info(package_name: str) -> Dict[str, Any]:
            """📦 Get comprehensive details about any Python package from PyPI.
            
            Essential for understanding packages before installation. Returns complete
            metadata including description, license, author, URLs, and classifiers.
            
            Args:
                package_name: Exact name of the Python package
            
            Returns:
                PackageInfo with description, license, URLs, dependencies, and more
            
            Use this to:
                - Understand what a package does
                - Check license compatibility
                - Find documentation and source code
                - View maintainer information
            """
            try:
                full_info = await self.client.get_package_info(package_name)
                
                # If there's an error, return as-is
                if "error" in full_info:
                    return cast(Dict[str, Any], full_info)
                
                # Extract essential info without the massive releases data
                info = full_info.get("info", {})
                releases = full_info.get("releases", {})
                
                # Build a condensed response
                condensed = {
                    "info": info,
                    "release_count": len(releases),
                    "available_versions": sorted(releases.keys(), reverse=True)[:10],  # Top 10 versions
                    "latest_version": info.get("version", "")
                }
                
                # Add URLs from the latest release if available
                latest_version = info.get("version")
                if latest_version and latest_version in releases:
                    latest_files = releases[latest_version]
                    condensed["latest_release_files"] = len(latest_files)
                    condensed["latest_release_types"] = list(set(
                        f.get("packagetype", "unknown") for f in latest_files
                    ))
                
                return condensed
                
            except Exception as e:
                logger.error(f"Error getting package info: {e}")
                return {
                    "error": {
                        "message": str(e),
                        "code": "package_info_error"
                    }
                }
        
        @self.mcp_server.tool()
        async def get_package_releases(
            package_name: str,
            limit: Optional[int] = 10
        ) -> Dict[str, Any]:
            """Get detailed release information for a specific package.
            
            Provides full release data for packages when needed. Use this after
            get_package_info to explore specific versions in detail.
            
            Args:
                package_name: Name of the Python package
                limit: Maximum number of releases to return (default: 10)
            
            Returns:
                Dictionary with release versions and their file details
            """
            try:
                full_info = await self.client.get_package_info(package_name)
                
                # If there's an error, return as-is
                if "error" in full_info:
                    return cast(Dict[str, Any], full_info)
                
                releases = full_info.get("releases", {})
                sorted_versions = sorted(releases.keys(), reverse=True)
                
                # Limit the number of releases
                if limit:
                    sorted_versions = sorted_versions[:limit]
                
                limited_releases = {
                    version: releases[version]
                    for version in sorted_versions
                }
                
                return {
                    "package_name": package_name,
                    "total_releases": len(releases),
                    "returned_releases": len(limited_releases),
                    "releases": limited_releases
                }
                
            except Exception as e:
                logger.error(f"Error getting package releases: {e}")
                return {
                    "error": {
                        "message": str(e),
                        "code": "releases_error"
                    }
                }
        
        @self.mcp_server.tool()
        async def get_latest_version(package_name: str) -> VersionInfo:
            """🚀 Check the latest version of any Python package on PyPI.
            
            Instantly see if updates are available. Essential for keeping projects
            current, secure, and compatible with the latest features.
            
            Args:
                package_name: Name of the Python package
            
            Returns:
                VersionInfo with latest stable version and release date
            """
            try:
                return await self.client.get_latest_version(package_name)
            except Exception as e:
                logger.error(f"Error getting latest version: {e}")
                return {
                    "package_name": package_name,
                    "version": "",
                    "error": {"message": str(e), "code": "version_error"}
                }
        
        @self.mcp_server.tool()
        async def get_dependencies(package_name: str, version: Optional[str] = None) -> DependenciesResult:
            """🔗 Analyze Python package dependencies from PyPI.
            
            Critical for dependency management and security audits. See all required
            and optional dependencies with version constraints to plan installations
            and identify potential conflicts.
            
            Args:
                package_name: Name of the Python package
                version: Specific version (optional, defaults to latest)
            
            Returns:
                DependenciesResult with install_requires and extras_require
            """
            try:
                return await self.client.get_dependencies(package_name, version)
            except Exception as e:
                logger.error(f"Error getting dependencies: {e}")
                return {
                    "package": package_name,
                    "version": version or "latest",
                    "install_requires": [],
                    "extras_require": {},
                    "error": {"message": str(e), "code": "dependencies_error"}
                }
        
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
                return {
                    "package": package_name,
                    "version": version or "latest",
                    "error": {"message": str(e), "code": "dependency_tree_error"}
                }
        
        @self.mcp_server.tool()
        async def get_package_stats(package_name: str) -> StatsResult:
            """📊 Get PyPI download statistics to gauge package popularity.
            
            Make informed decisions using real usage data from the Python community.
            Compare alternatives and track adoption trends over time.
            
            Args:
                package_name: Name of the Python package
            
            Returns:
                StatsResult with daily, weekly, and monthly download counts
            """
            try:
                return await self.client.get_package_stats(package_name)
            except Exception as e:
                logger.error(f"Error getting package stats: {e}")
                return {
                    "package_name": package_name,
                    "downloads": {},
                    "error": {"message": str(e), "code": "stats_error"}
                }
        
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
                return {
                    "package_name": package_name,
                    "exists": False,
                    "error": {"message": str(e), "code": "exists_error"}
                }
        
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
                return {
                    "package_name": package_name,
                    "version": version or "latest",
                    "metadata": {},
                    "error": {"message": str(e), "code": "metadata_error"}
                }
        
        @self.mcp_server.tool()
        async def list_package_versions(package_name: str) -> ReleasesInfo:
            """List all available versions of a package.
            
            Args:
                package_name: Name of the package
            
            Returns:
                ReleasesInfo with all available versions
            """
            try:
                return await self.client.get_package_releases(package_name)
            except Exception as e:
                logger.error(f"Error listing package versions: {e}")
                return {
                    "package_name": package_name,
                    "releases": [],
                    "error": {"message": str(e), "code": "versions_error"}
                }
        
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
                return {
                    "package_name": package_name,
                    "version1": version1,
                    "version2": version2,
                    "comparison": "error",
                    "error": {"message": str(e), "code": "comparison_error"}
                }
        
        @self.mcp_server.tool()
        async def check_requirements_txt(file_path: str) -> PackageRequirementsResult:
            """📋 Analyze requirements.txt for outdated packages and security updates.
            
            Automate dependency audits to keep projects secure and up-to-date. Get
            specific recommendations for compatible upgrades and security patches.
            
            Args:
                file_path: Path to requirements.txt file
            
            Returns:
                PackageRequirementsResult with current vs latest versions
            """
            try:
                return await self.client.check_requirements_file(file_path)
            except Exception as e:
                logger.error(f"Error checking requirements.txt: {e}")
                return {
                    "file_path": file_path,
                    "requirements": [],
                    "error": {"message": str(e), "code": "requirements_error"}
                }
        
        @self.mcp_server.tool()
        async def check_pyproject_toml(file_path: str) -> PackageRequirementsResult:
            """Check packages from a pyproject.toml file.
            
            Args:
                file_path: Path to pyproject.toml file
            
            Returns:
                PackageRequirementsResult with package status information
            """
            try:
                return await self.client.check_requirements_file(file_path)
            except Exception as e:
                logger.error(f"Error checking pyproject.toml: {e}")
                return {
                    "file_path": file_path,
                    "requirements": [],
                    "error": {"message": str(e), "code": "pyproject_error"}
                }
        
        @self.mcp_server.tool()
        async def get_package_documentation(package_name: str) -> DocumentationResult:
            """Get documentation links for a package.
            
            Args:
                package_name: Name of the package
            
            Returns:
                DocumentationResult with documentation URLs
            """
            try:
                return await self.client.get_documentation_url(package_name)
            except Exception as e:
                logger.error(f"Error getting package documentation: {e}")
                return {
                    "package_name": package_name,
                    "documentation_url": None,
                    "error": {"message": str(e), "code": "documentation_error"}
                }
        
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
                if not feed.get("error"):
                    releases = []
                    feed_releases = feed.get("releases", [])
                    for release in feed_releases[:20]:  # Limit to 20 recent releases
                        releases.append(
                            f"- {release.get('title', 'Unknown')} "
                            f"({release.get('published_date', 'Unknown date')})"
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
                if not feed.get("error"):
                    packages = []
                    feed_packages = feed.get("packages", [])
                    for pkg in feed_packages[:20]:  # Limit to 20 new packages
                        packages.append(
                            f"- {pkg.get('title', 'Unknown')} "
                            f"({pkg.get('published_date', 'Unknown date')})"
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
                if not feed.get("error"):
                    updates = []
                    feed_updates = feed.get("updates", [])
                    for update in feed_updates[:20]:  # Limit to 20 updates
                        updates.append(
                            f"- {update.get('title', 'Unknown')} "
                            f"({update.get('published_date', 'Unknown date')})"
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