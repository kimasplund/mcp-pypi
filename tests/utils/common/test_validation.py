"""Tests for validation utilities."""

import pytest

from mcp_pypi.utils.common.validation import (
    sanitize_package_name,
    sanitize_version,
    validate_file_path,
)


class TestSanitizePackageName:
    """Tests for sanitize_package_name function."""

    def test_valid_package_name(self):
        """Test that valid package names pass through."""
        assert sanitize_package_name("requests") == "requests"
        assert sanitize_package_name("Flask") == "Flask"
        assert sanitize_package_name("my-package") == "my-package"
        assert sanitize_package_name("my_package") == "my_package"
        assert sanitize_package_name("package123") == "package123"
        assert sanitize_package_name("my.package") == "my.package"

    def test_invalid_package_name_raises(self):
        """Test that invalid package names raise ValueError."""
        with pytest.raises(ValueError):
            sanitize_package_name("package;rm -rf /")

        with pytest.raises(ValueError):
            sanitize_package_name("package`whoami`")

        with pytest.raises(ValueError):
            sanitize_package_name("../../../etc/passwd")

        with pytest.raises(ValueError):
            sanitize_package_name("package\x00name")


class TestSanitizeVersion:
    """Tests for sanitize_version function."""

    def test_valid_version(self):
        """Test that valid versions pass through."""
        assert sanitize_version("1.0.0") == "1.0.0"
        assert sanitize_version("2.3.4a1") == "2.3.4a1"
        assert sanitize_version("1.0.0+local") == "1.0.0+local"
        assert sanitize_version("1.0.0-beta.1") == "1.0.0-beta.1"

    def test_invalid_version_raises(self):
        """Test that invalid versions raise ValueError."""
        with pytest.raises(ValueError):
            sanitize_version("1.0.0;cat /etc/passwd")

        with pytest.raises(ValueError):
            sanitize_version("1.0.0`whoami`")


class TestValidateFilePath:
    """Tests for validate_file_path function."""

    def test_valid_absolute_path(self):
        """Test that valid absolute paths pass validation."""
        is_valid, error = validate_file_path("/home/user/project/requirements.txt")
        assert is_valid is True
        assert error is None

    def test_valid_relative_path(self):
        """Test that valid relative paths pass validation."""
        is_valid, error = validate_file_path("requirements.txt")
        assert is_valid is True
        assert error is None

    def test_empty_path_rejected(self):
        """Test that empty paths are rejected."""
        is_valid, error = validate_file_path("")
        assert is_valid is False
        assert error == "File path cannot be empty"

    def test_directory_traversal_rejected(self):
        """Test that directory traversal attempts are rejected."""
        # Simple traversal
        is_valid, error = validate_file_path("../requirements.txt")
        assert is_valid is False
        assert "traversal" in error.lower()

        # Double traversal
        is_valid, error = validate_file_path("../../etc/passwd")
        assert is_valid is False
        assert "traversal" in error.lower()

        # Hidden traversal in path
        is_valid, error = validate_file_path("/home/user/../../../etc/passwd")
        assert is_valid is False
        assert "traversal" in error.lower()

        # Traversal with encoded characters would need additional validation
        is_valid, error = validate_file_path("foo/../bar/../../etc/passwd")
        assert is_valid is False
        assert "traversal" in error.lower()

    def test_path_with_dots_not_traversal(self):
        """Test that paths with dots (but not ..) are allowed."""
        # File with dots in name
        is_valid, error = validate_file_path("/home/user/file.tar.gz")
        assert is_valid is True
        assert error is None

        # Hidden file
        is_valid, error = validate_file_path("/home/user/.env")
        assert is_valid is True
        assert error is None

        # Directory with dot
        is_valid, error = validate_file_path("/home/user/.config/settings.txt")
        assert is_valid is True
        assert error is None
