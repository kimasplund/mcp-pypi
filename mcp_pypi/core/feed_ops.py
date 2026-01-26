"""
Feed operations mixin for PyPI client.
"""

import logging
from typing import Any, Dict, List, cast

import defusedxml.ElementTree as ET

from mcp_pypi.core.models import (
    ErrorCode,
    FeedItem,
    PackagesFeed,
    ReleasesFeed,
    UpdatesFeed,
    format_error,
)
from mcp_pypi.utils.helpers import sanitize_package_name

logger = logging.getLogger("mcp-pypi.client")


class FeedOpsMixin:
    """Mixin providing RSS feed operations."""

    async def get_newest_packages(self) -> PackagesFeed:
        """Get the newest packages feed from PyPI."""
        url = "https://pypi.org/rss/packages.xml"

        try:
            data = await self.http.fetch(url)

            # Check for error in result
            if isinstance(data, dict) and "error" in data:
                return cast(PackagesFeed, data)

            # Handle the new format where raw data might be returned
            if isinstance(data, dict) and "raw_data" in data:
                raw_data = data["raw_data"]
                # Continue with XML parsing using raw_data
                if isinstance(raw_data, bytes):
                    data_str = raw_data.decode("utf-8")
                elif isinstance(raw_data, str):
                    data_str = raw_data
                else:
                    return {
                        "packages": [],
                        "error": {
                            "code": ErrorCode.PARSE_ERROR,
                            "message": f"Unexpected data type: {type(raw_data)}",
                        },
                    }
            elif isinstance(data, (str, bytes)):
                # Legacy format
                if isinstance(data, bytes):
                    data_str = data.decode("utf-8")
                else:
                    data_str = data
            else:
                return {
                    "packages": [],
                    "error": {
                        "code": ErrorCode.PARSE_ERROR,
                        "message": f"Unexpected data type: {type(data)}",
                    },
                }

            # Parse the XML string
            try:
                root = ET.fromstring(data_str)

                packages: List[FeedItem] = []
                for item in root.findall(".//item"):
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    desc_elem = item.find("description")
                    date_elem = item.find("pubDate")

                    if all(
                        elem is not None
                        for elem in (title_elem, link_elem, desc_elem, date_elem)
                    ):
                        packages.append(
                            {
                                "title": title_elem.text or "",
                                "link": link_elem.text or "",
                                "description": desc_elem.text or "",
                                "published_date": date_elem.text or "",
                            }
                        )

                return {"packages": packages}
            except ET.ParseError as e:
                logger.error(f"XML parse error: {e}")
                return {
                    "packages": [],
                    "error": {
                        "code": ErrorCode.PARSE_ERROR,
                        "message": f"Invalid XML response: {e}",
                    },
                }
        except Exception as e:
            logger.exception(f"Error parsing newest packages feed: {e}")
            return cast(PackagesFeed, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

    async def get_latest_updates(self) -> UpdatesFeed:
        """Get the latest updates feed from PyPI."""
        url = "https://pypi.org/rss/updates.xml"

        try:
            data = await self.http.fetch(url)

            # Check for error in result
            if isinstance(data, dict) and "error" in data:
                return cast(UpdatesFeed, data)

            # Handle the new format where raw data might be returned
            if isinstance(data, dict) and "raw_data" in data:
                raw_data = data["raw_data"]
                # Continue with XML parsing using raw_data
                if isinstance(raw_data, bytes):
                    data_str = raw_data.decode("utf-8")
                elif isinstance(raw_data, str):
                    data_str = raw_data
                else:
                    return {
                        "updates": [],
                        "error": {
                            "code": ErrorCode.PARSE_ERROR,
                            "message": f"Unexpected data type: {type(raw_data)}",
                        },
                    }

            elif isinstance(data, (str, bytes)):
                # Legacy format
                if isinstance(data, bytes):
                    data_str = data.decode("utf-8")
                else:
                    data_str = data
            else:
                return {
                    "updates": [],
                    "error": {
                        "code": ErrorCode.PARSE_ERROR,
                        "message": f"Unexpected data type: {type(data)}",
                    },
                }

            # Parse the XML string
            try:
                root = ET.fromstring(data_str)

                updates: List[FeedItem] = []
                for item in root.findall(".//item"):
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    desc_elem = item.find("description")
                    date_elem = item.find("pubDate")

                    if all(
                        elem is not None
                        for elem in (title_elem, link_elem, desc_elem, date_elem)
                    ):
                        updates.append(
                            {
                                "title": title_elem.text or "",
                                "link": link_elem.text or "",
                                "description": desc_elem.text or "",
                                "published_date": date_elem.text or "",
                            }
                        )

                return {"updates": updates}
            except ET.ParseError as e:
                logger.error(f"XML parse error: {e}")
                return {
                    "updates": [],
                    "error": {
                        "code": ErrorCode.PARSE_ERROR,
                        "message": f"Invalid XML response: {e}",
                    },
                }
        except Exception as e:
            logger.exception(f"Error parsing latest updates feed: {e}")
            return {
                "updates": [],
                "error": {"code": ErrorCode.UNKNOWN_ERROR, "message": str(e)},
            }

    async def get_project_releases(self, package_name: str) -> ReleasesFeed:
        """Get the releases feed for a project."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            url = f"https://pypi.org/rss/project/{sanitized_name}/releases.xml"

            data = await self.http.fetch(url)

            # Check for error in result
            if isinstance(data, dict) and "error" in data:
                return cast(ReleasesFeed, data)

            # Handle the new format where raw data might be returned
            if isinstance(data, dict) and "raw_data" in data:
                raw_data = data["raw_data"]
                # Continue with XML parsing using raw_data
                if isinstance(raw_data, bytes):
                    data_str = raw_data.decode("utf-8")
                elif isinstance(raw_data, str):
                    data_str = raw_data
                else:
                    return {
                        "releases": [],
                        "error": {
                            "code": ErrorCode.PARSE_ERROR,
                            "message": f"Unexpected data type: {type(raw_data)}",
                        },
                    }
            elif isinstance(data, (str, bytes)):
                # Legacy format
                if isinstance(data, bytes):
                    data_str = data.decode("utf-8")
                else:
                    data_str = data
            else:
                return {
                    "releases": [],
                    "error": {
                        "code": ErrorCode.PARSE_ERROR,
                        "message": f"Unexpected data type: {type(data)}",
                    },
                }

            # Parse the XML string
            try:
                root = ET.fromstring(data_str)

                releases: List[FeedItem] = []
                for item in root.findall(".//item"):
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    desc_elem = item.find("description")
                    date_elem = item.find("pubDate")

                    if all(
                        elem is not None
                        for elem in (title_elem, link_elem, desc_elem, date_elem)
                    ):
                        releases.append(
                            {
                                "title": title_elem.text or "",
                                "link": link_elem.text or "",
                                "description": desc_elem.text or "",
                                "published_date": date_elem.text or "",
                            }
                        )

                return {"releases": releases}
            except ET.ParseError as e:
                logger.error(f"XML parse error: {e}")
                return {
                    "releases": [],
                    "error": {
                        "code": ErrorCode.PARSE_ERROR,
                        "message": f"Invalid XML response: {e}",
                    },
                }
        except Exception as e:
            logger.exception(f"Error parsing project releases feed: {e}")
            return {
                "releases": [],
                "error": {"code": ErrorCode.UNKNOWN_ERROR, "message": str(e)},
            }

    async def get_updates_feed(self) -> UpdatesFeed:
        """Get package updates feed from PyPI RSS."""
        try:
            # PyPI RSS feed for updates
            url = "https://pypi.org/rss/updates.xml"

            # Fetch the RSS feed
            response = await self.http.fetch(url)

            # Check if we got an error
            if isinstance(response, dict) and "error" in response:
                return {"updates": [], "error": response["error"]}

            # If we have defusedxml, use it for secure parsing
            try:
                # Extract raw XML data from response
                if isinstance(response, dict) and "raw_data" in response:
                    xml_data = response["raw_data"]

                    # Parse the XML
                    if isinstance(xml_data, bytes):
                        root = ET.fromstring(xml_data)
                    elif isinstance(xml_data, str):
                        root = ET.fromstring(xml_data.encode("utf-8"))
                    else:
                        return {
                            "updates": [],
                            "error": {
                                "message": "Unexpected response format from RSS feed",
                                "code": "parse_error",
                            },
                        }

                    # Parse RSS items
                    updates = []

                    # RSS 2.0 format
                    for item in root.findall(".//item"):
                        title_elem = item.find("title")
                        link_elem = item.find("link")
                        desc_elem = item.find("description")
                        pub_date_elem = item.find("pubDate")

                        if title_elem is not None and title_elem.text:
                            # Extract package name and version from title
                            # Format is usually "package-name 1.2.3"
                            title = title_elem.text.strip()
                            parts = title.rsplit(" ", 1)

                            package_name = parts[0] if parts else title
                            version = parts[1] if len(parts) > 1 else ""

                            updates.append(
                                {
                                    "package_name": package_name,
                                    "version": version,
                                    "title": title,
                                    "link": (
                                        link_elem.text if link_elem is not None else ""
                                    ),
                                    "description": (
                                        desc_elem.text if desc_elem is not None else ""
                                    ),
                                    "published_date": (
                                        pub_date_elem.text
                                        if pub_date_elem is not None
                                        else ""
                                    ),
                                }
                            )

                    return {"updates": updates}
                else:
                    return {
                        "updates": [],
                        "error": {
                            "message": "Invalid response format from RSS feed",
                            "code": "parse_error",
                        },
                    }

            except ImportError:
                return {
                    "updates": [],
                    "error": {
                        "message": "RSS parsing requires defusedxml for security (install with: pip install defusedxml)",
                        "code": "missing_dependency",
                    },
                }

        except Exception as e:
            logger.exception(f"Error getting updates feed: {e}")
            return {"updates": [], "error": {"message": str(e), "code": "feed_error"}}

    async def get_packages_feed(self) -> Dict[str, Any]:
        """Get newest packages feed from PyPI RSS.

        Returns:
            Dict with list of newly created packages
        """
        try:
            # PyPI RSS feed for newest packages
            url = "https://pypi.org/rss/packages.xml"

            # Fetch the RSS feed
            response = await self.http.fetch(url)

            # Check if we got an error
            if isinstance(response, dict) and "error" in response:
                return {"packages": [], "error": response["error"]}

            # Parse RSS/XML
            try:
                # Extract raw XML data from response
                if isinstance(response, dict) and "raw_data" in response:
                    xml_data = response["raw_data"]

                    # Parse the XML
                    if isinstance(xml_data, bytes):
                        root = ET.fromstring(xml_data)
                    elif isinstance(xml_data, str):
                        root = ET.fromstring(xml_data.encode("utf-8"))
                    else:
                        return {
                            "packages": [],
                            "error": {
                                "message": "Unexpected response format from RSS feed",
                                "code": "parse_error",
                            },
                        }

                    # Parse RSS items
                    packages = []

                    # RSS 2.0 format
                    for item in root.findall(".//item"):
                        title_elem = item.find("title")
                        link_elem = item.find("link")
                        desc_elem = item.find("description")
                        pub_date_elem = item.find("pubDate")

                        if title_elem is not None and title_elem.text:
                            packages.append(
                                {
                                    "name": title_elem.text.strip(),
                                    "link": (
                                        link_elem.text if link_elem is not None else ""
                                    ),
                                    "description": (
                                        desc_elem.text if desc_elem is not None else ""
                                    ),
                                    "published_date": (
                                        pub_date_elem.text
                                        if pub_date_elem is not None
                                        else ""
                                    ),
                                }
                            )

                    return {"packages": packages}
                else:
                    return {
                        "packages": [],
                        "error": {
                            "message": "Invalid response format from RSS feed",
                            "code": "parse_error",
                        },
                    }

            except ImportError:
                return {
                    "packages": [],
                    "error": {
                        "message": "RSS parsing requires defusedxml for security (install with: pip install defusedxml)",
                        "code": "missing_dependency",
                    },
                }

        except Exception as e:
            logger.exception(f"Error getting newest packages feed: {e}")
            return {"packages": [], "error": {"message": str(e), "code": "feed_error"}}

    async def get_project_releases_feed(self, package_name: str) -> Dict[str, Any]:
        """Get releases feed for a specific project from PyPI RSS.

        Args:
            package_name: Name of the package

        Returns:
            Dict with list of releases for the project
        """
        try:
            # PyPI RSS feed for project releases
            url = f"https://pypi.org/rss/project/{package_name}/releases.xml"

            # Fetch the RSS feed
            response = await self.http.fetch(url)

            # Check if we got an error
            if isinstance(response, dict) and "error" in response:
                return {"releases": [], "error": response["error"]}

            # Parse RSS/XML
            try:
                # Extract raw XML data from response
                if isinstance(response, dict) and "raw_data" in response:
                    xml_data = response["raw_data"]

                    # Parse the XML
                    if isinstance(xml_data, bytes):
                        root = ET.fromstring(xml_data)
                    elif isinstance(xml_data, str):
                        root = ET.fromstring(xml_data.encode("utf-8"))
                    else:
                        return {
                            "releases": [],
                            "error": {
                                "message": "Unexpected response format from RSS feed",
                                "code": "parse_error",
                            },
                        }

                    # Parse RSS items
                    releases = []

                    # RSS 2.0 format
                    for item in root.findall(".//item"):
                        title_elem = item.find("title")
                        link_elem = item.find("link")
                        desc_elem = item.find("description")
                        pub_date_elem = item.find("pubDate")

                        if title_elem is not None and title_elem.text:
                            # Extract version from title (format: "package_name version")
                            title = title_elem.text.strip()
                            parts = title.rsplit(" ", 1)
                            version = parts[1] if len(parts) > 1 else ""

                            releases.append(
                                {
                                    "version": version,
                                    "title": title,
                                    "link": (
                                        link_elem.text if link_elem is not None else ""
                                    ),
                                    "description": (
                                        desc_elem.text if desc_elem is not None else ""
                                    ),
                                    "published_date": (
                                        pub_date_elem.text
                                        if pub_date_elem is not None
                                        else ""
                                    ),
                                }
                            )

                    return {"package_name": package_name, "releases": releases}
                else:
                    return {
                        "releases": [],
                        "error": {
                            "message": "Invalid response format from RSS feed",
                            "code": "parse_error",
                        },
                    }

            except ImportError:
                return {
                    "releases": [],
                    "error": {
                        "message": "RSS parsing requires defusedxml for security (install with: pip install defusedxml)",
                        "code": "missing_dependency",
                    },
                }

        except Exception as e:
            logger.exception(f"Error getting project releases feed: {e}")
            return {"releases": [], "error": {"message": str(e), "code": "feed_error"}}

    async def get_releases_feed(self) -> Dict[str, Any]:
        """Get recent releases feed from PyPI RSS.

        This is an alias for get_updates_feed() as PyPI's updates feed
        shows the latest releases across all packages.

        Returns:
            Dict with list of recent releases
        """
        # PyPI's updates feed shows recent releases
        result = await self.get_updates_feed()

        # Transform the response to match expected format
        if "updates" in result:
            return {"releases": result["updates"], "error": result.get("error")}
        return {
            "releases": [],
            "error": result.get("error") if isinstance(result, dict) else None,
        }
