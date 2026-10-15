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
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of results (1-50)"),
    color: bool = typer.Option(True, help="Colorize output"),
):
    """Search PyPI package names (name-like keywords work best)."""

    async def run():
        config = get_config()
        client = PyPIClient(config)

        try:
            result = await client.search_packages(query, limit)

            if "error" in result:
                print_error(result["error"]["message"])
                return

            if color and "results" in result:
                table = Table(title=f"Search Results for '{query}'")
                table.add_column("Package")
                table.add_column("Version")
                table.add_column("Summary")

                for package in result["results"]:
                    summary = package.get("summary") or ""
                    if len(summary) > 60:
                        summary = summary[:57] + "..."

                    table.add_row(package["name"], package["version"], summary)

                console.print(table)
                if result.get("note"):
                    console.print(f"[yellow]{result['note']}[/yellow]")
            else:
                output_json(result, color)
        finally:
            await client.close()

    asyncio.run(run())
