#!/usr/bin/env python3
"""
Test the User-Agent functionality in MCP-PyPI client.
"""

import asyncio
import logging
import sys
import os

# Add the parent directory to the path to import mcp_pypi
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from mcp_pypi.core import PyPIClient
from mcp_pypi.core.models import PyPIClientConfig

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


async def test_default_user_agent():
    """Test using the default User-Agent."""
    print("\n=== Testing with Default User-Agent ===")

    # Create client with default User-Agent
    client = PyPIClient()

    # Print the current User-Agent
    print(f"Using User-Agent: {client.config.user_agent}")

    # Make a request to check if package exists
    print("Testing request with requests package...")
    result = await client.check_package_exists("requests")

    print(f"Result: {result}")

    await client.close()


async def test_custom_user_agent():
    """Test using a custom User-Agent."""
    print("\n=== Testing with Custom User-Agent ===")

    # Create client
    client = PyPIClient()

    # Set custom User-Agent
    custom_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    client.set_user_agent(custom_ua)

    # Print the current User-Agent
    print(f"Using User-Agent: {client.config.user_agent}")

    # Make a request to check if package exists
    print("Testing request with numpy package...")
    result = await client.check_package_exists("numpy")

    print(f"Result: {result}")

    await client.close()


async def main():
    """Run all tests."""
    print("Testing User-Agent functionality in MCP-PyPI client")

    await test_default_user_agent()
    await test_custom_user_agent()

    print("\nTests completed.")


if __name__ == "__main__":
    asyncio.run(main())
