"""
Version information for mcp-pypi.

This module provides a single source of truth for version information.
The version is dynamically read from pyproject.toml to avoid duplication.
"""

import sys
from pathlib import Path

def get_version() -> str:
    """
    Get the version from pyproject.toml.
    
    Returns:
        str: The current version of the package.
    """
    try:
        # Find pyproject.toml relative to this file
        project_root = Path(__file__).parent.parent
        pyproject_path = project_root / "pyproject.toml"
        
        if pyproject_path.exists():
            # Use tomllib for Python 3.11+ or tomli for older versions
            if sys.version_info >= (3, 11):
                import tomllib
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)
            else:
                try:
                    import tomli
                    with open(pyproject_path, "rb") as f:
                        data = tomli.load(f)
                except ImportError:
                    # Fallback: parse manually if tomli not available
                    with open(pyproject_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip().startswith("version = "):
                                # Extract version from: version = "2.0.3"
                                return line.split('"')[1]
                    return "2.1.0"
            
            return data["project"]["version"]
        else:
            # Fallback for development/edge cases
            return "2.1.0"
    except Exception:
        # Fallback version if reading fails
        return "2.1.0"

# Export version for easy import
__version__ = get_version()