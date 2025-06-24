#!/usr/bin/env python
"""
Tests for the MCP-PyPI server functionality.
"""

import asyncio
import json
import logging
import os
import tempfile
import uuid
from typing import Any, Dict

import pytest
from fastmcp import FastMCP
from mcp.client.session import ClientSession

from mcp_pypi.cli.mcp_server import run_server
from mcp_pypi.core.models import PyPIClientConfig

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("mcp-test")


class MockClient:
    """Mock MCP client for testing."""

    def __init__(self):
        self.sent_messages = []
        self.received_messages = []
        self.session_id = str(uuid.uuid4())
        # Create memory streams for communication
        self.reader_stream, self.writer_stream = asyncio.Queue(), asyncio.Queue()

    async def send(self, message: Dict[str, Any]):
        """Send a message to the MCP server."""
        message_json = json.dumps(message)
        logger.debug(f"Sending: {message_json}")
        self.sent_messages.append(message)
        await self.reader_stream.put(message_json)

    async def receive(self):
        """Receive a message from the MCP server."""
        message_json = await self.writer_stream.get()
        logger.debug(f"Received: {message_json}")
        message = json.loads(message_json)
        self.received_messages.append(message)
        return message

    async def initialize(self):
        """Send an initialize request."""
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-03-26"},
        }
        await self.send(init_request)
        return await self.receive()


@pytest.mark.asyncio
async def test_mcp_server_initialization():
    """Test the MCP server initialization."""
    # Create a temporary directory for caching
    with tempfile.TemporaryDirectory() as temp_dir:
        # Start the server in a separate task
        server_task = asyncio.create_task(
            run_server(
                host="127.0.0.1",
                port=9999,  # Use a different port for testing
                verbose=True,
                cache_dir=temp_dir,
                cache_ttl=60,
                stdin_mode=True,  # Use STDIO mode for testing
            )
        )

        try:
            # Give the server time to start up
            await asyncio.sleep(1)

            # Create a mock client and send an initialize request
            client = MockClient()
            response = await client.initialize()

            # Check the response
            assert response["jsonrpc"] == "2.0"
            assert response["id"] == 1
            assert "result" in response
            assert "capabilities" in response["result"]
            assert "protocolVersion" in response["result"]
            assert response["result"]["protocolVersion"] == "2025-03-26"

        finally:
            # Clean up
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
