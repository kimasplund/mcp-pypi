#!/usr/bin/env python3
"""Test if BeautifulSoup is detected correctly"""

import asyncio
import logging
from mcp_pypi.core import PyPIClient
from mcp_pypi.core.models import PyPIClientConfig
from mcp_pypi.utils import configure_logging


async def main():
    """Main function"""
    # Configure more verbose logging
    configure_logging(level=logging.DEBUG)

    # Import bs4 directly to verify it's available
    try:
        import bs4

        print(f"bs4 is available, version: {bs4.__version__}")
    except ImportError:
        print("bs4 is not available")

    # Check if PyPIClient detects bs4
    config = PyPIClientConfig()
    client = PyPIClient(config)
    print(f"PyPIClient._has_bs4: {client._has_bs4}")

    # Test the search_packages method with our fix
    print("\nTest search_packages method:")
    search_result = await client.search_packages("requests")

    print(f"Search result type: {type(search_result)}")

    if isinstance(search_result, dict):
        print(f"Search result keys: {search_result.keys()}")

        if "message" in search_result:
            print(f"Message: {search_result['message']}")

        if "results" in search_result:
            results = search_result["results"]
            print(f"Results is a {type(results)}, length: {len(results)}")

            if results:
                print("First result:", results[0])
    else:
        print("Search result is not a dictionary")

    # Test with a different search term
    print("\nTesting with another search term:")
    search_result2 = await client.search_packages("flask")

    if isinstance(search_result2, dict):
        print(f"Search result keys: {search_result2.keys()}")

        if "message" in search_result2:
            print(f"Message: {search_result2['message']}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
