"""Prompt templates for common PyPI tasks."""

from __future__ import annotations

from fastmcp import FastMCP


def register_prompts(mcp: FastMCP) -> None:
    """Register prompts with the MCP server."""

    @mcp.prompt(title="Analyze dependencies")
    def analyze_dependencies(package_name: str) -> str:
        """Analyze a package's dependencies for security and freshness."""
        return (
            f"Analyze the dependencies of the PyPI package '{package_name}'.\n"
            f"1. Call get_package for '{package_name}' to read its metadata and "
            "requirements.\n"
            "2. Call check_packages on its dependencies to find outdated or "
            "missing ones.\n"
            "3. Call check_vulnerabilities for the package and any dependency "
            "with a known risk.\n"
            "4. Summarize security issues, outdated pins, and recommended "
            "version updates."
        )

    @mcp.prompt(title="Compare packages")
    def compare_packages(packages: str) -> str:
        """Compare candidate packages and recommend one."""
        return (
            f"Compare these PyPI packages: {packages}.\n"
            "1. Call search_packages if any name is uncertain.\n"
            "2. Call get_package for each to compare maintenance status, "
            "release recency, and dependencies.\n"
            "3. Call check_vulnerabilities on each latest version.\n"
            "4. Recommend one package and explain the trade-offs."
        )
