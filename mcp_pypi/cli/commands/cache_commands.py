"""
Cache management commands for the MCP-PyPI CLI.
"""

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel

from mcp_pypi.cli.utils import get_config, output_json
from mcp_pypi.core import PyPIClient

console = Console()

cache_app = typer.Typer(name="cache", help="Cache management commands")


@cache_app.command("clear")
def clear_cache():
    """Clear the cache."""

    async def run():
        config = get_config()
        client = PyPIClient(config)

        try:
            await client.cache.clear()
            console.print("[green]Cache cleared successfully[/green]")
        finally:
            await client.close()

    asyncio.run(run())


@cache_app.command("stats")
def cache_stats(color: bool = typer.Option(True, help="Colorize output")):
    """Get cache statistics."""

    async def run():
        config = get_config()
        client = PyPIClient(config)

        try:
            stats = await client.cache.get_stats()

            if color:
                console.print(
                    Panel(
                        f"[bold]Cache Directory:[/bold] {config.cache_dir}\n"
                        f"[bold]Size:[/bold] {stats.get('size_mb', 0):.2f} MB of {stats.get('max_size_mb', 0):.2f} MB\n"
                        f"[bold]Files:[/bold] {stats.get('file_count', 0)}\n"
                        f"[bold]TTL:[/bold] {stats.get('ttl_seconds', 0)} seconds\n",
                        title="Cache Statistics",
                    )
                )
            else:
                output_json(stats, False)
        finally:
            await client.close()

    asyncio.run(run())
