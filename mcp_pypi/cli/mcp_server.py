"""
MCP server implementation using the official MCP Python SDK.
"""

import asyncio
import logging
import sys
from typing import Optional

import typer
from rich.console import Console

from mcp_pypi.core.models import PyPIClientConfig
from mcp_pypi.server import PyPIMCPServer
from mcp_pypi.utils import configure_logging

# Set up console for output
console = Console()
stderr_console = Console(stderr=True)

# Create the MCP server app
app = typer.Typer(
    name="mcp-server",
    help="Start an MCP-compliant server for PyPI"
)

@app.command("run")
def run_server(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to listen on"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Log file path"),
    cache_dir: Optional[str] = typer.Option(None, "--cache-dir", help="Cache directory path"),
    cache_ttl: int = typer.Option(3600, "--cache-ttl", help="Cache TTL in seconds"),
    stdin_mode: bool = typer.Option(False, "--stdin", help="Read MCP requests from stdin")
):
    """
    Start the MCP server for PyPI.
    
    This command starts an MCP-compliant server that exposes all PyPI client functionality
    using the official MCP Python SDK.
    
    The server can operate in two modes:
    
    1. HTTP Server Mode (default): Exposes the API over HTTP on the specified host and port
    2. STDIN Mode (--stdin): Reads MCP requests from standard input (for MCP integration)
    
    Example usage:
    
        pypi-mcp mcp-server run
        pypi-mcp mcp-server run --port 8001
        pypi-mcp mcp-server run --stdin
        pypi-mcp mcp-server run --verbose
    """
    # Configure logging
    log_level = logging.DEBUG if verbose else logging.INFO
    configure_logging(log_level, file_path=log_file)
    
    # Create PyPI client config
    config = PyPIClientConfig()
    if cache_dir:
        config.cache_dir = cache_dir
    if cache_ttl:
        config.cache_ttl = cache_ttl
    
    # Create the MCP server
    server = PyPIMCPServer(config)
    
    # Start the appropriate server type
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

if __name__ == "__main__":
    app() 