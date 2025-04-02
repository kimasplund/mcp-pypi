"""Tests for the main entry point of the package."""

import sys
from unittest.mock import patch, MagicMock
import importlib.util
import importlib.machinery

def test_main_entry_point():
    """Test that the main entry point calls the app function."""
    with patch('mcp_pypi.cli.main.app') as mock_app:
        mock_app.return_value = 0
        
        # Save original __name__ value
        original_name = "__main__"
        
        with patch('sys.exit') as mock_exit:
            # Load the __main__.py file as a module
            spec = importlib.util.spec_from_file_location(
                "__main__", "mcp_pypi/__main__.py"
            )
            main_module = importlib.util.module_from_spec(spec)
            
            # Execute the module with __name__ set to "__main__"
            with patch.object(main_module, '__name__', original_name):
                spec.loader.exec_module(main_module)
            
            # Check that app and sys.exit were called
            mock_app.assert_called_once()
            mock_exit.assert_called_once_with(mock_app.return_value) 