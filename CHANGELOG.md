# Changelog

All notable changes to MCP-PyPI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.6.2] - 2025-06-24

### 🎉 New Features
- **Comprehensive Dependency File Support**: security_audit_project now scans ALL common Python dependency files:
  - setup.py / setup.cfg
  - Pipfile / Pipfile.lock
  - poetry.lock
  - environment.yml / conda.yml
  - constraints.txt
  - (in addition to existing requirements.txt and pyproject.toml support)

- **Beautiful Security Reports**: Added formatted security reports with:
  - Color-coded severity levels (🚨 RED=Critical, ⚠️ ORANGE=High, etc.)
  - ASCII art tables showing vulnerability distribution
  - Visual progress bars for each severity level
  - Prioritized fix recommendations with clear action items
  - Security score (0-100) with color indicators

- **New Security Tools**:
  - `get_security_report`: Returns a beautifully formatted, color-coded security report
  - `quick_security_check`: Simple pass/fail check for CI/CD pipelines

### 🐛 Bug Fixes
- Fixed method reference errors in security_audit_project (changed from self.method to direct function calls)
- Fixed vulnerability counting bug in scan_installed_packages (now correctly sums vulnerabilities)

### 🔧 Improvements
- Enhanced security_audit_project to be truly comprehensive, living up to its name
- Better handling of different dependency file formats with specific parsers for each type
- Added formatted_report field to security_audit_project output
- Improved user experience with visual security reporting

## [2.6.1] - 2025-06-24

### 🎉 New Features
- **OSV Vulnerability Integration**: Implemented check_vulnerabilities using Google's OSV database for comprehensive security scanning
- **Package Changelog Retrieval**: Added get_package_changelog method with GitHub releases integration and metadata parsing (limited to 5 releases to avoid token limits)
- **Complete RSS Feed Support**: Implemented all PyPI RSS feeds - packages.xml, updates.xml, and project releases
- **Enhanced HTTP Client**: Added support for POST requests with JSON payloads for OSV API integration
- **Version Parsing Improvements**: Better handling of git commit hashes and pre-release versions

### 🔧 Improvements
- **Better Error Handling**: Added proper package existence checks before vulnerability scanning
- **XML Content Support**: HTTP client now correctly handles and returns raw XML/RSS content
- **Cache Attribute Fix**: Corrected cache reference from self.cache_manager to self.cache throughout
- **Security Enhancements**: Using defusedxml for safe XML parsing of RSS feeds

### 🐛 Bug Fixes
- Fixed AttributeError when accessing cache in check_vulnerabilities method
- Fixed RSS feed parsing by properly handling raw XML responses from HTTP client
- Fixed version parsing for packages using git commit hashes
- Added error handling for non-existent packages in vulnerability checks
- Fixed method naming mismatch for RSS feeds (get_packages_feed, get_releases_feed)
- Fixed changelog token limit issue by truncating to 5 releases with 1000 char limit per release

### 📝 Documentation
- Updated CLAUDE.md with latest build/test commands and code patterns
- Enhanced inline documentation for new methods
- Added security best practices for XML parsing

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

[2.6.1]: https://github.com/kimasplund/mcp-pypi/compare/v2.6.0...v2.6.1
[2.2.0]: https://github.com/kimasplund/mcp-pypi/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/kimasplund/mcp-pypi/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/kimasplund/mcp-pypi/releases/tag/v2.0.0