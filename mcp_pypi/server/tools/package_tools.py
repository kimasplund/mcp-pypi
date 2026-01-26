"""Package information tools for PyPI MCP Server.

Contains tools for getting package info, releases, versions, metadata,
and version comparisons.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from mcp.types import ToolAnnotations

from mcp_pypi.core.models import (
    ExistsResult,
    MetadataResult,
    ReleasesInfo,
    VersionComparisonResult,
    VersionInfo,
)
from mcp_pypi.utils.common.validation import validate_pagination

if TYPE_CHECKING:
    from mcp_pypi.server import PyPIMCPServer

logger = logging.getLogger("mcp-pypi.server")


def register_package_tools(server: "PyPIMCPServer") -> None:
    """Register package-related tools with the MCP server.

    Args:
        server: The PyPIMCPServer instance to register tools with.
    """

    @server.mcp_server.tool(
        annotations=ToolAnnotations(readOnlyHint=True),
        tags={"package", "info"},
    )
    async def get_package_info(package_name: str) -> Dict[str, Any]:
        """Get comprehensive details about any Python package from PyPI.

        Essential for understanding packages before installation. Returns complete
        metadata including description, license, author, URLs, and classifiers.

        Recommendation: When evaluating packages for use, follow up with
        check_vulnerabilities to ensure security. Quality packages deserve security verification.

        Args:
            package_name (str, required): Exact name of the Python package.
                Must match PyPI package name exactly (case-insensitive).
                Examples: "requests", "django", "numpy", "beautifulsoup4"

        Returns:
            Dict containing:
            - info: Package metadata (description, license, author, etc.)
            - release_count: Number of releases available
            - available_versions: List of recent versions
            - latest_version: Current latest version
            - latest_release_files: Number of distribution files

        Example usage:
            get_package_info("requests")
            -> Returns full metadata for the requests library

        Common errors:
            - "Package not found" - Check spelling and try search_packages first
            - Use exact names: "beautifulsoup4" not "beautifulsoup" or "bs4"
        """
        try:
            full_info = await server.client.get_package_info(package_name)

            if "error" in full_info:
                return cast(Dict[str, Any], full_info)

            info = full_info.get("info", {})
            releases = full_info.get("releases", {})

            condensed = {
                "info": info,
                "release_count": len(releases),
                "available_versions": sorted(releases.keys(), reverse=True)[:10],
                "latest_version": info.get("version", ""),
            }

            latest_version = info.get("version")
            if latest_version and latest_version in releases:
                latest_files = releases[latest_version]
                condensed["latest_release_files"] = len(latest_files)
                condensed["latest_release_types"] = list(
                    set(f.get("packagetype", "unknown") for f in latest_files)
                )

            return condensed

        except Exception as e:
            logger.error(f"Error getting package info: {e}")
            return {"error": {"message": str(e), "code": "package_info_error"}}

    @server.mcp_server.tool(
        annotations=ToolAnnotations(readOnlyHint=True),
        tags={"package", "releases"},
    )
    async def get_package_releases(
        package_name: str,
        limit: int = 10,
        offset: int = 0,
        sort: str = "version_desc",
    ) -> Dict[str, Any]:
        """Get detailed release information for a specific package with pagination.

        Provides full release data for packages when needed. Use this after
        get_package_info to explore specific versions in detail.

        Args:
            package_name: Name of the Python package
            limit: Maximum number of releases to return (default: 10)
            offset: Number of releases to skip for pagination (default: 0)
            sort: Sort order for releases. Options:
                - "version_desc" (default): Newest versions first
                - "version_asc": Oldest versions first
                - "date_desc": Most recent release date first
                - "date_asc": Oldest release date first

        Returns:
            Dictionary with release versions and their file details, plus pagination info
        """
        try:
            # Validate pagination parameters
            limit, offset = validate_pagination(limit, offset, max_limit=100)

            full_info = await server.client.get_package_info(package_name)

            if "error" in full_info:
                return cast(Dict[str, Any], full_info)

            releases = full_info.get("releases", {})

            if sort == "version_asc":
                sorted_versions = sorted(releases.keys(), reverse=False)
            elif sort == "date_desc":

                def get_upload_time(version: str) -> str:
                    files = releases.get(version, [])
                    if files:
                        return files[0].get("upload_time", "")
                    return ""

                sorted_versions = sorted(
                    releases.keys(), key=get_upload_time, reverse=True
                )
            elif sort == "date_asc":

                def get_upload_time_asc(version: str) -> str:
                    files = releases.get(version, [])
                    if files:
                        return files[0].get("upload_time", "")
                    return ""

                sorted_versions = sorted(
                    releases.keys(), key=get_upload_time_asc, reverse=False
                )
            else:
                sorted_versions = sorted(releases.keys(), reverse=True)

            total = len(sorted_versions)
            paginated_versions = sorted_versions[offset : offset + limit]

            limited_releases = {
                version: releases[version] for version in paginated_versions
            }

            return {
                "package_name": package_name,
                "total_releases": total,
                "returned_releases": len(limited_releases),
                "releases": limited_releases,
                "offset": offset,
                "limit": limit,
                "has_more": (offset + limit) < total,
                "sort": sort,
            }

        except Exception as e:
            logger.error(f"Error getting package releases: {e}")
            return {"error": {"message": str(e), "code": "releases_error"}}

    @server.mcp_server.tool(
        annotations=ToolAnnotations(readOnlyHint=True),
        tags={"package", "version"},
    )
    async def get_latest_version(package_name: str) -> VersionInfo:
        """Check the latest version of any Python package on PyPI.

        Instantly see if updates are available. Essential for keeping projects
        current, secure, and compatible with the latest features.

        Args:
            package_name: Name of the Python package

        Returns:
            VersionInfo with latest stable version and release date
        """
        try:
            return await server.client.get_latest_version(package_name)
        except Exception as e:
            logger.error(f"Error getting latest version: {e}")
            return {
                "package_name": package_name,
                "version": "",
                "error": {"message": str(e), "code": "version_error"},
            }

    @server.mcp_server.tool(
        annotations=ToolAnnotations(readOnlyHint=True),
        tags={"package", "validation"},
    )
    async def check_package_exists(package_name: str) -> ExistsResult:
        """Check if a package exists on PyPI.

        Args:
            package_name: Name of the package

        Returns:
            ExistsResult indicating whether the package exists
        """
        try:
            return await server.client.check_package_exists(package_name)
        except Exception as e:
            logger.error(f"Error checking package existence: {e}")
            return {
                "package_name": package_name,
                "exists": False,
                "error": {"message": str(e), "code": "exists_error"},
            }

    @server.mcp_server.tool(
        annotations=ToolAnnotations(readOnlyHint=True),
        tags={"package", "metadata"},
    )
    async def get_package_metadata(
        package_name: str, version: Optional[str] = None
    ) -> MetadataResult:
        """Get metadata for a package.

        Args:
            package_name: Name of the package
            version: Specific version (optional, defaults to latest)

        Returns:
            MetadataResult with package metadata
        """
        try:
            return await server.client.get_package_metadata(package_name, version)
        except Exception as e:
            logger.error(f"Error getting package metadata: {e}")
            return {
                "package_name": package_name,
                "version": version or "latest",
                "metadata": {},
                "error": {"message": str(e), "code": "metadata_error"},
            }

    @server.mcp_server.tool(
        annotations=ToolAnnotations(readOnlyHint=True),
        tags={"package", "versions"},
    )
    async def list_package_versions(package_name: str) -> ReleasesInfo:
        """List all available versions of a package.

        Args:
            package_name: Name of the package

        Returns:
            ReleasesInfo with all available versions
        """
        try:
            return await server.client.get_package_releases(package_name)
        except Exception as e:
            logger.error(f"Error listing package versions: {e}")
            return {
                "package_name": package_name,
                "releases": [],
                "error": {"message": str(e), "code": "versions_error"},
            }

    @server.mcp_server.tool(
        annotations=ToolAnnotations(readOnlyHint=True),
        tags={"package", "comparison"},
    )
    async def compare_versions(
        package_name: str, version1: str, version2: str
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
            return await server.client.compare_versions(
                package_name, version1, version2
            )
        except Exception as e:
            logger.error(f"Error comparing versions: {e}")
            return {
                "package_name": package_name,
                "version1": version1,
                "version2": version2,
                "comparison": "error",
                "error": {"message": str(e), "code": "comparison_error"},
            }
