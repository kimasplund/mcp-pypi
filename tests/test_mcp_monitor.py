#!/usr/bin/env python3
"""
Test script for MCP Monitor functionality.
This includes tests for both message formats (newline and binary).
"""

import asyncio
import json
import struct
import os
import sys
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import logging

# Add parent directory to path to import module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.mcp_monitor import MCPMonitor, MessageFormat

# Disable logging during tests
logging.disable(logging.CRITICAL)


class TestMCPMonitor(unittest.TestCase):
    """Test cases for the MCPMonitor class"""

    def setUp(self):
        """Set up test fixtures"""
        self.monitor = MCPMonitor(
            server_host="localhost", server_port=5555, debug=False
        )
        # Mock the reader and writer
        self.monitor.reader = AsyncMock()
        self.monitor.writer = MagicMock()
        self.monitor.connected = True

    async def mock_receive_newline(self, message):
        """Mock receiving a newline-delimited message"""
        json_data = json.dumps(message)
        self.monitor.reader.readline.return_value = f"{json_data}\n".encode("utf-8")
        return await self.monitor.receive_message()

    async def mock_receive_binary(self, message):
        """Mock receiving a binary length-prefixed message"""
        json_data = json.dumps(message).encode("utf-8")
        length = len(json_data)
        header = struct.pack(">I", length)

        # First read 4 bytes for length
        self.monitor.reader.readexactly.side_effect = [header, json_data]

        return await self.monitor.receive_message()

    async def test_send_message_newline(self):
        """Test sending a message in newline format"""
        self.monitor.message_format = MessageFormat.NEWLINE

        # Mock writer.drain to return a completed future
        self.monitor.writer.drain.return_value = asyncio.Future()
        self.monitor.writer.drain.return_value.set_result(None)

        message = {"test": "message"}
        result = await self.monitor.send_message(message)

        self.assertTrue(result)
        self.monitor.writer.write.assert_called_once()
        # Verify newline was appended
        call_args = self.monitor.writer.write.call_args[0][0]
        self.assertTrue(call_args.endswith(b"\n"))

    async def test_send_message_binary(self):
        """Test sending a message in binary format"""
        self.monitor.message_format = MessageFormat.BINARY

        # Mock writer.drain to return a completed future
        self.monitor.writer.drain.return_value = asyncio.Future()
        self.monitor.writer.drain.return_value.set_result(None)

        message = {"test": "message"}
        result = await self.monitor.send_message(message)

        self.assertTrue(result)
        self.monitor.writer.write.assert_called_once()
        # Verify first 4 bytes are header
        call_args = self.monitor.writer.write.call_args[0][0]
        self.assertEqual(len(call_args), 4 + len(json.dumps(message).encode("utf-8")))

    async def test_receive_message_newline(self):
        """Test receiving a message in newline format"""
        self.monitor.message_format = MessageFormat.NEWLINE

        test_message = {"type": "test", "value": 123}
        received = await self.mock_receive_newline(test_message)

        self.assertEqual(received, test_message)

    async def test_receive_message_binary(self):
        """Test receiving a message in binary format"""
        self.monitor.message_format = MessageFormat.BINARY

        test_message = {"type": "test", "value": 456}
        received = await self.mock_receive_binary(test_message)

        self.assertEqual(received, test_message)

    async def test_auto_detect_from_newline(self):
        """Test auto-detecting newline format"""
        self.monitor.message_format = MessageFormat.AUTO_DETECT

        # Setup mock to simulate newline format
        test_message = {"type": "test", "value": "newline"}
        json_data = json.dumps(test_message)
        encoded = json_data.encode("utf-8")

        # First byte is {
        self.monitor.reader.read.side_effect = [
            b"{",  # First byte
            encoded[1:4],  # Next 3 bytes
        ]

        # Rest of the message
        self.monitor.reader.readline.return_value = encoded[4:] + b"\n"

        received = await self.monitor.receive_message()

        self.assertEqual(received, test_message)
        self.assertEqual(self.monitor.detected_message_format, MessageFormat.NEWLINE)

    async def test_auto_detect_from_binary(self):
        """Test auto-detecting binary format"""
        self.monitor.message_format = MessageFormat.AUTO_DETECT

        # Setup mock to simulate binary format
        test_message = {"type": "test", "value": "binary"}
        json_data = json.dumps(test_message).encode("utf-8")
        length = len(json_data)

        # Pack binary header (4 bytes)
        header = struct.pack(">I", length)

        # First 4 bytes (length)
        self.monitor.reader.read.side_effect = [
            header[0:1],  # First byte
            header[1:4],  # Next 3 bytes
        ]

        # Rest of the message
        self.monitor.reader.readexactly.return_value = json_data

        received = await self.monitor.receive_message()

        self.assertEqual(received, test_message)
        self.assertEqual(self.monitor.detected_message_format, MessageFormat.BINARY)

    def test_get_current_message_format(self):
        """Test the get_current_message_format method"""
        # Test with explicit format
        self.monitor.message_format = MessageFormat.NEWLINE
        self.assertEqual(self.monitor.get_current_message_format(), "NEWLINE")

        # Test with auto-detect but no detection yet
        self.monitor.message_format = MessageFormat.AUTO_DETECT
        self.monitor.detected_message_format = None
        self.assertEqual(self.monitor.get_current_message_format(), "AUTO_DETECT")

        # Test with auto-detect and detected format
        self.monitor.message_format = MessageFormat.AUTO_DETECT
        self.monitor.detected_message_format = MessageFormat.BINARY
        self.assertEqual(
            self.monitor.get_current_message_format(), "AUTO_DETECT (detected: BINARY)"
        )


# Run the tests
def run_tests():
    # Create async test suite
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    test_methods = [
        "test_send_message_newline",
        "test_send_message_binary",
        "test_receive_message_newline",
        "test_receive_message_binary",
        "test_auto_detect_from_newline",
        "test_auto_detect_from_binary",
        "test_get_current_message_format",
    ]

    # Run each test method in the event loop
    for test_name in test_methods:
        test = TestMCPMonitor(test_name)
        test.setUp()
        method = getattr(test, test_name)

        if asyncio.iscoroutinefunction(method):
            loop.run_until_complete(method())
        else:
            method()

    print("All tests passed!")


if __name__ == "__main__":
    run_tests()
