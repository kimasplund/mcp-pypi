"""Tool registration modules for PyPI MCP Server.

This package contains modular tool registration functions that are called
by the main PyPIMCPServer to register all available MCP tools.
"""

from mcp_pypi.server.tools.audit_tools import register_audit_tools
from mcp_pypi.server.tools.dependency_tools import register_dependency_tools
from mcp_pypi.server.tools.file_tools import register_file_tools
from mcp_pypi.server.tools.package_tools import register_package_tools
from mcp_pypi.server.tools.search_tools import register_search_tools
from mcp_pypi.server.tools.vulnerability_tools import register_vulnerability_tools

# Shared MCP tool annotations: every tool is a read-only PyPI/OSV lookup.
TOOL_ANNOTATIONS: dict[str, bool] = {
    "readOnlyHint": True,
    "idempotentHint": True,
    "openWorldHint": True,
}

__all__ = [
    "TOOL_ANNOTATIONS",
    "register_package_tools",
    "register_search_tools",
    "register_dependency_tools",
    "register_vulnerability_tools",
    "register_audit_tools",
    "register_file_tools",
]
