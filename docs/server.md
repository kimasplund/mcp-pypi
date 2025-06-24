# MCP-PyPI Server Architecture

This document provides detailed information about the MCP-PyPI server implementation, architecture, and capabilities.

## Overview

MCP-PyPI is a security-focused Model Context Protocol server that provides comprehensive PyPI package management capabilities. Built on FastMCP, it offers:

- 21 tools for package discovery, security scanning, and dependency analysis
- Multiple transport options (STDIO and HTTP)
- Advanced caching strategies
- Real-time vulnerability checking
- Comprehensive error handling

## Architecture

### Core Components

```
mcp_pypi/
├── server/
│   └── __init__.py      # PyPIMCPServer class (main server)
├── core/
│   ├── __init__.py      # PyPIClient (async PyPI API client)
│   ├── cache.py         # Caching implementations
│   └── models/          # Pydantic models for data validation
└── cli/
    ├── main.py          # Unified CLI entry point
    └── server_command.py # MCP server command implementation
```

### PyPIMCPServer

The main server class that:
- Inherits from FastMCP for protocol compliance
- Registers all 21 tools with proper typing
- Manages the PyPI client instance
- Handles transport negotiation

```python
class PyPIMCPServer:
    """A fully compliant MCP server for PyPI functionality."""
    
    def __init__(self, config: Optional[PyPIClientConfig] = None):
        self.client = PyPIClient(config or PyPIClientConfig())
        self.mcp_server = FastMCP(name="mcp-pypi")
        self._register_tools()
```

### PyPIClient

Async client for PyPI API interactions:
- Configurable caching (memory/disk/hybrid)
- ETag support for efficient updates
- Rate limiting and retry logic
- User agent customization

## Transport Mechanisms

### STDIO Transport (Default)

Used for integration with MCP clients like Claude Desktop:

```bash
mcp-pypi serve
```

Features:
- Direct process communication
- No network overhead
- Ideal for local integrations

### HTTP Transport

Provides both SSE and streamable-HTTP endpoints:

```bash
mcp-pypi serve --transport http --port 8080
```

Endpoints:
- `/sse` - Server-Sent Events for real-time updates
- `/mcp` - Streamable HTTP for request/response

## Tool Categories

### 1. Package Information Tools

Tools for discovering and analyzing packages:

- `search_packages` - Full-text search across PyPI
- `get_package_info` - Comprehensive package metadata
- `get_latest_version` - Quick version check
- `get_package_stats` - Download statistics
- `list_package_versions` - Version history

### 2. Dependency Analysis Tools

Tools for understanding package relationships:

- `get_dependencies` - Direct dependencies with constraints
- `get_dependency_tree` - Recursive dependency graph
- `compare_versions` - Version comparison logic

### 3. Security Scanning Tools

Advanced security analysis capabilities:

- `check_vulnerabilities` - OSV database integration
- `scan_dependency_vulnerabilities` - Deep tree scanning
- `scan_installed_packages` - Environment auditing
- `security_audit_project` - Complete project analysis

### 4. File Analysis Tools

Project-level dependency management:

- `check_requirements_txt` - Requirements file analysis
- `check_pyproject_toml` - Modern Python project files

### 5. Documentation Tools

Package documentation and changelogs:

- `get_package_documentation` - Find documentation URLs
- `get_package_changelog` - Extract changelog data

## Security Features

### Vulnerability Detection

Integration with Google's OSV (Open Source Vulnerabilities) database:

```python
async def check_vulnerabilities(self, package_name: str, version: Optional[str] = None):
    """Check for known vulnerabilities using OSV API."""
    # Queries OSV database for CVEs and security advisories
    # Returns severity-classified vulnerability list
```

### Version Constraint Analysis

Detects when version constraints allow vulnerable versions:

```python
# Checks if constraints like ">=2.0.0" allow vulnerable versions
# Recommends safe version ranges
```

### Transitive Dependency Scanning

Recursive scanning of dependency trees:

```python
async def scan_dependency_vulnerabilities(
    self, 
    package_name: str,
    max_depth: int = 2,
    include_dev: bool = False
):
    """Deep scan for hidden vulnerabilities in dependencies."""
```

## Caching System

### Cache Strategies

1. **Memory Cache**
   - Fast, in-memory storage
   - Limited by available RAM
   - Lost on restart

2. **Disk Cache**
   - Persistent storage
   - Survives restarts
   - Slower than memory

3. **Hybrid Cache** (Default)
   - Memory cache with disk backup
   - Best performance/persistence balance
   - Automatic promotion/demotion

### Cache Implementation

```python
class HybridCache(CacheProtocol):
    """Two-tier cache: memory (L1) and disk (L2)."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.memory_cache = MemoryCache()
        self.disk_cache = DiskCache(cache_dir)
```

## Error Handling

Comprehensive error handling with typed responses:

```python
class ErrorResult(TypedDict):
    error: ErrorDict

class ErrorDict(TypedDict):
    code: str
    message: str
    details: NotRequired[Dict[str, Any]]
```

Error codes follow a consistent pattern:
- `not_found` - Resource not found
- `invalid_input` - Validation failure
- `network_error` - Connection issues
- `parse_error` - Data parsing failure

## Configuration

### Environment Variables

- `MCP_PYPI_CACHE_DIR` - Cache directory location
- `MCP_PYPI_LOG_LEVEL` - Logging verbosity
- `MCP_PYPI_USER_AGENT` - Custom user agent

### Server Configuration

```python
config = PyPIClientConfig(
    cache_dir=Path("~/.cache/mcp-pypi"),
    cache_strategy="hybrid",
    user_agent="MCP-PyPI/2.6.8",
    request_timeout=30.0,
    max_retries=3
)
```

## Performance Optimization

### Async Operations

All I/O operations are async for maximum concurrency:

```python
async def get_package_info(self, package_name: str) -> PackageInfo:
    """Async package info retrieval."""
    return await self.client.get_package_info(package_name)
```

### Parallel Processing

Dependency trees are processed in parallel:

```python
# Fetch all dependencies concurrently
tasks = [self._fetch_dep(dep) for dep in dependencies]
results = await asyncio.gather(*tasks)
```

### Efficient Caching

- ETag validation reduces unnecessary downloads
- Selective cache invalidation for security data
- Configurable TTL for different data types

## Monitoring and Logging

### Structured Logging

```python
logger.info(
    "Package vulnerability check",
    extra={
        "package": package_name,
        "version": version,
        "vulnerabilities_found": len(vulns)
    }
)
```

### Performance Metrics

- Request latency tracking
- Cache hit/miss ratios
- API rate limit monitoring

## Integration Patterns

### With Claude Desktop

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

### With Custom MCP Clients

```python
from mcp import Client
import httpx

async with httpx.AsyncClient() as http:
    async with Client("http://localhost:8080/mcp", http) as client:
        result = await client.invoke_tool(
            "security_audit_project",
            {"project_path": "/path/to/project"}
        )
```

### In CI/CD Pipelines

```yaml
- name: Security Audit
  run: |
    mcp-pypi serve --transport http &
    SERVER_PID=$!
    # Run security checks
    kill $SERVER_PID
```

## Future Enhancements

Planned improvements include:

1. **WebSocket Transport** - Real-time bidirectional communication
2. **GraphQL Interface** - Flexible query capabilities
3. **Webhook Support** - Event-driven notifications
4. **Multi-tenant Support** - Isolated environments
5. **Plugin Architecture** - Extensible tool system

## Technical Details

### Protocol Compliance

MCP-PyPI implements the full MCP specification:
- Protocol version negotiation
- Capability advertisement
- Tool discovery and invocation
- Error handling standards

### Security Considerations

- No credentials stored or transmitted
- Rate limiting to prevent abuse
- Input validation on all parameters
- Safe file path handling

### Performance Characteristics

- Startup time: <1 second
- Tool response time: 50-500ms (cached)
- Memory usage: 50-200MB
- Concurrent requests: Unlimited (async)

## Troubleshooting

Common issues and solutions:

1. **Port Already in Use**
   ```bash
   mcp-pypi serve --transport http --port 8081
   ```

2. **Cache Corruption**
   ```bash
   mcp-pypi cache clear
   ```

3. **SSL Certificate Issues**
   ```bash
   export REQUESTS_CA_BUNDLE=/path/to/cert
   ```

## Support

- GitHub: https://github.com/kimasplund/mcp-pypi
- Author: Kim Asplund (kim.asplund@gmail.com)
- License: MIT