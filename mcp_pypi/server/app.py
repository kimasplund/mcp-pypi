"""fastmcp 4 server factory."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

from fastmcp import FastMCP

from mcp_pypi import __version__
from mcp_pypi.core import PyPIClient
from mcp_pypi.core.models import PyPIClientConfig
from mcp_pypi.server.instructions import INSTRUCTIONS
from mcp_pypi.server.prompts import register_prompts
from mcp_pypi.server.resources import register_resources
from mcp_pypi.server.tools.dependencies import register_dependencies_tools
from mcp_pypi.server.tools.packages import register_packages_tools
from mcp_pypi.server.tools.project import register_project_tools
from mcp_pypi.server.tools.security import register_security_tools


def build_server(
    config: PyPIClientConfig | None = None, client: PyPIClient | None = None
) -> FastMCP:
    """Build the MCP server; the client is closed when the server shuts down."""
    client = client or PyPIClient(config or PyPIClientConfig())

    @contextlib.asynccontextmanager
    async def _lifespan(server: FastMCP) -> AsyncIterator[dict]:
        try:
            yield {}
        finally:
            await client.close()

    mcp = FastMCP(
        name="mcp-pypi",
        instructions=INSTRUCTIONS,
        version=__version__,
        website_url="https://github.com/kimasplund/mcp-pypi",
        mask_error_details=True,
        lifespan=_lifespan,
    )
    register_packages_tools(mcp, client)
    register_dependencies_tools(mcp, client)
    register_security_tools(mcp, client)
    register_project_tools(mcp, client)
    register_resources(mcp, client)
    register_prompts(mcp)
    return mcp
