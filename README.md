# 🐍 MCP-PyPI

[![PyPI](https://img.shields.io/pypi/v/mcp-pypi.svg)](https://pypi.org/project/mcp-pypi/)
[![License](https://img.shields.io/pypi/l/mcp-pypi.svg)](https://github.com/kimasplund/mcp-pypi/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/mcp-pypi.svg)](https://pypi.org/project/mcp-pypi/)
[![Downloads](https://img.shields.io/pypi/dm/mcp-pypi.svg)](https://pypi.org/project/mcp-pypi/)

A Model Context Protocol (MCP) server that provides AI agents with intelligent access to PyPI - the Python Package Index. Search, analyze, and understand Python packages with unprecedented ease.

## ✨ What is MCP-PyPI?

MCP-PyPI empowers AI assistants like Claude to interact with the Python package ecosystem. It provides real-time access to package information, dependencies, version history, and more through an intuitive set of tools.

### 🎯 Key Features

- **🔍 Smart Package Search** - Find the perfect Python package from 500,000+ options
- **📊 Download Statistics** - Gauge package popularity with real usage data  
- **🔗 Dependency Analysis** - Understand package requirements and conflicts
- **🛡️ Security Scanning** - Check for vulnerabilities and outdated dependencies
- **📋 Requirements Auditing** - Analyze and update requirements.txt files
- **🚀 Version Management** - Track releases, compare versions, check compatibility
- **⚡ Lightning Fast** - Intelligent caching for instant responses

## 🚀 Quick Start

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
```

## 🛠️ Available Tools

### Package Discovery
- **search_packages** - 🔍 Search PyPI to discover Python packages
- **get_package_info** - 📦 Get comprehensive package details
- **check_package_exists** - ✅ Verify if a package exists on PyPI

### Version Management  
- **get_latest_version** - 🚀 Check the latest available version
- **list_package_versions** - 📚 List all available versions
- **compare_versions** - 🔄 Compare two package versions

### Dependency Analysis
- **get_dependencies** - 🔗 Analyze package dependencies
- **get_dependency_tree** - 🌳 Visualize complete dependency tree
- **check_vulnerabilities** - 🛡️ Scan for security vulnerabilities

### Project Management
- **check_requirements_txt** - 📋 Audit requirements.txt files
- **check_pyproject_toml** - 🎯 Analyze pyproject.toml dependencies

### Statistics & Info
- **get_package_stats** - 📊 Get download statistics
- **get_package_metadata** - 📋 Access complete metadata
- **get_package_documentation** - 📖 Find documentation links

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

This project is licensed under a Commercial License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built on the [Model Context Protocol](https://modelcontextprotocol.io/)
- Powered by the [Python Package Index](https://pypi.org/)
- Enhanced with [FastMCP](https://github.com/modelcontextprotocol/python-sdk)

## 📞 Support

- 📧 Email: kim.asplund@gmail.com
- 🐛 Issues: [GitHub Issues](https://github.com/kimasplund/mcp-pypi/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/kimasplund/mcp-pypi/discussions)

---

Made with ❤️ for the Python and AI communities