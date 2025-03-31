---
tools:
  - name: pypi
    description: Tools for interacting with the Python Package Index (PyPI)
    container:
      image: pypi-mcp:latest
      dockerfile: ./Dockerfile
      
mcp:
  - name: PyPI
    description: Tools for interacting with the Python Package Index (PyPI), enabling package information retrieval, version checking, download URL generation, and RSS feed access.
    ref: file://pypi.md
    icon: https://pypi.org/static/images/logo-small.2a411bc6.svg
---

# PyPI MCP Server

This MCP server provides tools to interact with the Python Package Index (PyPI) API.

## Tools

### get_package_info
Gets detailed information about a Python package from PyPI's JSON API.

**Parameters:**
- `package_name`: The name of the package to get information for

**Example:**
```
get_package_info package_name=requests
```

### get_latest_version
Gets the latest version of a Python package.

**Parameters:**
- `package_name`: The name of the package to get the latest version for

**Example:**
```
get_latest_version package_name=requests
```

### get_package_releases
Gets all release versions of a Python package.

**Parameters:**
- `package_name`: The name of the package to get releases for

**Example:**
```
get_package_releases package_name=requests
```

### get_release_urls
Gets download URLs for a specific release of a Python package.

**Parameters:**
- `package_name`: The name of the package
- `version`: The version to get URLs for

**Example:**
```
get_release_urls package_name=requests version=2.28.1
```

### get_source_url
Generates a predictable source package URL according to PyPI's convention.

**Parameters:**
- `package_name`: The name of the package
- `version`: The version of the package

**Example:**
```
get_source_url package_name=virtualenv version=15.2.0
```

### get_wheel_url
Generates a predictable wheel package URL according to PyPI's convention.

**Parameters:**
- `package_name`: The name of the package
- `version`: The version of the package
- `python_tag`: The Python implementation and version tag (e.g., py3)
- `abi_tag`: The ABI tag (e.g., none)
- `platform_tag`: The platform tag (e.g., any)
- `build_tag`: Optional build tag

**Example:**
```
get_wheel_url package_name=requests version=2.28.1 python_tag=py3 abi_tag=none platform_tag=any
```

### get_newest_packages
Gets the newest packages feed from PyPI.

**Example:**
```
get_newest_packages
```

### get_latest_updates
Gets the latest updates feed from PyPI.

**Example:**
```
get_latest_updates
```

### get_project_releases
Gets the releases feed for a specific project.

**Parameters:**
- `package_name`: The name of the package to get releases for

**Example:**
```
get_project_releases package_name=requests
```

### search_packages
Searches for packages on PyPI.

**Parameters:**
- `query`: The search query
- `page`: Optional page number (default: 1)

**Example:**
```
search_packages query=http client
```

### compare_versions
Compares two version numbers of a package.

**Parameters:**
- `package_name`: The name of the package
- `version1`: First version to compare
- `version2`: Second version to compare

**Example:**
```
compare_versions package_name=requests version1=2.28.1 version2=2.27.0
```

### get_dependencies
Gets the dependencies for a package.

**Parameters:**
- `package_name`: The name of the package
- `version`: Optional specific version

**Example:**
```
get_dependencies package_name=requests version=2.28.1
```

### check_package_exists
Checks if a package exists on PyPI.

**Parameters:**
- `package_name`: The name of the package to check

**Example:**
```
check_package_exists package_name=requests
```

### get_package_metadata
Gets detailed metadata for a package.

**Parameters:**
- `package_name`: The name of the package
- `version`: Optional specific version

**Example:**
```
get_package_metadata package_name=requests version=2.28.1
```

### get_package_stats
Gets download statistics for a package.

**Parameters:**
- `package_name`: The name of the package
- `version`: Optional specific version

**Example:**
```
get_package_stats package_name=requests version=2.28.1
```

### get_dependency_tree
Gets the dependency tree for a package with recursive dependencies.

**Parameters:**
- `package_name`: The name of the package
- `version`: Optional specific version
- `depth`: Maximum depth of the dependency tree (default: 3)

**Example:**
```
get_dependency_tree package_name=django version=4.2.0 depth=2
```

### get_documentation_url
Gets documentation URL and summary for a package.

**Parameters:**
- `package_name`: The name of the package
- `version`: Optional specific version

**Example:**
```
get_documentation_url package_name=requests version=2.28.1
```

### check_requirements_file
Checks a requirements.txt file for outdated packages.

**Parameters:**
- `file_path`: Path to requirements.txt file

**Example:**
```
check_requirements_file file_path=/path/to/requirements.txt
```

## Implementation

The PyPI MCP server is implemented using Python with the following features:

1. JSON API integration for package information
2. RSS feed parsing for updates and new packages
3. Predictable URL generation for downloading packages
4. Version comparison utilities
5. Dependency resolution and visualization
6. Package metadata retrieval
7. Local caching with ETag support
8. User-Agent configuration with contact info
9. Package statistics retrieval
10. Documentation URL discovery
11. Requirements analysis for outdated packages

## References

- [PyPI JSON API](https://docs.pypi.org/api/json/)
- [PyPI RSS Feeds](https://docs.pypi.org/api/feeds/)
- [PyPI Integration Guide](https://docs.pypi.org/api/) 