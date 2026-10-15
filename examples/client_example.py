"""Call mcp-pypi from Python: start the server over stdio and use two of its tools.

Run with: uv run python examples/client_example.py
"""

import asyncio
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def main() -> None:
    transport = StdioTransport(command=sys.executable, args=["-m", "mcp_pypi", "serve"])
    async with Client(transport) as client:
        tools = await client.list_tools()
        print(f"{len(tools)} tools:", ", ".join(t.name for t in tools))

        found = await client.call_tool("search_packages", {"query": "httpx", "limit": 3})
        for hit in found.data.results:
            print(f"- {hit.name} {hit.version or ''}: {hit.summary or ''}")

        report = await client.call_tool("check_vulnerabilities", {"packages": ["jinja2==2.4.1"]})
        print(f"jinja2 2.4.1: {report.data.total_vulnerabilities} known vulnerabilities")


if __name__ == "__main__":
    asyncio.run(main())
