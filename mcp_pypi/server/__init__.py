#!/usr/bin/env python
"""MCP-PyPI package server.

This module provides server implementation for PyPI package management through the
Model Context Protocol (MCP), including tools for package information, dependency
tracking, and other PyPI-related operations.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastmcp import FastMCP

from mcp_pypi.core import PyPIClient
from mcp_pypi.core.models import PyPIClientConfig

from mcp_pypi.server.helpers import (
    check_setup_py,
    check_setup_cfg,
    check_pipfile,
    check_pipfile_lock,
    check_poetry_lock,
    check_conda_file,
    format_security_report,
)
from mcp_pypi.server.prompts import register_prompts
from mcp_pypi.server.resources import register_resources
from mcp_pypi.server.tools import (
    register_package_tools,
    register_search_tools,
    register_dependency_tools,
    register_vulnerability_tools,
    register_audit_tools,
    register_file_tools,
)

# Protocol version for MCP
PROTOCOL_VERSION = "2025-06-18"

logger = logging.getLogger("mcp-pypi.server")


class PyPIMCPServer:
    """A fully compliant MCP server for PyPI functionality."""

    def __init__(
        self,
        config: Optional[PyPIClientConfig] = None,
        host: str = "127.0.0.1",
        port: int = 8143,
    ):
        """Initialize the MCP server with PyPI client."""
        self.config = config or PyPIClientConfig()
        self.client = PyPIClient(self.config)

        # Store host/port for runtime (fastmcp 2.14.4 pattern)
        self._host = host
        self._port = port

        # Initialize FastMCP server with modern 2.14.4 pattern
        self.mcp_server = FastMCP(
            name="PyPI MCP Server",
            instructions="AI-powered Python package intelligence - search, analyze, and understand PyPI packages",
        )

        # Configure protocol version
        self.protocol_version = PROTOCOL_VERSION
        logger.info(f"Using protocol version: {self.protocol_version}")

        # Register all tools, resources, and prompts
        self._register_tools()
        self._register_resources()
        self._register_prompts()

        logger.info("PyPI MCP Server initialization complete")

    def configure_client(self, config: PyPIClientConfig) -> None:
        """Configure the PyPI client with new settings."""
        self.config = config
        self.client = PyPIClient(config)
        logger.info("PyPI client reconfigured")

    def _register_tools(self) -> None:
        """Register all PyPI tools with the MCP server."""
        register_package_tools(self)
        register_search_tools(self)
        register_dependency_tools(self)
        register_vulnerability_tools(self)
        register_audit_tools(self)
        register_file_tools(self)

    def _register_resources(self) -> None:
        """Register PyPI resources with the MCP server."""
        register_resources(self)

    def _register_prompts(self) -> None:
        """Register prompts with the MCP server."""
        register_prompts(self)

    async def _check_setup_py(
        self, setup_file: Path, results: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Parse setup.py for dependencies."""
        return await check_setup_py(self, setup_file, results)

    async def _check_setup_cfg(
        self, setup_cfg: Path, results: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Parse setup.cfg for dependencies."""
        return await check_setup_cfg(self, setup_cfg, results)

    async def _check_pipfile(
        self, pipfile: Path, results: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Parse Pipfile for dependencies."""
        return await check_pipfile(self, pipfile, results)

    async def _check_pipfile_lock(
        self, pipfile_lock: Path, results: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Parse Pipfile.lock for exact versions."""
        return await check_pipfile_lock(self, pipfile_lock, results)

    async def _check_poetry_lock(
        self, poetry_lock: Path, results: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Parse poetry.lock for exact versions."""
        return await check_poetry_lock(self, poetry_lock, results)

    async def _check_conda_file(
        self, conda_file: Path, results: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Parse conda environment files."""
        return await check_conda_file(self, conda_file, results)

    def _format_security_report(self, audit_result: Dict[str, Any]) -> str:
        """Format the security audit results into a beautiful colored report with tables."""
        return format_security_report(audit_result)

    def run(self, transport: Literal["stdio", "http"] = "stdio") -> None:
        """Run the MCP server.

        Args:
            transport: Transport method to use:
                - "stdio": Direct process communication
                - "http": HTTP server with both SSE (/sse) and streamable-http (/mcp) endpoints
        """
        if transport == "stdio":
            self.mcp_server.run(transport="stdio")
        elif transport == "http":
            # When running HTTP mode, both SSE and streamable-http endpoints are available
            logger.info(f"Starting HTTP server on {self._host}:{self._port}")
            logger.info(f"SSE endpoint: http://{self._host}:{self._port}/sse")
            logger.info(f"Streamable-HTTP endpoint: http://{self._host}:{self._port}/mcp")
            self.mcp_server.run(
                transport="sse",
                host=self._host,
                port=self._port,
            )
        else:
            raise ValueError(f"Unknown transport: {transport}. Use 'stdio' or 'http'")

    async def run_async(self, transport: Literal["stdio", "http"] = "stdio") -> None:
        """Run the MCP server asynchronously.

        Args:
            transport: Transport method to use:
                - "stdio": Direct process communication
                - "http": HTTP server with both SSE (/sse) and streamable-http (/mcp) endpoints
        """
        if transport == "stdio":
            await self.mcp_server.run_stdio_async()
        elif transport == "http":
            # When running HTTP mode, both SSE and streamable-http endpoints are available
            logger.info(f"Starting HTTP server on {self._host}:{self._port}")
            logger.info(f"SSE endpoint: http://{self._host}:{self._port}/sse")
            logger.info(f"Streamable-HTTP endpoint: http://{self._host}:{self._port}/mcp")
            await self.mcp_server.run_sse_async(
                host=self._host,
                port=self._port,
            )
        else:
            raise ValueError(f"Unknown transport: {transport}. Use 'stdio' or 'http'")


# Re-export the server class
__all__ = ["PyPIMCPServer"]
