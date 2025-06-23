"""
Error handling utilities for MCP-PyPI.

This module provides standardized error handling and formatting
to ensure consistent error responses throughout the codebase.
"""

import traceback
import logging
from typing import Any, Callable, Dict, Optional, TypeVar, cast
from functools import wraps

from mcp_pypi.utils.common.constants import ErrorCode

# Type variables for function signatures
T = TypeVar("T")
R = TypeVar("R")

# Set up logger
logger = logging.getLogger("mcp-pypi.error-handling")


def format_error(error_code: str, message: str) -> Dict[str, Any]:
    """
    Format an error response in a standardized way.

    Args:
        error_code: A code identifying the error type
        message: A human-readable error message

    Returns:
        A dictionary containing the error details
    """
    return {"error": {"code": error_code, "message": message}}


def handle_client_error(func_name: str, error: Exception) -> Dict[str, Any]:
    """
    Handle client-side errors in a standardized way.

    Args:
        func_name: The name of the function where the error occurred
        error: The exception that was raised

    Returns:
        A formatted error response
    """
    error_msg = str(error)
    error_type = type(error).__name__

    logger.error(f"Error in {func_name}: {error_type} - {error_msg}")
    logger.debug(traceback.format_exc())

    if isinstance(error, ValueError):
        return format_error(ErrorCode.INVALID_INPUT, error_msg)
    elif isinstance(error, (ConnectionError, TimeoutError)):
        return format_error(ErrorCode.NETWORK_ERROR, error_msg)
    elif isinstance(error, FileNotFoundError):
        return format_error(ErrorCode.FILE_ERROR, error_msg)
    elif isinstance(error, PermissionError):
        return format_error(ErrorCode.PERMISSION_ERROR, error_msg)
    else:
        return format_error(ErrorCode.UNKNOWN_ERROR, f"{error_type}: {error_msg}")


def error_handler(result_type: Any) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """
    Decorator for standardized error handling.

    Args:
        result_type: The type to cast the error result to

    Returns:
        Decorated function with standardized error handling
    """

    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> R:
            try:
                return await func(*args, **kwargs)  # type: ignore[misc]
            except Exception as e:
                func_name = func.__name__
                error_result = handle_client_error(func_name, e)
                return cast(R, error_result)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> R:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                func_name = func.__name__
                error_result = handle_client_error(func_name, e)
                return cast(R, error_result)

        if asyncio := func.__code__.co_flags & 0x80:  # Check if it's an async function
            return cast(Callable[..., R], async_wrapper)
        return cast(Callable[..., R], sync_wrapper)

    return decorator
