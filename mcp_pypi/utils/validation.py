"""
Validation utilities for MCP-PyPI.

This module contains functions for validating and sanitizing inputs
to ensure they are safe for use in PyPI requests.
"""

import re
from typing import Any, Dict, Optional, Tuple


def normalize_package_name(name: str) -> str:
    """Normalize package name per PEP 503.

    Converts to lowercase and replaces any runs of [-_.] with a single hyphen.

    Args:
        name: Package name to normalize

    Returns:
        Normalized package name

    Examples:
        >>> normalize_package_name("Beautiful-Soup")
        'beautiful-soup'
        >>> normalize_package_name("Django_REST_framework")
        'django-rest-framework'
        >>> normalize_package_name("requests")
        'requests'
    """
    return re.sub(r"[-_.]+", "-", name.lower())


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


def validate_pagination(
    limit: int,
    offset: int,
    max_limit: int = 100,
    min_limit: int = 1,
) -> Tuple[int, int]:
    """
    Validate and clamp pagination parameters.

    Args:
        limit: Requested limit (will be clamped to min_limit..max_limit)
        offset: Requested offset (will be clamped to >= 0)
        max_limit: Maximum allowed limit (default: 100)
        min_limit: Minimum allowed limit (default: 1)

    Returns:
        A tuple of (validated_limit, validated_offset)
    """
    validated_limit = max(min_limit, min(limit, max_limit))
    validated_offset = max(0, offset)
    return validated_limit, validated_offset


def validate_depth(depth: int, max_depth: int = 5, min_depth: int = 1) -> int:
    """
    Validate and clamp depth parameter for tree operations.

    Args:
        depth: Requested depth
        max_depth: Maximum allowed depth (default: 5)
        min_depth: Minimum allowed depth (default: 1)

    Returns:
        Validated depth clamped to min_depth..max_depth
    """
    return max(min_depth, min(depth, max_depth))


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


def make_error_response(message: str, code: str = "error") -> Dict[str, Any]:
    """Create a standardized error response.

    Args:
        message: Human-readable error message
        code: Error code for programmatic handling

    Returns:
        Standardized error dict: {"error": {"message": ..., "code": ...}}
    """
    return {"error": {"message": message, "code": code}}
