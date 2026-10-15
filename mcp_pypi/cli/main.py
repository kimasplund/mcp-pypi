"""
Command Line Interface for the MCP-PyPI client.
"""

import logging
import sys

import typer
from rich.console import Console

from mcp_pypi.cli.commands.cache_commands import cache_app
from mcp_pypi.cli.commands.check_requirements import check_requirements
from mcp_pypi.cli.commands.feed_commands import feed_app
from mcp_pypi.cli.commands.package_commands import package_app, stats_app
from mcp_pypi.cli.commands.search_commands import search_packages
from mcp_pypi.cli.commands.serve import serve_command, show_stdio_connection_help
from mcp_pypi.cli.utils import global_options
from mcp_pypi.utils import configure_logging

console = Console()
stderr_console = Console(stderr=True)


def version_callback(value: bool):
    """Show the version and exit."""
    if value:
        from mcp_pypi import __version__

        print(f"MCP-PyPI version: {__version__}")
        raise typer.Exit()


def get_markdown_file(filename: str) -> str | None:
    """Get markdown file content from package or filesystem."""
    import importlib.resources
    from pathlib import Path

    content = None

    try:
        file_resource = importlib.resources.files("mcp_pypi") / filename
        if file_resource.is_file():
            content = file_resource.read_text(encoding="utf-8")
    except Exception:
        pass

    if not content:
        package_dir = Path(__file__).parent.parent
        file_path = package_dir / filename

        if not file_path.exists():
            file_path = package_dir.parent / filename

        if file_path.exists():
            with open(file_path, encoding="utf-8") as f:
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
                "[dim]This might happen if the package was installed without including "
                "README.md[/dim]"
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
                "[dim]This might happen if the package was installed without including "
                "CHANGELOG.md[/dim]"
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
app.command("check-requirements")(check_requirements)


@app.command("stdio")
def stdio_command(
    cache_dir: str | None = typer.Option(None, "--cache-dir", help="Custom cache directory"),
    cache_strategy: str = typer.Option(
        "hybrid", "--cache-strategy", help="Cache strategy: memory, disk, or hybrid"
    ),
    cache_ttl: int = typer.Option(
        604800, "--cache-ttl", help="Cache TTL in seconds (default: 1 week)"
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
    user_agent: str | None = typer.Option(None, "--user-agent", help="Custom user agent string"),
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


@app.callback()
def main(
    cache_dir: str | None = typer.Option(None, "--cache-dir", help="Cache directory path"),
    cache_ttl: int = typer.Option(
        604800, "--cache-ttl", help="Cache TTL in seconds (default: 1 week)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    log_file: str | None = typer.Option(None, "--log-file", help="Log file path"),
    version: bool = typer.Option(
        None,
        "--version",
        "-V",
        callback=version_callback,
        help="Show version and exit",
    ),
    readme: bool = typer.Option(
        None,
        "--readme",
        callback=readme_callback,
        help="Show README documentation and exit",
    ),
    changelog: bool = typer.Option(
        None,
        "--changelog",
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
