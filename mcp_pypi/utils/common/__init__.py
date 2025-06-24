"""
Common utilities module for MCP-PyPI.

This module contains shared functionality used across the MCP-PyPI codebase.
It helps reduce code duplication and improve maintainability.
"""

from mcp_pypi.utils.common.constants import (DEFAULT_CACHE_DIR,
                                             DEFAULT_CACHE_MAX_SIZE,
                                             DEFAULT_CACHE_TTL, USER_AGENT,
                                             ErrorCode)
from mcp_pypi.utils.common.error_handling import (format_error,
                                                  handle_client_error)
# Import public components for easier access
from mcp_pypi.utils.common.validation import (sanitize_package_name,
                                              sanitize_version)

__all__ = [
    "sanitize_package_name",
    "sanitize_version",
    "format_error",
    "handle_client_error",
    "ErrorCode",
    "USER_AGENT",
    "DEFAULT_CACHE_DIR",
    "DEFAULT_CACHE_TTL",
    "DEFAULT_CACHE_MAX_SIZE",
]
