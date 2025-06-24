# 🐍 MCP-PyPI

[![PyPI](https://img.shields.io/pypi/v/mcp-pypi.svg)](https://pypi.org/project/mcp-pypi/)
[![License](https://img.shields.io/pypi/l/mcp-pypi.svg)](https://github.com/kimasplund/mcp-pypi/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/mcp-pypi.svg)](https://pypi.org/project/mcp-pypi/)
[![Downloads](https://img.shields.io/pypi/dm/mcp-pypi.svg)](https://pypi.org/project/mcp-pypi/)

A security-focused Model Context Protocol (MCP) server that helps AI agents write safer Python code. Search packages, scan for vulnerabilities, audit dependencies, and ensure security across your entire Python project.

## ✨ What is MCP-PyPI?

MCP-PyPI is a security-focused Model Context Protocol server that empowers AI assistants to write safer Python code. Beyond basic package information, it provides comprehensive vulnerability scanning, dependency auditing, and proactive security recommendations to ensure AI-generated code uses secure, up-to-date dependencies.

**🛡️ Security First**: Every tool is designed to encourage security best practices, from checking vulnerabilities before suggesting packages to scanning entire project dependency trees for hidden risks.

### 🎯 Key Features

- **🛡️ Comprehensive Security Scanning** - Check vulnerabilities using OSV database across packages, dependencies, and entire projects
- **🔍 Security-Aware Package Search** - Find safe packages from 500,000+ options with vulnerability status
- **📋 Project-Wide Security Audits** - Scan requirements.txt, pyproject.toml, and installed environments
- **🔗 Deep Dependency Analysis** - Detect vulnerabilities in transitive dependencies others might miss
- **🚨 Proactive Security Alerts** - Get warnings before adding vulnerable packages to projects
- **📊 Risk Assessment & Scoring** - Security scores, fix time estimates, and prioritized remediation plans
- **⚡ Smart Caching** - Fast vulnerability checks with configurable TTL for different data types
- **🚀 Version Management** - Track releases, compare versions, identify security updates

### 🤔 Why Security Matters

When AI assistants suggest Python packages, they might unknowingly recommend packages with known vulnerabilities. MCP-PyPI ensures that:

- **Before Installation**: AI checks for vulnerabilities before suggesting any package
- **During Development**: Continuous scanning catches new vulnerabilities in existing dependencies  
- **Before Deployment**: Comprehensive audits ensure production code is secure
- **Transitive Safety**: Hidden vulnerabilities in dependencies-of-dependencies are detected

## 🚀 Quick Start

### System Requirements

- Python 3.10 or higher
- pip package manager
- Virtual environment (recommended)

### Installation

```bash
# Basic installation
pip install mcp-pypi

# With HTTP transport support
pip install "mcp-pypi[http]"

# With all features
pip install "mcp-pypi[all]"
```

### Running the Server

```bash
# Start with default stdio transport (for Claude Desktop)
mcp-pypi serve

# Alternative stdio command (for compatibility)
mcp-pypi stdio

# Start with HTTP transport
mcp-pypi serve --transport http

# With custom cache directory
mcp-pypi serve --cache-dir ~/.pypi-cache
```

## 🤖 Using with Claude Desktop

Add to your Claude Desktop configuration (`claude.json`):

```json
{
  "servers": {
    "pypi": {
      "command": "mcp-pypi",
      "args": ["serve"],
      "description": "Access Python package information from PyPI"
    }
  }
}

// Alternative using stdio command (equivalent to above)
{
  "servers": {
    "pypi": {
      "command": "mcp-pypi",
      "args": ["stdio"],
      "description": "Access Python package information from PyPI"
    }
  }
}
```

## 🖥️ Using with Claude Code (Terminal)

Add the MCP server to Claude Code:

```bash
# Add the server (using serve command)
claude mcp add mcp-pypi -- mcp-pypi serve

# Alternative using stdio command
claude mcp add mcp-pypi -- mcp-pypi stdio

# The server will be available in your next Claude Code session
```

## 🛠️ Available Tools

### Package Discovery
- **search_packages** - 🔍 Search PyPI to discover Python packages
- **get_package_info** - 📦 Get comprehensive package details
- **check_package_exists** - ✅ Verify if a package exists on PyPI

### Version Management  
- **get_latest_version** - 🚀 Check the latest available version
- **get_package_releases** - 📅 Get detailed release information for a package
- **list_package_versions** - 📚 List all available versions
- **compare_versions** - 🔄 Compare two package versions

### Dependency Analysis
- **get_dependencies** - 🔗 Analyze package dependencies
- **get_dependency_tree** - 🌳 Visualize complete dependency tree
- **check_vulnerabilities** - 🛡️ Scan for security vulnerabilities using OSV database
- **scan_dependency_vulnerabilities** - 🛡️🔍 Deep scan entire dependency tree for vulnerabilities

### Project Management
- **check_requirements_txt** - 📋🛡️ Security audit requirements.txt files
- **check_pyproject_toml** - 🎯🛡️ Security audit pyproject.toml dependencies
- **scan_installed_packages** - 🛡️💻 Scan virtual/system environments for vulnerabilities
- **security_audit_project** - 🛡️🔍🚨 Comprehensive project-wide security audit
- **quick_security_check** - 🚦 Quick pass/fail security check for CI/CD
- **get_security_report** - 🛡️📊 Beautiful, color-coded security report

### Statistics & Info
- **get_package_stats** - 📊 Get download statistics
- **get_package_metadata** - 📋 Access complete metadata
- **get_package_documentation** - 📖 Find documentation links
- **get_package_changelog** - 📝 Get changelog information from GitHub releases

## 💡 Example Usage

Once configured, you can ask Claude:

- "Search for web scraping packages on PyPI"
- "What's the latest version of Django?"
- "Check if my requirements.txt has any outdated packages"
- "Show me the dependencies for FastAPI"
- "Find popular data visualization libraries"
- "Compare pandas version 2.0.0 with 2.1.0"

## 🔧 Advanced Configuration

### Environment Variables

```bash
# Custom cache directory
export PYPI_CACHE_DIR=/path/to/cache

# Cache TTL (seconds)
export PYPI_CACHE_TTL=3600

# Vulnerability cache TTL (seconds) - default 1 hour
export PYPI_VULNERABILITY_CACHE_TTL=3600

# Custom user agent
export PYPI_USER_AGENT="MyApp/1.0"
```

### Programmatic Usage

```python
from mcp_pypi.server import PyPIMCPServer
from mcp_pypi.core.models import PyPIClientConfig

# Custom configuration
config = PyPIClientConfig(
    cache_dir="/tmp/pypi-cache",
    cache_ttl=7200,
    cache_strategy="hybrid"
)

# Create and run server
server = PyPIMCPServer(config=config)
server.run(transport="http", host="0.0.0.0", port=8080)
```

## 📊 Performance

- **Intelligent Caching**: Hybrid memory/disk caching with LRU/LFU/FIFO strategies
- **Concurrent Requests**: Async architecture for parallel operations
- **Minimal Overhead**: Direct PyPI API integration
- **Configurable TTL**: Control cache duration based on your needs

## 🛡️ Security & Caching

### Vulnerability Data Caching

Vulnerability checks are cached to improve performance and reduce API load:

- **Default TTL**: 1 hour (3600 seconds)
- **Configurable**: Use `PYPI_VULNERABILITY_CACHE_TTL` environment variable
- **Cache Key**: Based on package name + version
- **OSV API**: Queries are cached to avoid repeated lookups

### Why Caching Matters

1. **Performance**: Vulnerability checks can be slow, caching makes subsequent checks instant
2. **Rate Limiting**: Prevents hitting OSV API rate limits during large scans
3. **Consistency**: Ensures consistent results during a security audit
4. **Offline Support**: Cached results available even if OSV API is unreachable

### Cache Management

```bash
# Clear all caches
mcp-pypi cache clear

# View cache statistics
mcp-pypi cache stats

# Set shorter TTL for development (5 minutes)
export PYPI_VULNERABILITY_CACHE_TTL=300
```

## 🖥️ CLI Usage

MCP-PyPI includes a full-featured command-line interface for direct package operations:

### Help and Documentation
```bash
# Show version
mcp-pypi --version

# Display README documentation
mcp-pypi --readme

# Show changelog
mcp-pypi --changelog

# Get connection examples
mcp-pypi serve --help-connecting
mcp-pypi stdio --help-connecting
```

### Package Information
```bash
# Search for packages
mcp-pypi search "web scraping"

# Get package info
mcp-pypi package info requests

# Check latest version
mcp-pypi package version django

# List all versions
mcp-pypi package releases numpy

# Get dependencies
mcp-pypi package dependencies flask

# Compare versions
mcp-pypi package compare pandas 2.0.0 2.1.0
```

### Security Checks
```bash
# Check requirements file
mcp-pypi check-requirements /path/to/requirements.txt

# View package statistics
mcp-pypi stats downloads requests
```

### Cache Management
```bash
# Clear cache
mcp-pypi cache clear

# View cache statistics
mcp-pypi cache stats
```

## ❓ Troubleshooting

### Common Issues

**Connection Issues with stdio**
- Ensure you're using the absolute path to `mcp-pypi` in your configuration
- Try using `mcp-pypi stdio` instead of `mcp-pypi serve` for better compatibility
- Check logs with `--log-level DEBUG` for detailed error messages

**Token Limit Errors**
- Some operations like changelog retrieval are automatically limited to prevent token overflow
- Use more specific queries when searching for packages
- Check individual packages rather than bulk operations

**Cache Issues**
- Clear cache with `mcp-pypi cache clear` if you see stale data
- Adjust cache TTL with environment variables for your use case
- Default cache location is `~/.cache/mcp-pypi/`

**Import Errors**
- Ensure you have Python 3.10+ installed
- Install with `pip install "mcp-pypi[all]"` for all dependencies
- Use a virtual environment to avoid conflicts

## 🤝 Contributing

Contributions are welcome! Please check out our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/kimasplund/mcp-pypi.git
cd mcp-pypi

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run with debug logging
mcp-pypi serve --log-level DEBUG
```

## 📄 License

This project is dual-licensed:

- **Open Source**: MIT License for personal, educational, and non-profit use - see [LICENSE](LICENSE)
- **Commercial**: Commercial License required for business use - see [LICENSE-COMMERCIAL](LICENSE-COMMERCIAL)

### Quick License Guide:
- ✅ **Free to use**: Personal projects, education, non-profits, open source
- 💰 **Commercial license required**: For-profit companies, commercial products, consulting
- 📧 **Contact**: kim.asplund@gmail.com for commercial licensing

## 🙏 Acknowledgments

- Built on the [Model Context Protocol](https://modelcontextprotocol.io/)
- Powered by the [Python Package Index](https://pypi.org/)
- Security scanning via [OSV (Open Source Vulnerabilities)](https://osv.dev/) database by Google
- Enhanced with [FastMCP](https://github.com/modelcontextprotocol/python-sdk)

## 📞 Support

- 🌐 Website: [asplund.kim](https://asplund.kim)
- 📧 Email: kim.asplund@gmail.com
- 🐛 Issues: [GitHub Issues](https://github.com/kimasplund/mcp-pypi/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/kimasplund/mcp-pypi/discussions)

---

Made with ❤️ for the Python and AI communities