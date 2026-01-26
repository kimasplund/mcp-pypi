"""Prompt registration for PyPI MCP Server.

Contains prompt templates for common PyPI-related tasks.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mcp.types import GetPromptResult, PromptMessage, TextContent

if TYPE_CHECKING:
    from mcp_pypi.server import PyPIMCPServer

logger = logging.getLogger("mcp-pypi.server")


def register_prompts(server: "PyPIMCPServer") -> None:
    """Register prompts with the MCP server.

    Args:
        server: The PyPIMCPServer instance to register prompts with.
    """

    @server.mcp_server.prompt()
    async def analyze_dependencies() -> GetPromptResult:
        """Analyze package dependencies and suggest improvements."""
        return GetPromptResult(
            description="Analyze package dependencies for security and compatibility",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            "Please analyze the dependencies of the specified package and:\n"
                            "1. Check for security vulnerabilities\n"
                            "2. Identify outdated dependencies\n"
                            "3. Suggest version updates\n"
                            "4. Check for dependency conflicts\n"
                            "5. Recommend best practices for dependency management"
                        ),
                    ),
                )
            ],
        )

    @server.mcp_server.prompt()
    async def package_comparison() -> GetPromptResult:
        """Compare multiple packages and recommend the best option."""
        return GetPromptResult(
            description="Compare packages and provide recommendations",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            "Please compare the specified packages based on:\n"
                            "1. Download statistics and popularity\n"
                            "2. Maintenance status and last update\n"
                            "3. Documentation quality\n"
                            "4. Dependencies and size\n"
                            "5. Community support and issues\n"
                            "Provide a recommendation on which package to use."
                        ),
                    ),
                )
            ],
        )
