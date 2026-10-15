"""
Validation utilities for MCP-PyPI.

Name normalization and file-path checks. URL-safe name/version sanitizing lives in
`mcp_pypi.utils.sanitize`.
"""

import re


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


def validate_file_path(file_path: str) -> tuple[bool, str | None]:
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
