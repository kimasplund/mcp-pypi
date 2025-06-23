"""
Validation utilities for MCP-PyPI.

This module contains functions for validating and sanitizing inputs
to ensure they are safe for use in PyPI requests.
"""

import re
from typing import Optional, Tuple


def sanitize_package_name(package_name: str) -> str:
    """
    Sanitize a package name for use in URLs.

    Args:
        package_name: The raw package name

    Returns:
        The sanitized package name

    Raises:
        ValueError: If the package name contains invalid characters
    """
    # Only allow valid package name characters
    if not re.match(r"^[a-zA-Z0-9._-]+$", package_name):
        raise ValueError(f"Invalid package name: {package_name}")
    return package_name


def sanitize_version(version: str) -> str:
    """
    Sanitize a version string for use in URLs.

    Args:
        version: The raw version string

    Returns:
        The sanitized version string

    Raises:
        ValueError: If the version contains invalid characters
    """
    # Only allow valid version characters
    if not re.match(r"^[a-zA-Z0-9._+\-]+$", version):
        raise ValueError(f"Invalid version: {version}")
    return version


def validate_file_path(file_path: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a file path for security.

    Args:
        file_path: The file path to validate

    Returns:
        A tuple of (is_valid, error_message)
    """
    # Basic validation - could be expanded for more security
    if not file_path:
        return False, "File path cannot be empty"

    # Check for directory traversal attempts
    if ".." in file_path:
        return False, "Directory traversal not allowed"

    return True, None
