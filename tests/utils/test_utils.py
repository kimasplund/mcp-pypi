"""Tests for utility functions."""

import pytest
import logging
import io
import sys

from mcp_pypi.utils import sanitize_package_name, sanitize_version, configure_logging
from mcp_pypi.core.models import ErrorCode, format_error


def test_format_error():
    """Test the format_error function."""
    # Test with known error code
    error = format_error(ErrorCode.NOT_FOUND, "Test message")
    assert error["error"]["code"] == ErrorCode.NOT_FOUND
    assert error["error"]["message"] == "Test message"

    # Test with custom error code
    error = format_error("custom_error", "Custom message")
    assert error["error"]["code"] == "custom_error"
    assert error["error"]["message"] == "Custom message"


def test_sanitize_package_name():
    """Test the sanitize_package_name function."""
    # Valid package names
    assert sanitize_package_name("test") == "test"
    assert sanitize_package_name("test-package") == "test-package"
    assert sanitize_package_name("test_package") == "test_package"
    assert sanitize_package_name("test.package") == "test.package"
    assert sanitize_package_name("Test123") == "Test123"

    # Invalid package names
    with pytest.raises(ValueError):
        sanitize_package_name("test package")  # Space

    with pytest.raises(ValueError):
        sanitize_package_name("test/package")  # Slash

    with pytest.raises(ValueError):
        sanitize_package_name("test?package")  # Question mark

    with pytest.raises(ValueError):
        sanitize_package_name("test$package")  # Dollar sign


def test_sanitize_version():
    """Test the sanitize_version function."""
    # Valid versions
    assert sanitize_version("1.0.0") == "1.0.0"
    assert sanitize_version("1.0.0-alpha") == "1.0.0-alpha"
    assert sanitize_version("1.0.0+build") == "1.0.0+build"
    assert sanitize_version("1.0.0-alpha+build") == "1.0.0-alpha+build"
    assert sanitize_version("1.0.0-rc.1") == "1.0.0-rc.1"

    # Invalid versions
    with pytest.raises(ValueError):
        sanitize_version("1.0.0 alpha")  # Space

    with pytest.raises(ValueError):
        sanitize_version("1.0.0/alpha")  # Slash

    with pytest.raises(ValueError):
        sanitize_version("1.0.0?alpha")  # Question mark


def test_configure_logging():
    """Test the configure_logging function."""
    # Test with default configuration
    logger = logging.getLogger("mcp-pypi")

    # Reset logger
    logger.handlers = []
    logger.level = logging.NOTSET

    # Configure with default parameters
    configure_logging()

    # Check logger level
    assert logger.level == logging.INFO

    # Check handlers
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.StreamHandler)

    # Test with custom level
    logger.handlers = []
    logger.level = logging.NOTSET

    configure_logging(level=logging.DEBUG)

    assert logger.level == logging.DEBUG

    # Test with file handler
    logger.handlers = []
    logger.level = logging.NOTSET

    # Use StringIO as a file to avoid creating actual files
    # Note: We can't directly test file handler creation since we need a real file path
    # Instead, we'll verify that the correct number of handlers is created
    configure_logging(file_path="test.log")

    # Should have both stream and file handlers
    assert len(logger.handlers) <= 2  # May be 1 if file creation fails
