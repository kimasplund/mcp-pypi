"""
Package information commands for the MCP-PyPI CLI.

Includes: info, version, releases, dependencies, exists, metadata, compare, and stats.
"""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mcp_pypi.cli.utils import get_config, output_json, print_error
from mcp_pypi.core import PyPIClient

console = Console()

package_app = typer.Typer(name="package", help="Package information commands")
stats_app = typer.Typer(name="stats", help="Package statistics commands")


@package_app.command("info")
def package_info(
    package_name: str = typer.Argument(..., help="Name of the package"),
    color: bool = typer.Option(True, help="Colorize output"),
):
    """Get package information."""

    async def run():
        config = get_config()
        client = PyPIClient(config)

        try:
            result = await client.get_package_info(package_name)
            output_json(result, color)
        finally:
            await client.close()

    asyncio.run(run())


@package_app.command("version")
def latest_version(
    package_name: str = typer.Argument(..., help="Name of the package"),
    color: bool = typer.Option(True, help="Colorize output"),
):
    """Get latest version of a package."""

    async def run():
        config = get_config()
        client = PyPIClient(config)

        try:
            result = await client.get_latest_version(package_name)

            if "error" in result:
                print_error(result["error"]["message"])
                return

            if color:
                console.print(
                    f"Latest version of [bold]{package_name}[/bold]: [green]{result['version']}[/green]"
                )
            else:
                print(result["version"])
        finally:
            await client.close()

    asyncio.run(run())


@package_app.command("releases")
def package_releases(
    package_name: str = typer.Argument(..., help="Name of the package"),
    color: bool = typer.Option(True, help="Colorize output"),
):
    """Get all releases of a package."""

    async def run():
        config = get_config()
        client = PyPIClient(config)

        try:
            result = await client.get_package_releases(package_name)

            if "error" in result:
                print_error(result["error"]["message"])
                return

            if color:
                table = Table(title=f"Releases for {package_name}")
                table.add_column("Version")
                table.add_column("Release Date", style="green")

                release_dates = {}
                project_releases = await client.get_project_releases(package_name)

                if "releases" in project_releases:
                    for release in project_releases["releases"]:
                        version = release["title"].split(" ")[-1]
                        release_dates[version] = release["published_date"]

                for version in result["releases"]:
                    date = release_dates.get(version, "")
                    table.add_row(version, date)

                console.print(table)
            else:
                output_json(result, False)
        finally:
            await client.close()

    asyncio.run(run())


@package_app.command("dependencies")
def package_dependencies(
    package_name: str = typer.Argument(..., help="Name of the package"),
    version: Optional[str] = typer.Option(None, help="Package version (optional)"),
    color: bool = typer.Option(True, help="Colorize output"),
):
    """Get package dependencies."""

    async def run():
        config = get_config()
        client = PyPIClient(config)

        try:
            result = await client.get_dependencies(package_name, version)

            if "error" in result:
                print_error(result["error"]["message"])
                return

            if color and "dependencies" in result:
                table = Table(
                    title=f"Dependencies for {package_name}"
                    + (f" {version}" if version else "")
                )
                table.add_column("Package")
                table.add_column("Version Spec")
                table.add_column("Extras")
                table.add_column("Environment Marker")

                for dep in result["dependencies"]:
                    table.add_row(
                        dep["name"],
                        dep["version_spec"] or "",
                        ", ".join(dep.get("extras", [])),
                        dep.get("marker") or "",
                    )

                console.print(table)
            else:
                output_json(result, color)
        finally:
            await client.close()

    asyncio.run(run())


@package_app.command("exists")
def check_package_exists(
    package_name: str = typer.Argument(..., help="Name of the package"),
    color: bool = typer.Option(True, help="Colorize output"),
):
    """Check if a package exists on PyPI."""

    async def run():
        config = get_config()
        client = PyPIClient(config)

        try:
            result = await client.check_package_exists(package_name)

            if "error" in result:
                print_error(result["error"]["message"])
                return

            if color:
                if result["exists"]:
                    console.print(
                        f"Package [bold]{package_name}[/bold] [green]exists[/green] on PyPI"
                    )
                else:
                    console.print(
                        f"Package [bold]{package_name}[/bold] [red]does not exist[/red] on PyPI"
                    )
            else:
                print("true" if result["exists"] else "false")
        finally:
            await client.close()

    asyncio.run(run())


@package_app.command("metadata")
def package_metadata(
    package_name: str = typer.Argument(..., help="Name of the package"),
    version: Optional[str] = typer.Option(None, help="Package version (optional)"),
    color: bool = typer.Option(True, help="Colorize output"),
):
    """Get package metadata."""

    async def run():
        config = get_config()
        client = PyPIClient(config)

        try:
            result = await client.get_package_metadata(package_name, version)

            if "error" in result:
                print_error(result["error"]["message"])
                return

            if color and "metadata" in result:
                metadata = result["metadata"]
                console.print(
                    Panel(
                        f"[bold]{metadata.get('name')} {metadata.get('version')}[/bold]\n\n"
                        f"{metadata.get('summary', '')}\n\n"
                        f"[bold]Author:[/bold] {metadata.get('author', 'Unknown')}\n"
                        f"[bold]License:[/bold] {metadata.get('license', 'Unknown')}\n"
                        f"[bold]Homepage:[/bold] {metadata.get('homepage', 'Not specified')}\n"
                        f"[bold]Requires Python:[/bold] {metadata.get('requires_python', 'Any')}\n",
                        title="Package Metadata",
                    )
                )
            else:
                output_json(result, color)
        finally:
            await client.close()

    asyncio.run(run())


@package_app.command("compare")
def compare_versions(
    package_name: str = typer.Argument(..., help="Name of the package"),
    version1: str = typer.Argument(..., help="First version"),
    version2: str = typer.Argument(..., help="Second version"),
    color: bool = typer.Option(True, help="Colorize output"),
):
    """Compare two package versions."""

    async def run():
        config = get_config()
        client = PyPIClient(config)

        try:
            result = await client.compare_versions(package_name, version1, version2)

            if "error" in result:
                print_error(result["error"]["message"])
                return

            if color:
                if result["are_equal"]:
                    console.print(
                        f"Versions [bold]{version1}[/bold] and [bold]{version2}[/bold] are [green]equal[/green]"
                    )
                elif result["is_version1_greater"]:
                    console.print(
                        f"Version [bold]{version1}[/bold] is [green]greater than[/green] [bold]{version2}[/bold]"
                    )
                else:
                    console.print(
                        f"Version [bold]{version2}[/bold] is [green]greater than[/green] [bold]{version1}[/bold]"
                    )
            else:
                output_json(result, False)
        finally:
            await client.close()

    asyncio.run(run())


@stats_app.command("downloads")
def package_stats(
    package_name: str = typer.Argument(..., help="Name of the package"),
    version: Optional[str] = typer.Option(None, help="Package version (optional)"),
    color: bool = typer.Option(True, help="Colorize output"),
):
    """Get package download statistics."""

    async def run():
        config = get_config()
        client = PyPIClient(config)

        try:
            result = await client.get_package_stats(package_name, version)

            if "error" in result:
                print_error(result["error"]["message"])
                return

            if color and "downloads" in result:
                table = Table(
                    title=f"Download Stats for {package_name}"
                    + (f" {version}" if version else "")
                )
                table.add_column("Period")
                table.add_column("Downloads")

                table.add_row("Last day", f"{result.get('last_day', 0):,}")
                table.add_row("Last week", f"{result.get('last_week', 0):,}")
                table.add_row("Last month", f"{result.get('last_month', 0):,}")

                console.print(table)

                monthly_table = Table(title="Monthly Downloads")
                monthly_table.add_column("Month")
                monthly_table.add_column("Downloads")

                for month, count in result["downloads"].items():
                    monthly_table.add_row(month, f"{count:,}")

                console.print(monthly_table)
            else:
                output_json(result, color)
        finally:
            await client.close()

    asyncio.run(run())
