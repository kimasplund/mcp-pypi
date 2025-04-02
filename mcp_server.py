#!/usr/bin/env python3
"""
MCP Server for PyPI Client

This script starts an MCP-compliant server for the PyPI client,
using the official MCP Python SDK.
"""

import asyncio
import logging
import sys
from pathlib import Path

from mcp_pypi.server import PyPIMCPServer
from mcp_pypi.core.models import PyPIClientConfig
from mcp_pypi.utils import configure_logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)

async def main():
    """Run the MCP server."""
    print("MCP server starting...", file=sys.stderr)
    
    # Create PyPI client config
    config = PyPIClientConfig()
    
    # Create and run the MCP server
    server = PyPIMCPServer(config)
    
    try:
        await server.process_stdin()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        print("MCP server shutdown complete", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(main()) 