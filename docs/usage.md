# MCP-PyPI Usage Guide

How to run mcp-pypi, call its tools, and use the command line. For client setup snippets see the [README](../README.md); for every parameter see [pypi.md](pypi.md).

## Install and run

```bash
# Run without installing
uvx mcp-pypi serve

# Or install
pip install mcp-pypi
mcp-pypi serve
```

Requires Python 3.11 or newer. There are no optional extras.

```bash
mcp-pypi serve                                     # stdio (default)
mcp-pypi serve --transport http                    # http://127.0.0.1:8143/mcp
mcp-pypi serve --transport http --port 8080
mcp-pypi serve --cache-dir /path/to/cache
mcp-pypi serve --log-level DEBUG
mcp-pypi serve --help-connecting                   # print client connection examples
```

See [transports.md](transports.md) for the two transports.

## Environment variables

| Variable | Default |
|----------|---------|
| `PYPI_CACHE_DIR` | `<system temp dir>/pypi_mcp_cache` |
| `PYPI_CACHE_TTL` | `604800` (seconds) |
| `PYPI_CACHE_MAX_SIZE` | `104857600` (bytes) |
| `PYPI_CACHE_STRATEGY` | `hybrid` (accepted for compatibility; no effect) |
| `PYPI_VULNERABILITY_CACHE_TTL` | `3600` (seconds) |
| `PYPI_MAX_RETRIES` | `3` |
| `PYPI_RETRY_DELAY` | `1.0` (seconds) |
| `PYPI_TIMEOUT` | `30.0` (seconds) |
| `PYPI_USER_AGENT` | `mcp-pypi/<version> (+https://github.com/kimasplund/mcp-pypi)` |

## The tools

| Task | Tool |
|------|------|
| Find the exact name of a package | `search_packages` |
| Read a package's metadata | `get_package` |
| List or page through releases | `get_package_versions` |
| Compare two versions | `compare_versions` |
| Read release notes | `get_package_changelog` |
| Popularity signal | `get_download_stats` |
| Direct or transitive requirements | `get_dependencies` |
| Check that names exist before suggesting them | `check_packages` |
| Vulnerabilities for specific packages or versions | `check_vulnerabilities` |
| Audit a repository's dependency files | `audit_project` |
| Audit an installed virtualenv | `scan_installed_packages` |

### Example calls

These are the arguments an MCP client sends. With the FastMCP client:

```python
from fastmcp import Client

async with Client("http://127.0.0.1:8143/mcp") as client:
    # Do these names exist, and what are their latest versions?
    checked = await client.call_tool("check_packages", {"names": ["httpx", "requessts"]})

    # Known vulnerabilities for a pinned version, including dependencies
    vulns = await client.call_tool(
        "check_vulnerabilities",
        {"packages": ["django==4.2.0"], "include_transitive": True, "max_depth": 2},
    )

    # Audit a project directory (or one file, e.g. "requirements.txt")
    audit = await client.call_tool("audit_project", {"path": "/path/to/project"})
    print(audit.data.totals)
```

### Reading results

Results are structured data matching each tool's `outputSchema`. Look at `result.data` (or `structuredContent` in raw MCP). Problems with a whole call, such as an unknown package or a network failure, raise an error (`isError: true` in raw MCP) with a short message. Problems with one item of a batch appear in that item's `error` field.

### Audits never report unchecked items as clean

`audit_project` and `scan_installed_packages` list dependencies they could not check (`totals.unchecked`, `unchecked`) and unreadable files (`totals.files_with_errors`). Treat a result with unchecked items as incomplete, not as "no vulnerabilities".

## Command line

The CLI uses the same code as the server.

```bash
mcp-pypi --version

mcp-pypi search "http client" --limit 10

mcp-pypi package info requests
mcp-pypi package version numpy
mcp-pypi package releases django
mcp-pypi package dependencies flask
mcp-pypi package dependencies flask --version 3.0.0
mcp-pypi package exists some-name
mcp-pypi package metadata requests
mcp-pypi package compare pandas 2.0.0 2.1.0

mcp-pypi stats downloads requests

mcp-pypi check-requirements .
mcp-pypi check-requirements requirements.txt --format json --full

mcp-pypi cache stats
mcp-pypi cache clear
```

`search` matches package names only; `--limit` is 1-50. `stats downloads` reports the last day, week and month from pypistats.

### check-requirements and CI

`check-requirements PATH` accepts a project directory or a single dependency file and runs the full audit (vulnerable, outdated and unchecked dependencies). Options: `--format table|json` and `--full` (also list clean dependencies).

Exit codes: `1` if any dependency has a known vulnerability, `2` on an error, `0` otherwise. An audit with unchecked dependencies but no vulnerabilities exits `0`, so for a strict gate use JSON output and also fail on `totals.unchecked`:

```yaml
- name: Dependency audit
  run: |
    pip install mcp-pypi
    mcp-pypi check-requirements . --format json > audit.json
```

## Prompts and resources

Prompts: `analyze_dependencies` (argument `package_name`) and `compare_packages` (argument `packages`). Resources: `pypi://recent-releases`, `pypi://new-packages`, `pypi://updated-packages`.

## Troubleshooting

- **Server will not start**: run `mcp-pypi serve --log-level DEBUG` in a terminal; check that the port is free in HTTP mode.
- **Client cannot find the command**: use the absolute path to `uvx` or `mcp-pypi`.
- **Search fails with an index error**: the first search needs network access to download the package-name index (see [caching.md](caching.md)).
- **Stale data**: `mcp-pypi cache clear`.
- **Issues**: https://github.com/kimasplund/mcp-pypi/issues
