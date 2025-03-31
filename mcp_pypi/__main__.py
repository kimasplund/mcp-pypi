#!/usr/bin/env python3
"""
Main entry point for the MCP-PyPI package when executed as a script.
This simply imports and runs the CLI app.
"""

import sys
from mcp_pypi.cli.main import app

if __name__ == "__main__":
    sys.exit(app()) 