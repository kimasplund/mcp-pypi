"""
CLI package for MCP-PyPI.
"""

from mcp_pypi.cli.main import app, entry_point
from mcp_pypi.cli.server import RPCServer, start_server

__all__ = ["app", "entry_point", "RPCServer", "start_server"]
