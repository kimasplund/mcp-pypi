# Version Management

This document describes how version numbering is handled in the mcp-pypi project.

## Single Source of Truth

**The version is defined in one place only: `pyproject.toml`**

```toml
[project]
version = "2.0.3"
```

## Dynamic Version Import

All code that needs the version imports it dynamically from `pyproject.toml`:

```python
from mcp_pypi import __version__
print(f"MCP-PyPI version: {__version__}")
```

## Implementation Details

### 1. Version Module (`mcp_pypi/_version.py`)

This module reads the version from `pyproject.toml` and provides it to the rest of the codebase:

- Uses `tomllib` (Python 3.11+) or `tomli` (older versions)
- Falls back to manual parsing if TOML libraries unavailable
- Provides robust error handling with fallback version

### 2. Main Module (`mcp_pypi/__init__.py`)

Exports the version for easy importing:

```python
from ._version import __version__
```

### 3. CLI Integration (`mcp_pypi/cli/main.py`)

Uses dynamic import for version commands and MCP schema:

```python
from mcp_pypi import __version__

# In version command
print(f"MCP-PyPI version: {__version__}")

# In MCP schema
def get_mcp_schema():
    return {
        "version": __version__,
        # ...
    }
```

## Benefits

✅ **Single source of truth** - Version only defined in `pyproject.toml`  
✅ **No duplication** - No risk of version mismatches  
✅ **Automatic consistency** - All components use the same version  
✅ **Easy updates** - Change version in one place only  
✅ **Standards compliant** - Follows PEP 621 modern packaging  

## Updating the Version

To update the project version:

1. **Edit `pyproject.toml`** - Change the version field:
   ```toml
   [project]
   version = "2.1.0"  # Update this line only
   ```

2. **That's it!** - All other code automatically uses the new version

## Python Compatibility

The version system works with:
- **Python 3.11+**: Uses built-in `tomllib`
- **Python 3.10**: Uses `tomli` dependency (already in requirements)
- **Fallback**: Manual parsing if TOML libraries unavailable

## Migration from Old System

**Before** (multiple version definitions):
```python
# pyproject.toml
version = "2.0.3"

# mcp_pypi/__init__.py
__version__ = "2.0.3"

# mcp_pypi/cli/main.py
"version": "2.0.1"  # 😱 Out of sync!
```

**After** (single source of truth):
```python
# pyproject.toml (ONLY place to define version)
version = "2.0.3"

# All other files import dynamically
from mcp_pypi import __version__
```

## Testing Version Consistency

The version system includes self-validation to ensure consistency across all components.