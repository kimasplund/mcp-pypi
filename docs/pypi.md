# MCP-PyPI API Reference

Complete API documentation for all 21 tools provided by the MCP-PyPI server.

## Table of Contents

1. [Package Information Tools](#package-information-tools)
2. [Security Scanning Tools](#security-scanning-tools)
3. [Documentation Tools](#documentation-tools)
4. [Error Handling](#error-handling)
5. [Type Definitions](#type-definitions)

## Package Information Tools

### search_packages

Search PyPI to discover Python packages for any task.

**Parameters:**
- `query` (string, required): Search terms describing what you're looking for
- `limit` (integer, optional): Maximum number of results (1-100, default: 10)

**Returns:** `SearchResult`
```json
{
  "packages": [
    {
      "name": "requests",
      "version": "2.31.0",
      "description": "Python HTTP for Humans."
    }
  ],
  "total": 1523
}
```

### get_package_info

Get comprehensive details about any Python package from PyPI.

**Parameters:**
- `package_name` (string, required): Exact name of the Python package

**Returns:** `PackageInfo`
```json
{
  "info": {
    "name": "requests",
    "version": "2.31.0",
    "summary": "Python HTTP for Humans.",
    "author": "Kenneth Reitz",
    "license": "Apache 2.0",
    "home_page": "https://requests.readthedocs.io",
    "requires_python": ">=3.7"
  }
}
```

### get_package_releases

Get detailed release information for a specific package.

**Parameters:**
- `package_name` (string, required): Name of the Python package
- `limit` (integer, optional): Maximum number of releases (default: 10)

**Returns:** Release information with file details

### get_latest_version

Check the latest version of any Python package on PyPI.

**Parameters:**
- `package_name` (string, required): Name of the Python package

**Returns:** `VersionInfo`
```json
{
  "version": "2.31.0",
  "release_date": "2023-05-22T15:47:19"
}
```

### get_dependencies

Analyze Python package dependencies from PyPI.

**Parameters:**
- `package_name` (string, required): Name of the Python package
- `version` (string, optional): Specific version (defaults to latest)

**Returns:** `DependenciesResult`
```json
{
  "dependencies": {
    "install_requires": ["urllib3>=1.21.1", "certifi>=2017.4.17"],
    "extras_require": {
      "security": ["pyOpenSSL>=0.14", "cryptography>=1.3.4"]
    }
  }
}
```

### get_dependency_tree

Get the full dependency tree for a package.

**Parameters:**
- `package_name` (string, required): Name of the package
- `version` (string, optional): Specific version (defaults to latest)
- `max_depth` (integer, optional): Maximum depth (1-3, default: 3)

**Returns:** `DependencyTreeResult` with nested dependencies

### get_package_stats

Get PyPI download statistics to gauge package popularity.

**Parameters:**
- `package_name` (string, required): Name of the Python package

**Returns:** `StatsResult`
```json
{
  "daily_downloads": 7813294,
  "weekly_downloads": 49642387,
  "monthly_downloads": 195841592
}
```

### check_package_exists

Check if a package exists on PyPI.

**Parameters:**
- `package_name` (string, required): Name of the package

**Returns:** `ExistsResult`
```json
{
  "exists": true,
  "exact_name": "requests"
}
```

### get_package_metadata

Get metadata for a package.

**Parameters:**
- `package_name` (string, required): Name of the package
- `version` (string, optional): Specific version (defaults to latest)

**Returns:** `MetadataResult` with full package metadata

### list_package_versions

List all available versions of a package.

**Parameters:**
- `package_name` (string, required): Name of the package

**Returns:** `ReleasesInfo`
```json
{
  "package_name": "requests",
  "versions": ["2.31.0", "2.30.0", "2.29.0"],
  "latest_version": "2.31.0",
  "release_count": 126
}
```

### compare_versions

Compare two versions of a package.

**Parameters:**
- `package_name` (string, required): Name of the package
- `version1` (string, required): First version to compare
- `version2` (string, required): Second version to compare

**Returns:** `VersionComparisonResult` with comparison details

## Security Scanning Tools

### check_vulnerabilities

Check for known vulnerabilities in a Python package using Google's OSV database.

**Parameters:**
- `package_name` (string, required): Name of the package to check
- `version` (string, optional): Specific version (checks all if not provided)

**Returns:** Vulnerability report
```json
{
  "vulnerable": true,
  "total_vulnerabilities": 3,
  "critical_count": 1,
  "high_count": 2,
  "vulnerabilities": [
    {
      "id": "GHSA-xxx",
      "summary": "Security vulnerability description",
      "severity": "CRITICAL",
      "cve": ["CVE-2023-xxxxx"],
      "affected_versions": [">=2.0.0,<2.1.0"]
    }
  ]
}
```

### scan_dependency_vulnerabilities

Deep scan for vulnerabilities in a package's entire dependency tree.

**Parameters:**
- `package_name` (string, required): Root package to analyze
- `version` (string, optional): Specific version to analyze
- `max_depth` (integer, optional): Depth to scan (1-3, default: 2)
- `include_dev` (boolean, optional): Include dev dependencies (default: false)

**Returns:** Comprehensive vulnerability analysis with dependency tree

### scan_installed_packages

Scan installed packages in Python environments for vulnerabilities.

**Parameters:**
- `environment_path` (string, optional): Path to Python environment (auto-detects if not provided)
- `include_system` (boolean, optional): Include system packages (default: false)
- `output_format` (string, optional): "summary" or "detailed" (default: "summary")

**Returns:** Environment vulnerability report

### quick_security_check

Quick security check with pass/fail status for CI/CD.

**Parameters:**
- `project_path` (string, optional): Path to project root
- `fail_on_critical` (boolean, optional): Fail on CRITICAL vulnerabilities (default: true)
- `fail_on_high` (boolean, optional): Fail on HIGH vulnerabilities (default: true)

**Returns:** Pass/fail status
```json
{
  "passed": false,
  "status": "❌ FAILED",
  "reason": "Found 2 CRITICAL vulnerabilities",
  "summary": {
    "critical": 2,
    "high": 5,
    "medium": 10
  },
  "security_score": 65
}
```

### get_security_report

Get a beautiful, color-coded security report for your Python project.

**Parameters:**
- `project_path` (string, optional): Path to project root
- `check_files` (boolean, optional): Analyze dependency files (default: true)
- `check_installed` (boolean, optional): Scan virtual environments (default: true)
- `check_transitive` (boolean, optional): Deep dependency analysis (default: true)
- `max_depth` (integer, optional): Dependency tree depth (default: 2)

**Returns:** Formatted security report with colors and tables

### security_audit_project

Comprehensive security audit of an entire Python project.

**Parameters:**
- `project_path` (string, optional): Path to project root
- `check_files` (boolean, optional): Analyze dependency files (default: true)
- `check_installed` (boolean, optional): Scan virtual environments (default: true)
- `check_transitive` (boolean, optional): Deep dependency analysis (default: true)
- `max_depth` (integer, optional): Dependency tree depth (default: 2)

**Returns:** Complete audit report
```json
{
  "overall_risk_level": "HIGH",
  "security_score": 72,
  "priority_fixes": [
    {
      "package": "urllib3",
      "current": "1.26.0",
      "safe": "1.26.18",
      "severity": "CRITICAL"
    }
  ],
  "remediation_plan": {
    "immediate": ["Update urllib3 to 1.26.18"],
    "short_term": ["Update requests to 2.31.0"],
    "long_term": ["Enable automated dependency updates"]
  }
}
```

### check_requirements_txt

Analyze requirements.txt for outdated packages and security issues.

**Parameters:**
- `file_path` (string, required): Absolute path to requirements.txt file

**Returns:** `PackageRequirementsResult`
```json
{
  "outdated": [
    {
      "package": "django",
      "current_version": "3.2.0",
      "latest_version": "4.2.0",
      "constraint": ">=3.2.0"
    }
  ],
  "vulnerable": [
    {
      "package": "pillow",
      "version": "8.0.0",
      "vulnerabilities": 3
    }
  ]
}
```

### check_pyproject_toml

Analyze pyproject.toml for outdated packages and security issues.

**Parameters:**
- `file_path` (string, required): Absolute path to pyproject.toml file

**Returns:** Similar to check_requirements_txt but handles all dependency groups

## Documentation Tools

### get_package_documentation

Get documentation links for a package.

**Parameters:**
- `package_name` (string, required): Name of the package

**Returns:** `DocumentationResult`
```json
{
  "documentation_url": "https://docs.python-requests.org/",
  "homepage": "https://requests.readthedocs.io",
  "repository": "https://github.com/psf/requests",
  "bugtracker": "https://github.com/psf/requests/issues"
}
```

### get_package_changelog

Get changelog for a package.

**Parameters:**
- `package_name` (string, required): Name of the package
- `version` (string, optional): Specific version (defaults to latest)

**Returns:** Changelog text or error if not found

## Error Handling

All tools return standardized error responses when something goes wrong:

```json
{
  "error": {
    "code": "not_found",
    "message": "Package 'nonexistent-package' not found on PyPI"
  }
}
```

### Error Codes

- `not_found` - Package or resource not found
- `invalid_input` - Invalid parameter value provided
- `network_error` - Error communicating with PyPI
- `parse_error` - Error parsing response from PyPI
- `file_error` - Error accessing or reading a file
- `permission_error` - Insufficient permissions
- `vulnerability_check_error` - Error checking vulnerabilities

## Type Definitions

### Core Types

All responses use TypedDict for type safety:

```python
class ErrorDict(TypedDict):
    code: str
    message: str
    details: NotRequired[Dict[str, Any]]

class PackageInfo(TypedDict):
    info: Dict[str, Any]
    releases: NotRequired[Dict[str, List[Dict[str, Any]]]]
    urls: NotRequired[List[Dict[str, Any]]]
    vulnerabilities: NotRequired[List[Dict[str, Any]]]

class SearchResult(TypedDict):
    packages: List[Dict[str, str]]
    total: int

class VersionInfo(TypedDict):
    version: str
    release_date: NotRequired[str]

class DependenciesResult(TypedDict):
    dependencies: Dict[str, Any]
    dev_dependencies: NotRequired[Dict[str, Any]]
    optional_dependencies: NotRequired[Dict[str, Any]]
```

### Security Types

```python
class VulnerabilityInfo(TypedDict):
    id: str
    summary: str
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    cve: List[str]
    affected_versions: List[str]
    fixed_versions: NotRequired[List[str]]

class SecurityAuditResult(TypedDict):
    overall_risk_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "SECURE"]
    security_score: int
    total_vulnerabilities: int
    priority_fixes: List[Dict[str, Any]]
    remediation_plan: Dict[str, List[str]]
```

## Usage Examples

### Basic Package Search
```python
# Search for web scraping packages
result = await client.invoke_tool(
    "search_packages",
    {"query": "web scraping", "limit": 5}
)
```

### Security Workflow
```python
# 1. Check package before installation
info = await client.invoke_tool("get_package_info", {"package_name": "requests"})
vulns = await client.invoke_tool("check_vulnerabilities", {"package_name": "requests"})

# 2. Deep scan dependencies
deps = await client.invoke_tool(
    "scan_dependency_vulnerabilities",
    {"package_name": "requests", "max_depth": 3}
)

# 3. Audit entire project
audit = await client.invoke_tool(
    "security_audit_project",
    {"project_path": "/path/to/project"}
)
```

### Requirements Management
```python
# Check requirements file
result = await client.invoke_tool(
    "check_requirements_txt",
    {"file_path": "/path/to/requirements.txt"}
)

# Update based on vulnerabilities
for pkg in result["vulnerable"]:
    latest = await client.invoke_tool(
        "get_latest_version",
        {"package_name": pkg["package"]}
    )
```

## Best Practices

1. **Always use absolute paths** for file operations
2. **Check vulnerabilities before installing** new packages
3. **Use specific versions** in production after security verification
4. **Scan transitive dependencies** with appropriate depth
5. **Regular security audits** with security_audit_project

## Rate Limiting

PyPI API has rate limits. The client handles these automatically with:
- Exponential backoff
- Request caching
- ETag support

## Support

- GitHub: https://github.com/kimasplund/mcp-pypi
- Author: Kim Asplund (kim.asplund@gmail.com)