"""The `serve` command: run the MCP server over stdio or streamable HTTP."""

import logging
from typing import Any

import typer

from mcp_pypi.core.models import PyPIClientConfig
from mcp_pypi.server import build_server
from mcp_pypi.utils import configure_logging

TRANSPORTS = ("stdio", "http")


def show_stdio_connection_help() -> None:
    """Print connection examples for the stdio transport."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax

    console = Console()
    console.print("\n[bold cyan]Connection Examples for MCP-PyPI (stdio transport)[/bold cyan]\n")

    console.print("[bold]1. Claude Desktop Configuration[/bold]")
    console.print("Add to your Claude Desktop configuration file:")
    console.print(
        "[dim]* macOS: ~/Library/Application Support/Claude/claude_desktop_config.json[/dim]"
    )
    console.print("[dim]* Windows: %APPDATA%\\Claude\\claude_desktop_config.json[/dim]\n")
    config_example = """{
  "mcpServers": {
    "pypi": {
      "command": "uvx",
      "args": ["mcp-pypi", "serve"]
    }
  }
}"""
    syntax = Syntax(config_example, "json", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, title="claude_desktop_config.json", border_style="green"))

    console.print("\n[bold]2. Claude Code (Terminal)[/bold]")
    console.print("Add the server using the Claude CLI:\n")
    console.print("[green]claude mcp add pypi -- uvx mcp-pypi serve[/green]")

    console.print("\n[bold]3. Custom Configuration Options[/bold]")
    custom_example = """{
  "mcpServers": {
    "pypi": {
      "command": "uvx",
      "args": ["mcp-pypi", "serve", "--cache-dir", "/path/to/cache", "--log-level", "DEBUG"]
    }
  }
}"""
    syntax = Syntax(custom_example, "json", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, title="Advanced Example", border_style="yellow"))

    console.print("\n[bold]Tips:[/bold]")
    console.print("* The server starts automatically when the client connects")
    console.print("* Logs go to stderr; check them with: [dim]--log-level DEBUG[/dim]")
    console.print("* Persist the cache with: [dim]--cache-dir ~/.pypi-cache[/dim]\n")


def show_http_connection_help(host: str = "127.0.0.1", port: int = 8143) -> None:
    """Print connection examples for the streamable HTTP transport."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax

    console = Console()
    url = f"http://{host}:{port}/mcp"
    console.print("\n[bold cyan]Connection Examples for MCP-PyPI (HTTP transport)[/bold cyan]\n")
    console.print(f"[bold]Start the server:[/bold] mcp-pypi serve --transport http --port {port}")
    console.print(f"[bold]MCP endpoint (streamable HTTP):[/bold] {url}\n")

    config_example = f"""{{
  "mcpServers": {{
    "pypi": {{
      "url": "{url}"
    }}
  }}
}}"""
    syntax = Syntax(config_example, "json", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, title="MCP Client Configuration", border_style="green"))

    console.print("\n[bold]Claude Code[/bold]")
    console.print(f"[green]claude mcp add --transport http pypi {url}[/green]")

    console.print("\n[bold]Tips:[/bold]")
    console.print("* Use --host 0.0.0.0 to allow external connections (no authentication)")
    console.print("* Check server logs on stderr: [dim]--log-level DEBUG[/dim]\n")


def serve_command(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to (http only)"),
    port: int = typer.Option(8143, "--port", "-p", help="Port to bind to (http only)"),
    transport: str = typer.Option(
        "stdio",
        "--transport",
        "-t",
        help="Transport: stdio, or http (streamable HTTP at /mcp)",
    ),
    cache_dir: str | None = typer.Option(None, "--cache-dir", help="Cache directory path"),
    cache_strategy: str = typer.Option(
        "hybrid", "--cache-strategy", help="Cache strategy: memory, disk, hybrid"
    ),
    cache_ttl: int = typer.Option(
        604800, "--cache-ttl", help="Cache TTL in seconds (default: 1 week)"
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
    user_agent: str | None = typer.Option(None, "--user-agent", help="Custom user agent string"),
    help_connecting: bool = typer.Option(
        False, "--help-connecting", help="Show connection examples for Claude"
    ),
) -> None:
    """Start the MCP server for PyPI operations.

    Transports: stdio (default, for MCP clients that launch the server) or http
    (streamable HTTP, endpoint /mcp).
    """
    if transport not in TRANSPORTS:
        raise typer.BadParameter(
            f"unknown transport '{transport}'; use 'stdio' or 'http'", param_hint="--transport"
        )

    if help_connecting:
        if transport == "stdio":
            show_stdio_connection_help()
        else:
            show_http_connection_help(host, port)
        raise typer.Exit()

    # Logging goes to stderr: stdout is the protocol channel in stdio mode.
    configure_logging(getattr(logging, log_level.upper(), logging.INFO))
    logger = logging.getLogger("mcp-pypi.cli.server")

    config_kwargs: dict[str, Any] = {"cache_strategy": cache_strategy, "cache_ttl": cache_ttl}
    if cache_dir is not None:
        config_kwargs["cache_dir"] = cache_dir
    if user_agent is not None:
        config_kwargs["user_agent"] = user_agent

    try:
        server = build_server(PyPIClientConfig(**config_kwargs))
        logger.info("Starting PyPI MCP server with %s transport", transport)
        if transport == "http":
            logger.info("Streamable HTTP endpoint: http://%s:%s/mcp", host, port)
            server.run(transport="http", host=host, port=port)
        else:
            server.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error("Server error: %s", e, exc_info=True)
        raise typer.Exit(1) from e
