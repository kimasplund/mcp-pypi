"""Tests for the main entry point of the package."""

import importlib.machinery
import importlib.util
import sys
from unittest.mock import MagicMock, patch


def test_main_entry_point():
    """Test that the main entry point calls the entry_point function.

    The __main__.py imports entry_point from mcp_pypi.cli.main and calls
    sys.exit(entry_point()). Since entry_point() catches exceptions and
    returns None on success, sys.exit is called with None.
    """
    with patch("mcp_pypi.cli.main.entry_point") as mock_entry_point:
        mock_entry_point.return_value = None  # entry_point returns None on success

        with patch("sys.exit") as mock_exit:
            # Load the __main__.py file as a module
            spec = importlib.util.spec_from_file_location(
                "__main__", "mcp_pypi/__main__.py"
            )
            main_module = importlib.util.module_from_spec(spec)

            # Execute the module with __name__ set to "__main__"
            with patch.object(main_module, "__name__", "__main__"):
                spec.loader.exec_module(main_module)

            # Check that entry_point and sys.exit were called
            mock_entry_point.assert_called_once()
            mock_exit.assert_called_once_with(None)
