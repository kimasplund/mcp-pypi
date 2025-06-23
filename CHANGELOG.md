# Changelog

All notable changes to MCP-PyPI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.0] - 2025-06-23

### 🎉 New Features
- **Enhanced Tool Descriptions**: All tools now have compelling, action-oriented descriptions with emojis for better LLM discoverability
- **Unified CLI**: Single `mcp-pypi` entry point with logical subcommands instead of multiple separate commands
- **Improved Server Description**: FastMCP server now includes an engaging description highlighting key capabilities

### 🔧 Improvements
- **Better Tool Naming**: Tools clearly indicate they work with "Python packages from PyPI"
- **Rich Examples**: Tool descriptions include practical examples showing expected outputs
- **Consistent Cache TTL**: Default cache duration unified to 1 week (604800 seconds) across all components
- **Enhanced README**: Complete rewrite with emojis, badges, and clear sections for PyPI presentation

### 🐛 Bug Fixes
- Fixed cache directory initialization when `cache_dir` is None
- Fixed inconsistent cache TTL defaults between CLI and models
- Resolved import errors from removed protocol negotiation utilities

### 📝 Documentation
- Added comprehensive CLAUDE.md for AI code assistants
- Created tool_descriptions.py with detailed descriptions for all tools
- Updated all documentation to reflect new CLI structure
- Added clear examples and use cases throughout

### 🚨 Breaking Changes
- Removed `mcp-pypi-server`, `mcp-pypi-run`, and `mcp-pypi-rpc` entry points
- All functionality now accessible through `mcp-pypi` command with subcommands
- Transport options simplified to "stdio" and "http" (http includes both SSE and streamable-http)

### Migration Guide
- Replace `mcp-pypi-server` with `mcp-pypi serve`
- Replace `mcp-pypi-run --transport stdio` with `mcp-pypi serve --transport stdio`
- HTTP transport now automatically provides both /sse and /mcp endpoints

## [2.1.0] - 2025-06-20

### Added
- Initial unified CLI structure
- Basic MCP server implementation
- PyPI client with caching support

## [2.0.0] - 2025-06-15

### Added
- Complete rewrite using FastMCP
- Support for Model Context Protocol
- Advanced caching system
- Multiple transport options

[2.2.0]: https://github.com/kimasplund/mcp-pypi/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/kimasplund/mcp-pypi/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/kimasplund/mcp-pypi/releases/tag/v2.0.0