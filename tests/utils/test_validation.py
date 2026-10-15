"""Tests for validation utilities."""

from mcp_pypi.utils.validation import normalize_package_name, validate_file_path


class TestNormalizePackageName:
    """normalize_package_name follows PEP 503."""

    def test_normalizes_case_and_separators(self):
        assert normalize_package_name("Django_REST.framework") == "django-rest-framework"
        assert normalize_package_name("requests") == "requests"


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
