"""
Command Line Interface for the MCP-PyPI client.
"""

import asyncio
import json
import os
import logging
import sys
from typing import Optional, List, Dict, Any

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

# Import the mcp-server command
from mcp_pypi.cli.mcp_server import app as mcp_server_app

# Set up consoles
console = Console()
stderr_console = Console(stderr=True)

# Define version callback first
def version_callback(value: bool):
    """Show the version and exit."""
    if value:
        from mcp_pypi import __version__
        print(f"MCP-PyPI version: {__version__}")
        raise typer.Exit()

# Create the CLI app
app = typer.Typer(
    name="pypi-mcp",
    help="PyPI-MCP-Tool: A client for interacting with PyPI (Python Package Index)",
    add_completion=True
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

server_app = typer.Typer(name="server", help="MCP server commands")
app.add_typer(server_app)

# Add the MCP server app
app.add_typer(mcp_server_app)

# Global options
class GlobalOptions:
    cache_dir: Optional[str] = None
    cache_ttl: int = 3600
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

def output_json(data: Dict[str, Any], color: bool = True) -> None:
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
        None, "--cache-dir", 
        help="Cache directory path"
    ),
    cache_ttl: int = typer.Option(
        3600, "--cache-ttl", 
        help="Cache TTL in seconds"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", 
        help="Enable verbose logging"
    ),
    log_file: Optional[str] = typer.Option(
        None, "--log-file", 
        help="Log file path"
    ),
    version: bool = typer.Option(
        None, 
        "--version", 
        "-V", 
        is_flag=True, 
        callback=version_callback, 
        help="Show version and exit"
    )
):
    """PyPI-MCP-Tool: A client for interacting with PyPI (Python Package Index)"""
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
    color: bool = typer.Option(True, help="Colorize output")
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
    color: bool = typer.Option(True, help="Colorize output")
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
                console.print(f"Latest version of [bold]{package_name}[/bold]: [green]{result['version']}[/green]")
            else:
                print(result["version"])
        finally:
            await client.close()
    
    asyncio.run(run())

@package_app.command("releases")
def package_releases(
    package_name: str = typer.Argument(..., help="Name of the package"),
    color: bool = typer.Option(True, help="Colorize output")
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
    color: bool = typer.Option(True, help="Colorize output")
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
                table = Table(title=f"Dependencies for {package_name}" + (f" {version}" if version else ""))
                table.add_column("Package")
                table.add_column("Version Spec")
                table.add_column("Extras")
                table.add_column("Environment Marker")
                
                for dep in result["dependencies"]:
                    table.add_row(
                        dep["name"],
                        dep["version_spec"] or "",
                        ", ".join(dep.get("extras", [])),
                        dep.get("marker") or ""
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
    color: bool = typer.Option(True, help="Colorize output")
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
                    console.print(f"Package [bold]{package_name}[/bold] [green]exists[/green] on PyPI")
                else:
                    console.print(f"Package [bold]{package_name}[/bold] [red]does not exist[/red] on PyPI")
            else:
                print("true" if result["exists"] else "false")
        finally:
            await client.close()
    
    asyncio.run(run())

@package_app.command("metadata")
def package_metadata(
    package_name: str = typer.Argument(..., help="Name of the package"),
    version: Optional[str] = typer.Option(None, help="Package version (optional)"),
    color: bool = typer.Option(True, help="Colorize output")
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
                console.print(Panel(
                    f"[bold]{metadata.get('name')} {metadata.get('version')}[/bold]\n\n"
                    f"{metadata.get('summary', '')}\n\n"
                    f"[bold]Author:[/bold] {metadata.get('author', 'Unknown')}\n"
                    f"[bold]License:[/bold] {metadata.get('license', 'Unknown')}\n"
                    f"[bold]Homepage:[/bold] {metadata.get('homepage', 'Not specified')}\n"
                    f"[bold]Requires Python:[/bold] {metadata.get('requires_python', 'Any')}\n",
                    title=f"Package Metadata"
                ))
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
    color: bool = typer.Option(True, help="Colorize output")
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
                    console.print(f"Versions [bold]{version1}[/bold] and [bold]{version2}[/bold] are [green]equal[/green]")
                elif result["is_version1_greater"]:
                    console.print(f"Version [bold]{version1}[/bold] is [green]greater than[/green] [bold]{version2}[/bold]")
                else:
                    console.print(f"Version [bold]{version2}[/bold] is [green]greater than[/green] [bold]{version1}[/bold]")
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
    color: bool = typer.Option(True, help="Colorize output")
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
                table = Table(title=f"Download Stats for {package_name}" + (f" {version}" if version else ""))
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
    color: bool = typer.Option(True, help="Colorize output")
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
                        package["description"][:50] + ("..." if len(package["description"]) > 50 else "")
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
    color: bool = typer.Option(True, help="Colorize output")
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
                    
                    table.add_row(
                        name,
                        version,
                        update["published_date"]
                    )
                
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
    color: bool = typer.Option(True, help="Colorize output")
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
                        
                    table.add_row(
                        package["name"],
                        package["version"],
                        description
                    )
                
                console.print(table)
            else:
                output_json(result, color)
        finally:
            await client.close()
    
    asyncio.run(run())

# Requirements file check
@app.command("check-requirements")
def check_requirements_file(
    file_path: str = typer.Argument(..., help="Path to requirements.txt file"),
    color: bool = typer.Option(True, help="Colorize output")
):
    """Check a requirements file for outdated packages."""
    async def run():
        config = get_config()
        client = PyPIClient(config)
        
        try:
            result = await client.check_requirements_file(file_path)
            
            if "error" in result:
                print_error(result["error"]["message"])
                return
            
            if color:
                # Display outdated packages
                if "outdated" in result and result["outdated"]:
                    table = Table(title="Outdated Packages")
                    table.add_column("Package")
                    table.add_column("Current Version")
                    table.add_column("Latest Version")
                    
                    for pkg in result["outdated"]:
                        table.add_row(
                            pkg["package"],
                            pkg["current_version"],
                            pkg["latest_version"]
                        )
                    
                    console.print(table)
                else:
                    console.print("[green]All packages are up to date![/green]")
                
                # Display up-to-date packages
                if "up_to_date" in result and result["up_to_date"]:
                    table = Table(title="Up-to-date Packages")
                    table.add_column("Package")
                    table.add_column("Version")
                    
                    for pkg in result["up_to_date"]:
                        table.add_row(
                            pkg["package"],
                            pkg["current_version"]
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
def cache_stats(
    color: bool = typer.Option(True, help="Colorize output")
):
    """Get cache statistics."""
    async def run():
        config = get_config()
        client = PyPIClient(config)
        
        try:
            stats = await client.cache.get_stats()
            
            if color:
                console.print(Panel(
                    f"[bold]Cache Directory:[/bold] {config.cache_dir}\n"
                    f"[bold]Size:[/bold] {stats.get('size_mb', 0):.2f} MB of {stats.get('max_size_mb', 0):.2f} MB\n"
                    f"[bold]Files:[/bold] {stats.get('file_count', 0)}\n"
                    f"[bold]TTL:[/bold] {stats.get('ttl_seconds', 0)} seconds\n",
                    title="Cache Statistics"
                ))
            else:
                output_json(stats, False)
        finally:
            await client.close()
    
    asyncio.run(run())

@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to listen on (will auto-scan for available ports if busy)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Log file path"),
    cache_dir: Optional[str] = typer.Option(None, "--cache-dir", help="Cache directory path"),
    cache_ttl: int = typer.Option(3600, "--cache-ttl", help="Cache TTL in seconds"),
    stdin_mode: bool = typer.Option(False, "--stdin", help="Read JSON-RPC requests from stdin"),
    legacy_mode: bool = typer.Option(False, "--legacy", help="Use legacy JSON-RPC server instead of MCP SDK")
):
    """Start the JSON-RPC server for MCP-PyPI.
    
    This command starts a JSON-RPC 2.0 compliant server that exposes all PyPI client functionality.
    The server can operate in several modes:
    
    1. HTTP Server Mode (default): Exposes the API over HTTP on the specified host and port
    2. STDIN Mode (--stdin): Reads JSON-RPC requests from standard input (for MCP integration)
    3. Legacy Mode (--legacy): Uses the legacy JSON-RPC implementation instead of the MCP SDK
    
    Features:
    - Automatic port selection if the specified port is busy
    - Tool discovery via the "describe" method
    - Full JSON-RPC 2.0 compliance
    - Proper error handling with standard error codes
    
    Example usage:
    
        pypi-mcp serve
        pypi-mcp serve --port 8001
        pypi-mcp serve --stdin
        pypi-mcp serve --verbose
    
    For integrating with MCP tools, use the --stdin mode.
    """
    # Configure logging
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Ensure log_file is None or a valid string
    safe_log_file = None
    if log_file and isinstance(log_file, str):
        safe_log_file = log_file
    
    # Configure logging with safe parameters
    configure_logging(log_level, file_path=safe_log_file)
    
    # Create config with local options (overriding global ones)
    config = PyPIClientConfig()
    if cache_dir:
        config.cache_dir = cache_dir
    elif global_options.cache_dir:
        config.cache_dir = global_options.cache_dir
        
    if cache_ttl:
        config.cache_ttl = cache_ttl
    elif global_options.cache_ttl:
        config.cache_ttl = global_options.cache_ttl
    
    stderr_console.print(f"[bold blue]Using cache directory: {config.cache_dir}[/bold blue]")
    
    # Decide which server implementation to use
    if legacy_mode:
        # Use the legacy server implementation
        stderr_console.print("[bold yellow]Starting legacy JSON-RPC server...[/bold yellow]")
        try:
            if stdin_mode:
                from mcp_pypi.cli.server import process_mcp_stdin
                asyncio.run(process_mcp_stdin(verbose))
            else:
                from mcp_pypi.cli.server import start_server
                asyncio.run(start_server(host, port))
        except KeyboardInterrupt:
            stderr_console.print("[yellow]Server stopped.[/yellow]")
    else:
        # Use the MCP SDK server implementation
        server = PyPIMCPServer(config)
        
        if stdin_mode:
            stderr_console.print("[bold green]Starting MCP stdin mode...[/bold green]")
            try:
                asyncio.run(server.process_stdin())
            except KeyboardInterrupt:
                stderr_console.print("[yellow]Server stopped.[/yellow]")
        else:
            stderr_console.print(f"[bold green]Starting MCP HTTP server on {host}:{port}...[/bold green]")
            try:
                asyncio.run(server.start_http_server(host, port))
            except KeyboardInterrupt:
                stderr_console.print("[yellow]Server stopped.[/yellow]")

async def handle_execute_request(request_data, pypi_client):
    tool_name = request_data.get("params", {}).get("name")
    args = request_data.get("params", {}).get("arguments", {})
    request_id = request_data.get("id")
    
    response = {"id": request_id}
    
    try:
        if tool_name == "get_package_info":
            package_name = args.get("package_name")
            logging.debug(f"Getting package info for: {package_name}")
            result = await pypi_client.get_package_info(package_name)
            if not result or (isinstance(result, dict) and "info" not in result and "error" not in result):
                logging.warn(f"Empty result for package_info: {result}")
                response["result"] = {"error": {"code": "empty_result", "message": "No data returned from PyPI"}}
            else:
                response["result"] = result
            
        elif tool_name == "get_latest_version":
            package_name = args.get("package_name")
            logging.debug(f"Getting latest version for: {package_name}")
            result = await pypi_client.get_latest_version(package_name)
            if isinstance(result, dict) and "version" in result:
                response["result"] = {"version": result["version"]}
            elif isinstance(result, str):
                response["result"] = {"version": result}
            else:
                response["result"] = result
            
        elif tool_name == "get_dependency_tree":
            package_name = args.get("package_name")
            version = args.get("version")
            depth = args.get("depth", 1)
            logging.debug(f"Getting dependency tree for: {package_name} (version: {version}, depth: {depth})")
            result = await pypi_client.get_dependency_tree(package_name, version, depth)
            response["result"] = result
            
        elif tool_name == "search_packages":
            query = args.get("query")
            logging.debug(f"Searching for packages: {query}")
            result = await pypi_client.search_packages(query)
            # Handle security challenge case
            if isinstance(result, dict) and "error" in result:
                response["result"] = result
            elif isinstance(result, dict) and "results" in result:
                response["result"] = result
            elif isinstance(result, list):
                response["result"] = {"results": result}
            else:
                response["result"] = {"error": {"code": "unexpected_format", "message": "Unexpected search result format"}}
            
        elif tool_name == "get_package_stats":
            package_name = args.get("package_name")
            version = args.get("version")
            logging.debug(f"Getting package stats for: {package_name} (version: {version})")
            result = await pypi_client.get_package_stats(package_name, version)
            response["result"] = result
        else:
            logging.error(f"Unknown tool: {tool_name}")
            response["error"] = {"code": -32601, "message": f"Tool not found: {tool_name}"}
        
        logging.debug(f"Tool execution successful")
        logging.debug(f"Result: {response.get('result')}")
    except Exception as e:
        logging.error(f"Error executing tool: {str(e)}")
        response["error"] = {"code": -32000, "message": str(e)}
    
    logging.debug(f"Response type: {type(response)}")
    if "result" in response:
        logging.debug(f"Result type: {type(response.get('result'))}")
    
    write_response(response)

def write_response(response: Dict[str, Any]):
    """Write a response to stdout and flush immediately."""
    try:
        # Check if result is empty string and convert to dict if needed
        if "result" in response and response["result"] == "":
            response["result"] = {"message": "Empty result from API"}
        
        # Debug output before serializing
        stderr_console.print(f"[dim blue]Response type: {type(response)}[/dim blue]")
        if "result" in response:
            stderr_console.print(f"[dim blue]Result type: {type(response['result'])}[/dim blue]")
        
        stderr_console.print(f"[dim blue]Sending response: {str(response)[:80]}...[/dim blue]")
        response_json = json.dumps(response)
        print(response_json, flush=True)
        stderr_console.print(f"[green]Response sent[/green]")
    except Exception as e:
        stderr_console.print(f"[red]Error sending response: {e}[/red]")
        # Try to send a simpler error response
        simple_response = {
            "id": response.get("id", 0),
            "error": {
                "code": -32603,
                "message": f"Error serializing response: {str(e)}"
            }
        }
        print(json.dumps(simple_response), flush=True)

def get_mcp_schema():
    """Return the MCP schema for tool discovery."""
    return {
        "name": "PYPI_MCP",
        "version": "2.0.0",
        "description": "Tools for interacting with the Python Package Index (PyPI)",
        "tools": [
            {
                "name": "get_package_info",
                "description": "Get detailed information about a Python package from PyPI",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "package_name": {
                            "type": "string",
                            "description": "The name of the package to get information about"
                        }
                    },
                    "required": ["package_name"]
                }
            },
            {
                "name": "get_latest_version",
                "description": "Get the latest version of a package from PyPI",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "package_name": {
                            "type": "string",
                            "description": "The name of the package to get the version for"
                        }
                    },
                    "required": ["package_name"]
                }
            },
            {
                "name": "get_dependency_tree",
                "description": "Get the dependency tree for a package",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "package_name": {
                            "type": "string",
                            "description": "The name of the package to get dependencies for"
                        },
                        "version": {
                            "type": "string",
                            "description": "The specific version to check (defaults to latest)"
                        },
                        "depth": {
                            "type": "integer",
                            "description": "How deep to traverse the dependency tree",
                            "default": 1
                        }
                    },
                    "required": ["package_name"]
                }
            },
            {
                "name": "search_packages",
                "description": "Search for packages on PyPI",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_package_stats",
                "description": "Get download statistics for a package",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "package_name": {
                            "type": "string",
                            "description": "The name of the package to get statistics for"
                        },
                        "version": {
                            "type": "string",
                            "description": "The specific version to check (defaults to latest)"
                        }
                    },
                    "required": ["package_name"]
                }
            }
        ]
    }

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