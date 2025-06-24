#!/usr/bin/env python
"""
MCP-PyPI: Model Context Protocol server for PyPI package information.

This package provides an MCP-compliant server that exposes tools for accessing
PyPI package information, allowing AI assistants to search packages, check dependencies,
and analyze package data in real-time.
"""

# Try to get version from package metadata (single source of truth)
try:
    from importlib.metadata import version

    __version__ = version("mcp-pypi")
except Exception:
    # Fallback during development or if package is not installed
    __version__ = "dev"

__author__ = "Kim Asplund"
__email__ = "kim.asplund@gmail.com"

from mcp_pypi.server import PyPIMCPServer
