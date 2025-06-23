"""
Constants used throughout the MCP-PyPI codebase.

Centralizing constants helps reduce code duplication and makes
maintenance easier.
"""

import os
import tempfile
from pathlib import Path

# Try to get version from package metadata
try:
    from importlib.metadata import version
    __version__ = version("mcp-pypi")
except Exception:
    # Fallback if package is not installed or during development
    __version__ = "dev"

# User agent for API requests
USER_AGENT = f"MCP-PyPI/{__version__} (+https://github.com/kimasplund/mcp-pypi)"

# Cache settings
DEFAULT_CACHE_DIR = os.path.join(Path.home(), ".cache", "mcp-pypi")
DEFAULT_CACHE_TTL = 604800  # 1 week in seconds
DEFAULT_CACHE_MAX_SIZE = 100 * 1024 * 1024  # 100 MB

# API settings
DEFAULT_API_TIMEOUT = 10  # seconds
DEFAULT_API_RETRIES = 3

# Rate limiting
DEFAULT_RATE_LIMIT = 10  # requests per second


class ErrorCode:
    """Error codes for MCP-PyPI errors."""

    NOT_FOUND = "not_found"
    INVALID_INPUT = "invalid_input"
    NETWORK_ERROR = "network_error"
    PARSE_ERROR = "parse_error"
    FILE_ERROR = "file_error"
    PERMISSION_ERROR = "permission_error"
    UNKNOWN_ERROR = "unknown_error"
