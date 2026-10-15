# 🐍 MCP-PyPI

[![PyPI](https://img.shields.io/pypi/v/mcp-pypi.svg)](https://pypi.org/project/mcp-pypi/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-pypi.svg)](https://pypi.org/project/mcp-pypi/)
[![License](https://img.shields.io/pypi/l/mcp-pypi.svg)](https://github.com/kimasplund/mcp-pypi/blob/main/LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/mcp-pypi.svg)](https://pypi.org/project/mcp-pypi/)

A Model Context Protocol (MCP) server that gives AI assistants accurate PyPI data and vulnerability checks, so the dependencies they suggest exist, are current, and have no known security advisories.

Upgrading from 3.x? The tool set changed. See [Upgrading from 3.x](CHANGELOG.md#400---unreleased).

## What it does

- Looks up package metadata, versions, dependencies, changelogs and download counts from PyPI.
- Checks packages against the [OSV](https://osv.dev/) vulnerability database, optionally including transitive dependencies.
- Audits a project: `requirements*.txt`, `constraints*.txt`, `pyproject.toml` (including Poetry), `setup.py` (parsed, never executed), `setup.cfg`, `Pipfile`, `Pipfile.lock`, `poetry.lock` and conda `environment.yml` (pip section).
- Scans an installed environment (a virtualenv) for vulnerable packages.
- Verifies that package names exist before an assistant recommends them (`check_packages`).
- Returns typed, structured results with an output schema, and reports failures as MCP tool errors.

## 🚀 Quick Start

Requires Python 3.11 or newer.

```bash
# Run without installing (recommended for MCP clients)
uvx mcp-pypi serve

# Or install it
pip install mcp-pypi
mcp-pypi serve
```

`serve` uses the stdio transport by default, which is what MCP clients that launch the server themselves expect. For HTTP, see [HTTP mode](#http-mode).

## 🤖 Using with Claude Desktop

Add the server to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "mcp-pypi": {
      "command": "uvx",
      "args": ["mcp-pypi", "serve"]
    }
  }
}
```

Restart Claude Desktop after saving. If you installed with `pip`, use `"command": "mcp-pypi"` and `"args": ["serve"]` instead (give the absolute path if Claude Desktop cannot find it).

## 🖥️ Using with Claude Code (Terminal)

```bash
claude mcp add mcp-pypi -- uvx mcp-pypi serve
```

The server is available in your next Claude Code session.

## 🖱️ Using with Cursor IDE

Cursor supports MCP servers through configuration files. Configure mcp-pypi globally (all projects) or per project.

### Quick Setup via Settings UI

1. Open Cursor Settings (`Cmd+,` on Mac, `Ctrl+,` on Windows/Linux)
2. Navigate to **Features** > **Model Context Protocol**
3. Click **Add New MCP Server**
4. Enter the configuration shown below

### Configuration File Setup

**Global Configuration** (available in all projects):

| Platform | Location |
|----------|----------|
| macOS/Linux | `~/.cursor/mcp.json` |
| Windows | `C:\Users\YourUsername\.cursor\mcp.json` |

**Project Configuration** (project-specific):
Create `.cursor/mcp.json` in your project root.

### Configuration Example

Add mcp-pypi to your `mcp.json` file:

```json
{
  "mcpServers": {
    "mcp-pypi": {
      "command": "uvx",
      "args": ["mcp-pypi", "serve"]
    }
  }
}
```

**With custom options:**

```json
{
  "mcpServers": {
    "mcp-pypi": {
      "command": "uvx",
      "args": ["mcp-pypi", "serve", "--log-level", "DEBUG"],
      "env": {
        "PYPI_CACHE_DIR": "/path/to/cache"
      }
    }
  }
}
```

### Verification

1. Restart Cursor completely after adding the configuration
2. Open any project and switch to **Agent Mode** (not Ask Mode)
3. The MCP tools should appear in the tools list
4. Test by asking: "Search for web scraping packages on PyPI"

### Troubleshooting Cursor

| Issue | Solution |
|-------|----------|
| Tools not appearing | Ensure Cursor is in Agent Mode, not Ask Mode |
| Server not starting | Check `uvx` (or `mcp-pypi`) is installed and in PATH |
| Configuration errors | Open Output panel (`Cmd+Shift+U`) and select "MCP Logs" |
| Server crashes | Toggle server off/on in Settings without removing config |

## 🌐 HTTP mode

For clients that connect over the network instead of launching the server:

```bash
mcp-pypi serve --transport http
```

The server listens on `http://127.0.0.1:8143/mcp` (streamable HTTP). Change the bind address with `--host` and `--port`. There is no authentication, so only bind to a non-loopback address on a network you trust. See [docs/transports.md](docs/transports.md).

## 🛠️ Available Tools

Eleven read-only tools. All of them return structured output with an output schema; failures are reported as MCP tool errors.

| Tool | What it does |
|------|--------------|
| `search_packages` | Search PyPI package names and return ranked matches with summaries. |
| `get_package` | Get metadata for a package: versions, license, URLs, classifiers and yank status. |
| `get_package_versions` | List released versions with upload time, yank status and file types (paginated). |
| `compare_versions` | Compare two versions of a package using PEP 440 ordering. |
| `get_package_changelog` | Get changelog text from a package's project links or GitHub releases. |
| `get_download_stats` | Get recent download counts (last day, week and month) from pypistats.org. |
| `get_dependencies` | List the requirements of a package, optionally as a transitive tree (`depth` 1-5). |
| `check_packages` | Check up to 100 package names on PyPI and report latest version and summary. |
| `check_vulnerabilities` | Check up to 100 packages against OSV for known vulnerabilities, optionally with transitive dependencies. |
| `audit_project` | Audit a project's dependency files for vulnerabilities, outdated pins and drift. |
| `scan_installed_packages` | Scan a Python environment's installed packages for known vulnerabilities. |

Parameters and result fields are documented in [docs/pypi.md](docs/pypi.md). The server also provides two prompts (`analyze_dependencies`, `compare_packages`, both taking arguments) and three read-only resources (`pypi://recent-releases`, `pypi://new-packages`, `pypi://updated-packages`).

### Notes on search

PyPI's own search page sits behind a JavaScript challenge, so `search_packages` does not use it. It searches the PyPI Simple index of package names locally and ranks matches by name similarity and download popularity. It matches names, not descriptions, so name-like keywords (`web scraping` is weaker than `scrapy` or `beautifulsoup`) work best.

## 💡 Example Usage

Once configured, you can ask your assistant:

- "Does a package called `fastapi-users` exist, and what is its latest version?"
- "Check my project's dependencies for known vulnerabilities."
- "Show me the dependency tree for FastAPI, two levels deep."
- "Compare pandas 2.0.0 with 2.1.0."
- "Find packages with `scrape` in the name and pick the most popular."

## 🔧 Configuration

### Environment Variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `PYPI_CACHE_DIR` | `<system temp dir>/pypi_mcp_cache` | Cache directory |
| `PYPI_CACHE_TTL` | `604800` (1 week) | Cache TTL in seconds |
| `PYPI_CACHE_MAX_SIZE` | `104857600` (100 MB) | Maximum cache size in bytes |
| `PYPI_CACHE_STRATEGY` | `hybrid` | Accepted for compatibility; responses are always cached as files on disk |
| `PYPI_VULNERABILITY_CACHE_TTL` | `3600` (1 hour) | TTL for vulnerability results, in seconds |
| `PYPI_MAX_RETRIES` | `3` | Retries for failed requests |
| `PYPI_RETRY_DELAY` | `1.0` | Base retry delay in seconds (exponential backoff) |
| `PYPI_TIMEOUT` | `30.0` | Request timeout in seconds |
| `PYPI_USER_AGENT` | `mcp-pypi/<version> (+https://github.com/kimasplund/mcp-pypi)` | User-Agent sent to PyPI and OSV |

`mcp-pypi serve` also accepts `--cache-dir`, `--cache-strategy`, `--cache-ttl`, `--user-agent`, `--log-level`, `--host`, `--port` and `--transport`; flags take precedence over the environment. See [docs/caching.md](docs/caching.md) for how caching works.

### Programmatic Usage

```python
from mcp_pypi.core.models import PyPIClientConfig
from mcp_pypi.server import build_server

config = PyPIClientConfig(cache_dir="/tmp/pypi-cache", cache_ttl=7200)
server = build_server(config)  # a fastmcp.FastMCP instance

server.run()  # stdio
# server.run(transport="http", host="127.0.0.1", port=8143)
```

## 🖥️ CLI Usage

The CLI calls the same code as the server, which is handy for scripts and CI.

```bash
mcp-pypi --version

# Search package names
mcp-pypi search "http client" --limit 10

# Package information
mcp-pypi package info requests
mcp-pypi package version django
mcp-pypi package releases numpy
mcp-pypi package dependencies flask
mcp-pypi package compare pandas 2.0.0 2.1.0

# Download statistics (last day, week, month)
mcp-pypi stats downloads requests

# Audit a project directory or a single dependency file
mcp-pypi check-requirements .
mcp-pypi check-requirements requirements.txt --format json --full

# Cache
mcp-pypi cache stats
mcp-pypi cache clear
```

`check-requirements` runs the same audit as the `audit_project` tool. It exits `1` if any dependency has a known vulnerability, `2` on an error, and `0` otherwise. An audit that could not check some dependencies but found no vulnerabilities also exits `0`; the unchecked dependencies are listed in the output, so read it (or use `--format json` and check `totals.unchecked`) if you gate CI on it.

## ❓ Troubleshooting

**The client cannot start the server**
- Use the absolute path to `uvx` or `mcp-pypi` in the client config if it is not on the client's `PATH`.
- Run `uvx mcp-pypi serve --log-level DEBUG` in a terminal to see startup errors. Logs go to stderr so they do not corrupt the stdio stream.

**Search returns nothing or reports the index is unavailable**
- The first search downloads the PyPI package-name index (about 4 MB, cached on disk). With no network and no cached copy, search fails with a clear error; other tools still work.

**Stale data**
- Run `mcp-pypi cache clear`, or lower `PYPI_CACHE_TTL`.

**Python version errors**
- mcp-pypi needs Python 3.11 or newer. `uvx` picks a suitable interpreter automatically.

## 🤝 Contributing

Contributions are welcome. Open an issue first for larger changes.

```bash
git clone https://github.com/kimasplund/mcp-pypi.git
cd mcp-pypi
uv sync

uv run ruff check
uv run ruff format --check
uv run pyrefly check
uv run pytest                  # offline tests
uv run pytest -m integration   # live network tests
```

## 📄 License

MIT. See [LICENSE](LICENSE).

## 🙏 Acknowledgments

- Built on the [Model Context Protocol](https://modelcontextprotocol.io/) and [FastMCP](https://github.com/PrefectHQ/fastmcp)
- Package data from the [Python Package Index](https://pypi.org/); download counts from [pypistats.org](https://pypistats.org/) and [top-pypi-packages](https://hugovk.github.io/top-pypi-packages/)
- Vulnerability data from [OSV (Open Source Vulnerabilities)](https://osv.dev/)

## 📞 Support

- Issues: [GitHub Issues](https://github.com/kimasplund/mcp-pypi/issues)
- Discussions: [GitHub Discussions](https://github.com/kimasplund/mcp-pypi/discussions)
- Email: kim.asplund@gmail.com
