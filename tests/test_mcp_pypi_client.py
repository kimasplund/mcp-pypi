#!/usr/bin/env python3
"""
Test client for the Model Context Protocol (MCP) PyPI server.

This script connects to a running MCP-PyPI server, performs initialization,
and executes basic PyPI operations to verify functionality.
"""

import asyncio
import json
import logging
import sys
import uuid
from typing import Any, Dict, List, Optional, Union

from utils.messages import (ErrorResponse, Message, Notification, Request,
                            Response)
from utils.transports.http import HTTPTransport

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_pypi_client")


class MCPPyPIClient:
    """A simple client for testing the MCP-PyPI server."""

    def __init__(
        self, transport: Union[HTTPTransport, Any], client_info: Dict[str, Any] = None
    ):
        """Initialize the MCP PyPI client.

        Args:
            transport: The transport to use for communication
            client_info: Client information to send during initialization
        """
        self.transport = transport
        self.client_info = client_info or {"name": "test-client", "version": "0.1.0"}
        self.pending_requests = {}
        self.initialized = False
        self.server_info = None
        self.supported_tools = None

    async def initialize(self) -> Dict[str, Any]:
        """Initialize the MCP connection with the server.

        Returns:
            The server's initialization response
        """
        if self.initialized:
            logger.warning("Client already initialized")
            return self.server_info

        await self.transport.connect()

        # Send initialization request
        init_request = Request(
            id=str(uuid.uuid4()),
            method="initialize",
            params={"client_info": self.client_info, "protocol_version": "2025-03-26"},
        )

        logger.info(f"Sending initialization request: {init_request}")
        await self.transport.send_message(init_request.model_dump())

        # Wait for initialization response
        response_data = await self.transport.receive_message()
        response = Response.model_validate(response_data)

        if response.error:
            logger.error(f"Initialization failed: {response.error}")
            raise Exception(f"Initialization failed: {response.error}")

        self.initialized = True
        self.server_info = response.result
        self.supported_tools = self.server_info.get("tools", [])

        logger.info(f"Initialized with server: {self.server_info}")
        return self.server_info

    async def shutdown(self) -> None:
        """Send a shutdown request and close the connection."""
        if not self.initialized:
            logger.warning("Client not initialized, nothing to shutdown")
            return

        shutdown_request = Request(id=str(uuid.uuid4()), method="shutdown", params={})

        logger.info("Sending shutdown request")
        await self.transport.send_message(shutdown_request.model_dump())

        # Wait for shutdown response
        response_data = await self.transport.receive_message()
        response = Response.model_validate(response_data)

        if response.error:
            logger.error(f"Shutdown failed: {response.error}")
        else:
            logger.info("Shutdown successful")

        self.initialized = False
        await self.transport.disconnect()

    async def get_package_info(self, package_name: str) -> Dict[str, Any]:
        """Get information about a PyPI package.

        Args:
            package_name: The name of the package

        Returns:
            Package information from PyPI
        """
        if not self.initialized:
            raise Exception("Client not initialized")

        request_id = str(uuid.uuid4())
        request = Request(
            id=request_id,
            method="mcp_MCP_PyPi_get_package_info",
            params={"package_name": package_name},
        )

        logger.info(f"Getting package info for: {package_name}")
        await self.transport.send_message(request.model_dump())

        # Wait for response
        response_data = await self.transport.receive_message()
        response = Response.model_validate(response_data)

        if response.error:
            logger.error(f"Package info request failed: {response.error}")
            raise Exception(f"Package info request failed: {response.error}")

        return response.result

    async def search_packages(self, query: str) -> Dict[str, Any]:
        """Search for packages on PyPI.

        Args:
            query: The search query

        Returns:
            Search results from PyPI
        """
        if not self.initialized:
            raise Exception("Client not initialized")

        request_id = str(uuid.uuid4())
        request = Request(
            id=request_id,
            method="mcp_MCP_PyPi_search_packages",
            params={"query": query},
        )

        logger.info(f"Searching packages with query: {query}")
        await self.transport.send_message(request.model_dump())

        # Wait for response
        response_data = await self.transport.receive_message()
        response = Response.model_validate(response_data)

        if response.error:
            logger.error(f"Package search request failed: {response.error}")
            raise Exception(f"Package search request failed: {response.error}")

        return response.result


async def main():
    """Run the test client."""
    # Create HTTP transport to connect to the server
    transport = HTTPTransport(base_url="http://localhost:8080", polling_interval=0.5)

    client = MCPPyPIClient(transport)

    try:
        # Initialize the client
        await client.initialize()

        # Test getting package info
        package_info = await client.get_package_info("requests")
        print(f"\nPackage Information for 'requests':")
        print(json.dumps(package_info, indent=2))

        # Test searching packages
        search_results = await client.search_packages("http client")
        print(f"\nSearch Results for 'http client':")
        print(json.dumps(search_results, indent=2))

    except Exception as e:
        logger.error(f"Error during client test: {e}")
    finally:
        # Ensure we always try to shutdown properly
        await client.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Client test interrupted")
        sys.exit(0)
