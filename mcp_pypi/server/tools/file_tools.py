"""File-based tools for PyPI MCP Server.

Contains tools for checking requirements.txt, pyproject.toml,
and other file-based package operations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

from mcp.types import ToolAnnotations

from mcp_pypi.core.models import DocumentationResult, PackageRequirementsResult, StatsResult

if TYPE_CHECKING:
    from mcp_pypi.server import PyPIMCPServer

logger = logging.getLogger("mcp-pypi.server")


def register_file_tools(server: "PyPIMCPServer") -> None:
    """Register file-related tools with the MCP server.

    Args:
        server: The PyPIMCPServer instance to register tools with.
    """

    @server.mcp_server.tool(
        annotations=ToolAnnotations(readOnlyHint=True),
        tags={"file", "requirements"},
    )
    async def check_requirements_txt(file_path: str) -> PackageRequirementsResult:
        """Analyze requirements.txt for outdated packages and security issues.

        Audits your project dependencies to identify outdated packages and potential
        security vulnerabilities. Helps maintain healthy, secure dependency management.

        Provides insights on:
        - Version currency - how outdated are your packages?
        - Security status - any known vulnerabilities?
        - Update priority - which updates are most important?
        - Compatibility - will updates break your project?

        Args:
            file_path (str, required): Absolute path to requirements.txt file.
                Must be a complete path from root directory.
                Examples:
                - Linux/Mac: "/home/user/project/requirements.txt"
                - Windows: "C:\\Users\\user\\project\\requirements.txt"
                - WSL: "/mnt/c/Users/user/project/requirements.txt"

        Returns:
            PackageRequirementsResult containing:
            - outdated: List of packages that need updates
            - up_to_date: List of current packages
            - Each package includes: name, current_version, latest_version, constraint
            - error: Error details if file cannot be read or parsed

        Example usage:
            check_requirements_txt("/home/john/myapp/requirements.txt")
            -> Returns analysis of all packages in the requirements file

        Tip: Run before deployments and as part of regular maintenance.
        Consider using with scan_dependency_vulnerabilities for deeper analysis.

        IMPORTANT ACTIONS AFTER RUNNING THIS TOOL:
        1. If vulnerabilities found -> UPDATE constraints in this file
        2. Check OTHER dependency files -> pyproject.toml, setup.py, setup.cfg
        3. Ensure CONSISTENCY -> All files should have matching constraints

        DEPENDENCY FILE HIERARCHY:
        - pyproject.toml is the PRIMARY source (modern standard)
        - requirements.txt is SECONDARY (often generated from pyproject.toml)
        - setup.py/setup.cfg are LEGACY (should mirror pyproject.toml)

        If pyproject.toml exists in the project:
        1. Check if it's more authoritative (has [project] section)
        2. Consider updating pyproject.toml FIRST, then sync to other files
        3. Ensure requirements.txt doesn't have stricter constraints

        Common errors:
            - "File not found" - Ensure you use the full absolute path
            - "Invalid format" - Check requirements.txt syntax
        """
        return await _check_requirements_txt_impl(server, file_path)

    @server.mcp_server.tool(
        annotations=ToolAnnotations(readOnlyHint=True),
        tags={"file", "pyproject"},
    )
    async def check_pyproject_toml(file_path: str) -> PackageRequirementsResult:
        """Analyze pyproject.toml for outdated packages and security issues.

        Modern Python projects use pyproject.toml for dependency management. This tool
        audits all dependency groups to ensure security and currency.

        Comprehensive coverage:
        - [project.dependencies] - main dependencies
        - [project.optional-dependencies] - extras like dev, test, docs
        - Poetry/PDM style configurations
        - Version constraints and compatibility

        Args:
            file_path: Absolute path to pyproject.toml file
                     (e.g., /home/user/project/pyproject.toml)

        Returns:
            PackageRequirementsResult with:
            - Analysis of all dependency groups
            - Security status for each package
            - Update recommendations by priority
            - Constraint compatibility warnings

        Works with all modern Python packaging tools (pip, poetry, pdm, hatch).

        IMPORTANT ACTIONS AFTER RUNNING THIS TOOL:
        1. If vulnerabilities found -> UPDATE constraints in THIS file FIRST
        2. TRICKLE DOWN changes -> Update requirements.txt, setup.py, setup.cfg
        3. Ensure CONSISTENCY -> All files should have matching constraints

        PYPROJECT.TOML IS THE PRIMARY SOURCE:
        - This is the modern Python standard (PEP 621)
        - Other files should be generated from or match this file
        - When updating dependencies, start here then propagate changes

        UPDATE WORKFLOW:
        1. Update pyproject.toml with secure versions
        2. If requirements.txt exists -> Update to match or regenerate
        3. If setup.py exists -> Update install_requires to match
        4. If setup.cfg exists -> Update to match (or consider removing)
        5. Commit with message: "chore: Update dependencies for security (all files)"

        Note: Always use absolute paths, not relative paths like "pyproject.toml"
        """
        return await _check_pyproject_toml_impl(server, file_path)

    @server.mcp_server.tool(
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
        tags={"package", "documentation"},
    )
    async def get_package_documentation(package_name: str) -> DocumentationResult:
        """Get documentation links for a package.

        Args:
            package_name: Name of the package

        Returns:
            DocumentationResult with documentation URLs
        """
        try:
            return await server.client.get_documentation_url(package_name)
        except Exception as e:
            logger.error(f"Error getting package documentation: {e}")
            return {
                "package_name": package_name,
                "documentation_url": None,
                "error": {"message": str(e), "code": "documentation_error"},
            }

    @server.mcp_server.tool(
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
        tags={"package", "changelog"},
    )
    async def get_package_changelog(
        package_name: str, version: Optional[str] = None
    ) -> str:
        """Get changelog for a package.

        Args:
            package_name: Name of the package
            version: Specific version (optional, defaults to latest)

        Returns:
            Changelog text or error message
        """
        try:
            result = await server.client.get_package_changelog(package_name, version)
            return result if isinstance(result, str) else "No changelog available"
        except Exception as e:
            logger.error(f"Error getting package changelog: {e}")
            return f"Error getting changelog: {str(e)}"

    @server.mcp_server.tool(
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
        tags={"package", "stats"},
    )
    async def get_package_stats(package_name: str) -> StatsResult:
        """Get PyPI download statistics to gauge package popularity.

        Make informed decisions using real usage data from the Python community.
        Compare alternatives and track adoption trends over time.

        Args:
            package_name: Name of the Python package

        Returns:
            StatsResult with daily, weekly, and monthly download counts
        """
        try:
            return await server.client.get_package_stats(package_name)
        except Exception as e:
            logger.error(f"Error getting package stats: {e}")
            return {
                "package_name": package_name,
                "downloads": {},
                "error": {"message": str(e), "code": "stats_error"},
            }


async def _check_requirements_txt_impl(
    server: "PyPIMCPServer", file_path: str
) -> PackageRequirementsResult:
    """Internal implementation of check_requirements_txt."""
    try:
        return await server.client.check_requirements_file(file_path)
    except Exception as e:
        logger.error(f"Error checking requirements.txt: {e}")
        return {
            "file_path": file_path,
            "requirements": [],
            "error": {"message": str(e), "code": "requirements_error"},
        }


async def _check_pyproject_toml_impl(
    server: "PyPIMCPServer", file_path: str
) -> PackageRequirementsResult:
    """Internal implementation of check_pyproject_toml."""
    try:
        return await server.client.check_requirements_file(file_path)
    except Exception as e:
        logger.error(f"Error checking pyproject.toml: {e}")
        return {
            "file_path": file_path,
            "requirements": [],
            "error": {"message": str(e), "code": "pyproject_error"},
        }
