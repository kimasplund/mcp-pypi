#!/usr/bin/env python3
import asyncio
import json
import os
import sys
import logging
from pathlib import Path

# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_pypi.client import MCPClient

# Enable debug logging
os.environ["MCP_DEBUG"] = "1"
logging.basicConfig(level=logging.DEBUG)


async def main():
    """Example usage of the MCPClient"""
    client = MCPClient(protocol_version="2023-12-01")

    try:
        print("Connecting to server...")
        # Connect to the server
        server_process = await client.connect_subprocess()

        print("Initializing connection...")
        # Initialize the connection
        await client.initialize()

        print(
            f"Connected to server version: {client.server_info.get('server_version', 'unknown')}"
        )
        print(f"Protocol version: {client.protocol_version}")

        # List available tools
        print("\nAvailable tools:")
        for tool_name in client.tools:
            print(f"- {tool_name}")

        # List available resources
        print("\nAvailable resources:")
        for resource_name in client.resources:
            print(f"- {resource_name}")

        # Search for a package
        print("\nSearching for 'requests' package...")
        search_result = await client.invoke_tool("search", {"query": "requests"})
        print(f"Found {len(search_result.get('results', []))} results")

        # Print the first result
        if search_result.get("results"):
            first_result = search_result["results"][0]
            print(
                f"\nFirst result: {first_result.get('name')} - {first_result.get('description')}"
            )

        # Get popular packages resource
        print("\nGetting popular packages...")
        popular_packages = await client.get_resource("popular_packages")
        packages = json.loads(popular_packages)
        print(
            f"Popular packages: {', '.join([p.get('name', 'Unknown') for p in packages[:5]])}"
        )

        # Get resource templates
        print("\nAvailable resource templates:")
        for template_name in client.resource_templates:
            print(f"- {template_name}")

        # Creating a custom resource from template (if available)
        if "custom_package_list" in client.resource_templates:
            print("\nCreating custom package list...")
            template = await client.get_resource_template("custom_package_list")
            template_data = json.loads(template)

            # Modify template data
            if isinstance(template_data, dict):
                template_data["packages"] = ["requests", "flask", "django"]

                # Create the resource
                await client.create_resource_from_template(
                    "my_packages", "custom_package_list", json.dumps(template_data)
                )
                print("Custom resource created!")

                # Retrieve the created resource
                my_packages = await client.get_resource("my_packages")
                print(f"My packages: {my_packages}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Close the connection
        await client.close()

        # Terminate the server process
        if hasattr(client, "process") and client.process:
            client.process.terminate()
            await client.process.wait()


if __name__ == "__main__":
    asyncio.run(main())
