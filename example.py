#!/usr/bin/env python3
"""
Example usage of the MCP-PyPI client library.
"""

import asyncio
import json
from rich.console import Console
import logging
from typing import Dict, Any, List

# Import our PyPI client library
from mcp_pypi.core import PyPIClient
from mcp_pypi.core.models import PyPIClientConfig
from mcp_pypi.utils import configure_logging

console = Console()

async def main():
    """Run the example script."""
    # Configure logging
    configure_logging(level=logging.INFO)
    
    # Create a PyPI client with custom config
    config = PyPIClientConfig(cache_max_size=1 * 1024 * 1024)  # 1MB cache size
    client = PyPIClient(config)
    
    package_name = "requests"
    
    try:
        # Get package info
        console.print(f"Getting information for {package_name}")
        info = await client.get_package_info(package_name)
        
        if "error" in info:
            console.print(f"Error: {info['error']['message']}")
        else:
            version = info['info']['version']
            console.print(f"Latest version: {version}")
        
        # Get download statistics
        console.print("\nGetting download statistics")
        stats = await client.get_package_stats(package_name)
        
        if "error" in stats:
            console.print(f"Error: {stats['error']['message']}")
        else:
            downloads = stats.get('downloads', {})
            last_day = downloads.get('last_day', 0)
            last_week = downloads.get('last_week', 0)
            last_month = downloads.get('last_month', 0)
            console.print(f"Last day downloads: {last_day:,}")
            console.print(f"Last week downloads: {last_week:,}")
            console.print(f"Last month downloads: {last_month:,}")
        
        # Get package dependencies
        console.print("\nGetting dependencies")
        deps = await client.get_dependencies(package_name)
        
        if "error" in deps:
            console.print(f"Error: {deps['error']['message']}")
        elif "dependencies" in deps:
            for dep in deps["dependencies"]:
                name = dep.get("name", "")
                version_spec = dep.get("version_spec", "")
                console.print(f"  {name} {version_spec}")
        
        # Get documentation URL
        console.print("\nGetting documentation URL")
        docs = await client.get_documentation_url(package_name)
        
        if "error" in docs:
            console.print(f"Error: {docs['error']['message']}")
        else:
            doc_url = docs.get("docs_url", "")
            console.print(f"Documentation URL: {doc_url}")
        
        console.print("\nSearching for related packages")
        search_result = await client.search_packages("related:requests")
        
        # Handle different search result types properly
        if isinstance(search_result, str):
            # If we got a raw HTML string, convert it to a proper response format
            if "Client Challenge" in search_result:
                console.print("PyPI returned a security challenge page.")
                console.print("For security reasons, search results cannot be displayed.")
                console.print("Try using a web browser to search PyPI directly.")
            else:
                console.print("Search returned raw HTML content")
                console.print("Install beautifulsoup4 for better search results: pip install beautifulsoup4")
        elif isinstance(search_result, dict):
            if "error" in search_result:
                console.print(f"Search error: {search_result['error']['message']}")
            elif "message" in search_result:
                console.print(search_result['message'])
            elif "results" in search_result and isinstance(search_result["results"], list):
                if search_result["results"]:
                    console.print("Related packages:")
                    for pkg in search_result["results"][:3]:  # Show first 3 results
                        if isinstance(pkg, dict):
                            name = pkg.get('name', 'Unknown')
                            version = pkg.get('version', '')
                            description = pkg.get('description', '')[:60]
                            console.print(f"  {name} {version} - {description}...")
                else:
                    console.print("No related packages found")
            else:
                console.print("No search results returned")
        
        console.print("\nCache statistics")
        cache_stats = await client.cache.get_cache_stats()
        console.print(f"Total cache size: {cache_stats['total_size_mb']:.2f} MB")
        console.print(f"Number of cached items: {cache_stats['file_count']}")
        
    except Exception as e:
        console.print(f"Error: {str(e)}")
    finally:
        # Always close the client to release resources
        await client.close()

if __name__ == "__main__":
    asyncio.run(main()) 