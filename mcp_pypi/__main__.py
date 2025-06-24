#!/usr/bin/env python
"""
Main entry point for the MCP-PyPI package when executed as a script.
This simply imports and runs the CLI app.
"""

import sys

from mcp_pypi.cli.main import entry_point

if __name__ == "__main__":
    sys.exit(entry_point())
