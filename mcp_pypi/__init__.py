#!/usr/bin/env python
"""
MCP-PyPI: Model Context Protocol server for PyPI package information.

This package provides an MCP-compliant server that exposes tools for accessing
PyPI package information, allowing AI assistants to search packages, check dependencies,
and analyze package data in real-time.
"""

__version__ = "2.0.1"
__author__ = "Kim Asplund"
__email__ = "kim.asplund@gmail.com"

from mcp_pypi.server import PyPIMCPServer
