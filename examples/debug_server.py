#!/usr/bin/env python3
import asyncio
import json
import sys
import os
import logging
from pathlib import Path
import signal
import time

# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_pypi.client import MCPClient
from mcp_pypi.server import MCPServer

# Enable debug logging
os.environ["MCP_DEBUG"] = "1"
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("debug_server")


async def monitor_server_process(server_process):
    """Monitor the server process for any issues"""
    while True:
        if server_process.returncode is not None:
            logger.error(f"Server process exited with code {server_process.returncode}")
            break

        # Check stdout and stderr
        try:
            stdout = await server_process.stdout.read(1024)
            if stdout:
                logger.debug(f"Server stdout: {stdout.decode('utf-8')}")
        except Exception as e:
            logger.error(f"Error reading server stdout: {e}")

        try:
            stderr = await server_process.stderr.read(1024)
            if stderr:
                logger.error(f"Server stderr: {stderr.decode('utf-8')}")
        except Exception as e:
            logger.error(f"Error reading server stderr: {e}")

        await asyncio.sleep(0.1)


async def test_direct_server():
    """Test the server directly without using the client"""
    logger.info("Starting server directly")

    server = MCPServer(protocol_version="2023-12-01")

    # Create pipes for communication
    client_read, server_write = os.pipe()
    server_read, client_write = os.pipe()

    # Set up the server with the pipes
    server.set_io(os.fdopen(server_read, "rb"), os.fdopen(server_write, "wb"))

    # Start the server in a separate task
    server_task = asyncio.create_task(server.run())

    try:
        # Create reader and writer for client side
        client_reader = asyncio.StreamReader()
        client_protocol = asyncio.StreamReaderProtocol(client_reader)

        loop = asyncio.get_event_loop()
        transport, _ = await loop.connect_read_pipe(
            lambda: client_protocol, os.fdopen(client_read, "rb")
        )

        client_writer_transport, client_writer_protocol = await loop.connect_write_pipe(
            asyncio.BaseProtocol, os.fdopen(client_write, "wb")
        )

        # Helper to write messages
        async def write_message(msg):
            data = json.dumps(msg).encode("utf-8")
            length = len(data)
            header = length.to_bytes(4, byteorder="big")
            client_writer_transport.write(header + data)
            await asyncio.sleep(0.1)  # Give time for the server to process

        # Helper to read messages
        async def read_message():
            header = await client_reader.readexactly(4)
            length = int.from_bytes(header, byteorder="big")
            data = await client_reader.readexactly(length)
            return json.loads(data.decode("utf-8"))

        # Initialize
        logger.info("Sending initialization")
        await write_message(
            {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {"protocol_version": "2023-12-01"},
                "id": 1,
            }
        )

        init_response = await read_message()
        logger.info(f"Initialization response: {json.dumps(init_response, indent=2)}")

        # List tools
        logger.info("Listing tools")
        await write_message(
            {"jsonrpc": "2.0", "method": "listTools", "params": {}, "id": 2}
        )

        tools_response = await read_message()
        logger.info(f"Tools response: {json.dumps(tools_response, indent=2)}")

        # Invoke search tool
        logger.info("Invoking search tool")
        await write_message(
            {
                "jsonrpc": "2.0",
                "method": "invokeTool",
                "params": {"tool": "search", "parameters": {"query": "requests"}},
                "id": 3,
            }
        )

        search_response = await read_message()
        logger.info(f"Search response: {json.dumps(search_response, indent=2)}")

        # Get a resource
        logger.info("Getting resource")
        await write_message(
            {
                "jsonrpc": "2.0",
                "method": "getResource",
                "params": {"name": "popular_packages"},
                "id": 4,
            }
        )

        resource_response = await read_message()
        logger.info(f"Resource response: {json.dumps(resource_response, indent=2)}")

    except Exception as e:
        logger.error(f"Error in direct server test: {e}", exc_info=True)
    finally:
        # Close everything
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

        transport.close()
        client_writer_transport.close()


async def test_client_server():
    """Test the client-server communication"""
    logger.info("Starting client-server test")

    client = MCPClient(protocol_version="2023-12-01")

    try:
        # Connect to the server
        logger.info("Connecting to server")
        server_process = await client.connect_subprocess()

        # Start monitoring the server process
        monitor_task = asyncio.create_task(monitor_server_process(server_process))

        # Initialize the connection
        logger.info("Initializing connection")
        await client.initialize()

        logger.info(
            f"Connected to server version: {client.server_info.get('server_version', 'unknown')}"
        )
        logger.info(f"Protocol version: {client.protocol_version}")

        # List available tools
        logger.info(f"Available tools: {client.tools}")

        # List available resources
        logger.info(f"Available resources: {client.resources}")

        # Search for a package
        logger.info("Searching for 'requests' package")
        try:
            search_result = await client.invoke_tool("search", {"query": "requests"})
            logger.info(f"Search results: {json.dumps(search_result, indent=2)}")
        except Exception as e:
            logger.error(f"Error searching: {e}", exc_info=True)

        # Get popular packages resource
        logger.info("Getting popular packages")
        try:
            popular_packages = await client.get_resource("popular_packages")
            packages = json.loads(popular_packages)
            logger.info(f"Popular packages: {json.dumps(packages[:2], indent=2)}")
        except Exception as e:
            logger.error(f"Error getting resource: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Error in client-server test: {e}", exc_info=True)
    finally:
        # Cancel monitor task
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        # Close the connection
        logger.info("Closing connection")
        await client.close()

        # Terminate the server process
        if hasattr(client, "process") and client.process:
            logger.info("Terminating server process")
            client.process.terminate()
            await client.process.wait()


async def main():
    """Run all tests"""
    logger.info("Starting debug tests")

    # Set a timeout for the entire script
    try:
        await asyncio.wait_for(test_client_server(), 30)
    except asyncio.TimeoutError:
        logger.error("Client-server test timed out")

    await asyncio.sleep(1)  # Brief pause between tests

    try:
        await asyncio.wait_for(test_direct_server(), 30)
    except asyncio.TimeoutError:
        logger.error("Direct server test timed out")

    logger.info("All tests completed")


if __name__ == "__main__":
    # Handle keyboard interrupts gracefully
    def signal_handler(*args):
        logger.info("Received interrupt, shutting down")
        for task in asyncio.all_tasks():
            task.cancel()

    signal.signal(signal.SIGINT, signal_handler)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
