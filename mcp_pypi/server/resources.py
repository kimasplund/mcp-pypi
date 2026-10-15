"""Resource registration for PyPI MCP Server.

Contains resource endpoints for PyPI feed data.
"""

from __future__ import annotations

import logging

from fastmcp import FastMCP

from mcp_pypi.core import PyPIClient

logger = logging.getLogger("mcp-pypi.server")


def register_resources(mcp: FastMCP, client: PyPIClient) -> None:
    """Register PyPI resources with the MCP server.

    Args:
        mcp: The FastMCP server to register resources with.
        client: The PyPI client used to fetch feeds.
    """

    @mcp.resource("pypi://recent-releases", title="Recent releases")
    async def get_recent_releases() -> str:
        """Get recent package releases from PyPI."""
        try:
            feed = await client.get_releases_feed()
            if not feed.get("error"):
                releases = []
                feed_releases = feed.get("releases", [])
                for release in feed_releases[:20]:
                    releases.append(
                        f"- {release.get('title', 'Unknown')} "
                        f"({release.get('published_date', 'Unknown date')})"
                    )
                return "Recent PyPI Releases:\n\n" + "\n".join(releases)
            return "No recent releases available"
        except Exception as e:
            logger.error(f"Error getting recent releases: {e}")
            return f"Error getting recent releases: {str(e)}"

    @mcp.resource("pypi://new-packages", title="New packages")
    async def get_new_packages() -> str:
        """Get newly created packages on PyPI."""
        try:
            feed = await client.get_packages_feed()
            if not feed.get("error"):
                packages = []
                feed_packages = feed.get("packages", [])
                for pkg in feed_packages[:20]:
                    packages.append(
                        f"- {pkg.get('title', 'Unknown')} "
                        f"({pkg.get('published_date', 'Unknown date')})"
                    )
                return "New PyPI Packages:\n\n" + "\n".join(packages)
            return "No new packages available"
        except Exception as e:
            logger.error(f"Error getting new packages: {e}")
            return f"Error getting new packages: {str(e)}"

    @mcp.resource("pypi://updated-packages", title="Updated packages")
    async def get_updated_packages() -> str:
        """Get recently updated packages on PyPI."""
        try:
            feed = await client.get_updates_feed()
            if not feed.get("error"):
                updates = []
                feed_updates = feed.get("updates", [])
                for update in feed_updates[:20]:
                    updates.append(
                        f"- {update.get('title', 'Unknown')} "
                        f"({update.get('published_date', 'Unknown date')})"
                    )
                return "Recently Updated PyPI Packages:\n\n" + "\n".join(updates)
            return "No recent updates available"
        except Exception as e:
            logger.error(f"Error getting package updates: {e}")
            return f"Error getting package updates: {str(e)}"
