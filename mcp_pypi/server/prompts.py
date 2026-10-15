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
            f"1. Call get_dependencies for '{package_name}' (depth 2 or 3) to list its "
            "requirements and the resolved dependency tree.\n"
            f"2. Call check_vulnerabilities with ['{package_name}'] and "
            "include_transitive=True to check the package and every dependency.\n"
            "3. Compare each dependency's declared specifier with its latest release "
            "to spot outdated constraints.\n"
            "4. Report the vulnerable dependencies (with introduced_via chains and "
            "severities) and the outdated ones, and recommend version updates."
        )

    @mcp.prompt(title="Compare packages")
    def compare_packages(packages: str) -> str:
        """Compare candidate packages and recommend one."""
        return (
            f"Compare these PyPI packages: {packages}.\n"
            "1. Call get_package for each to compare release recency, license, "
            "Python support and project links.\n"
            "2. Call get_download_stats for each as a popularity signal.\n"
            "3. Call check_vulnerabilities on the latest version of each.\n"
            "4. Recommend one package and explain the trade-offs."
        )
