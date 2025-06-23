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
from datetime import datetime
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
            description="""🐍 Security-First Python Package Intelligence

Helps AI assistants write safer Python code by providing comprehensive package 
analysis with integrated security scanning. Search, evaluate, and verify packages
before recommending them.

Core philosophy: Great code starts with secure dependencies.

Key capabilities:
• 🛡️ Proactive vulnerability scanning for all packages
• 🔍 Smart search with security awareness
• 📊 Package evaluation with safety metrics
• 🔗 Deep dependency security analysis
• 📋 Project-wide security auditing
• 🚀 Safe version recommendations"""
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
            
            💡 Pro tip: After finding interesting packages, use get_package_info for details
            and check_vulnerabilities to ensure they're safe to recommend.
            
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
            
            🛡️ Recommendation: When evaluating packages for use, follow up with
            check_vulnerabilities to ensure security. Quality packages deserve security verification.
            
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
            """📋 Analyze requirements.txt for outdated packages and security issues.
            
            Audits your project dependencies to identify outdated packages and potential
            security vulnerabilities. Helps maintain healthy, secure dependency management.
            
            Provides insights on:
            • Version currency - how outdated are your packages?
            • Security status - any known vulnerabilities?
            • Update priority - which updates are most important?
            • Compatibility - will updates break your project?
            
            Args:
                file_path: Path to requirements.txt file
            
            Returns:
                PackageRequirementsResult with:
                - Package-by-package analysis
                - Security alerts for vulnerable packages
                - Prioritized update recommendations
                - Version compatibility information
            
            💡 Tip: Run before deployments and as part of regular maintenance.
            Consider using with scan_dependency_vulnerabilities for deeper analysis.
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
            """🎯 Analyze pyproject.toml for outdated packages and security issues.
            
            Modern Python projects use pyproject.toml for dependency management. This tool
            audits all dependency groups to ensure security and currency.
            
            Comprehensive coverage:
            • [project.dependencies] - main dependencies
            • [project.optional-dependencies] - extras like dev, test, docs
            • Poetry/PDM style configurations
            • Version constraints and compatibility
            
            Args:
                file_path: Path to pyproject.toml file
            
            Returns:
                PackageRequirementsResult with:
                - Analysis of all dependency groups
                - Security status for each package
                - Update recommendations by priority
                - Constraint compatibility warnings
            
            💡 Works with all modern Python packaging tools (pip, poetry, pdm, hatch).
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
            """🛡️ Check for known vulnerabilities in a Python package.
            
            Uses Google's OSV (Open Source Vulnerabilities) database to identify CVEs,
            security advisories, and known issues. Essential for responsible package recommendations.
            
            When to use:
            ✓ Before recommending any package for production use
            ✓ When evaluating package options for security-sensitive contexts
            ✓ During security audits or dependency updates
            ✓ When users ask about package safety
            
            Args:
                package_name: Name of the package to check
                version: Specific version (optional, checks all versions if not provided)
            
            Returns:
                Dictionary containing:
                - vulnerabilities: List of vulnerability details (CVE, severity, affected versions)
                - vulnerable: Boolean indicating if vulnerabilities exist
                - total_vulnerabilities: Total count of vulnerabilities found
                - critical_count, high_count, medium_count, low_count: Counts by severity
            
            Note: No vulnerabilities doesn't mean a package is perfect, but it's a good security indicator.
            """
            try:
                result = await self.client.check_vulnerabilities(package_name, version)
                return result if isinstance(result, dict) else {"error": str(result)}
            except Exception as e:
                logger.error(f"Error checking vulnerabilities: {e}")
                return {"error": f"Error checking vulnerabilities: {str(e)}"}
        
        @self.mcp_server.tool()
        async def scan_dependency_vulnerabilities(
            package_name: str,
            version: Optional[str] = None,
            max_depth: int = 2,
            include_dev: bool = False
        ) -> Dict[str, Any]:
            """🛡️🔍 Deep scan for vulnerabilities in a package's entire dependency tree.
            
            Goes beyond surface-level checks to analyze transitive dependencies - the hidden
            packages that your dependencies depend on. Crucial for comprehensive security assessment.
            
            Why this matters:
            Many vulnerabilities hide in transitive dependencies. A package might be secure,
            but if it depends on vulnerable packages, your project inherits those risks.
            
            Args:
                package_name: Root package to analyze
                version: Specific version (optional, uses latest if not provided)
                max_depth: How deep to scan dependency tree (default: 2, max: 3)
                include_dev: Include development dependencies (default: False)
            
            Returns:
                Dictionary containing:
                - all_clear: Boolean for quick security status check
                - vulnerable_packages: List of packages with vulnerabilities
                - severity_summary: Breakdown by severity level
                - recommendation: Human-readable security assessment
                - dependency_tree: Full tree for understanding relationships
                
            Best for:
            - Comprehensive security evaluation before adoption
            - Understanding the full security impact of a package
            - Finding hidden vulnerabilities in dependency chains
            """
            try:
                # First get the dependency tree
                tree_result = await self.client.get_dependency_tree(package_name, version, max_depth)
                if "error" in tree_result:
                    return cast(Dict[str, Any], tree_result)
                
                # Track all packages to scan
                packages_to_scan = set()
                vulnerable_packages = []
                total_vulnerabilities = 0
                severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
                
                # Helper to extract packages from tree
                def extract_packages(node, depth=0):
                    if depth > max_depth:
                        return
                    
                    pkg_name = node.get("name", "")
                    pkg_version = node.get("version", "")
                    if pkg_name:
                        packages_to_scan.add((pkg_name, pkg_version))
                    
                    # Process dependencies
                    for dep in node.get("dependencies", []):
                        extract_packages(dep, depth + 1)
                    
                    # Process dev dependencies if requested
                    if include_dev:
                        for dep in node.get("dev_dependencies", []):
                            extract_packages(dep, depth + 1)
                
                # Extract all packages from the tree
                extract_packages(tree_result)
                
                # Check each package for vulnerabilities
                for pkg_name, pkg_version in packages_to_scan:
                    vuln_result = await self.client.check_vulnerabilities(
                        pkg_name, 
                        pkg_version if pkg_version else None
                    )
                    
                    if vuln_result.get("vulnerable", False):
                        vuln_count = vuln_result.get("total_vulnerabilities", 0)
                        total_vulnerabilities += vuln_count
                        
                        # Update severity counts
                        severity_counts["critical"] += vuln_result.get("critical_count", 0)
                        severity_counts["high"] += vuln_result.get("high_count", 0)
                        severity_counts["medium"] += vuln_result.get("medium_count", 0)
                        severity_counts["low"] += vuln_result.get("low_count", 0)
                        
                        vulnerable_packages.append({
                            "package": pkg_name,
                            "version": pkg_version or "latest",
                            "vulnerabilities": vuln_count,
                            "critical": vuln_result.get("critical_count", 0),
                            "high": vuln_result.get("high_count", 0),
                            "summary": vuln_result.get("vulnerabilities", [])[0].get("summary", "") 
                                      if vuln_result.get("vulnerabilities") else ""
                        })
                
                # Sort vulnerable packages by severity
                vulnerable_packages.sort(
                    key=lambda p: (p["critical"], p["high"], p["vulnerabilities"]), 
                    reverse=True
                )
                
                return {
                    "package": f"{package_name} {version or 'latest'}",
                    "total_packages_scanned": len(packages_to_scan),
                    "vulnerable_packages": vulnerable_packages,
                    "total_vulnerabilities": total_vulnerabilities,
                    "severity_summary": severity_counts,
                    "all_clear": len(vulnerable_packages) == 0,
                    "recommendation": (
                        "✅ No vulnerabilities found in dependency tree!" 
                        if len(vulnerable_packages) == 0
                        else f"⚠️ Found {total_vulnerabilities} vulnerabilities in {len(vulnerable_packages)} packages. "
                             f"Review CRITICAL ({severity_counts['critical']}) and HIGH ({severity_counts['high']}) issues first."
                    ),
                    "dependency_tree": tree_result
                }
                
            except Exception as e:
                logger.error(f"Error scanning dependency vulnerabilities: {e}")
                return {"error": f"Error scanning dependencies: {str(e)}"}
        
        @self.mcp_server.tool()
        async def scan_installed_packages(
            environment_path: Optional[str] = None,
            include_system: bool = False,
            output_format: str = "summary"
        ) -> Dict[str, Any]:
            """🛡️💻 Scan installed packages in Python environments for vulnerabilities.
            
            Analyzes your actual installed packages to identify security risks. Automatically
            detects common virtual environment locations or accepts specific paths.
            
            Smart detection includes:
            • Virtual environments (.venv, venv, env, virtualenv)
            • Conda environments
            • Poetry/Pipenv environments
            • System packages (with explicit permission)
            
            Perfect timing:
            ⏰ After installing new packages - catch issues immediately
            ⏰ Before deploying - ensure production safety
            ⏰ During code reviews - verify environment security
            ⏰ Regular audits - catch newly discovered vulnerabilities
            
            Args:
                environment_path: Path to environment (auto-detects if not provided)
                include_system: Include system packages (default: False)
                output_format: "summary" or "detailed" (default: "summary")
            
            Returns:
                Dictionary containing:
                - all_clear: Quick boolean security status
                - vulnerability_summary: Count by severity level
                - top_risks: Most critical packages to fix
                - update_commands: Copy-paste commands for fixes
                - recommendation: Human-readable assessment
            
            Tip: Regular scans catch vulnerabilities discovered after installation.
            """
            try:
                import subprocess
                import json
                import os
                from pathlib import Path
                
                # Auto-detect environment if not specified
                if not environment_path:
                    # Check common virtual environment locations
                    for venv_name in ['.venv', 'venv', 'env', '.env', 'virtualenv']:
                        venv_path = Path.cwd() / venv_name
                        if venv_path.exists() and (venv_path / 'bin' / 'pip').exists():
                            environment_path = str(venv_path)
                            break
                        elif venv_path.exists() and (venv_path / 'Scripts' / 'pip.exe').exists():
                            environment_path = str(venv_path)
                            break
                
                # Determine pip command
                if environment_path:
                    # Virtual environment
                    if os.name == 'nt':  # Windows
                        pip_cmd = os.path.join(environment_path, 'Scripts', 'pip.exe')
                    else:  # Unix-like
                        pip_cmd = os.path.join(environment_path, 'bin', 'pip')
                    env_type = "virtualenv"
                    
                    # Check if it's actually a conda env
                    conda_meta = Path(environment_path) / 'conda-meta'
                    if conda_meta.exists():
                        env_type = "conda"
                else:
                    # System pip
                    pip_cmd = 'pip'
                    env_type = "system"
                
                # Get list of installed packages
                try:
                    result = subprocess.run(
                        [pip_cmd, 'list', '--format=json'],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    installed_packages = json.loads(result.stdout)
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to get package list: {e}")
                    return {
                        "error": {
                            "message": f"Failed to get package list: {str(e)}",
                            "code": "pip_list_error"
                        }
                    }
                
                # Scan each package for vulnerabilities
                vulnerable_packages = []
                total_packages = len(installed_packages)
                critical_count = 0
                high_count = 0
                medium_count = 0
                low_count = 0
                
                for pkg in installed_packages:
                    pkg_name = pkg['name']
                    pkg_version = pkg['version']
                    
                    # Check vulnerabilities for this specific version
                    vuln_result = await self.client.check_vulnerabilities(pkg_name, pkg_version)
                    
                    if vuln_result.get("vulnerable", False):
                        vuln_count = vuln_result.get("total_vulnerabilities", 0)
                        critical = vuln_result.get("critical_count", 0)
                        high = vuln_result.get("high_count", 0)
                        medium = vuln_result.get("medium_count", 0)
                        low = vuln_result.get("low_count", 0)
                        
                        critical_count += critical
                        high_count += high
                        medium_count += medium
                        low_count += low
                        
                        # Get latest safe version
                        latest_version_info = await self.client.get_latest_version(pkg_name)
                        latest_version = latest_version_info.get("version", "unknown")
                        
                        vulnerable_packages.append({
                            "package": pkg_name,
                            "installed_version": pkg_version,
                            "latest_version": latest_version,
                            "vulnerabilities": vuln_count,
                            "critical": critical,
                            "high": high,
                            "medium": medium,
                            "low": low,
                            "summary": vuln_result.get("vulnerabilities", [])[0].get("summary", "") 
                                      if vuln_result.get("vulnerabilities") else "Multiple vulnerabilities found"
                        })
                
                # Sort by severity
                vulnerable_packages.sort(
                    key=lambda p: (p["critical"], p["high"], p["medium"], p["vulnerabilities"]), 
                    reverse=True
                )
                
                # Generate update commands
                update_commands = []
                if vulnerable_packages:
                    if env_type in ["virtualenv", "system"]:
                        # Group updates for efficiency
                        critical_updates = [p for p in vulnerable_packages if p["critical"] > 0]
                        high_updates = [p for p in vulnerable_packages if p["high"] > 0 and p["critical"] == 0]
                        
                        if critical_updates:
                            pkgs = " ".join([f"{p['package']}=={p['latest_version']}" for p in critical_updates[:5]])
                            update_commands.append(f"{pip_cmd} install --upgrade {pkgs}")
                        
                        if high_updates and len(update_commands) < 3:
                            pkgs = " ".join([f"{p['package']}=={p['latest_version']}" for p in high_updates[:5]])
                            update_commands.append(f"{pip_cmd} install --upgrade {pkgs}")
                    
                    elif env_type == "conda":
                        for pkg in vulnerable_packages[:5]:  # Top 5 most critical
                            update_commands.append(f"conda update {pkg['package']}")
                
                # Generate summary
                total_vulnerabilities = critical_count + high_count + medium_count + low_count
                
                return {
                    "environment_type": env_type,
                    "environment_path": environment_path or "system",
                    "python_version": subprocess.run([pip_cmd, '--version'], 
                                                   capture_output=True, text=True).stdout.strip(),
                    "total_packages": total_packages,
                    "vulnerable_packages": vulnerable_packages if output_format == "detailed" else len(vulnerable_packages),
                    "vulnerability_summary": {
                        "total": total_vulnerabilities,
                        "critical": critical_count,
                        "high": high_count,
                        "medium": medium_count,
                        "low": low_count
                    },
                    "top_risks": vulnerable_packages[:10] if output_format == "summary" else [],
                    "all_clear": len(vulnerable_packages) == 0,
                    "recommendation": (
                        f"✅ All {total_packages} packages are secure!" 
                        if len(vulnerable_packages) == 0
                        else f"⚠️ Found {total_vulnerabilities} vulnerabilities in {len(vulnerable_packages)} packages. "
                             f"URGENT: Fix {critical_count} CRITICAL and {high_count} HIGH severity issues!"
                    ),
                    "update_commands": update_commands,
                    "scan_timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Error scanning installed packages: {e}")
                return {"error": f"Error scanning environment: {str(e)}"}
        
        @self.mcp_server.tool()
        async def security_audit_project(
            project_path: Optional[str] = None,
            check_files: bool = True,
            check_installed: bool = True,
            check_transitive: bool = True,
            max_depth: int = 2
        ) -> Dict[str, Any]:
            """🛡️🔍 Comprehensive security audit of an entire Python project.
            
            The most thorough security check available - analyzes every aspect of your
            project's dependencies to provide a complete security assessment with actionable insights.
            
            Unified analysis includes:
            ✓ All dependency files (requirements.txt, pyproject.toml, etc.)
            ✓ Installed packages in detected environments
            ✓ Transitive dependencies (dependencies of dependencies)
            ✓ Version constraints and compatibility
            ✓ Prioritized remediation recommendations
            
            Perfect for critical checkpoints:
            📍 Pre-deployment security verification
            📍 Pull request security reviews
            📍 Periodic security audits
            📍 Compliance documentation
            
            Args:
                project_path: Project root directory (auto-detects if not provided)
                check_files: Analyze dependency files (default: True)
                check_installed: Scan virtual environments (default: True)
                check_transitive: Deep dependency analysis (default: True)
                max_depth: Dependency tree depth (default: 2)
            
            Returns:
                Executive summary with:
                - overall_risk_level: Your security posture (CRITICAL/HIGH/MEDIUM/LOW/SECURE)
                - security_score: 0-100 rating for quick assessment
                - priority_fixes: What to fix first for maximum impact
                - remediation_plan: Step-by-step security improvements
                - estimated_fix_time: Realistic time to resolve issues
                
            💡 Pro tip: Run monthly or before major releases. The security score helps track
            improvement over time. Export results for compliance records.
            """
            try:
                from pathlib import Path
                
                # Auto-detect project path
                if not project_path:
                    project_path = os.getcwd()
                
                project_root = Path(project_path)
                
                # Initialize results
                results = {
                    "project_path": str(project_root),
                    "scan_timestamp": datetime.now().isoformat(),
                    "checks_performed": [],
                    "vulnerabilities_by_source": {},
                    "all_vulnerable_packages": {},
                    "total_vulnerabilities": 0,
                    "severity_breakdown": {
                        "critical": 0,
                        "high": 0,
                        "medium": 0,
                        "low": 0
                    }
                }
                
                # 1. Check requirements.txt files
                if check_files:
                    req_files = list(project_root.glob("**/requirements*.txt"))
                    for req_file in req_files:
                        results["checks_performed"].append(f"requirements.txt: {req_file.name}")
                        req_result = await self.check_requirements_txt(str(req_file))
                        
                        if not req_result.get("error"):
                            vulns = []
                            for req in req_result.get("requirements", []):
                                # Check each requirement for vulnerabilities
                                pkg_name = req.get("package", "")
                                current_version = req.get("current_version", "")
                                if pkg_name and current_version:
                                    vuln_check = await self.client.check_vulnerabilities(pkg_name, current_version)
                                    if vuln_check.get("vulnerable"):
                                        vulns.append({
                                            "package": pkg_name,
                                            "version": current_version,
                                            "vulnerabilities": vuln_check.get("total_vulnerabilities", 0),
                                            "critical": vuln_check.get("critical_count", 0),
                                            "high": vuln_check.get("high_count", 0)
                                        })
                                        
                                        # Track globally
                                        if pkg_name not in results["all_vulnerable_packages"]:
                                            results["all_vulnerable_packages"][pkg_name] = {
                                                "versions_affected": set(),
                                                "sources": [],
                                                "max_severity": "low"
                                            }
                                        results["all_vulnerable_packages"][pkg_name]["versions_affected"].add(current_version)
                                        results["all_vulnerable_packages"][pkg_name]["sources"].append(req_file.name)
                                        
                            results["vulnerabilities_by_source"][req_file.name] = vulns
                
                # 2. Check pyproject.toml
                if check_files:
                    pyproject_files = list(project_root.glob("**/pyproject.toml"))
                    for pyproject in pyproject_files:
                        results["checks_performed"].append(f"pyproject.toml: {pyproject.name}")
                        pyp_result = await self.check_pyproject_toml(str(pyproject))
                        
                        if not pyp_result.get("error"):
                            vulns = []
                            for req in pyp_result.get("requirements", []):
                                pkg_name = req.get("package", "")
                                current_version = req.get("current_version", "")
                                if pkg_name and current_version:
                                    vuln_check = await self.client.check_vulnerabilities(pkg_name, current_version)
                                    if vuln_check.get("vulnerable"):
                                        vulns.append({
                                            "package": pkg_name,
                                            "version": current_version,
                                            "vulnerabilities": vuln_check.get("total_vulnerabilities", 0),
                                            "critical": vuln_check.get("critical_count", 0),
                                            "high": vuln_check.get("high_count", 0)
                                        })
                                        
                                        if pkg_name not in results["all_vulnerable_packages"]:
                                            results["all_vulnerable_packages"][pkg_name] = {
                                                "versions_affected": set(),
                                                "sources": [],
                                                "max_severity": "low"
                                            }
                                        results["all_vulnerable_packages"][pkg_name]["versions_affected"].add(current_version)
                                        results["all_vulnerable_packages"][pkg_name]["sources"].append("pyproject.toml")
                                        
                            results["vulnerabilities_by_source"]["pyproject.toml"] = vulns
                
                # 3. Check installed packages
                if check_installed:
                    results["checks_performed"].append("installed packages")
                    env_result = await self.scan_installed_packages(output_format="detailed")
                    
                    if not env_result.get("error"):
                        results["installed_scan"] = {
                            "environment": env_result.get("environment_type"),
                            "total_packages": env_result.get("total_packages"),
                            "vulnerable_count": len(env_result.get("vulnerable_packages", [])),
                            "vulnerabilities": env_result.get("vulnerability_summary")
                        }
                        
                        # Add to totals
                        for vuln_pkg in env_result.get("vulnerable_packages", []):
                            pkg_name = vuln_pkg["package"]
                            if pkg_name not in results["all_vulnerable_packages"]:
                                results["all_vulnerable_packages"][pkg_name] = {
                                    "versions_affected": set(),
                                    "sources": [],
                                    "max_severity": "low"
                                }
                            results["all_vulnerable_packages"][pkg_name]["versions_affected"].add(
                                vuln_pkg["installed_version"]
                            )
                            results["all_vulnerable_packages"][pkg_name]["sources"].append("installed")
                
                # 4. Check transitive dependencies
                if check_transitive and results["all_vulnerable_packages"]:
                    results["checks_performed"].append("transitive dependencies")
                    # Pick top 3 packages to deep scan
                    top_packages = list(results["all_vulnerable_packages"].keys())[:3]
                    transitive_vulns = {}
                    
                    for pkg in top_packages:
                        trans_result = await self.scan_dependency_vulnerabilities(
                            pkg, 
                            max_depth=max_depth
                        )
                        if not trans_result.get("error"):
                            transitive_vulns[pkg] = trans_result.get("vulnerable_packages", [])
                    
                    results["transitive_scan"] = transitive_vulns
                
                # Calculate totals and risk assessment
                total_critical = 0
                total_high = 0
                total_medium = 0
                total_low = 0
                
                # Sum from all sources
                for source, vulns in results["vulnerabilities_by_source"].items():
                    for v in vulns:
                        total_critical += v.get("critical", 0)
                        total_high += v.get("high", 0)
                        # Rough estimates for medium/low
                        other_vulns = v.get("vulnerabilities", 0) - v.get("critical", 0) - v.get("high", 0)
                        total_medium += other_vulns // 2
                        total_low += other_vulns - (other_vulns // 2)
                
                if "installed_scan" in results:
                    inst_vulns = results["installed_scan"]["vulnerabilities"]
                    total_critical += inst_vulns.get("critical", 0)
                    total_high += inst_vulns.get("high", 0)
                    total_medium += inst_vulns.get("medium", 0)
                    total_low += inst_vulns.get("low", 0)
                
                results["severity_breakdown"] = {
                    "critical": total_critical,
                    "high": total_high,
                    "medium": total_medium,
                    "low": total_low
                }
                results["total_vulnerabilities"] = sum(results["severity_breakdown"].values())
                
                # Determine risk level
                if total_critical > 0:
                    risk_level = "🚨 CRITICAL"
                    risk_color = "red"
                elif total_high > 5:
                    risk_level = "⚠️ HIGH"
                    risk_color = "orange"
                elif total_high > 0 or total_medium > 10:
                    risk_level = "⚠️ MEDIUM"
                    risk_color = "yellow"
                elif results["total_vulnerabilities"] > 0:
                    risk_level = "ℹ️ LOW"
                    risk_color = "blue"
                else:
                    risk_level = "✅ SECURE"
                    risk_color = "green"
                
                # Calculate security score (0-100)
                security_score = 100
                security_score -= total_critical * 20  # Each critical = -20 points
                security_score -= total_high * 10      # Each high = -10 points
                security_score -= total_medium * 3     # Each medium = -3 points
                security_score -= total_low * 1        # Each low = -1 point
                security_score = max(0, security_score)
                
                # Generate remediation plan
                remediation_steps = []
                if total_critical > 0:
                    remediation_steps.append("1. 🚨 IMMEDIATELY update packages with CRITICAL vulnerabilities")
                if total_high > 0:
                    remediation_steps.append("2. ⚠️ Update packages with HIGH vulnerabilities within 24 hours")
                if total_medium > 0:
                    remediation_steps.append("3. 📋 Plan updates for MEDIUM vulnerabilities this week")
                if total_low > 0:
                    remediation_steps.append("4. ℹ️ Review LOW vulnerabilities in next maintenance window")
                
                # Estimate fix time
                fix_time_minutes = (total_critical * 15) + (total_high * 10) + (total_medium * 5) + (total_low * 2)
                if fix_time_minutes < 60:
                    estimated_fix_time = f"{fix_time_minutes} minutes"
                else:
                    estimated_fix_time = f"{fix_time_minutes // 60} hours {fix_time_minutes % 60} minutes"
                
                # Priority fixes (convert sets to lists for JSON serialization)
                priority_fixes = []
                for pkg_name, pkg_info in results["all_vulnerable_packages"].items():
                    pkg_info["versions_affected"] = list(pkg_info["versions_affected"])
                    priority_fixes.append({
                        "package": pkg_name,
                        "affected_versions": pkg_info["versions_affected"],
                        "found_in": pkg_info["sources"]
                    })
                
                # Sort by number of sources (packages used in multiple places are higher priority)
                priority_fixes.sort(key=lambda x: len(x["found_in"]), reverse=True)
                
                return {
                    "overall_risk_level": risk_level,
                    "security_score": security_score,
                    "total_vulnerabilities": results["total_vulnerabilities"],
                    "severity_breakdown": results["severity_breakdown"],
                    "checks_performed": results["checks_performed"],
                    "priority_fixes": priority_fixes[:10],  # Top 10
                    "vulnerabilities_by_source": results["vulnerabilities_by_source"],
                    "installed_environment": results.get("installed_scan", {}),
                    "estimated_fix_time": estimated_fix_time,
                    "remediation_plan": remediation_steps,
                    "recommendation": (
                        f"{risk_level}: Found {results['total_vulnerabilities']} vulnerabilities across your project. "
                        f"Security Score: {security_score}/100. "
                        f"Estimated fix time: {estimated_fix_time}. "
                        + ("URGENT ACTION REQUIRED!" if total_critical > 0 else "Please review and update.")
                    ),
                    "scan_timestamp": results["scan_timestamp"]
                }
                
            except Exception as e:
                logger.error(f"Error in project security audit: {e}")
                return {"error": f"Security audit failed: {str(e)}"}
    
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