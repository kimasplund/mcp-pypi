#!/usr/bin/env python3
"""Test script to verify multiple PyPI client methods."""

import asyncio
import json
import logging
from pprint import pprint

import pytest

from mcp_pypi.core import PyPIClient
from mcp_pypi.core.models import PyPIClientConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@pytest.mark.asyncio
async def test_client_methods():
    """Test various PyPI client methods."""
    # Create a client
    config = PyPIClientConfig()
    client = PyPIClient(config)

    try:
        print("\n=== Testing search_packages ===")
        result = await client.search_packages("requests")
        print(f"Found {len(result.get('results', []))} results")

        print("\n=== Testing get_dependencies ===")
        result = await client.get_dependencies("requests")
        if "dependencies" in result:
            print(f"Found {len(result['dependencies'])} dependencies")
            if result["dependencies"]:
                print(f"First dependency: {result['dependencies'][0]['name']}")

        print("\n=== Testing check_package_exists ===")
        result = await client.check_package_exists("requests")
        print(f"Package exists: {result.get('exists', False)}")

        print("\n=== Testing get_package_metadata ===")
        result = await client.get_package_metadata("requests")
        if "metadata" in result:
            print(f"Package name: {result['metadata'].get('name')}")
            print(f"Latest version: {result['metadata'].get('version')}")

        print("\n=== Testing get_package_stats ===")
        result = await client.get_package_stats("requests")
        if "downloads" in result:
            print(f"Monthly downloads: {sum(result['downloads'].values())}")

        print("\n=== Testing get_dependency_tree ===")
        result = await client.get_dependency_tree("requests", depth=1)
        if "tree" in result:
            deps = result["tree"].get("dependencies", [])
            print(f"Direct dependencies: {len(deps)}")
            if deps:
                print(f"First dependency: {deps[0]['name']}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_client_methods())
