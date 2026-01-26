"""
Command Line Interface for the MCP-PyPI client.
"""

import asyncio
import logging
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from mcp_pypi.cli.commands.cache_commands import cache_app
from mcp_pypi.cli.commands.feed_commands import feed_app
from mcp_pypi.cli.commands.package_commands import package_app, stats_app
from mcp_pypi.cli.commands.search_commands import search_packages
from mcp_pypi.cli.server_command import serve_command
from mcp_pypi.cli.utils import get_config, global_options, output_json, print_error
from mcp_pypi.core import PyPIClient
from mcp_pypi.utils import configure_logging

console = Console()
stderr_console = Console(stderr=True)


def show_stdio_connection_help():
    """Show connection examples for stdio transport."""
    console.print(
        "\n[bold cyan]Connection Examples for MCP-PyPI (stdio transport)[/bold cyan]\n"
    )

    console.print("[bold]1. Claude Desktop Configuration[/bold]")
    console.print("Add to your Claude Desktop configuration file:")
    console.print(
        "[dim]* macOS: ~/Library/Application Support/Claude/claude.json[/dim]"
    )
    console.print("[dim]* Windows: %APPDATA%\\Claude\\claude.json[/dim]\n")

    config_example = """{
  "servers": {
    "pypi": {
      "command": "mcp-pypi",
      "args": ["stdio"],
      "description": "Access Python package information from PyPI"
    }
  }
}"""
    syntax = Syntax(config_example, "json", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, title="claude.json", border_style="green"))

    console.print("\n[bold]2. Claude Code (Terminal)[/bold]")
    console.print("Add the server using the Claude CLI:\n")
    console.print("[green]claude mcp add mcp-pypi -- mcp-pypi stdio[/green]")

    console.print("\n[bold]3. Custom Configuration Options[/bold]")
    console.print("You can add additional arguments in the configuration:\n")

    custom_example = """{
  "servers": {
    "pypi": {
      "command": "mcp-pypi",
      "args": ["stdio", "--cache-dir", "/path/to/cache", "--log-level", "DEBUG"],
      "description": "PyPI server with custom cache"
    }
  }
}"""
    syntax = Syntax(custom_example, "json", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, title="Advanced Example", border_style="yellow"))

    console.print("\n[bold]Tips:[/bold]")
    console.print("* The server will start automatically when Claude connects")
    console.print("* Check logs if connection fails: [dim]--log-level DEBUG[/dim]")
    console.print(
        "* Use custom cache directory for persistence: [dim]--cache-dir ~/.pypi-cache[/dim]"
    )
    console.print("* All 21 PyPI tools will be available in your Claude conversation\n")


def show_http_connection_help(host: str = "127.0.0.1", port: int = 8080):
    """Show connection examples for HTTP transport."""
    console.print(
        "\n[bold cyan]Connection Examples for MCP-PyPI (HTTP transport)[/bold cyan]\n"
    )

    console.print(
        f"[bold]Server will be available at:[/bold] http://{host}:{port}\n"
    )

    console.print("[bold]1. MCP Client Configuration[/bold]")
    console.print("Configure your MCP client to connect to the HTTP endpoints:\n")

    console.print(f"* [bold]SSE Endpoint:[/bold] http://{host}:{port}/sse")
    console.print(f"* [bold]HTTP Endpoint:[/bold] http://{host}:{port}/mcp\n")

    config_example = f"""{{
  "servers": {{
    "pypi": {{
      "url": "http://{host}:{port}/sse",
      "transport": "sse",
      "description": "PyPI server via HTTP/SSE"
    }}
  }}
}}"""
    syntax = Syntax(config_example, "json", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, title="MCP Client Configuration", border_style="green"))

    console.print("\n[bold]2. Testing the Connection[/bold]")
    console.print("You can test the server is running with curl:\n")
    console.print(f"[green]curl http://{host}:{port}/sse[/green]")

    console.print("\n[bold]3. Direct API Usage[/bold]")
    console.print("You can also interact with the server directly:\n")

    api_example = f"""# List available tools
curl -X POST http://{host}:{port}/mcp \\
  -H "Content-Type: application/json" \\
  -d '{{"method": "tools/list"}}'

# Search for packages
curl -X POST http://{host}:{port}/mcp \\
  -H "Content-Type: application/json" \\
  -d '{{"method": "tools/call", "params": {{"name": "search_packages", "arguments": {{"query": "requests"}}}}}}'
"""
    syntax = Syntax(api_example, "bash", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, title="API Examples", border_style="yellow"))

    console.print("\n[bold]Tips:[/bold]")
    console.print(f"* Server is running at http://{host}:{port}")
    console.print("* Both SSE and HTTP transports are supported on the same port")
    console.print("* Use --host 0.0.0.0 to allow external connections")
    console.print("* Check server logs: [dim]--log-level DEBUG[/dim]\n")


def version_callback(value: bool):
    """Show the version and exit."""
    if value:
        from mcp_pypi import __version__

        print(f"MCP-PyPI version: {__version__}")
        raise typer.Exit()


def get_markdown_file(filename: str) -> Optional[str]:
    """Get markdown file content from package or filesystem."""
    import importlib.resources
    from pathlib import Path

    content = None

    try:
        if hasattr(importlib.resources, "files"):
            package_files = importlib.resources.files("mcp_pypi")
            file_resource = package_files / filename
            if file_resource.is_file():
                content = file_resource.read_text(encoding="utf-8")
        else:
            import pkg_resources

            content = pkg_resources.resource_string("mcp_pypi", filename).decode(
                "utf-8"
            )
    except Exception:
        pass

    if not content:
        package_dir = Path(__file__).parent.parent
        file_path = package_dir / filename

        if not file_path.exists():
            file_path = package_dir.parent / filename

        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

    return content


def readme_callback(value: bool):
    """Show the README and exit."""
    if value:
        from rich.markdown import Markdown

        readme_content = get_markdown_file("README.md")

        if readme_content:
            md = Markdown(readme_content, code_theme="monokai", justify="left")

            with console.pager():
                console.print(md)
        else:
            console.print("[red]README.md file not found![/red]")
            console.print(
                "[dim]This might happen if the package was installed without including README.md[/dim]"
            )
            console.print(
                "\n[bold]View online at:[/bold] https://github.com/kimasplund/mcp-pypi#readme"
            )

        raise typer.Exit()


def changelog_callback(value: bool):
    """Show the CHANGELOG and exit."""
    if value:
        from rich.markdown import Markdown

        changelog_content = get_markdown_file("CHANGELOG.md")

        if changelog_content:
            md = Markdown(changelog_content, code_theme="monokai", justify="left")

            with console.pager():
                console.print(md)
        else:
            console.print("[red]CHANGELOG.md file not found![/red]")
            console.print(
                "[dim]This might happen if the package was installed without including CHANGELOG.md[/dim]"
            )
            console.print(
                "\n[bold]View online at:[/bold] https://github.com/kimasplund/mcp-pypi/blob/main/CHANGELOG.md"
            )

        raise typer.Exit()


app = typer.Typer(
    name="mcp-pypi",
    help="MCP-PyPI: A client for interacting with PyPI (Python Package Index)",
    add_completion=True,
)

app.add_typer(cache_app)
app.add_typer(package_app)
app.add_typer(stats_app)
app.add_typer(feed_app)

app.command("serve")(serve_command)
app.command("search")(search_packages)


@app.command("stdio")
def stdio_command(
    cache_dir: Optional[str] = typer.Option(
        None, "--cache-dir", help="Custom cache directory"
    ),
    cache_strategy: str = typer.Option(
        "hybrid", "--cache-strategy", help="Cache strategy: memory, disk, or hybrid"
    ),
    cache_ttl: int = typer.Option(
        604800, "--cache-ttl", help="Cache TTL in seconds (default: 1 week)"
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
    user_agent: Optional[str] = typer.Option(
        None, "--user-agent", help="Custom user agent string"
    ),
    help_connecting: bool = typer.Option(
        False, "--help-connecting", help="Show connection examples for Claude"
    ),
):
    """
    Start the MCP server with stdio transport (alias for 'serve').

    This command is provided for compatibility as many LLMs default to trying 'mcp-pypi stdio'.
    It's equivalent to running 'mcp-pypi serve' or 'mcp-pypi serve --transport stdio'.
    """
    if help_connecting:
        show_stdio_connection_help()
        raise typer.Exit()

    serve_command(
        transport="stdio",
        host="127.0.0.1",
        port=8143,
        cache_dir=cache_dir,
        cache_strategy=cache_strategy,
        cache_ttl=cache_ttl,
        log_level=log_level,
        user_agent=user_agent,
        help_connecting=False,
    )


@app.command("check-requirements")
def check_requirements(
    file_path: str = typer.Argument(
        ..., help="Path to requirements file to check (.txt, .pip, or pyproject.toml)"
    ),
    format: str = typer.Option(
        None, "--format", "-f", help="Output format (json, table)"
    ),
    color: bool = typer.Option(True, "--color/--no-color", help="Colorize output"),
):
    """
    Check a requirements file for updates.

    Supports requirements.txt format and pyproject.toml (dependencies from Poetry, PEP 621, PDM, and Flit will be detected).
    """

    async def run():
        config = get_config()
        client = PyPIClient(config)

        try:
            result = await client.check_requirements_file(file_path)

            if "error" in result:
                print_error(result["error"]["message"])
                return

            if format == "json" or (format is None and not color):
                output_json(result, False)
                return

            if color and format != "json":
                if "outdated" in result and result["outdated"]:
                    console.print("\n[bold]Outdated packages:[/bold]")
                    table = Table(
                        "Package",
                        "Current",
                        "Latest",
                        "Constraint",
                        title="Outdated Packages",
                        title_style="bold magenta",
                        header_style="bold blue",
                    )

                    for pkg in result["outdated"]:
                        package_name = pkg.get("package", pkg.get("name", "Unknown"))
                        current_version = pkg.get("current_version", "Unknown")
                        latest_version = pkg.get("latest_version", "Unknown")
                        constraint = pkg.get("constraint", pkg.get("specs", ""))

                        table.add_row(
                            f"[bold]{package_name}[/bold]",
                            current_version,
                            f"[green]{latest_version}[/green]",
                            str(constraint),
                        )

                    console.print(table)
                else:
                    console.print("[green]All packages are up to date![/green]")

                if "up_to_date" in result and result["up_to_date"]:
                    console.print("\n[bold]Up-to-date packages:[/bold]")
                    table = Table(
                        "Package",
                        "Current",
                        "Latest",
                        "Constraint",
                        title="Up-to-date Packages",
                        title_style="bold blue",
                        header_style="bold cyan",
                    )

                    for pkg in result["up_to_date"]:
                        package_name = pkg.get("package", pkg.get("name", "Unknown"))
                        current_version = pkg.get("current_version", "Unknown")
                        latest_version = pkg.get("latest_version", "Unknown")
                        constraint = pkg.get("constraint", pkg.get("specs", ""))

                        table.add_row(
                            package_name,
                            current_version,
                            latest_version,
                            str(constraint),
                        )

                    console.print(table)
            else:
                output_json(result, False)
        finally:
            await client.close()

    asyncio.run(run())


@app.callback()
def main(
    cache_dir: Optional[str] = typer.Option(
        None, "--cache-dir", help="Cache directory path"
    ),
    cache_ttl: int = typer.Option(
        604800, "--cache-ttl", help="Cache TTL in seconds (default: 1 week)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Log file path"),
    version: bool = typer.Option(
        None,
        "--version",
        "-V",
        is_flag=True,
        callback=version_callback,
        help="Show version and exit",
    ),
    readme: bool = typer.Option(
        None,
        "--readme",
        is_flag=True,
        callback=readme_callback,
        help="Show README documentation and exit",
    ),
    changelog: bool = typer.Option(
        None,
        "--changelog",
        is_flag=True,
        callback=changelog_callback,
        help="Show CHANGELOG and exit",
    ),
):
    """MCP-PyPI: A client for interacting with PyPI (Python Package Index)"""
    global_options.cache_dir = cache_dir
    global_options.cache_ttl = cache_ttl
    global_options.verbose = verbose
    global_options.log_file = log_file

    log_level = logging.DEBUG if verbose else logging.INFO
    configure_logging(log_level, file_path=log_file)


def entry_point():
    """Entry point for the CLI."""
    try:
        app()
    except Exception as e:
        stderr_console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if "--verbose" in sys.argv or "-v" in sys.argv:
            stderr_console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    entry_point()
