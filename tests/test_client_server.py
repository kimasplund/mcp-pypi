import asyncio
import json
import os
import sys
import tempfile
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mcp_pypi.client import MCPClient
from mcp_pypi.server import Server


class TestClientServer(unittest.TestCase):
    """Tests for client-server communication"""

    def setUp(self):
        # Setup environment for testing
        self.env = os.environ.copy()
        self.env["MCP_DEBUG"] = "1"

        # Create a temporary directory for test artifacts
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        # Clean up temporary directory
        self.temp_dir.cleanup()

    async def _setup_client_server_pair(self):
        # Create server instance
        server = Server()

        # Create pipes for communication
        client_reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(client_reader)
        client_writer_transport, client_protocol = (
            await asyncio.get_event_loop().create_pipe(lambda: protocol, pipe=None)
        )
        client_writer = asyncio.StreamWriter(
            client_writer_transport,
            client_protocol,
            client_reader,
            asyncio.get_event_loop(),
        )

        server_reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(server_reader)
        server_writer_transport, server_protocol = (
            await asyncio.get_event_loop().create_pipe(lambda: protocol, pipe=None)
        )
        server_writer = asyncio.StreamWriter(
            server_writer_transport,
            server_protocol,
            server_reader,
            asyncio.get_event_loop(),
        )

        # Connect the pipes
        asyncio.get_event_loop().call_soon(lambda: client_writer_transport.write(b""))
        asyncio.get_event_loop().call_soon(lambda: server_writer_transport.write(b""))

        # Setup client with custom protocol version
        client = MCPClient(protocol_version="2023-12-01")
        client.reader = client_reader
        client.writer = client_writer

        # Setup server with custom stdin/stdout
        server.stdin = server_reader
        server.stdout = server_writer

        # Start server processing task
        server_task = asyncio.create_task(server.process_stdin())

        return client, server, server_task

    async def test_initialization(self):
        """Test client-server initialization sequence"""
        client, server, server_task = await self._setup_client_server_pair()

        try:
            # Initialize the client
            await client.initialize()

            # Check that initialization was successful
            self.assertTrue(client.initialized)
            self.assertIsNotNone(client.server_info)
            self.assertEqual(client.protocol_version, "2023-12-01")

            # Verify tools were fetched
            self.assertGreater(len(client.tools), 0)
            self.assertIn("search", client.tools)

            # Verify resources were fetched
            self.assertIn("popular_packages", client.resources)

        finally:
            # Cancel server task and close connections
            server_task.cancel()
            await client.close()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    async def test_tool_invocation(self):
        """Test invoking a tool through the client-server connection"""
        client, server, server_task = await self._setup_client_server_pair()

        try:
            # Initialize the client
            await client.initialize()

            # Invoke the search tool
            result = await client.invoke_tool("search", {"query": "requests"})

            # Verify we got a valid response
            self.assertIsInstance(result, dict)
            self.assertIn("results", result)
            self.assertIsInstance(result["results"], list)

        finally:
            # Cancel server task and close connections
            server_task.cancel()
            await client.close()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    async def test_resource_retrieval(self):
        """Test retrieving a resource from the server"""
        client, server, server_task = await self._setup_client_server_pair()

        try:
            # Initialize the client
            await client.initialize()

            # Get the popular_packages resource
            content = await client.get_resource("popular_packages")

            # Verify we got content
            self.assertIsInstance(content, str)
            self.assertGreater(len(content), 0)

            # Try to parse it as JSON
            packages = json.loads(content)
            self.assertIsInstance(packages, list)

        finally:
            # Cancel server task and close connections
            server_task.cancel()
            await client.close()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    async def test_error_handling(self):
        """Test error handling in client-server communication"""
        client, server, server_task = await self._setup_client_server_pair()

        try:
            # Initialize the client
            await client.initialize()

            # Try to invoke a non-existent tool
            with self.assertRaises(Exception) as context:
                await client.invoke_tool("nonexistent_tool", {})

            # Verify error message
            self.assertIn("not available", str(context.exception))

        finally:
            # Cancel server task and close connections
            server_task.cancel()
            await client.close()
            try:
                await server_task
            except asyncio.CancelledError:
                pass


def run_tests():
    """Run the tests"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestClientServer)
    runner = unittest.TextTestRunner()
    runner.run(suite)


if __name__ == "__main__":
    # We need to run the tests with asyncio
    asyncio.run(unittest.main())
