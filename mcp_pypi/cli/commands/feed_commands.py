"""
Feed commands for the MCP-PyPI CLI.

Includes: newest packages and latest updates.
"""

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from mcp_pypi.cli.utils import get_config, output_json, print_error
from mcp_pypi.core import PyPIClient

console = Console()

feed_app = typer.Typer(name="feed", help="PyPI feed commands")


@feed_app.command("newest")
def newest_packages(
    limit: int = typer.Option(10, help="Number of packages to display"),
    color: bool = typer.Option(True, help="Colorize output"),
):
    """Get newest packages on PyPI."""

    async def run():
        config = get_config()
        client = PyPIClient(config)

        try:
            result = await client.get_newest_packages()

            if "error" in result:
                print_error(result["error"]["message"])
                return

            if color and "packages" in result:
                table = Table(title="Newest Packages on PyPI")
                table.add_column("Package")
                table.add_column("Date")
                table.add_column("Description")

                for i, package in enumerate(result["packages"]):
                    if i >= limit:
                        break

                    title_parts = package["title"].split()
                    name = title_parts[0] if title_parts else ""

                    table.add_row(
                        name,
                        package["published_date"],
                        package["description"][:50]
                        + ("..." if len(package["description"]) > 50 else ""),
                    )

                console.print(table)
            else:
                if "packages" in result:
                    result["packages"] = result["packages"][:limit]
                output_json(result, color)
        finally:
            await client.close()

    asyncio.run(run())


@feed_app.command("updates")
def latest_updates(
    limit: int = typer.Option(10, help="Number of updates to display"),
    color: bool = typer.Option(True, help="Colorize output"),
):
    """Get latest package updates on PyPI."""

    async def run():
        config = get_config()
        client = PyPIClient(config)

        try:
            result = await client.get_latest_updates()

            if "error" in result:
                print_error(result["error"]["message"])
                return

            if color and "updates" in result:
                table = Table(title="Latest Package Updates on PyPI")
                table.add_column("Package")
                table.add_column("Version")
                table.add_column("Date")

                for i, update in enumerate(result["updates"]):
                    if i >= limit:
                        break

                    title_parts = update["title"].split()
                    name = title_parts[0] if len(title_parts) > 0 else ""
                    version = title_parts[-1] if len(title_parts) > 1 else ""

                    table.add_row(name, version, update["published_date"])

                console.print(table)
            else:
                if "updates" in result:
                    result["updates"] = result["updates"][:limit]
                output_json(result, color)
        finally:
            await client.close()

    asyncio.run(run())
