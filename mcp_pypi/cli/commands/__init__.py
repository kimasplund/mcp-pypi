"""
Command modules for the MCP-PyPI CLI.

This module re-exports all command apps for convenience.
"""

from mcp_pypi.cli.commands.cache_commands import cache_app
from mcp_pypi.cli.commands.feed_commands import feed_app
from mcp_pypi.cli.commands.package_commands import package_app, stats_app
from mcp_pypi.cli.commands.search_commands import search_packages

__all__ = [
    "cache_app",
    "feed_app",
    "package_app",
    "stats_app",
    "search_packages",
]
