---
mcp:
  - name: MCP-PyPI
    description: Security-focused MCP server for PyPI package management. Search packages, scan for vulnerabilities, audit dependencies, and ensure security across your entire Python project.
    icon: https://upload.wikimedia.org/wikipedia/commons/0/04/PyPI-Logo-notext.svg
    version: 2.7.1
    tools:
      # Package Information Tools
      - name: search_packages
        description: Search PyPI to discover Python packages for any task
        parameters:
          - name: query
            description: Search terms describing what you're looking for
            type: string
            required: true
          - name: limit
            description: Maximum number of results to return (1-100)
            type: integer
            required: false
            default: 10
      - name: get_package_info
        description: Get comprehensive details about any Python package from PyPI
        parameters:
          - name: package_name
            description: Exact name of the Python package
            type: string
            required: true
      - name: get_package_releases
        description: Get detailed release information for a specific package
        parameters:
          - name: package_name
            description: Name of the Python package
            type: string
            required: true
          - name: limit
            description: Maximum number of releases to return
            type: integer
            required: false
            default: 10
      - name: get_latest_version
        description: Check the latest version of any Python package on PyPI
        parameters:
          - name: package_name
            description: Name of the Python package
            type: string
            required: true
      - name: get_dependencies
        description: Analyze Python package dependencies from PyPI
        parameters:
          - name: package_name
            description: Name of the Python package
            type: string
            required: true
          - name: version
            description: Specific version (optional, defaults to latest)
            type: string
            required: false
      - name: get_dependency_tree
        description: Get the full dependency tree for a package
        parameters:
          - name: package_name
            description: Name of the package
            type: string
            required: true
          - name: version
            description: Specific version (optional, defaults to latest)
            type: string
            required: false
          - name: max_depth
            description: Maximum depth to traverse (default: 3)
            type: integer
            required: false
            default: 3
      - name: get_package_stats
        description: Get PyPI download statistics to gauge package popularity
        parameters:
          - name: package_name
            description: Name of the Python package
            type: string
            required: true
      - name: check_package_exists
        description: Check if a package exists on PyPI
        parameters:
          - name: package_name
            description: Name of the package
            type: string
            required: true
      - name: get_package_metadata
        description: Get metadata for a package
        parameters:
          - name: package_name
            description: Name of the package
            type: string
            required: true
          - name: version
            description: Specific version (optional, defaults to latest)
            type: string
            required: false
      - name: list_package_versions
        description: List all available versions of a package
        parameters:
          - name: package_name
            description: Name of the package
            type: string
            required: true
      - name: compare_versions
        description: Compare two versions of a package
        parameters:
          - name: package_name
            description: Name of the package
            type: string
            required: true
          - name: version1
            description: First version to compare
            type: string
            required: true
          - name: version2
            description: Second version to compare
            type: string
            required: true
      # Security Scanning Tools
      - name: check_requirements_txt
        description: Analyze requirements.txt for outdated packages and security issues
        parameters:
          - name: file_path
            description: Absolute path to requirements.txt file
            type: string
            required: true
      - name: check_pyproject_toml
        description: Analyze pyproject.toml for outdated packages and security issues
        parameters:
          - name: file_path
            description: Absolute path to pyproject.toml file
            type: string
            required: true
      - name: check_vulnerabilities
        description: Check for known vulnerabilities in a Python package
        parameters:
          - name: package_name
            description: Name of the package to check
            type: string
            required: true
          - name: version
            description: Specific version to check (optional, checks all if not provided)
            type: string
            required: false
      - name: scan_dependency_vulnerabilities
        description: Deep scan for vulnerabilities in a package's entire dependency tree
        parameters:
          - name: package_name
            description: Root package to analyze
            type: string
            required: true
          - name: version
            description: Specific version to analyze (optional)
            type: string
            required: false
          - name: max_depth
            description: How deep to scan the dependency tree (1-3)
            type: integer
            required: false
            default: 2
          - name: include_dev
            description: Include development dependencies
            type: boolean
            required: false
            default: false
      - name: scan_installed_packages
        description: Scan installed packages in Python environments for vulnerabilities
        parameters:
          - name: environment_path
            description: Absolute path to Python environment directory (optional, auto-detects if not provided)
            type: string
            required: false
          - name: include_system
            description: Include system packages
            type: boolean
            required: false
            default: false
          - name: output_format
            description: Output format - 'summary' or 'detailed'
            type: string
            required: false
            default: summary
      - name: quick_security_check
        description: Quick security check with pass/fail status
        parameters:
          - name: project_path
            description: Absolute path to project root directory (optional)
            type: string
            required: false
          - name: fail_on_critical
            description: Fail if any CRITICAL vulnerabilities
            type: boolean
            required: false
            default: true
          - name: fail_on_high
            description: Fail if any HIGH vulnerabilities
            type: boolean
            required: false
            default: true
      - name: get_security_report
        description: Get a beautiful, color-coded security report for your Python project
        parameters:
          - name: project_path
            description: Absolute path to project root directory (optional)
            type: string
            required: false
          - name: check_files
            description: Analyze dependency files
            type: boolean
            required: false
            default: true
          - name: check_installed
            description: Scan virtual environments
            type: boolean
            required: false
            default: true
          - name: check_transitive
            description: Deep dependency analysis
            type: boolean
            required: false
            default: true
          - name: max_depth
            description: Dependency tree depth
            type: integer
            required: false
            default: 2
      - name: security_audit_project
        description: Comprehensive security audit of an entire Python project
        parameters:
          - name: project_path
            description: Absolute path to project root directory (optional)
            type: string
            required: false
          - name: check_files
            description: Analyze dependency files
            type: boolean
            required: false
            default: true
          - name: check_installed
            description: Scan virtual environments
            type: boolean
            required: false
            default: true
          - name: check_transitive
            description: Deep dependency analysis
            type: boolean
            required: false
            default: true
          - name: max_depth
            description: Dependency tree depth
            type: integer
            required: false
            default: 2
      # Documentation and Utility Tools
      - name: get_package_documentation
        description: Get documentation links for a package
        parameters:
          - name: package_name
            description: Name of the package
            type: string
            required: true
      - name: get_package_changelog
        description: Get changelog for a package
        parameters:
          - name: package_name
            description: Name of the package
            type: string
            required: true
          - name: version
            description: Specific version (optional, defaults to latest)
            type: string
            required: false
prompts:
  - name: security_audit
    description: Perform a comprehensive security audit of a Python project
    prompt: |
      I need a comprehensive security audit of the Python project at {{project_path}}.
      Please:
      1. Discover ALL dependency files (requirements.txt, pyproject.toml, setup.py, setup.cfg, etc.)
      2. Check each file for outdated packages and security vulnerabilities
      3. Scan the dependency tree for transitive vulnerabilities
      4. Check if version constraints allow vulnerable versions
      5. Provide a prioritized list of security issues to fix
      6. Suggest specific version updates that resolve vulnerabilities
      7. Ensure consistency across all dependency files
  - name: find_secure_package
    description: Find a secure package for specific functionality
    prompt: |
      I need a Python package that can {{functionality}}.
      Please:
      1. Search for packages that provide this functionality
      2. Check each candidate for known vulnerabilities
      3. Analyze their dependency trees for security issues
      4. Compare download statistics and maintenance status
      5. Recommend the most secure and well-maintained option
      6. Provide a security assessment for the recommendation
  - name: update_dependencies_safely
    description: Update project dependencies while maintaining security
    prompt: |
      I need to update the dependencies in {{project_path}} safely.
      Please:
      1. Audit all dependency files in the project
      2. Identify which packages have updates available
      3. Check if updates fix any security vulnerabilities
      4. Verify update compatibility with Python version requirements
      5. Create an update plan that prioritizes security fixes
      6. Ensure all dependency files remain consistent after updates
---

# MCP-PyPI: Security-Focused Python Package Intelligence

A Model Context Protocol (MCP) server that empowers AI assistants to write safer Python code through comprehensive PyPI integration, vulnerability scanning, and dependency auditing.

## Overview

MCP-PyPI goes beyond basic package information to provide security-first intelligence about Python packages. It helps AI assistants make informed decisions about dependencies, identify vulnerabilities before they become problems, and maintain secure Python projects.

## Key Features

### 🔍 **Package Discovery & Analysis**
- Search 500,000+ packages with intelligent ranking
- Deep dependency tree analysis (including transitive dependencies)
- Download statistics and popularity metrics
- Comprehensive metadata including licenses and classifiers

### 🛡️ **Security Scanning**
- Real-time vulnerability checking using Google's OSV database
- Deep scanning of entire dependency trees
- Version constraint analysis (catches when `>=3.8.0` allows vulnerable versions)
- Security reports with severity classification

### 📋 **Project Auditing**
- Automatic discovery of ALL dependency files
- Consistency checking across requirements.txt, pyproject.toml, setup.py, setup.cfg
- Virtual environment scanning
- Prioritized remediation recommendations

### 🚀 **Developer Productivity**
- Quick security checks for CI/CD pipelines
- Formatted reports with actionable insights
- Changelog extraction for update decisions
- Documentation link discovery

## Installation

```bash
# Basic installation
pip install mcp-pypi

# With search optimization
pip install "mcp-pypi[search]"

# Full installation with all features
pip install "mcp-pypi[all]"
```

## Configuration

### For Claude Desktop

Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "mcp-pypi": {
      "command": "mcp-pypi",
      "args": ["serve"]
    }
  }
}
```

### For Other MCP Clients

```json
{
  "mcpServers": {
    "mcp-pypi": {
      "command": "mcp-pypi",
      "args": ["serve", "--transport", "stdio"]
    }
  }
}
```

### HTTP Transport (Alternative)

```json
{
  "mcpServers": {
    "mcp-pypi": {
      "command": "mcp-pypi",
      "args": ["serve", "--transport", "http", "--port", "8080"]
    }
  }
}
```

## Usage Examples

### Security Audit

```python
# Comprehensive project audit
result = await security_audit_project("/path/to/project")
# Automatically discovers and checks ALL dependency files
# Returns prioritized vulnerabilities with fix recommendations
```

### Package Research

```python
# Search with security in mind
packages = await search_packages("web scraping")
for pkg in packages:
    vulns = await check_vulnerabilities(pkg.name)
    stats = await get_package_stats(pkg.name)
    # Make informed decisions based on security and popularity
```

### Dependency Analysis

```python
# Deep dependency scanning
tree = await scan_dependency_vulnerabilities("django", max_depth=3)
# Reveals hidden vulnerabilities in transitive dependencies
```

## Tool Categories

### Information Gathering
- `search_packages` - Discover packages by functionality
- `get_package_info` - Detailed package metadata
- `get_latest_version` - Check for updates
- `get_package_stats` - Download statistics
- `list_package_versions` - Version history

### Dependency Analysis
- `get_dependencies` - Direct dependencies
- `get_dependency_tree` - Full dependency graph
- `compare_versions` - Version comparison

### Security Scanning
- `check_vulnerabilities` - Package vulnerability check
- `scan_dependency_vulnerabilities` - Deep dependency scanning
- `scan_installed_packages` - Environment scanning
- `quick_security_check` - CI/CD pass/fail check
- `get_security_report` - Formatted security report
- `security_audit_project` - Complete project audit

### File Analysis
- `check_requirements_txt` - Analyze requirements files
- `check_pyproject_toml` - Analyze modern Python projects

### Documentation
- `get_package_documentation` - Find docs
- `get_package_changelog` - Review changes

## Security Best Practices

1. **Always Audit Before Installing**
   ```python
   info = await get_package_info("unknown-package")
   vulns = await check_vulnerabilities("unknown-package")
   deps = await scan_dependency_vulnerabilities("unknown-package")
   ```

2. **Check Version Constraints**
   - MCP-PyPI detects when constraints like `>=2.0.0` allow vulnerable versions
   - Always use specific version pins for production

3. **Regular Audits**
   ```python
   # Run weekly security audits
   report = await security_audit_project("/production/app")
   ```

4. **Dependency Hierarchy**
   - pyproject.toml is the primary source (modern standard)
   - requirements.txt is secondary (often generated)
   - setup.cfg is legacy but still checked

## Advanced Features

### Intelligent Caching
- ETag-based HTTP caching
- Configurable cache strategies (memory/disk/hybrid)
- Automatic cache invalidation for security data

### Comprehensive Error Handling
- Detailed error codes and messages
- Graceful fallbacks for network issues
- Clear guidance for resolution

### Performance Optimization
- Async operations throughout
- Parallel dependency resolution
- Efficient tree traversal algorithms

## Contributing

We welcome contributions! See [CONTRIBUTING.md](https://github.com/kimasplund/mcp-pypi/blob/main/CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](https://github.com/kimasplund/mcp-pypi/blob/main/LICENSE)

## Acknowledgments

- Built on the [Model Context Protocol](https://modelcontextprotocol.io)
- Vulnerability data from [Google OSV](https://osv.dev)
- Package data from [PyPI](https://pypi.org)

## Author

Kim Asplund
- Email: kim.asplund@gmail.com
- Website: https://asplund.kim
- GitHub: https://github.com/kimasplund

---

*Making Python dependency management secure by default for AI assistants.*