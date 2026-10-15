# Changelog

All notable changes to MCP-PyPI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.0.1] - Unreleased

### Fixed
- Links in the README now work on the PyPI project page (they were relative and returned 404 there).
- `mcp-pypi --readme` and `mcp-pypi --changelog` work in installed packages; README and CHANGELOG are now bundled in the wheel.
- The PyPI summary and the CLI help banner describe what v4 does (MCP server plus dependency vulnerability auditing).
- The `get_package_changelog` documentation matches its behaviour: only GitHub release pages are fetched, other changelog links are returned without being requested.

## [4.0.0] - 2026-10-15

mcp-pypi 4.0 is a rework of the server and tool set. If you only use it through an MCP client, update the client config to `uvx mcp-pypi serve` (see the README) and let your assistant discover the new tools. If you import `mcp_pypi` in Python or run the HTTP server, read the breaking changes below.

### Breaking changes

- **23 tools are now 11** (mapping below). Tool names, parameters and result shapes changed.
- Tools return typed structured output with an `outputSchema`. Failures are reported as MCP tool errors (`isError`) instead of `{"error": ...}` results.
- **SSE transport removed.** HTTP mode is streamable HTTP only, at `http://127.0.0.1:8143/mcp`; the `/sse` endpoint is gone.
- HTTP mode on a loopback address rejects requests whose `Host` header is not a loopback name (HTTP 421) or whose `Origin` is another site (HTTP 403), as DNS-rebinding protection.
- The hardcoded MCP protocol version is removed; the SDK negotiates it.
- Python 3.11 or newer is required (3.10 is no longer supported).
- aiohttp 3.14.3 or newer is required; earlier releases have known OSV advisories.
- Now built on fastmcp 4.1 (MCP Python SDK 2.x).
- Removed Python modules: `mcp_pypi.client`, `mcp_pypi.cli.server` (`RPCServer`), `mcp_pypi.utils.cache`, `mcp_pypi.utils.common`, `mcp_pypi.core.requirements_ops`, and the `PyPIMCPServer` class. Use `mcp_pypi.server.build_server(config)`, which returns a `fastmcp.FastMCP` instance.
- Extras `[all]`, `[viz]`, `[search]` and `[docs]` are removed. A plain `pip install mcp-pypi` has everything; `[http]` is not needed either.
- License is now MIT only. The commercial license was dropped.
- The User-Agent is now `mcp-pypi/<version> (+https://github.com/kimasplund/mcp-pypi)`.
- The default cache directory is now the per-user cache directory (`~/.cache/mcp-pypi` on Linux, via `platformdirs`) instead of the shared `<system temp dir>/pypi_mcp_cache`. `PYPI_CACHE_DIR` and `--cache-dir` still override it.
- CLI changes:
  - `search` takes `--limit` instead of `--page`.
  - `stats downloads` no longer has `--version` or the monthly table; it reports the pypistats last day, week and month.
  - `check-requirements` now runs the full project audit (vulnerable, outdated and unchecked dependencies) and accepts a project directory or a dependency file. It exits `1` if any dependency is vulnerable, `2` on an error and `0` otherwise; an audit that leaves some dependencies unchecked but finds no vulnerabilities exits `0`. Its `--color/--no-color` option is removed.

### Tool mapping (v3 to v4)

| # | v4.0 tool | Signature | Replaces (v3) |
|---|---|---|---|
| 1 | `search_packages` | `(query: str, limit: int = 10)` | `search_packages` |
| 2 | `get_package` | `(package_name: str, version: str \| None = None)` | `get_package_info`, `get_package_metadata`, `get_latest_version`, `check_package_exists`, `get_package_documentation` |
| 3 | `get_package_versions` | `(package_name: str, limit: int = 20, offset: int = 0, sort: Literal["newest","oldest"] = "newest")` | `get_package_releases`, `list_package_versions` |
| 4 | `compare_versions` | `(package_name: str, version1: str, version2: str)` | `compare_versions` |
| 5 | `get_package_changelog` | `(package_name: str, version: str \| None = None)` | `get_package_changelog` |
| 6 | `get_download_stats` | `(package_name: str)` | `get_package_stats` |
| 7 | `get_dependencies` | `(package_name: str, version: str \| None = None, depth: int = 1)` | `get_dependencies`, `get_dependency_tree` |
| 8 | `check_packages` | `(names: list[str])` | `batch_check_packages` |
| 9 | `check_vulnerabilities` | `(packages: list[str], include_transitive: bool = False, max_depth: int = 2)` | `check_vulnerabilities`, `batch_check_vulnerabilities`, `scan_dependency_vulnerabilities` |
| 10 | `audit_project` | `(path: str, detail: Literal["summary","full"] = "summary")` | `security_audit_project`, `quick_security_check`, `get_security_report`, `check_requirements_txt`, `check_pyproject_toml` |
| 11 | `scan_installed_packages` | `(environment_path: str \| None = None)` | `scan_installed_packages` |

Removed without replacement: ANSI-colour report formatting and the `output_format` parameters (use `detail` on `audit_project`; the other tools always return structured data).

### Added

- `audit_project`: audits a directory or a single file. Supported: `requirements*.txt`, `constraints*.txt`, `pyproject.toml` (including Poetry), `setup.py` (parsed, never executed), `setup.cfg`, `Pipfile`, `Pipfile.lock`, `poetry.lock` and the pip section of conda `environment.yml`.
- `check_packages`: verifies that package names exist (with latest version and summary) so assistants can check names before suggesting them.
- Prompts now take arguments (`analyze_dependencies`, `compare_packages`).
- CI on every push and pull request, and a release workflow that publishes to PyPI with Trusted Publishing.

### Fixed

- **Vulnerability checks now use OSV's own version matching.** Earlier versions sent the version where OSV ignores it and then filtered the advisories themselves. Checks of several packages at once (`check_vulnerabilities` with two or more items, `audit_project`, `scan_installed_packages`, `check-requirements`) could report vulnerable pins as clean, and single-package checks missed advisories that cover several version ranges (for example 20 of the 56 advisories for Django 3.2.5). Vulnerability results cached by earlier versions are ignored.
- `get_package` and `get_dependencies` report a version that does not exist as a missing version (naming the latest release) instead of claiming the package does not exist.
- **Search works again.** PyPI's HTML search page is behind a JavaScript challenge. `search_packages` now searches the PyPI Simple index of package names locally and ranks by name match and download popularity. It matches package names, not full descriptions. The index is cached on disk (see `docs/caching.md`).
- Download stats no longer fabricate numbers when pypistats is unavailable; the call fails instead.
- `get_package_changelog` no longer requests arbitrary URLs taken from package metadata (a malicious package could point them at local services). It only calls the GitHub releases API for real `github.com` URLs, matched by parsed hostname instead of substring; other changelog URLs are returned as links.
- Vulnerability checks match mixed-case and underscore names (`Django`, `PyYAML`, `typing_extensions`) and count GitHub advisory `MODERATE` severity as medium.
- Installed-package scans read the environment's package metadata directly instead of running its interpreter, so they work in uv-created virtualenvs that have no pip, never execute code from the scanned environment, and never silently scan an unrelated environment. The path must be a venv (`pyvenv.cfg`) or conda environment (`conda-meta/`).
- Audits never report unchecked dependencies or unreadable files as clean. `check_vulnerabilities` lists items it could not check in `unchecked` and fails only when none could be checked; `audit_project` says when it stopped discovering files at the 50-file cap; a `setup.py` whose `install_requires` is not a literal list of strings is reported as unreadable instead of as having no dependencies.
- Upper-bound-only constraints (for example `urllib3<2`) are checked at the highest allowed release instead of an arbitrary one.

## [3.0.0] - 2026-01-26

### 🚨 Breaking Changes
- **BREAKING**: Upgraded from mcp SDK's built-in FastMCP to standalone fastmcp 2.14.4

### 🔧 Improvements
- Refactored server module from monolithic ~2800 lines to modular architecture
- Refactored core module from ~2770 lines to mixin-based architecture
- Refactored CLI module to command-based structure
- FastMCP initialization compatibility with current API (removed unsupported description parameter)
- Transport handling for HTTP mode with proper host/port configuration

### 🚀 New Features
- **Tool annotations**: Added readOnlyHint and openWorldHint for LLM safety hints
- **Tool tags**: Added categorization tags (security, package, dependencies, file, search)
- **Modern FastMCP 2.14.4 features**: instructions parameter, improved transport handling
- **New modular tool files**:
  - package_tools.py
  - search_tools.py
  - dependency_tools.py
  - vulnerability_tools.py
  - audit_tools.py
  - file_tools.py
- **New core mixin modules**:
  - package_ops.py
  - dependency_ops.py
  - vulnerability_ops.py
  - feed_ops.py
  - requirements_ops.py
  - search_ops.py
- **New CLI command modules**:
  - package_commands.py
  - search_commands.py
  - feed_commands.py
  - cache_commands.py

## [2.7.1] - 2025-06-24

### 🔧 Improvements
- **Enhanced dependency file hierarchy guidance**:
  - Clear instructions that pyproject.toml is the PRIMARY source
  - Requirements.txt is SECONDARY (often generated)
  - Update workflow: pyproject.toml → requirements.txt → setup.py
- **Improved next_steps logic**:
  - Detects if pyproject.toml exists and guides accordingly
  - Different guidance based on which files are present
  - Emphasizes "trickle down" approach for consistency
- **Updated tool descriptions**:
  - POST-AUDIT checklist now shows correct update order
  - Warnings about common mistakes (updating wrong file first)
  - Clear commit message suggestions for all files

### 📚 Documentation
- Updated TOOL_DESCRIPTION_IMPROVEMENTS.md with:
  - Python dependency file priority order
  - Correct update workflow for LLMs
  - Key principles for maintaining consistency

## [2.7.0] - 2025-06-24

### 🚀 New Features
- **Enhanced tool descriptions for better LLM guidance**:
  - Added explicit action directives (e.g., "UPDATE ALL dependency files")
  - Clear warnings about checking multiple dependency locations
  - POST-AUDIT ACTION CHECKLIST for comprehensive fixes
- **Improved tool outputs**:
  - Added `action_required` and `next_steps` fields when vulnerabilities found
  - Automatic detection of other dependency files in the project
  - Specific guidance on maintaining consistency across files

### 📚 Documentation
- Added TOOL_DESCRIPTION_IMPROVEMENTS.md with detailed guidance on:
  - How LLMs should handle security findings
  - Ensuring all dependency files are updated
  - Maintaining version consistency
  - Future improvements roadmap

## [2.6.9] - 2025-06-24

### 🔐 Security Updates
- **Updated minimum version constraints** to eliminate all security vulnerabilities:
  - aiohttp: `>=3.10.11` → `>=3.12.13` (in both requirements.txt and pyproject.toml)
  - pydantic: `>=2.0.0` → `>=2.11.7` (in both requirements.txt and pyproject.toml)
- Now fully compliant with OSV scanner requirements - no vulnerable versions allowed

## [2.6.8] - 2025-06-24

### 🔐 Security Enhancements
- **Enhanced version constraint security checking**:
  - Now checks if minimum allowed version (e.g., `>=3.8.0`) has vulnerabilities
  - Automatically finds and recommends the earliest safe version
  - Provides clear security recommendations for updating constraints
  - Prevents situations where constraints allow vulnerable versions
- **Updated aiohttp minimum version** from `>=3.8.0` to `>=3.10.11` to address security vulnerabilities

### 🔧 Improvements
- Added `_find_earliest_safe_version()` helper method for intelligent version recommendations
- Enhanced both requirements.txt and pyproject.toml checking with security awareness
- Improved alignment with OSV scanner behavior for better CI/CD compatibility

## [2.6.7] - 2025-06-24

### 🔧 Improvements
- **Enhanced pyproject.toml classifiers** for better PyPI discoverability:
  - Added "Topic :: Software Development :: Quality Assurance"
  - Added "Topic :: Security" 
  - Added "Topic :: System :: Monitoring"
  - Added "Environment :: Console"
  - Added additional intended audiences (Information Technology, System Administrators)

## [2.6.6] - 2025-06-24

### 📚 Documentation
- **Enhanced README** with comprehensive updates:
  - Added missing tools to Available Tools section (4 tools were undocumented)
  - Added System Requirements section (Python 3.10+)
  - Added CLI Usage section with examples for all commands
  - Added Troubleshooting section with common issues and solutions
  - Added personal website to Support section
  - Now documents all 21 available tools

## [2.6.5] - 2025-06-24

### 🐛 Bug Fixes
- **Fixed `mcp-pypi stdio` command** - Now properly passes all required parameters
  - Added missing `cache_ttl` and `user_agent` parameters
  - Fixed port to use correct default (8143)
  - Ensures stdio command works as exact alias for serve

## [2.6.4] - 2025-06-24

### 🎉 New Features
- **Added `mcp-pypi stdio` command** for better LLM compatibility
  - Many LLMs default to trying `stdio` as a subcommand
  - This is now an alias for `mcp-pypi serve` with stdio transport
  - Improves user experience and reduces configuration errors

- **Added `--help-connecting` option** to both `serve` and `stdio` commands
  - Shows detailed connection examples for Claude Desktop and Claude Code
  - Displays JSON configuration snippets with syntax highlighting
  - Provides platform-specific file paths (macOS/Windows)
  - Includes advanced configuration examples and troubleshooting tips
  - For HTTP transport, shows API usage examples with curl

- **Added `--readme` option** to main command
  - Displays the full README documentation in a formatted, readable way
  - Uses Rich library for beautiful markdown rendering
  - Includes syntax highlighting for code blocks
  - Automatically uses pager for long content
  - Works both in development and when installed as a package

- **Added `--changelog` option** to main command
  - Shows the complete version history in formatted markdown
  - Helps users quickly see what's new and what has changed
  - Uses the same beautiful rendering as --readme
  - Provides fallback link to GitHub if file not found

### 🔧 Improvements
- **Enhanced tool parameter descriptions** for better LLM understanding
  - Added type information (str, int, bool) and required/optional status
  - Included concrete examples for all parameters
  - Clarified default values for optional parameters
  - Added platform-specific examples for file paths (Linux/Mac/Windows)
  - Included common error sections to help avoid mistakes
  - Updated all file-related tools to explicitly require absolute paths

## [2.6.3] - 2025-06-24

### 🐛 Bug Fixes
- **Token Limit Issues**: Properly handle large responses that exceed MCP's 25K token limit
  - check_vulnerabilities: Limited to 20 vulnerabilities with essential fields only
  - get_package_changelog: Use GitHub API pagination (per_page=5) instead of fetching all
  - Trimmed summaries (500 chars), CVE lists (5), and references (3) per vulnerability
  - Added truncation notes when results are limited

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

[3.0.0]: https://github.com/kimasplund/mcp-pypi/compare/v2.7.1...v3.0.0
[2.6.1]: https://github.com/kimasplund/mcp-pypi/compare/v2.6.0...v2.6.1
[2.2.0]: https://github.com/kimasplund/mcp-pypi/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/kimasplund/mcp-pypi/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/kimasplund/mcp-pypi/releases/tag/v2.0.0