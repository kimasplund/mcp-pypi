---
mcp:
  - name: PYPI_MCP
    description: Tools for interacting with the Python Package Index (PyPI), enabling package information retrieval, version checking, download URL generation, and dependency analysis.
    icon: https://upload.wikimedia.org/wikipedia/commons/0/04/PyPI-Logo-notext.svg
    version: 2.0.1
    tools:
      - name: get_package_info
        description: Get detailed information about a Python package from PyPI
        parameters:
          - name: package_name
            description: The name of the package to get information about
            type: string
            required: true
      - name: get_latest_version
        description: Get the latest version of a package from PyPI
        parameters:
          - name: package_name
            description: The name of the package to get the version for
            type: string
            required: true
      - name: get_dependency_tree
        description: Get the dependency tree for a package
        parameters:
          - name: package_name
            description: The name of the package to get dependencies for
            type: string
            required: true
          - name: version
            description: The specific version to check (defaults to latest)
            type: string
            required: false
          - name: depth
            description: How deep to traverse the dependency tree
            type: integer
            required: false
            default: 1
      - name: search_packages
        description: Search for packages on PyPI
        parameters:
          - name: query
            description: The search query
            type: string
            required: true
      - name: get_package_stats
        description: Get download statistics for a package
        parameters:
          - name: package_name
            description: The name of the package to get statistics for
            type: string
            required: true
          - name: version
            description: The specific version to check (defaults to latest)
            type: string
            required: false
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
      I need a Python package that can {{functionality}}.
      Please:
      1. Search for packages that might provide this functionality
      2. Compare the top options
      3. Recommend which one I should use based on popularity, maintenance status, and features
      4. Show a basic usage example of the recommended package
---

# PyPI MCP Server

This MCP server provides tools to interact with the Python Package Index (PyPI) API.

## Overview

The PyPI MCP server enables AI assistants to interact with the Python Package Index (PyPI) to gather information about Python packages, check versions, analyze dependencies, and more.

## Installation

You can install the client using pip:

```bash
pip install mcp-pypi
```

For improved search functionality:

```bash
pip install "mcp-pypi[search]"
```

## Setup

Add the PyPI MCP server to your MCP configuration:

```json
{
  "mcpServers": {
    "PYPI_MCP": {
      "command": "mcp-pypi",
      "args": ["serve"]
    }
  }
}
```

## Tools

### get_package_info

Get detailed information about a Python package from PyPI.

**Parameters:**
- `package_name` (string): The name of the package to get information about

**Example Response:**
```json
{
  "info": {
    "name": "requests",
    "version": "2.28.1",
    "summary": "Python HTTP for Humans.",
    "description": "...",
    "author": "Kenneth Reitz",
    "author_email": "me@kennethreitz.org",
    "license": "Apache 2.0",
    "project_urls": {
      "Homepage": "https://requests.readthedocs.io",
      "Documentation": "https://requests.readthedocs.io",
      "Source": "https://github.com/psf/requests"
    },
    "requires_python": ">=3.7, <4"
  },
  "releases": {
    "2.28.1": [
      {
        "filename": "requests-2.28.1-py3-none-any.whl",
        "url": "https://files.pythonhosted.org/packages/...",
        "size": 61768,
        "hashes": {
          "sha256": "..."
        },
        "requires_python": ">=3.7, <4"
      }
    ]
  }
}
```
### get_latest_version

Get the latest version of a package from PyPI.

**Parameters:**
- `package_name` (string): The name of the package to get the version for

**Example Response:**
```json
{
  "version": "2.28.1"
}
```

### get_dependency_tree

Get the dependency tree for a package.

**Parameters:**
- `package_name` (string): The name of the package to get dependencies for
- `version` (string, optional): The specific version to check (defaults to latest)
- `depth` (integer, optional): How deep to traverse the dependency tree (default: 1)

**Example Response:**
```json
{
  "name": "requests",
  "version": "2.28.1",
  "dependencies": [
    {
      "name": "charset-normalizer",
      "version": "2.0.12",
      "dependencies": []
    },
    {
      "name": "idna",
      "version": "3.3",
      "dependencies": []
    }
  ]
}
```

### search_packages

Search for packages on PyPI.

**Parameters:**
- `query` (string): The search query

**Example Response:**
```json
{
  "results": [
    {
      "name": "requests",
      "version": "2.28.1",
      "description": "Python HTTP for Humans.",
      "url": "https://pypi.org/project/requests/"
    },
    {
      "name": "requests-aws",
      "version": "0.1.8",
      "description": "AWS authentication for Requests",
      "url": "https://pypi.org/project/requests-aws/"
    }
  ]
}
```

### get_package_stats

Get download statistics for a package.

**Parameters:**
- `package_name` (string): The name of the package to get statistics for
- `version` (string, optional): The specific version to check (defaults to latest)

**Example Response:**
```json
{
  "last_day": 7813294,
  "last_week": 49642387,
  "last_month": 195841592,
  "downloads": {
    "2023-01": 178431659,
    "2023-02": 164298345,
    "2023-03": 195841592
  }
}
```

## Error Handling

All tools return standardized error responses:

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
