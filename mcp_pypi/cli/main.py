"""
Command Line Interface for the MCP-PyPI client.
"""

import asyncio
import json
import os
import logging
import sys
from typing import Optional, List, Dict, Any, Mapping

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.logging import RichHandler
from rich.syntax import Syntax

from mcp_pypi.core.models import PyPIClientConfig
from mcp_pypi.core import PyPIClient
from mcp_pypi.utils import configure_logging
from mcp_pypi.server import PyPIMCPServer

# Import the server command function
from mcp_pypi.cli.server_command import serve_command

# Set up consoles
console = Console()
stderr_console = Console(stderr=True)


def show_stdio_connection_help():
    """Show connection examples for stdio transport."""
    console.print("\n[bold cyan]📚 Connection Examples for MCP-PyPI (stdio transport)[/bold cyan]\n")
    
    console.print("[bold]1️⃣  Claude Desktop Configuration[/bold]")
    console.print("Add to your Claude Desktop configuration file:")
    console.print("[dim]• macOS: ~/Library/Application Support/Claude/claude.json[/dim]")
    console.print("[dim]• Windows: %APPDATA%\\Claude\\claude.json[/dim]\n")
    
    config_example = '''{
  "servers": {
    "pypi": {
      "command": "mcp-pypi",
      "args": ["stdio"],
      "description": "Access Python package information from PyPI"
    }
  }
}'''
    syntax = Syntax(config_example, "json", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, title="claude.json", border_style="green"))
    
    console.print("\n[bold]2️⃣  Claude Code (Terminal)[/bold]")
    console.print("Add the server using the Claude CLI:\n")
    console.print("[green]claude mcp add mcp-pypi -- mcp-pypi stdio[/green]")
    
    console.print("\n[bold]3️⃣  Custom Configuration Options[/bold]")
    console.print("You can add additional arguments in the configuration:\n")
    
    custom_example = '''{
  "servers": {
    "pypi": {
      "command": "mcp-pypi",
      "args": ["stdio", "--cache-dir", "/path/to/cache", "--log-level", "DEBUG"],
      "description": "PyPI server with custom cache"
    }
  }
}'''
    syntax = Syntax(custom_example, "json", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, title="Advanced Example", border_style="yellow"))
    
    console.print("\n[bold]💡 Tips:[/bold]")
    console.print("• The server will start automatically when Claude connects")
    console.print("• Check logs if connection fails: [dim]--log-level DEBUG[/dim]")
    console.print("• Use custom cache directory for persistence: [dim]--cache-dir ~/.pypi-cache[/dim]")
    console.print("• All 21 PyPI tools will be available in your Claude conversation\n")


def show_http_connection_help(host: str = "127.0.0.1", port: int = 8080):
    """Show connection examples for HTTP transport."""
    console.print("\n[bold cyan]📚 Connection Examples for MCP-PyPI (HTTP transport)[/bold cyan]\n")
    
    console.print(f"[bold]🌐 Server will be available at:[/bold] http://{host}:{port}\n")
    
    console.print("[bold]1️⃣  MCP Client Configuration[/bold]")
    console.print("Configure your MCP client to connect to the HTTP endpoints:\n")
    
    console.print(f"• [bold]SSE Endpoint:[/bold] http://{host}:{port}/sse")
    console.print(f"• [bold]HTTP Endpoint:[/bold] http://{host}:{port}/mcp\n")
    
    config_example = f'''{{
  "servers": {{
    "pypi": {{
      "url": "http://{host}:{port}/sse",
      "transport": "sse",
      "description": "PyPI server via HTTP/SSE"
    }}
  }}
}}'''
    syntax = Syntax(config_example, "json", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, title="MCP Client Configuration", border_style="green"))
    
    console.print("\n[bold]2️⃣  Testing the Connection[/bold]")
    console.print("You can test the server is running with curl:\n")
    console.print(f"[green]curl http://{host}:{port}/sse[/green]")
    
    console.print("\n[bold]3️⃣  Direct API Usage[/bold]")
    console.print("You can also interact with the server directly:\n")
    
    api_example = f'''# List available tools
curl -X POST http://{host}:{port}/mcp \\
  -H "Content-Type: application/json" \\
  -d '{{"method": "tools/list"}}'

# Search for packages
curl -X POST http://{host}:{port}/mcp \\
  -H "Content-Type: application/json" \\
  -d '{{"method": "tools/call", "params": {{"name": "search_packages", "arguments": {{"query": "requests"}}}}}}'
'''
    syntax = Syntax(api_example, "bash", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, title="API Examples", border_style="yellow"))
    
    console.print("\n[bold]💡 Tips:[/bold]")
    console.print(f"• Server is running at http://{host}:{port}")
    console.print("• Both SSE and HTTP transports are supported on the same port")
    console.print("• Use --host 0.0.0.0 to allow external connections")
    console.print("• Check server logs: [dim]--log-level DEBUG[/dim]\n")


# Define version callback first
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
    
    # Try to get from package resources first (for installed package)
    try:
        if hasattr(importlib.resources, 'files'):
            # Python 3.9+
            package_files = importlib.resources.files('mcp_pypi')
            file_resource = package_files / filename
            if file_resource.is_file():
                content = file_resource.read_text(encoding='utf-8')
        else:
            # Python 3.8
            import pkg_resources
            content = pkg_resources.resource_string('mcp_pypi', filename).decode('utf-8')
    except Exception:
        pass
    
    # If not found, try file system paths (for development)
    if not content:
        package_dir = Path(__file__).parent.parent
        file_path = package_dir / filename
        
        if not file_path.exists():
            # Try one more level up
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
            # Create markdown object with custom width
            md = Markdown(readme_content, code_theme="monokai", justify="left")
            
            # Print with pager for long content
            with console.pager():
                console.print(md)
        else:
            console.print("[red]README.md file not found![/red]")
            console.print("[dim]This might happen if the package was installed without including README.md[/dim]")
            console.print("\n[bold]View online at:[/bold] https://github.com/kimasplund/mcp-pypi#readme")
        
        raise typer.Exit()


def changelog_callback(value: bool):
    """Show the CHANGELOG and exit."""
    if value:
        from rich.markdown import Markdown
        
        changelog_content = get_markdown_file("CHANGELOG.md")
        
        if changelog_content:
            # Create markdown object with custom width
            md = Markdown(changelog_content, code_theme="monokai", justify="left")
            
            # Print with pager for long content
            with console.pager():
                console.print(md)
        else:
            console.print("[red]CHANGELOG.md file not found![/red]")
            console.print("[dim]This might happen if the package was installed without including CHANGELOG.md[/dim]")
            console.print("\n[bold]View online at:[/bold] https://github.com/kimasplund/mcp-pypi/blob/main/CHANGELOG.md")
        
        raise typer.Exit()


# Create the CLI app
app = typer.Typer(
    name="mcp-pypi",
    help="MCP-PyPI: A client for interacting with PyPI (Python Package Index)",
    add_completion=True,
)

# Create subcommands
cache_app = typer.Typer(name="cache", help="Cache management commands")
app.add_typer(cache_app)

package_app = typer.Typer(name="package", help="Package information commands")
app.add_typer(package_app)

stats_app = typer.Typer(name="stats", help="Package statistics commands")
app.add_typer(stats_app)

feed_app = typer.Typer(name="feed", help="PyPI feed commands")
app.add_typer(feed_app)

# Add the serve command to the main app
app.command("serve")(serve_command)

# Add stdio command as an alias for serve with stdio transport
@app.command("stdio")
def stdio_command(
    cache_dir: Optional[str] = typer.Option(None, "--cache-dir", help="Custom cache directory"),
    cache_strategy: str = typer.Option("hybrid", "--cache-strategy", help="Cache strategy: memory, disk, or hybrid"),
    cache_ttl: int = typer.Option(604800, "--cache-ttl", help="Cache TTL in seconds (default: 1 week)"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
    user_agent: Optional[str] = typer.Option(None, "--user-agent", help="Custom user agent string"),
    help_connecting: bool = typer.Option(False, "--help-connecting", help="Show connection examples for Claude"),
):
    """
    Start the MCP server with stdio transport (alias for 'serve').
    
    This command is provided for compatibility as many LLMs default to trying 'mcp-pypi stdio'.
    It's equivalent to running 'mcp-pypi serve' or 'mcp-pypi serve --transport stdio'.
    """
    if help_connecting:
        show_stdio_connection_help()
        raise typer.Exit()
    
    # Import serve_command parameters
    from mcp_pypi.cli.server_command import serve_command
    
    # Call serve_command with stdio transport explicitly set
    serve_command(
        transport="stdio",
        host="127.0.0.1",  # Ignored for stdio
        port=8143,  # Ignored for stdio but use default
        cache_dir=cache_dir,
        cache_strategy=cache_strategy,
        cache_ttl=cache_ttl,
        log_level=log_level,
        user_agent=user_agent,
        help_connecting=False  # Already handled above
    )


# Global options
class GlobalOptions:
    cache_dir: Optional[str] = None
    cache_ttl: int = 604800  # 1 week
    verbose: bool = False
    log_file: Optional[str] = None


# Create a single instance
global_options = GlobalOptions()


def get_config() -> PyPIClientConfig:
    """Create configuration from global options."""
    config = PyPIClientConfig()

    if global_options.cache_dir:
        config.cache_dir = global_options.cache_dir

    if global_options.cache_ttl:
        config.cache_ttl = global_options.cache_ttl

    return config


def output_json(data: Mapping[str, Any], color: bool = True) -> None:
    """Output JSON data to the console."""
    if color:
        json_str = json.dumps(data, indent=2)
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
        console.print(syntax)
    else:
        print(json.dumps(data, indent=2))


def print_error(message: str) -> None:
    """Print an error message to the console."""
    console.print(f"[bold red]Error:[/bold red] {message}")


# Define callback for global options
@app.callback()
def main(
    cache_dir: Optional[str] = typer.Option(
        None, "--cache-dir", help="Cache directory path"
    ),
    cache_ttl: int = typer.Option(604800, "--cache-ttl", help="Cache TTL in seconds (default: 1 week)"),
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
    # Store options
    global_options.cache_dir = cache_dir
    global_options.cache_ttl = cache_ttl
    global_options.verbose = verbose
    global_options.log_file = log_file

    # Configure logging
    log_level = logging.DEBUG if verbose else logging.INFO
    configure_logging(log_level, file_path=log_file)


# Package information commands
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

                # Get the release dates
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
                        title=f"Package Metadata",
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


# Stats commands
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

                # Add summary rows
                table.add_row("Last day", f"{result.get('last_day', 0):,}")
                table.add_row("Last week", f"{result.get('last_week', 0):,}")
                table.add_row("Last month", f"{result.get('last_month', 0):,}")

                # Add monthly data
                console.print(table)

                # Add monthly breakdown
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


# Feed commands
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


# Search command
@app.command("search")
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


# Requirements file check
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

            # Use json format if specified, or if color is False
            if format == "json" or (format is None and not color):
                output_json(result, False)
                return

            if color and format != "json":
                # Display outdated packages
                if "outdated" in result and result["outdated"]:
                    console.print(f"\n[bold]Outdated packages:[/bold]")
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

                # Display up-to-date packages
                if "up_to_date" in result and result["up_to_date"]:
                    console.print(f"\n[bold]Up-to-date packages:[/bold]")
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
                            package_name, current_version, latest_version, str(constraint)
                        )

                    console.print(table)
            else:
                output_json(result, False)
        finally:
            await client.close()

    asyncio.run(run())


# Cache commands
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
