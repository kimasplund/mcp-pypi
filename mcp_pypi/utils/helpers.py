"""
Helper utility functions for the MCP-PyPI client.
"""

import re


def sanitize_package_name(package_name: str) -> str:
    """Sanitize package name for use in URLs."""
    # Only allow alphanumeric chars, dash, underscore, and dot
    if not re.match(r"^[a-zA-Z0-9._-]+$", package_name):
        raise ValueError(f"Invalid package name: {package_name}")
    return package_name


def sanitize_version(version: str) -> str:
    """Sanitize version for use in URLs."""
    # Only allow valid version characters
    if not re.match(r"^[a-zA-Z0-9._+\-]+$", version):
        raise ValueError(f"Invalid version: {version}")
    return version
