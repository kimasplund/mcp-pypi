# Transports

mcp-pypi supports two MCP transports: **stdio** (the default) and **streamable HTTP**. Choose with `mcp-pypi serve --transport stdio|http`.

| Transport | Use when | Endpoint |
|-----------|----------|----------|
| stdio | The MCP client launches the server itself (Claude Desktop, Claude Code, Cursor) | none; the client talks over the process's stdin/stdout |
| http | The server runs separately and clients connect over the network | `http://127.0.0.1:8143/mcp` |

Coming from 3.x? Transport changes are listed in [Upgrading from 3.x](../CHANGELOG.md#400---unreleased).

## stdio

```bash
uvx mcp-pypi serve          # or: mcp-pypi serve   /   mcp-pypi stdio
```

`mcp-pypi stdio` is an alias for `serve` with stdio, kept because many tools guess that command.

Client configuration:

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

Notes:

- stdout carries the protocol. The server never prints anything else there; logs go to stderr (`--log-level DEBUG` for more).
- Environment variables for the server go in the client's `env` block, for example `"env": {"PYPI_CACHE_DIR": "/path/to/cache"}`.
- If the client cannot find `uvx` or `mcp-pypi`, use the absolute path in `command`.

## Streamable HTTP

```bash
mcp-pypi serve --transport http                        # 127.0.0.1:8143
mcp-pypi serve --transport http --host 0.0.0.0 --port 8080
```

| Option | Default |
|--------|---------|
| `--host`, `-h` | `127.0.0.1` |
| `--port`, `-p` | `8143` |

The MCP endpoint is `http://<host>:<port>/mcp`. Connect from a client:

```bash
# Claude Code
claude mcp add --transport http mcp-pypi http://127.0.0.1:8143/mcp
```

For clients configured with JSON, point the HTTP/streamable-HTTP server entry at the same URL. The exact key names (`url`, `type`) depend on the client; check its documentation.

You can also connect from Python with the FastMCP client:

```python
import asyncio

from fastmcp import Client


async def main():
    async with Client("http://127.0.0.1:8143/mcp") as client:
        result = await client.call_tool("check_packages", {"names": ["requests", "reqests"]})
        print(result.data)


asyncio.run(main())
```

### Security

The HTTP transport has no authentication or TLS. By default it binds to loopback only, so just local processes can reach it. On a loopback address it also checks the `Host` and `Origin` headers, as the MCP transport specification requires: a request whose `Host` is not a loopback name gets HTTP 421 and one from a foreign browser `Origin` gets HTTP 403, so a web page cannot reach the server through DNS rebinding. If you bind to another address, put it behind a reverse proxy that provides authentication and TLS, or restrict access at the network level. Anyone who can reach the endpoint can make the server read dependency files and scan environments on its host (`audit_project`, `scan_installed_packages`).

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Address already in use` | Pick another port with `--port` |
| Client gets 404 | The endpoint is `/mcp`; check the URL path |
| Client shows garbled or no tools over stdio | Something else is writing to stdout; run the command in a terminal and check for non-protocol output |
| Need to see what the server is doing | `--log-level DEBUG` (stderr) |

`mcp-pypi serve --help-connecting` prints connection examples for the selected transport.
