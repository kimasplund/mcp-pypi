#!/usr/bin/env python
"""
Tests for the STDIO transport implementation.
"""

import os
import asyncio
import unittest
import sys
import json
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.transports import STDIOTransport

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class STDIOTransportTest(unittest.TestCase):
    """Test cases for STDIO transport."""

    def setUp(self):
        """Set up test environment."""
        # Path to the echo server script
        self.echo_server_path = str(Path(__file__).parent / "echo_mcp_server.py")

        # Ensure the script is executable
        os.chmod(self.echo_server_path, 0o755)

    async def test_newline_format(self):
        """Test STDIO transport with newline format."""
        # Create STDIO transport with subprocess mode
        transport = STDIOTransport(
            message_format="newline",
            subprocess_cmd=[self.echo_server_path, "newline"],
            debug=True,
        )

        try:
            # Connect to the subprocess
            connected = await transport.connect()
            self.assertTrue(connected, "Failed to connect")
            self.assertTrue(transport.is_connected, "Transport should be connected")

            # Initialize the connection
            init_message = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {"version": "2025-03-26"},
            }

            sent = await transport.send_message(init_message)
            self.assertTrue(sent, "Failed to send initialize message")

            # Receive response
            response = await transport.receive_message()
            self.assertIsNotNone(response, "No response received")
            self.assertEqual(
                response.get("id"), 1, "Response ID should match request ID"
            )
            self.assertIn("result", response, "Response should contain result")
            self.assertIn(
                "server_info",
                response.get("result", {}),
                "Result should contain server_info",
            )

            # List tools
            list_tools_message = {
                "jsonrpc": "2.0",
                "method": "list_tools",
                "id": 2,
                "params": {},
            }

            sent = await transport.send_message(list_tools_message)
            self.assertTrue(sent, "Failed to send list_tools message")

            # Receive response
            response = await transport.receive_message()
            self.assertIsNotNone(response, "No response received")
            self.assertEqual(
                response.get("id"), 2, "Response ID should match request ID"
            )
            self.assertIn("result", response, "Response should contain result")
            self.assertIn(
                "tools", response.get("result", {}), "Result should contain tools list"
            )

            # Echo test
            echo_message = {
                "jsonrpc": "2.0",
                "method": "invoke_tool",
                "id": 3,
                "params": {
                    "tool_name": "echo",
                    "parameters": {"message": "Hello, STDIO transport!"},
                },
            }

            sent = await transport.send_message(echo_message)
            self.assertTrue(sent, "Failed to send echo message")

            # Receive response
            response = await transport.receive_message()
            self.assertIsNotNone(response, "No response received")
            self.assertEqual(
                response.get("id"), 3, "Response ID should match request ID"
            )
            self.assertIn("result", response, "Response should contain result")
            self.assertEqual(
                response.get("result", {}).get("message"),
                "Hello, STDIO transport!",
                "Echo response should match sent message",
            )

        finally:
            # Clean up
            await transport.disconnect()

    async def test_binary_format(self):
        """Test STDIO transport with binary format."""
        # Create STDIO transport with subprocess mode
        transport = STDIOTransport(
            message_format="binary",
            subprocess_cmd=[self.echo_server_path, "binary"],
            debug=True,
        )

        try:
            # Connect to the subprocess
            connected = await transport.connect()
            self.assertTrue(connected, "Failed to connect")
            self.assertTrue(transport.is_connected, "Transport should be connected")

            # Initialize the connection
            init_message = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {"version": "2025-03-26"},
            }

            sent = await transport.send_message(init_message)
            self.assertTrue(sent, "Failed to send initialize message")

            # Receive response
            response = await transport.receive_message()
            self.assertIsNotNone(response, "No response received")
            self.assertEqual(
                response.get("id"), 1, "Response ID should match request ID"
            )
            self.assertIn("result", response, "Response should contain result")
            self.assertIn(
                "server_info",
                response.get("result", {}),
                "Result should contain server_info",
            )

            # Send a test message
            test_message = {
                "jsonrpc": "2.0",
                "method": "test",
                "id": 2,
                "params": {"binary": True, "data": "This is a binary format test"},
            }

            sent = await transport.send_message(test_message)
            self.assertTrue(sent, "Failed to send test message")

            # Receive response
            response = await transport.receive_message()
            self.assertIsNotNone(response, "No response received")
            self.assertEqual(
                response.get("id"), 2, "Response ID should match request ID"
            )
            self.assertIn("result", response, "Response should contain result")
            self.assertEqual(
                response.get("result", {}).get("method"),
                "test",
                "Response should contain echoed method",
            )
            self.assertEqual(
                response.get("result", {}).get("params", {}).get("data"),
                "This is a binary format test",
                "Response should contain echoed data",
            )

        finally:
            # Clean up
            await transport.disconnect()

    async def test_auto_format_detection(self):
        """Test STDIO transport with auto format detection."""
        # Create STDIO transport with subprocess mode and auto format detection
        transport = STDIOTransport(
            message_format="auto",
            subprocess_cmd=[self.echo_server_path, "auto"],
            debug=True,
        )

        try:
            # Connect to the subprocess
            connected = await transport.connect()
            self.assertTrue(connected, "Failed to connect")
            self.assertTrue(transport.is_connected, "Transport should be connected")

            # Initialize the connection
            init_message = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {"version": "2025-03-26"},
            }

            sent = await transport.send_message(init_message)
            self.assertTrue(sent, "Failed to send initialize message")

            # Receive response
            response = await transport.receive_message()
            self.assertIsNotNone(response, "No response received")
            self.assertEqual(
                response.get("id"), 1, "Response ID should match request ID"
            )
            self.assertIn("result", response, "Response should contain result")

            # Send another message to confirm format was detected correctly
            test_message = {
                "jsonrpc": "2.0",
                "method": "test_auto_detection",
                "id": 2,
                "params": {"auto_detected": True},
            }

            sent = await transport.send_message(test_message)
            self.assertTrue(sent, "Failed to send test message")

            # Receive response
            response = await transport.receive_message()
            self.assertIsNotNone(response, "No response received")
            self.assertEqual(
                response.get("id"), 2, "Response ID should match request ID"
            )
            self.assertIn("result", response, "Response should contain result")
            self.assertEqual(
                response.get("result", {}).get("params", {}).get("auto_detected"),
                True,
                "Response should contain echoed auto_detected parameter",
            )

        finally:
            # Clean up
            await transport.disconnect()


def run_async_test(test_func):
    """Run an async test function."""
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_func)


if __name__ == "__main__":
    # Run individual tests manually
    test = STDIOTransportTest()
    test.setUp()

    print("\n=== Testing Newline Format ===")
    run_async_test(test.test_newline_format())

    print("\n=== Testing Binary Format ===")
    run_async_test(test.test_binary_format())

    print("\n=== Testing Auto Format Detection ===")
    run_async_test(test.test_auto_format_detection())

    print("\nAll tests completed successfully!")

    # Alternatively, run with unittest
    # unittest.main()
