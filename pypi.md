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
    icon: https://upload.wikimedia.org/wikipedia/commons/0/04/PyPI-Logo-notext.svg
    version: 1.0.0
prompts:
  - name: find_dependencies
    description: Find all dependencies for a Python package
    prompt: |
      I need to understand the dependencies for the Python package {{package_name}}{{#version}} version {{version}}{{/version}}.
      Can you:
      1. Get the direct dependencies
      2. Show them in a tree structure to see the relationships
      3. Explain any circular dependencies if they exist
      4. Note if any dependencies are optional or environment-specific
  - name: check_outdated_packages
    description: Analyze a requirements file for outdated packages
    prompt: |
      I have a requirements.txt file at {{file_path}}. Please:
      1. Check which packages are outdated
      2. For each outdated package, show the current version and the latest available version
      3. Indicate any security concerns with outdated versions
      4. Suggest a plan for updating, highlighting any potential compatibility issues
  - name: find_package_documentation
    description: Find documentation and resources for a Python package
    prompt: |
      I'm working with the {{package_name}} package and need to find its documentation.
      Please:
      1. Get the official documentation URL
      2. Provide a brief summary of what the package does
      3. Suggest helpful resources for learning how to use it effectively
  - name: search_package_functionality
    description: Find packages that provide specific functionality
    prompt: |
      I'm looking for a Python package that can {{functionality}}.
      Please:
      1. Search for relevant packages
      2. Compare the popularity and maintenance status of the options
      3. Recommend the best package for my needs based on documentation, stability, and community support
---

# PyPI MCP Server

This MCP server provides tools to interact with the Python Package Index (PyPI) API.

## Tools

### get_package_info
Gets detailed information about a Python package from PyPI's JSON API.

**Parameters:**
- `package_name`: The name of the package to get information for

**Returns:**
- `info`: Object containing package metadata
- `releases`: Object mapping version strings to release information
- `urls`: Array of download URLs for the latest version

**Example:**
```
get_package_info package_name=requests
```

### get_latest_version
Gets the latest version of a Python package.

**Parameters:**
- `package_name`: The name of the package to get the latest version for

**Returns:**
- `version`: String containing the latest version number

**Example:**
```
get_latest_version package_name=requests
```

### get_package_releases
Gets all release versions of a Python package.

**Parameters:**
- `package_name`: The name of the package to get releases for

**Returns:**
- `releases`: Array of version strings representing all published releases

**Example:**
```
get_package_releases package_name=requests
```

### get_release_urls
Gets download URLs for a specific release of a Python package.

**Parameters:**
- `package_name`: The name of the package
- `version`: The version to get URLs for

**Returns:**
- `urls`: Array of objects containing download URLs and metadata

**Example:**
```
get_release_urls package_name=requests version=2.28.1
```

### get_source_url
Generates a predictable source package URL according to PyPI's convention.

**Parameters:**
- `package_name`: The name of the package
- `version`: The version of the package

**Returns:**
- `url`: String containing the source package URL

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

**Returns:**
- `url`: String containing the wheel package URL

**Example:**
```
get_wheel_url package_name=requests version=2.28.1 python_tag=py3 abi_tag=none platform_tag=any
```

### get_newest_packages
Gets the newest packages feed from PyPI.

**Returns:**
- `items`: Array of objects containing information about new packages

**Example:**
```
get_newest_packages
```

### get_latest_updates
Gets the latest updates feed from PyPI.

**Returns:**
- `items`: Array of objects containing information about recently updated packages

**Example:**
```
get_latest_updates
```

### get_project_releases
Gets the releases feed for a specific project.

**Parameters:**
- `package_name`: The name of the package to get releases for

**Returns:**
- `items`: Array of objects containing information about project releases

**Example:**
```
get_project_releases package_name=requests
```

### search_packages
Searches for packages on PyPI.

**Parameters:**
- `query`: The search query
- `page`: Optional page number (default: 1)

**Returns:**
- `results`: Array of objects containing search results
- `search_url`: URL used for the search

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

**Returns:**
- `version1`: First version string
- `version2`: Second version string
- `is_version1_greater`: Boolean indicating if version1 > version2
- `is_version2_greater`: Boolean indicating if version2 > version1
- `are_equal`: Boolean indicating if versions are equal

**Example:**
```
compare_versions package_name=requests version1=2.28.1 version2=2.27.0
```

### get_dependencies
Gets the dependencies for a package.

**Parameters:**
- `package_name`: The name of the package
- `version`: Optional specific version

**Returns:**
- `dependencies`: Array of dependency objects with name and version specification
- `extras`: Object mapping extra names to arrays of dependencies

**Example:**
```
get_dependencies package_name=requests version=2.28.1
```

### check_package_exists
Checks if a package exists on PyPI.

**Parameters:**
- `package_name`: The name of the package to check

**Returns:**
- `exists`: Boolean indicating if the package exists

**Example:**
```
check_package_exists package_name=requests
```

### get_package_metadata
Gets detailed metadata for a package.

**Parameters:**
- `package_name`: The name of the package
- `version`: Optional specific version

**Returns:**
- `metadata`: Object containing package metadata including name, version, summary, author, etc.

**Example:**
```
get_package_metadata package_name=requests version=2.28.1
```

### get_package_stats
Gets download statistics for a package.

**Parameters:**
- `package_name`: The name of the package
- `version`: Optional specific version

**Returns:**
- `downloads`: Object containing download statistics including total, monthly, and daily counts

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

**Returns:**
- `tree`: Object representing the dependency tree structure
- `flat_list`: Array of all dependencies as strings
- `visualization_url`: Optional URL to HTML visualization of the dependency tree

**Example:**
```
get_dependency_tree package_name=django version=4.2.0 depth=2
```

### get_documentation_url
Gets documentation URL and summary for a package.

**Parameters:**
- `package_name`: The name of the package
- `version`: Optional specific version

**Returns:**
- `docs_url`: URL to package documentation
- `summary`: Brief description of the package

**Example:**
```
get_documentation_url package_name=requests version=2.28.1
```

### check_requirements_file
Checks a requirements.txt file for outdated packages.

**Parameters:**
- `file_path`: Path to requirements.txt file

**Returns:**
- `outdated`: Array of objects with outdated packages (package, current_version, latest_version)
- `up_to_date`: Array of objects with up-to-date packages (package, version)

**Example:**
```
check_requirements_file file_path=/path/to/requirements.txt
```

## Error Responses

All tools return standardized error responses when issues occur:

```json
{
  "error": {
    "code": "error_code",
    "message": "Human-readable error message"
  }
}
```

Common error codes:
- `not_found`: Package or resource not found
- `invalid_input`: Invalid parameter value provided
- `network_error`: Error communicating with PyPI
- `parse_error`: Error parsing response from PyPI
- `file_error`: Error accessing or reading a file
- `permission_error`: Insufficient permissions to access a resource

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
- [Model Context Protocol Spec](https://modelcontextprotocol.io) 