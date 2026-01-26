"""Dependency tools for PyPI MCP Server.

Contains tools for analyzing package dependencies and dependency trees.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from mcp.types import ToolAnnotations

from mcp_pypi.core.models import DependenciesResult, DependencyTreeResult
from mcp_pypi.utils.common.validation import validate_depth

if TYPE_CHECKING:
    from mcp_pypi.server import PyPIMCPServer

logger = logging.getLogger("mcp-pypi.server")


def register_dependency_tools(server: "PyPIMCPServer") -> None:
    """Register dependency-related tools with the MCP server.

    Args:
        server: The PyPIMCPServer instance to register tools with.
    """

    @server.mcp_server.tool(
        annotations=ToolAnnotations(readOnlyHint=True),
        tags={"dependencies", "info"},
    )
    async def get_dependencies(
        package_name: str, version: Optional[str] = None
    ) -> DependenciesResult:
        """Analyze Python package dependencies from PyPI.

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
            return await server.client.get_dependencies(package_name, version)
        except Exception as e:
            logger.error(f"Error getting dependencies: {e}")
            return {
                "package": package_name,
                "version": version or "latest",
                "install_requires": [],
                "extras_require": {},
                "error": {"message": str(e), "code": "dependencies_error"},
            }

    @server.mcp_server.tool(
        annotations=ToolAnnotations(readOnlyHint=True),
        tags={"dependencies", "tree"},
    )
    async def get_dependency_tree(
        package_name: str,
        version: Optional[str] = None,
        max_depth: int = 3,
        max_width: int = 50,
    ) -> DependencyTreeResult:
        """Get the full dependency tree for a package.

        Args:
            package_name: Name of the package
            version: Specific version (optional, defaults to latest)
            max_depth: Maximum depth to traverse (default: 3)
            max_width: Maximum dependencies to include per level (default: 50).
                Helps prevent excessive output for packages with many dependencies.

        Returns:
            DependencyTreeResult with nested dependency structure
        """
        try:
            # Validate depth parameter (clamp to 1-5 for safety)
            max_depth = validate_depth(max_depth, max_depth=5)
            # Also validate max_width (clamp to 1-100)
            max_width = max(1, min(max_width, 100))

            return await server.client.get_dependency_tree(
                package_name, version, depth=max_depth, max_width=max_width
            )
        except Exception as e:
            logger.error(f"Error getting dependency tree: {e}")
            return {
                "package": package_name,
                "version": version or "latest",
                "error": {"message": str(e), "code": "dependency_tree_error"},
            }
