# Server Architecture

How the mcp-pypi 4.x server is put together, and how to embed or extend it. For installing and configuring a client, see the [README](../README.md).

## Overview

mcp-pypi is a [FastMCP](https://github.com/PrefectHQ/fastmcp) 4 server (built on the MCP Python SDK 2.x). It exposes:

- 11 read-only tools (see [pypi.md](pypi.md)), each with a typed `outputSchema`
- 2 prompts that take arguments, and 3 resources with PyPI feed data
- server instructions that tell the model which tool to use and which dependency file is authoritative (`pyproject.toml` first)
- two transports: stdio (default) and streamable HTTP (see [transports.md](transports.md))

The server does not hardcode an MCP protocol version; negotiation is left to the SDK.

## Layout

```
mcp_pypi/
├── server/
│   ├── app.py             # build_server(): creates the FastMCP instance
│   ├── instructions.py    # server instructions sent on connect
│   ├── prompts.py         # analyze_dependencies, compare_packages
│   ├── resources.py       # pypi:// feed resources
│   ├── schemas.py         # Pydantic output models for the tools
│   ├── errors.py          # core errors -> ToolError messages
│   └── tools/             # packages.py, dependencies.py, security.py, project.py, osv.py
├── core/                  # PyPIClient and its operation mixins
│   ├── client.py
│   ├── package_ops.py, dependency_ops.py, vulnerability_ops.py, feed_ops.py, search_ops.py
│   ├── project_files.py   # dependency file parsers (used by audit_project)
│   ├── search_index.py    # local package-name index and popularity data
│   ├── stats.py           # pypistats
│   ├── cache/             # on-disk response cache
│   ├── http/              # async HTTP client with retries
│   └── models/            # PyPIClientConfig and shared types
├── cli/                   # the `mcp-pypi` command (Typer)
└── utils/                 # logging, input validation, sanitizing
```

## Building the server

`build_server` is the supported entry point:

```python
from mcp_pypi.core.models import PyPIClientConfig
from mcp_pypi.server import build_server

server = build_server(PyPIClientConfig(cache_dir="/var/cache/mcp-pypi"))

server.run()  # stdio
# server.run(transport="http", host="127.0.0.1", port=8143)
```

`build_server(config=None, client=None)` creates one `PyPIClient` (or uses the one you pass), registers all tools, prompts and resources, and closes the client when the server shuts down. `PyPIClientConfig` reads its defaults from the `PYPI_*` environment variables; see the [README](../README.md#-configuration) for the list.

## Tools and errors

Tools are `async` functions registered with `@mcp.tool`. Each is annotated read-only and open-world (it talks to external services), has a timeout (60 s for lookups, 180 s for tools that call OSV or read many files), and returns a Pydantic model from `server/schemas.py`. FastMCP turns that return type into the tool's `outputSchema` and fills `structuredContent`.

Failures raise `ToolError`, which FastMCP sends as a tool result with `isError: true`. `server/errors.py` maps the core client's error codes to short messages: unknown packages get a "did you mean" hint, transient network failures say to retry, and unexpected exceptions are masked (`mask_error_details=True`) so internals are not leaked. In batch tools a single bad item is reported in that item and does not fail the call.

## Security model

- Tools never modify your project or environment and never run project code (the only writes are to the cache directory). `audit_project` parses `setup.py` statically instead of executing it.
- File and directory arguments are checked before use (empty paths and `..` traversal are rejected). Run the server as a user that can read only what you are willing to expose to the assistant.
- `scan_installed_packages` runs the target environment's own Python to list packages, with a 60 second limit, and never falls back to scanning a different environment.
- No credentials are stored or required. Requests go to `pypi.org`, `api.osv.dev`, `pypistats.org` and, for search ranking, `hugovk.github.io`.
- The HTTP transport has no authentication; keep it bound to loopback (the default) unless the network is trusted.

## Data sources

| Data | Source |
|------|--------|
| Package metadata, versions | PyPI JSON API (`/pypi/<name>/json`) |
| Package names for search | PyPI Simple index (PEP 691 JSON) |
| Popularity ranking | top-pypi-packages (30-day downloads) |
| Download stats | pypistats.org |
| Vulnerabilities | OSV (`querybatch` for multiple packages) |
| Changelogs | Project links in metadata, GitHub releases |

## Caching

Responses and the search index are cached on disk; see [caching.md](caching.md).

## Troubleshooting

- **Port already in use**: `mcp-pypi serve --transport http --port 8081`
- **Stale or odd results**: `mcp-pypi cache clear`
- **Startup problems**: `mcp-pypi serve --log-level DEBUG`; logs go to stderr because stdout carries the protocol in stdio mode.
