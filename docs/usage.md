# MCP-PyPI Usage Guide

This document provides comprehensive instructions on using MCP-PyPI, a security-focused Model Context Protocol server for Python package management.

## Installation

```bash
# Basic installation
pip install mcp-pypi

# With search optimization
pip install "mcp-pypi[search]"

# Full installation with all features
pip install "mcp-pypi[all]"
```

## Starting the Server

MCP-PyPI uses a unified CLI with the `mcp-pypi` command:

```bash
# Start with default stdio transport (for MCP clients)
mcp-pypi serve

# Start with HTTP transport
mcp-pypi serve --transport http --port 8080

# Specify custom cache directory
mcp-pypi serve --cache-dir /path/to/cache

# Enable debug logging
mcp-pypi serve --log-level DEBUG

# Use specific cache strategy
mcp-pypi serve --cache-strategy hybrid  # Options: memory, disk, hybrid
```

## Transport Options

### STDIO Transport (Default)
Used for integration with MCP clients like Claude Desktop:

```bash
mcp-pypi serve
```

### HTTP Transport
Provides both SSE and streamable-HTTP endpoints on the same port:

```bash
mcp-pypi serve --transport http --host 0.0.0.0 --port 8143
```

This starts:
- SSE endpoint: `http://host:port/sse`
- Streamable-HTTP endpoint: `http://host:port/mcp`

## Configuration

### Claude Desktop Configuration

Add to your Claude Desktop settings:

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

### Environment Variables

- `MCP_PYPI_CACHE_DIR`: Override default cache location
- `MCP_PYPI_LOG_LEVEL`: Set logging verbosity (DEBUG, INFO, WARNING, ERROR)
- `MCP_PYPI_USER_AGENT`: Custom user agent for PyPI requests

## Available Tools

MCP-PyPI provides 21 comprehensive tools organized by category:

### Package Information (11 tools)
- `search_packages` - Search PyPI to discover Python packages
- `get_package_info` - Get comprehensive package details
- `get_package_releases` - Get detailed release information
- `get_latest_version` - Check the latest version
- `get_dependencies` - Analyze package dependencies
- `get_dependency_tree` - Get full dependency tree
- `get_package_stats` - Get download statistics
- `check_package_exists` - Check if package exists
- `get_package_metadata` - Get package metadata
- `list_package_versions` - List all available versions
- `compare_versions` - Compare two versions

### Security Scanning (7 tools)
- `check_vulnerabilities` - Check for known vulnerabilities
- `scan_dependency_vulnerabilities` - Deep scan dependency tree
- `scan_installed_packages` - Scan Python environments
- `quick_security_check` - Pass/fail security check
- `get_security_report` - Formatted security report
- `security_audit_project` - Comprehensive project audit
- `check_requirements_txt` - Analyze requirements files
- `check_pyproject_toml` - Analyze pyproject.toml files

### Documentation (2 tools)
- `get_package_documentation` - Get documentation links
- `get_package_changelog` - Get changelog information

## Command-Line Usage

MCP-PyPI also provides direct CLI commands for testing:

### Package Commands
```bash
# Get package info
mcp-pypi package info requests

# Get latest version
mcp-pypi package version numpy

# Show releases
mcp-pypi package releases django --limit 5

# Get dependencies
mcp-pypi package dependencies flask
```

### Search Commands
```bash
# Search for packages
mcp-pypi search "web scraping" --limit 10
```

### Security Commands
```bash
# Check vulnerabilities
mcp-pypi package info requests --check-vulnerabilities

# Check requirements file
mcp-pypi check-requirements /path/to/requirements.txt
```

### Statistics Commands
```bash
# Get download stats
mcp-pypi stats requests
```

### Cache Management
```bash
# Clear cache
mcp-pypi cache clear

# Show cache statistics
mcp-pypi cache stats
```

## Usage Examples

### Basic Package Information
```python
# Through MCP client
result = await client.invoke_tool(
    "get_package_info",
    {"package_name": "requests"}
)
```

### Security Audit
```python
# Comprehensive project audit
result = await client.invoke_tool(
    "security_audit_project",
    {
        "project_path": "/path/to/project",
        "check_transitive": True,
        "max_depth": 3
    }
)
```

### Dependency Analysis
```python
# Deep dependency scanning
result = await client.invoke_tool(
    "scan_dependency_vulnerabilities",
    {
        "package_name": "django",
        "max_depth": 3,
        "include_dev": True
    }
)
```

### Requirements File Check
```python
# Check for outdated and vulnerable packages
result = await client.invoke_tool(
    "check_requirements_txt",
    {"file_path": "/absolute/path/to/requirements.txt"}
)
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
- `invalid_input`: Invalid parameter value
- `network_error`: Error communicating with PyPI
- `parse_error`: Error parsing response
- `file_error`: Error accessing file
- `permission_error`: Insufficient permissions

## Advanced Features

### Caching Strategies

MCP-PyPI supports three caching strategies:

1. **Memory Cache** (fast, limited size)
   ```bash
   mcp-pypi serve --cache-strategy memory
   ```

2. **Disk Cache** (persistent, unlimited size)
   ```bash
   mcp-pypi serve --cache-strategy disk --cache-dir /path/to/cache
   ```

3. **Hybrid Cache** (best of both, default)
   ```bash
   mcp-pypi serve --cache-strategy hybrid
   ```

### Security Features

1. **Version Constraint Analysis**
   - Detects when constraints like `>=2.0.0` allow vulnerable versions
   - Recommends safe version ranges

2. **Transitive Dependency Scanning**
   - Scans dependencies of dependencies
   - Configurable depth (1-3 levels)

3. **File Discovery**
   - Automatically finds ALL dependency files
   - Checks consistency across files

### Performance Optimization

- Async operations throughout
- Parallel dependency resolution
- ETag-based HTTP caching
- Configurable rate limiting

## Integration Examples

### Python Client Example

```python
import asyncio
import httpx
from mcp import Client

async def use_mcp_pypi():
    async with httpx.AsyncClient() as http_client:
        async with Client("http://localhost:8080/mcp", http_client) as client:
            # Search for packages
            result = await client.invoke_tool(
                "search_packages",
                {"query": "data visualization", "limit": 5}
            )
            
            # Check each for vulnerabilities
            for package in result["packages"]:
                vulns = await client.invoke_tool(
                    "check_vulnerabilities",
                    {"package_name": package["name"]}
                )
                print(f"{package['name']}: {vulns['total_vulnerabilities']} vulnerabilities")

asyncio.run(use_mcp_pypi())
```

### CI/CD Integration

```yaml
# GitHub Actions example
- name: Security Check
  run: |
    pip install mcp-pypi
    mcp-pypi serve --transport http --port 8080 &
    sleep 2
    # Use the quick_security_check tool via your MCP client
```

## Best Practices

1. **Always Check Security First**
   - Run `security_audit_project` before deployments
   - Use `check_vulnerabilities` before installing new packages

2. **Keep Dependencies Updated**
   - Regular audits with `check_requirements_txt`
   - Monitor transitive dependencies

3. **Use Specific Versions in Production**
   - Pin exact versions after security verification
   - Document why specific versions were chosen

4. **Leverage Caching Wisely**
   - Use hybrid cache for development
   - Clear cache when security checking

## Troubleshooting

### Server Won't Start
- Check if port is already in use
- Verify `mcp-pypi` is in PATH
- Try with `--log-level DEBUG`

### Connection Issues
- For stdio: Ensure proper MCP client configuration
- For HTTP: Check firewall/network settings
- Verify transport matches client expectations

### Cache Issues
- Clear cache with `mcp-pypi cache clear`
- Check cache directory permissions
- Try different cache strategy

### Performance Issues
- Reduce `max_depth` for dependency scanning
- Use memory cache for faster responses
- Enable HTTP keep-alive for multiple requests

## Support

- GitHub Issues: https://github.com/kimasplund/mcp-pypi/issues
- Author: Kim Asplund (kim.asplund@gmail.com)
- Website: https://asplund.kim