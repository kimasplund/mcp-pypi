"""
Utility functions for the MCP-PyPI client.
"""

import logging
from typing import Dict, Any

from mcp_pypi.core.models import ErrorCode, format_error
from mcp_pypi.utils.helpers import sanitize_package_name, sanitize_version

# Set up logging
logger = logging.getLogger("mcp-pypi")

def configure_logging(
    level: int = logging.INFO,
    format_str: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    file_path: str = None
) -> None:
    """Configure logging for the MCP-PyPI client.
    
    Args:
        level: The logging level (default: INFO)
        format_str: The logging format string
        file_path: Optional file path for logging to a file
    """
    handlers = []
    
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(format_str))
    handlers.append(console_handler)
    
    # Add file handler if file_path is provided and is a valid string
    if file_path and isinstance(file_path, str):
        try:
            file_handler = logging.FileHandler(file_path)
            file_handler.setFormatter(logging.Formatter(format_str))
            handlers.append(file_handler)
        except Exception as e:
            # Use print to stderr directly since logger might not be configured yet
            import sys
            print(f"Failed to create file handler for {file_path}: {e}", file=sys.stderr)
    
    # Configure the logger
    logger.setLevel(level)
    
    # Remove existing handlers and add new ones
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    for handler in handlers:
        logger.addHandler(handler)
    
    logger.debug("Logging configured")
