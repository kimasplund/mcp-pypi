"""
Shared utilities for the MCP-PyPI CLI.
"""

import json
from typing import Any, Mapping, Optional

from rich.console import Console
from rich.syntax import Syntax

from mcp_pypi.core.models import PyPIClientConfig

console = Console()


class GlobalOptions:
    """Container for global CLI options."""

    cache_dir: Optional[str] = None
    cache_ttl: int = 604800  # 1 week
    verbose: bool = False
    log_file: Optional[str] = None


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
