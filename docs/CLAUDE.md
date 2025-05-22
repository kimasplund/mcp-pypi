# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MCP-PyPI is a modern Python client library and CLI tool for interacting with the Python Package Index (PyPI). It implements the Model Context Protocol (MCP) to integrate with AI assistants like Claude.

### Core Architecture

**Modular Design with Dependency Injection:**
- `mcp_pypi.core.client.PyPIClient` - Main async client with configurable components
- `mcp_pypi.core.http.AsyncHTTPClient` - HTTP layer with caching and ETag support  
- `mcp_pypi.core.cache.AsyncCacheManager` - Thread-safe async caching
- `mcp_pypi.core.stats.PackageStatsService` - Real download statistics
- `mcp_pypi.server.PyPIMCPServer` - MCP-compliant server implementation

**Key Features:**
- True async/await throughout using aiohttp
- Comprehensive error handling with standardized error codes
- Security challenge detection for PyPI anti-scraping measures
- Support for multiple dependency file formats (requirements.txt, pyproject.toml with Poetry/PDM/Flit)
- Optional visualization with Plotly and enhanced search with BeautifulSoup

## Common Development Commands

```bash
# Install for development
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=mcp_pypi

# Run integration tests (requires network)
pytest --run-integration

# Run Docker tests (development only)
pytest tests/test_docker.py --run-docker

# Format code
black mcp_pypi tests

# Sort imports
isort mcp_pypi tests

# Type checking
mypy mcp_pypi

# Start MCP server (HTTP mode)
mcp-pypi serve

# Start MCP server (STDIN mode for MCP protocol)
mcp-pypi serve --stdin

# CLI usage examples
mcp-pypi package info requests
mcp-pypi search fastapi
mcp-pypi check-requirements requirements.txt
```

## Code Architecture Notes

**Client Configuration:**
- All components accept dependency injection for testing
- Configuration via `PyPIClientConfig` dataclass supports environment variables
- Always call `await client.close()` to release aiohttp resources

**Error Handling:**
- All methods return TypedDict types with optional `error` field
- Use `ErrorCode` constants for standardized error responses
- Network errors, parsing errors, and security challenges are handled gracefully

**Type System:**
- Complete type annotations using TypedDict for JSON responses
- Use `NotRequired` for optional fields (imported from typing_extensions for Python <3.11)
- All async methods properly typed with return type annotations

**Testing Structure:**
- Unit tests in `tests/core/` mirror the `mcp_pypi/core/` structure
- Integration tests marked with `@pytest.mark.integration`
- Docker tests for multi-version compatibility (development only)
- Mock fixtures in `conftest.py` for CI environments

**MCP Server Implementation:**
- Uses FastMCP for MCP protocol compliance
- Automatic port selection if specified port is occupied
- Tools, resources, and prompts registration patterns
- Server supports both HTTP and STDIN modes

## Important Development Patterns

**Async Resource Management:**
```python
async with PyPIClient() as client:
    result = await client.get_package_info("requests")
# Client automatically closed
```

**Error Response Checking:**
```python
result = await client.get_package_info("nonexistent")
if "error" in result:
    print(f"Error: {result['error']['message']}")
```

**Dependency Injection for Testing:**
```python
# In tests, inject mock dependencies
mock_http = MockHTTPClient()
client = PyPIClient(http_client=mock_http)
```

## Version Management

**Single Source of Truth**: Version is defined ONLY in `pyproject.toml`:
```toml
[project]
version = "2.1.0"
```

**Dynamic Import**: All code imports version dynamically:
```python
from mcp_pypi import __version__
```

**No Hardcoded Versions**: Never define version numbers in code - always import from the main module.

## Package Version Rules

When working with package dependencies:
- Always query latest versions using `get_latest_version()` tool
- Default to latest version unless constraints specified
- Use `check_requirements_file()` for dependency analysis
- Support multiple file formats: requirements.txt, pyproject.toml (PEP 621, Poetry, PDM, Flit)