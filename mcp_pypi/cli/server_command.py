"""MCP server command for the main CLI."""

import logging
from typing import Any, Dict, Literal, Optional

import typer

from mcp_pypi.core.models import PyPIClientConfig
from mcp_pypi.server import PyPIMCPServer
from mcp_pypi.utils import configure_logging


def serve_command(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8143, "--port", "-p", help="Port to bind to"),
    transport: str = typer.Option(
        "stdio",
        "--transport",
        "-t",
        help="Transport method: stdio or http (http provides both SSE and streamable-http endpoints)",
    ),
    cache_dir: Optional[str] = typer.Option(
        None, "--cache-dir", help="Cache directory path"
    ),
    cache_strategy: str = typer.Option(
        "hybrid", "--cache-strategy", help="Cache strategy: memory, disk, hybrid"
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
    """Start the MCP server for PyPI operations.

    The server can run in two transport modes:
    - stdio: Direct process communication (default, for MCP clients)
    - http: HTTP server with SSE and streamable-http endpoints
    """
    # Import the help functions from main
    from mcp_pypi.cli.main import (show_http_connection_help,
                                   show_stdio_connection_help)

    # Show connection help if requested
    if help_connecting:
        if transport == "stdio":
            show_stdio_connection_help()
        else:
            show_http_connection_help(host, port)
        raise typer.Exit()
    # Configure logging
    log_level_int = getattr(logging, log_level.upper(), logging.INFO)
    configure_logging(log_level_int)
    logger = logging.getLogger("mcp-pypi.cli.server")

    try:
        # Create client configuration with only non-None values
        config_kwargs: Dict[str, Any] = {
            "cache_strategy": cache_strategy,
            "cache_ttl": cache_ttl,
        }
        if cache_dir is not None:
            config_kwargs["cache_dir"] = cache_dir
        if user_agent is not None:
            config_kwargs["user_agent"] = user_agent

        config = PyPIClientConfig(**config_kwargs)

        # Create and run the server
        server = PyPIMCPServer(config=config, host=host, port=port)

        # Log startup info
        logger.info(f"Starting PyPI MCP server with {transport} transport")
        logger.info(f"Cache strategy: {cache_strategy}, TTL: {cache_ttl}s")

        if transport == "http":
            logger.info(f"Server will be available at:")
            logger.info(f"  SSE endpoint: http://{host}:{port}/sse")
            logger.info(f"  Streamable-HTTP endpoint: http://{host}:{port}/mcp")

        # Run the server
        server.run(transport=transport)  # type: ignore[arg-type]

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise typer.Exit(1)
