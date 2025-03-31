"""
Command Line Interface for the MCP-PyPI client.
"""

import asyncio
import json
import os
import logging
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

# Set up console
console = Console()
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

if __name__ == "__main__":
    app() 