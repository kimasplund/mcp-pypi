# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
MCP-PyPI is a Python 3.10+ Model Context Protocol server that provides PyPI package information through standardized AI agent interfaces. It supports two transport modes:
- **stdio**: Direct process communication (for MCP clients like Claude Desktop)
- **http**: HTTP server providing both SSE (/sse) and streamable-HTTP (/mcp) endpoints on the same port

The server implements the full MCP specification using the built-in FastMCP from mcp.server.

## Build & Test Commands

### Testing
- Run all tests: `pytest`
- Run specific test: `pytest -k "test_name"`
- Run single test file: `pytest tests/test_file.py`
- Run with coverage: `pytest --cov=mcp_pypi --cov-report=html --cov-report=term`
- Run integration tests: `pytest --run-integration`
- Debug mode: `pytest -xvs`

### Linting & Formatting
- Lint: `pylint mcp_pypi`
- Type check: `mypy mcp_pypi`
- Format: `black mcp_pypi tests`
- Sort imports: `isort mcp_pypi tests`

### Building
- Build package: `python -m build`
- Install dev: `pip install -e ".[dev,http,websocket,sse]"`
- Install basic: `pip install -e .`

## Code Architecture

### Core Components
1. **PyPIMCPServer** (`mcp_pypi/server/__init__.py`): Main MCP server class
   - Handles protocol negotiation
   - Manages tool registry (15+ PyPI operations)
   - Supports multiple transport mechanisms

2. **PyPIClient** (`mcp_pypi/core/client.py`): Async PyPI API client
   - Configurable caching (memory/disk/hybrid)
   - User agent customization
   - Rate limiting and error handling

3. **CLI Interface** (`mcp_pypi/cli/`): Typer-based unified command system
   - `main.py`: Main CLI with all commands
   - `server_command.py`: MCP server implementation
   - `server.py`: Legacy JSON-RPC server (deprecated)

### Entry Points
- `mcp-pypi`: Unified CLI with subcommands for both client and server operations
  - `mcp-pypi serve`: Start the MCP server with stdio or http transport
  - `mcp-pypi package`: Package information commands (info, version, releases, dependencies)
  - `mcp-pypi search`: Search for packages on PyPI
  - `mcp-pypi stats`: Package download statistics  
  - `mcp-pypi feed`: PyPI feed commands (newest, updates)
  - `mcp-pypi cache`: Cache management (clear, stats)
  - `mcp-pypi check-requirements`: Check requirements files for updates

### Key Patterns
- Pydantic models for data validation (`mcp_pypi/core/models/`)
- Structured error handling with ErrorCode enum
- Async/await throughout for performance
- Protocol version negotiation for compatibility
- Tool parameter validation using JSON schemas

## Configuration
Server supports environment variables and command-line arguments:
- `--transport`: stdio (default) or http
- `--host/--port`: For HTTP transport (default: 127.0.0.1:8143)
- `--cache-dir`: Custom cache location
- `--cache-strategy`: memory, disk, hybrid (default)
- `--log-level`: Logging verbosity

When using HTTP transport, the server provides:
- SSE endpoint: `http://host:port/sse`
- Streamable-HTTP endpoint: `http://host:port/mcp`

## Available Tools
The server provides 15+ tools for PyPI operations:
- Package info: search, latest version, dependencies
- File operations: check requirements.txt, pyproject.toml
- Statistics: download counts, release history
- Advanced: changelog extraction, vulnerability checks

## Code Style Guidelines
- Python 3.10+ with type hints
- Async/await for all I/O operations
- Pydantic for data validation
- Structured logging with contextual information
- Comprehensive docstrings for public APIs
- Test coverage for new features

## Common Tasks

### Adding a New Tool
1. Define tool in `PyPIMCPServer._register_tools()`
2. Implement handler method with proper typing
3. Add Pydantic model if needed in `core/models/`
4. Write tests in corresponding test file

### Running the Server
1. For MCP clients (stdio transport): `mcp-pypi serve`
2. For HTTP endpoints: `mcp-pypi serve --transport http --port 8143`
3. With custom cache: `mcp-pypi serve --cache-dir /path/to/cache`
4. Debug mode: `mcp-pypi serve --log-level DEBUG`

### Debugging
- Enable debug logging: `--log-level DEBUG`
- Check server logs for MCP protocol messages
- Use `mcp-pypi` CLI to test PyPI operations directly
- Run specific tests with `-xvs` for detailed output

## Testing Strategy
- Unit tests for individual components
- Integration tests for transport mechanisms
- Manual tests for interactive scenarios
- Mock PyPI responses for reliability