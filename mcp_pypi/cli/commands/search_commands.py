"""
Search commands for the MCP-PyPI CLI.
"""

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from mcp_pypi.cli.utils import get_config, output_json, print_error
from mcp_pypi.core import PyPIClient

console = Console()


def search_packages(
    query: str = typer.Argument(..., help="Search query"),
    page: int = typer.Option(1, help="Result page number"),
    color: bool = typer.Option(True, help="Colorize output"),
):
    """Search for packages on PyPI."""

    async def run():
        config = get_config()
        client = PyPIClient(config)

        try:
            result = await client.search_packages(query, page)

            if "error" in result:
                print_error(result["error"]["message"])
                return

            if "message" in result:
                console.print(f"[yellow]{result['message']}[/yellow]")
                console.print(f"Search URL: {result['search_url']}")
                return

            if color and "results" in result:
                table = Table(title=f"Search Results for '{query}' (Page {page})")
                table.add_column("Package")
                table.add_column("Version")
                table.add_column("Description")

                for package in result["results"]:
                    description = package.get("description", "")
                    if len(description) > 60:
                        description = description[:57] + "..."

                    table.add_row(package["name"], package["version"], description)

                console.print(table)
            else:
                output_json(result, color)
        finally:
            await client.close()

    asyncio.run(run())
