"""
Core client for interacting with PyPI.
"""

import asyncio
import datetime
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, cast
from urllib.parse import quote_plus

import defusedxml.ElementTree as ET
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from mcp_pypi.core.cache import AsyncCacheManager
from mcp_pypi.core.http import AsyncHTTPClient
from mcp_pypi.core.models import (DependenciesResult, DependencyTreeResult,
                                  DocumentationResult, ErrorCode, ExistsResult,
                                  FeedItem, MetadataResult, PackageInfo,
                                  PackageMetadata, PackageRequirement,
                                  PackageRequirementsResult, PackagesFeed,
                                  PyPIClientConfig, ReleasesFeed, ReleasesInfo,
                                  SearchResult, StatsResult, TreeNode,
                                  UpdatesFeed, UrlResult, UrlsInfo,
                                  VersionComparisonResult, VersionInfo,
                                  format_error)
from mcp_pypi.core.stats import PackageStatsService
from mcp_pypi.utils.helpers import sanitize_package_name, sanitize_version

# For Python < 3.11, use tomli for parsing TOML files
if sys.version_info < (3, 11):
    import tomli as tomllib  # type: ignore[import-not-found]
else:
    import tomllib

logger = logging.getLogger("mcp-pypi.client")


class PyPIClient:
    """Client for interacting with PyPI."""

    def __init__(
        self,
        config: Optional[PyPIClientConfig] = None,
        cache_manager: Optional[AsyncCacheManager] = None,
        http_client: Optional[AsyncHTTPClient] = None,
        stats_service: Optional[PackageStatsService] = None,
    ):
        """Initialize the PyPI client with optional dependency injection.

        Args:
            config: Optional configuration. If not provided, default config is used.
            cache_manager: Optional cache manager. If not provided, a new one is created.
            http_client: Optional HTTP client. If not provided, a new one is created.
            stats_service: Optional stats service. If not provided, a new one is created.
        """
        self.config = config or PyPIClientConfig()

        # Create or use provided dependencies
        self.cache = cache_manager or AsyncCacheManager(self.config)
        self.http = http_client or AsyncHTTPClient(self.config, self.cache)
        self.stats = stats_service or PackageStatsService(self.http)

        # Check for optional dependencies
        self._has_bs4 = self._check_import("bs4", "BeautifulSoup")
        self._has_plotly = self._check_import("plotly.graph_objects", "go")

    def _check_import(self, module: str, name: str) -> bool:
        """Check if a module can be imported."""
        try:
            __import__(module)
            return True
        except ImportError:
            logger.info(
                f"Optional dependency {module} not found; some features will be limited"
            )
            return False

    def set_user_agent(self, user_agent: str) -> None:
        """Set a custom User-Agent for all subsequent requests.

        Args:
            user_agent: The User-Agent string to use for PyPI requests
        """
        self.config.user_agent = user_agent
        logger.info(f"User-Agent updated to: {user_agent}")

    async def close(self) -> None:
        """Close the client and release resources."""
        await self.http.close()

    async def get_package_info(self, package_name: str) -> PackageInfo:
        """Get detailed package information from PyPI."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            url = f"https://pypi.org/pypi/{sanitized_name}/json"

            result = await self.http.fetch(url)

            # Check for error in result
            if isinstance(result, dict) and "error" in result:
                return cast(PackageInfo, result)

            # Handle the new format where raw data might be returned
            if isinstance(result, dict) and "raw_data" in result:
                content_type = result.get("content_type", "")
                raw_data = result["raw_data"]

                # Handle empty response
                if not raw_data:
                    logger.warning(f"Received empty response for {url}")
                    return cast(
                        PackageInfo,
                        format_error(ErrorCode.PARSE_ERROR, "Received empty response"),
                    )

                # If we got JSON content, parse it
                if "application/json" in content_type and isinstance(raw_data, str):
                    try:
                        parsed_data = json.loads(raw_data)
                        return cast(PackageInfo, parsed_data)
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding JSON from raw_data: {e}")
                        return cast(
                            PackageInfo,
                            format_error(
                                ErrorCode.PARSE_ERROR, f"Invalid JSON response: {e}"
                            ),
                        )
                else:
                    logger.warning(f"Received non-JSON content: {content_type}")
                    return cast(
                        PackageInfo,
                        format_error(
                            ErrorCode.PARSE_ERROR,
                            f"Unexpected content type: {content_type}",
                        ),
                    )

            # Already parsed JSON data
            return cast(PackageInfo, result)
        except ValueError as e:
            return cast(PackageInfo, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Unexpected error getting package info: {e}")
            return cast(PackageInfo, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

    async def get_latest_version(self, package_name: str) -> VersionInfo:
        """Get the latest version of a package."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            url = f"https://pypi.org/pypi/{sanitized_name}/json"

            data = await self.http.fetch(url)

            # Check for error in result
            if isinstance(data, dict) and "error" in data:
                return cast(VersionInfo, data)

            # Handle the new format where raw data might be returned
            if isinstance(data, dict) and "raw_data" in data:
                content_type = data.get("content_type", "")
                raw_data = data["raw_data"]

                # If we got JSON content, parse it
                if "application/json" in content_type and isinstance(raw_data, str):
                    try:
                        parsed_data = json.loads(raw_data)
                        version = parsed_data.get("info", {}).get("version", "")
                        return {"version": version}
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding JSON from raw_data: {e}")
                        return cast(
                            VersionInfo,
                            format_error(
                                ErrorCode.PARSE_ERROR, f"Invalid JSON response: {e}"
                            ),
                        )
                else:
                    logger.warning(f"Received non-JSON content: {content_type}")
                    return cast(
                        VersionInfo,
                        format_error(
                            ErrorCode.PARSE_ERROR,
                            f"Unexpected content type: {content_type}",
                        ),
                    )

            # Already parsed JSON data
            version = data.get("info", {}).get("version", "")
            return {"version": version}
        except ValueError as e:
            return cast(VersionInfo, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Unexpected error getting latest version: {e}")
            return cast(VersionInfo, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

    async def get_package_releases(self, package_name: str) -> ReleasesInfo:
        """Get all releases for a package."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            url = f"https://pypi.org/pypi/{sanitized_name}/json"

            data = await self.http.fetch(url)

            # Check for error in result
            if isinstance(data, dict) and "error" in data:
                return cast(ReleasesInfo, data)

            # Handle the new format where raw data might be returned
            if isinstance(data, dict) and "raw_data" in data:
                content_type = data.get("content_type", "")
                raw_data = data["raw_data"]

                # If we got JSON content, parse it
                if "application/json" in content_type and isinstance(raw_data, str):
                    try:
                        parsed_data = json.loads(raw_data)
                        releases = list(parsed_data.get("releases", {}).keys())
                        return {"releases": releases}
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding JSON from raw_data: {e}")
                        return cast(
                            ReleasesInfo,
                            format_error(
                                ErrorCode.PARSE_ERROR, f"Invalid JSON response: {e}"
                            ),
                        )
                else:
                    logger.warning(f"Received non-JSON content: {content_type}")
                    return cast(
                        ReleasesInfo,
                        format_error(
                            ErrorCode.PARSE_ERROR,
                            f"Unexpected content type: {content_type}",
                        ),
                    )

            # Already parsed JSON data
            releases = list(data.get("releases", {}).keys())
            return {"releases": releases}
        except ValueError as e:
            return cast(ReleasesInfo, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Unexpected error getting package releases: {e}")
            return cast(ReleasesInfo, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

    async def get_release_urls(self, package_name: str, version: str) -> UrlsInfo:
        """Get download URLs for a specific release version."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            sanitized_version = sanitize_version(version)
            url = f"https://pypi.org/pypi/{sanitized_name}/{sanitized_version}/json"

            result = await self.http.fetch(url)

            # Check for error in result
            if isinstance(result, dict) and "error" in result:
                return cast(UrlsInfo, result)

            # Handle the new format where raw data might be returned
            if isinstance(result, dict) and "raw_data" in result:
                content_type = result.get("content_type", "")
                raw_data = result["raw_data"]

                # If we got JSON content, parse it
                if "application/json" in content_type and isinstance(raw_data, str):
                    try:
                        parsed_data = json.loads(raw_data)
                        return {"urls": parsed_data["urls"]}
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.error(f"Error processing JSON from raw_data: {e}")
                        return cast(
                            UrlsInfo,
                            format_error(
                                ErrorCode.PARSE_ERROR, f"Invalid JSON response: {e}"
                            ),
                        )
                else:
                    logger.warning(f"Received non-JSON content: {content_type}")
                    return cast(
                        UrlsInfo,
                        format_error(
                            ErrorCode.PARSE_ERROR,
                            f"Unexpected content type: {content_type}",
                        ),
                    )

            # Already parsed JSON data
            return {"urls": result["urls"]}
        except ValueError as e:
            return cast(UrlsInfo, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Unexpected error getting release URLs: {e}")
            return cast(UrlsInfo, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

    def get_source_url(self, package_name: str, version: str) -> UrlResult:
        """Generate a predictable source package URL."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            sanitized_version = sanitize_version(version)

            first_letter = sanitized_name[0]
            url = f"https://files.pythonhosted.org/packages/source/{first_letter}/{sanitized_name}/{sanitized_name}-{sanitized_version}.tar.gz"

            return {"url": url}
        except ValueError as e:
            return cast(UrlResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Unexpected error generating source URL: {e}")
            return cast(UrlResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

    def get_wheel_url(
        self,
        package_name: str,
        version: str,
        python_tag: str,
        abi_tag: str,
        platform_tag: str,
        build_tag: Optional[str] = None,
    ) -> UrlResult:
        """Generate a predictable wheel package URL."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            sanitized_version = sanitize_version(version)

            # Clean tags according to PEP 491
            wheel_parts = {
                "name": sanitized_name,
                "version": sanitized_version,
                "python_tag": python_tag.replace(".", "_"),
                "abi_tag": abi_tag.replace(".", "_"),
                "platform_tag": platform_tag.replace(".", "_"),
            }

            # Add build tag if provided
            build_suffix = ""
            if build_tag:
                build_suffix = f"-{build_tag.replace('.', '_')}"

            # Format wheel filename
            filename = f"{wheel_parts['name']}-{wheel_parts['version']}{build_suffix}-{wheel_parts['python_tag']}-{wheel_parts['abi_tag']}-{wheel_parts['platform_tag']}.whl"

            first_letter = sanitized_name[0]
            url = f"https://files.pythonhosted.org/packages/{wheel_parts['python_tag']}/{first_letter}/{sanitized_name}/{filename}"

            return {"url": url}
        except ValueError as e:
            return cast(UrlResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Unexpected error generating wheel URL: {e}")
            return cast(UrlResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

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

    async def search_packages(self, query: str, page: int = 1) -> SearchResult:
        """Search for packages on PyPI."""
        query_encoded = quote_plus(query)
        url = f"https://pypi.org/search/?q={query_encoded}&page={page}"

        try:
            data = await self.http.fetch(url)

            # Check for error in result
            if isinstance(data, dict) and "error" in data:
                return cast(SearchResult, data)

            # Process the raw_data if in the new format
            html_content = None
            if isinstance(data, dict) and "raw_data" in data:
                raw_data = data["raw_data"]

                if isinstance(raw_data, bytes):
                    html_content = raw_data.decode("utf-8", errors="ignore")
                elif isinstance(raw_data, str):
                    html_content = raw_data
                else:
                    return {
                        "results": [],
                        "error": {
                            "code": ErrorCode.PARSE_ERROR,
                            "message": f"Unexpected data type: {type(raw_data)}",
                        },
                    }
            elif isinstance(data, (str, bytes)):
                # Legacy format
                if isinstance(data, bytes):
                    html_content = data.decode("utf-8", errors="ignore")
                else:
                    html_content = data
            else:
                return {
                    "results": [],
                    "error": {
                        "code": ErrorCode.PARSE_ERROR,
                        "message": f"Unexpected data type: {type(data)}",
                    },
                }

            # Handle case when we receive a Client Challenge page instead of search results
            if "Client Challenge" in html_content:
                logger.warning(
                    "Received a security challenge page from PyPI instead of search results"
                )
                return {
                    "search_url": url,
                    "message": "PyPI returned a security challenge page. Try using a web browser to search PyPI directly.",
                    "results": [],
                }

            # Check if BeautifulSoup is available for better parsing
            if self._has_bs4:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(html_content, "html.parser")
                results = []

                # Extract packages from search results
                for package in soup.select(".package-snippet"):
                    name_elem = package.select_one(".package-snippet__name")
                    version_elem = package.select_one(".package-snippet__version")
                    desc_elem = package.select_one(".package-snippet__description")

                    if name_elem and version_elem:
                        name = name_elem.text.strip()
                        version = version_elem.text.strip()
                        description = desc_elem.text.strip() if desc_elem else ""

                        results.append(
                            {
                                "name": name,
                                "version": version,
                                "description": description,
                                "url": f"https://pypi.org/project/{name}/",
                            }
                        )

                # Check if we found any results
                if results:
                    return {"search_url": url, "results": results}
                else:
                    # We have BeautifulSoup but couldn't find any packages
                    # This could be a format change or we're not getting the expected HTML
                    return {
                        "search_url": url,
                        "message": "No packages found or PyPI search page format has changed",
                        "results": [],
                    }

            # Fallback if BeautifulSoup is not available
            return {
                "search_url": url,
                "message": "For better search results, install Beautiful Soup: pip install beautifulsoup4",
                "results": [],  # Return empty results rather than raw HTML
            }
        except Exception as e:
            logger.exception(f"Error searching packages: {e}")
            return {
                "results": [],
                "error": {"code": ErrorCode.UNKNOWN_ERROR, "message": str(e)},
            }

    async def compare_versions(
        self, package_name: str, version1: str, version2: str
    ) -> VersionComparisonResult:
        """Compare two version numbers of a package."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            sanitized_v1 = sanitize_version(version1)
            sanitized_v2 = sanitize_version(version2)

            # Use packaging.version for reliable comparison
            v1 = Version(sanitized_v1)
            v2 = Version(sanitized_v2)

            return {
                "version1": sanitized_v1,
                "version2": sanitized_v2,
                "is_version1_greater": v1 > v2,
                "is_version2_greater": v2 > v1,
                "are_equal": v1 == v2,
            }
        except ValueError as e:
            return cast(
                VersionComparisonResult, format_error(ErrorCode.INVALID_INPUT, str(e))
            )
        except Exception as e:
            logger.exception(f"Error comparing versions: {e}")
            return cast(
                VersionComparisonResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e))
            )

    async def get_dependencies(
        self, package_name: str, version: Optional[str] = None
    ) -> DependenciesResult:
        """Get the dependencies for a package."""
        try:
            sanitized_name = sanitize_package_name(package_name)

            if version:
                sanitized_version = sanitize_version(version)
                url = f"https://pypi.org/pypi/{sanitized_name}/{sanitized_version}/json"
            else:
                url = f"https://pypi.org/pypi/{sanitized_name}/json"

            result = await self.http.fetch(url)

            # Check for error in result
            if isinstance(result, dict) and "error" in result:
                return cast(DependenciesResult, result)

            # Handle the new format where raw data might be returned
            if isinstance(result, dict) and "raw_data" in result:
                content_type = result.get("content_type", "")
                raw_data = result["raw_data"]

                # If we got JSON content, parse it
                if "application/json" in content_type and isinstance(raw_data, str):
                    try:
                        parsed_data = json.loads(raw_data)
                        parsed_result = parsed_data
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding JSON from raw_data: {e}")
                        return cast(
                            DependenciesResult,
                            format_error(
                                ErrorCode.PARSE_ERROR, f"Invalid JSON response: {e}"
                            ),
                        )
                else:
                    logger.warning(f"Received non-JSON content: {content_type}")
                    return cast(
                        DependenciesResult,
                        format_error(
                            ErrorCode.PARSE_ERROR,
                            f"Unexpected content type: {content_type}",
                        ),
                    )
            else:
                # Already parsed JSON data
                parsed_result = result

            requires_dist = parsed_result["info"].get("requires_dist", []) or []
            dependencies = []

            # Parse using packaging.requirements for better accuracy
            for req_str in requires_dist:
                try:
                    req = Requirement(req_str)
                    dep = {
                        "name": req.name,
                        "version_spec": str(req.specifier) if req.specifier else "",
                        "extras": list(req.extras) if req.extras else [],
                        "marker": str(req.marker) if req.marker else None,
                    }
                    dependencies.append(dep)
                except Exception as e:
                    logger.warning(f"Couldn't parse requirement '{req_str}': {e}")
                    # Add a simplified entry for unparseable requirements
                    if ":" in req_str:
                        name = req_str.split(":")[0].strip()
                    elif ";" in req_str:
                        name = req_str.split(";")[0].strip()
                    else:
                        name = req_str.split()[0].strip()

                    dependencies.append(
                        {
                            "name": name,
                            "version_spec": "",
                            "extras": [],
                            "marker": "Parse error",
                        }
                    )

            return {"dependencies": dependencies}
        except ValueError as e:
            return cast(
                DependenciesResult, format_error(ErrorCode.INVALID_INPUT, str(e))
            )
        except Exception as e:
            logger.exception(f"Error getting dependencies: {e}")
            return cast(
                DependenciesResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e))
            )

    async def check_package_exists(self, package_name: str) -> ExistsResult:
        """Check if a package exists on PyPI."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            url = f"https://pypi.org/pypi/{sanitized_name}/json"

            result = await self.http.fetch(url)

            # Check for error in result
            if isinstance(result, dict) and "error" in result:
                if result["error"]["code"] == ErrorCode.NOT_FOUND:
                    return {"exists": False}
                return cast(ExistsResult, result)

            # If we got a raw_data response, parse it if needed
            if isinstance(result, dict) and "raw_data" in result:
                # Simply the fact that we got a response means the package exists
                return {"exists": True}

            return {"exists": True}
        except ValueError as e:
            return cast(ExistsResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Error checking if package exists: {e}")
            return cast(ExistsResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

    async def get_package_metadata(
        self, package_name: str, version: Optional[str] = None
    ) -> MetadataResult:
        """Get detailed metadata for a package."""
        try:
            sanitized_name = sanitize_package_name(package_name)

            if version:
                sanitized_version = sanitize_version(version)
                url = f"https://pypi.org/pypi/{sanitized_name}/{sanitized_version}/json"
            else:
                url = f"https://pypi.org/pypi/{sanitized_name}/json"

            result = await self.http.fetch(url)

            # Check for error in result
            if isinstance(result, dict) and "error" in result:
                return cast(MetadataResult, result)

            # Handle the new format where raw data might be returned
            if isinstance(result, dict) and "raw_data" in result:
                content_type = result.get("content_type", "")
                raw_data = result["raw_data"]

                # If we got JSON content, parse it
                if "application/json" in content_type and isinstance(raw_data, str):
                    try:
                        parsed_data = json.loads(raw_data)
                        info = parsed_data.get("info", {})
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding JSON from raw_data: {e}")
                        return cast(
                            MetadataResult,
                            format_error(
                                ErrorCode.PARSE_ERROR, f"Invalid JSON response: {e}"
                            ),
                        )
                else:
                    logger.warning(f"Received non-JSON content: {content_type}")
                    return cast(
                        MetadataResult,
                        format_error(
                            ErrorCode.PARSE_ERROR,
                            f"Unexpected content type: {content_type}",
                        ),
                    )
            else:
                # Already parsed JSON data
                info = result.get("info", {})

            metadata: PackageMetadata = {
                "name": info.get("name", ""),
                "version": info.get("version", ""),
                "summary": info.get("summary", ""),
                "description": info.get("description", ""),
                "author": info.get("author", ""),
                "author_email": info.get("author_email", ""),
                "license": info.get("license", ""),
                "project_url": info.get("project_url", ""),
                "homepage": info.get("home_page", ""),
                "requires_python": info.get("requires_python", ""),
                "classifiers": info.get("classifiers", []),
                "keywords": (
                    info.get("keywords", "").split(",") if info.get("keywords") else []
                ),
            }

            return {"metadata": metadata}
        except ValueError as e:
            return cast(MetadataResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Error getting package metadata: {e}")
            return cast(MetadataResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

    async def get_package_stats(
        self, package_name: str, version: Optional[str] = None
    ) -> StatsResult:
        """Get download statistics for a package."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            sanitized_version = sanitize_version(version) if version else None

            # Check if package exists first
            exists_result = await self.check_package_exists(sanitized_name)
            if isinstance(exists_result, dict) and "error" in exists_result:
                return cast(StatsResult, exists_result)

            if not exists_result.get("exists", False):
                return cast(
                    StatsResult,
                    format_error(
                        ErrorCode.NOT_FOUND, f"Package '{sanitized_name}' not found"
                    ),
                )

            # Use the stats service to get real download stats
            return await self.stats.get_package_stats(sanitized_name, sanitized_version)

        except ValueError as e:
            return cast(StatsResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Error getting package stats: {e}")
            return cast(StatsResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

    async def get_dependency_tree(
        self, package_name: str, version: Optional[str] = None, depth: int = 3
    ) -> DependencyTreeResult:
        """Get the dependency tree for a package."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            if version:
                sanitized_version = sanitize_version(version)
            else:
                # Get latest version if not specified
                version_info = await self.get_latest_version(sanitized_name)
                if isinstance(version_info, dict) and "error" in version_info:
                    return cast(DependencyTreeResult, version_info)
                sanitized_version = version_info["version"]

            # Use iterative approach to avoid stack overflows with deep trees
            # Track visited packages to avoid cycles
            visited: Dict[str, Optional[str]] = {}
            flat_list: List[str] = []

            # Build dependency tree iteratively
            async def build_tree() -> TreeNode:
                queue: List[Tuple[str, Optional[str], int, Optional[str]]] = [
                    (sanitized_name, sanitized_version, 0, None)
                ]
                nodes: Dict[str, TreeNode] = {}

                # Root node
                root: TreeNode = {
                    "name": sanitized_name,
                    "version": sanitized_version,
                    "dependencies": [],
                }
                nodes[f"{sanitized_name}:{sanitized_version}"] = root

                while queue:
                    pkg_name, pkg_version, level, parent_key = queue.pop(0)

                    # Skip if too deep
                    if level > depth:
                        continue

                    # Generate a unique key for this package+version
                    pkg_key = f"{pkg_name}:{pkg_version}"

                    # Check for cycles
                    if pkg_key in visited:
                        if parent_key:
                            parent = nodes.get(parent_key)
                            if parent:
                                node: TreeNode = {
                                    "name": pkg_name,
                                    "version": pkg_version,
                                    "dependencies": [],
                                    "cycle": True,
                                }
                                parent["dependencies"].append(node)
                        continue

                    # Mark as visited
                    visited[pkg_key] = pkg_version

                    # Add to flat list
                    display_version = f" ({pkg_version})" if pkg_version else ""
                    flat_list.append(f"{pkg_name}{display_version}")

                    # Create node if not exists
                    if pkg_key not in nodes:
                        nodes[pkg_key] = {
                            "name": pkg_name,
                            "version": pkg_version,
                            "dependencies": [],
                        }

                    # Connect to parent
                    if parent_key and parent_key in nodes:
                        parent = nodes[parent_key]
                        if nodes[pkg_key] not in parent["dependencies"]:
                            parent["dependencies"].append(nodes[pkg_key])

                    # Get dependencies if not at max depth
                    if level < depth:
                        deps_result = await self.get_dependencies(pkg_name, pkg_version)

                        if isinstance(deps_result, dict) and "error" in deps_result:
                            # Skip this dependency if there was an error
                            continue

                        if "dependencies" in deps_result:
                            for dep in deps_result["dependencies"]:
                                # Extract the package name without version specifiers
                                dep_name = dep["name"]

                                # Get the version for this dependency
                                dep_version_info = await self.get_latest_version(
                                    dep_name
                                )
                                dep_version = (
                                    dep_version_info.get("version")
                                    if "error" not in dep_version_info
                                    else None
                                )

                                # Add to queue
                                queue.append(
                                    (dep_name, dep_version, level + 1, pkg_key)
                                )

                return root

            # Build the tree
            tree = await build_tree()

            # Generate visualization if Plotly is available
            visualization_url = None
            if self._has_plotly:
                try:
                    import plotly.graph_objects as go
                    import plotly.io as pio

                    # Create a simple tree visualization
                    labels = [f"{node.split(' ')[0]}" for node in flat_list]
                    parents = [""] + ["Root"] * (len(flat_list) - 1)

                    fig = go.Figure(
                        go.Treemap(
                            labels=labels, parents=parents, root_color="lightgrey"
                        )
                    )

                    fig.update_layout(
                        title=f"Dependency Tree for {sanitized_name} {sanitized_version}",
                        margin=dict(t=50, l=25, r=25, b=25),
                    )

                    # Save to temp file
                    viz_file = os.path.join(
                        self.config.cache_dir,
                        f"deptree_{sanitized_name}_{sanitized_version}.html",
                    )
                    pio.write_html(fig, viz_file)
                    visualization_url = f"file://{viz_file}"
                except Exception as e:
                    logger.warning(f"Failed to generate visualization: {e}")

            result: DependencyTreeResult = {"tree": tree, "flat_list": flat_list}

            if visualization_url:
                result["visualization_url"] = visualization_url

            return result
        except ValueError as e:
            return cast(
                DependencyTreeResult, format_error(ErrorCode.INVALID_INPUT, str(e))
            )
        except Exception as e:
            logger.exception(f"Error getting dependency tree: {e}")
            return cast(
                DependencyTreeResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e))
            )

    async def get_documentation_url(
        self, package_name: str, version: Optional[str] = None
    ) -> DocumentationResult:
        """Get documentation URL for a package."""
        try:
            sanitized_name = sanitize_package_name(package_name)

            # Get package info
            info = await self.get_package_info(sanitized_name)

            if "error" in info:
                return cast(DocumentationResult, info)

            metadata = info["info"]

            # Look for documentation URL
            docs_url = None

            # Check project_urls first
            project_urls = metadata.get("project_urls", {}) or {}

            # Search for documentation keywords in project_urls
            for key, url in project_urls.items():
                if not key or not url:
                    continue

                if any(
                    term in key.lower()
                    for term in ["doc", "documentation", "docs", "readthedocs", "rtd"]
                ):
                    docs_url = url
                    break

            # If not found, try home page or common doc sites
            if not docs_url:
                docs_url = metadata.get("documentation_url") or metadata.get("docs_url")

            if not docs_url:
                docs_url = metadata.get("home_page")

            if not docs_url:
                # Try common documentation sites
                docs_url = f"https://readthedocs.org/projects/{sanitized_name}/"

            # Get summary
            summary = metadata.get("summary", "No summary available")

            return {"docs_url": docs_url or "Not available", "summary": summary}
        except ValueError as e:
            return cast(
                DocumentationResult, format_error(ErrorCode.INVALID_INPUT, str(e))
            )
        except Exception as e:
            logger.exception(f"Error getting documentation URL: {e}")
            return cast(
                DocumentationResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e))
            )

    async def check_requirements_file(
        self, file_path: str
    ) -> PackageRequirementsResult:
        """Check a requirements file for outdated packages."""
        try:
            # Validate file path for security
            path = Path(file_path).resolve()

            # Check if file exists
            if not path.exists():
                return cast(
                    PackageRequirementsResult,
                    format_error(ErrorCode.FILE_ERROR, f"File not found: {file_path}"),
                )

            # Check file extension
            if path.name.endswith((".toml")):
                return await self._check_pyproject_toml(path)
            elif path.name.endswith((".txt", ".pip")):
                return await self._check_requirements_txt(path)
            else:
                return cast(
                    PackageRequirementsResult,
                    format_error(
                        ErrorCode.INVALID_INPUT,
                        f"File must be a .txt, .pip, or .toml file: {file_path}",
                    ),
                )
        except Exception as e:
            logger.exception(f"Error checking requirements file: {e}")
            return cast(
                PackageRequirementsResult,
                format_error(
                    ErrorCode.UNKNOWN_ERROR,
                    f"Error checking requirements file: {str(e)}",
                ),
            )

    async def _check_requirements_txt(self, path: Path) -> PackageRequirementsResult:
        """Check a requirements.txt file for outdated packages."""
        try:
            # Read file
            try:
                with path.open("r") as f:
                    requirements = f.readlines()
            except PermissionError:
                return cast(
                    PackageRequirementsResult,
                    format_error(
                        ErrorCode.PERMISSION_ERROR,
                        f"Permission denied when reading file: {str(path)}",
                    ),
                )
            except Exception as e:
                return cast(
                    PackageRequirementsResult,
                    format_error(ErrorCode.FILE_ERROR, f"Error reading file: {str(e)}"),
                )

            outdated: List[PackageRequirement] = []
            up_to_date: List[PackageRequirement] = []

            for req_line in requirements:
                req_line = req_line.strip()
                if not req_line or req_line.startswith("#"):
                    continue

                # Remove inline comments before parsing
                if "#" in req_line:
                    req_line = req_line.split("#", 1)[0].strip()

                # Parse requirement
                try:
                    # Use packaging.requirements for accurate parsing
                    req = Requirement(req_line)
                    pkg_name = req.name

                    # Get latest version
                    latest_version_info = await self.get_latest_version(pkg_name)

                    if "error" in latest_version_info:
                        # Skip packages we can't find
                        continue

                    latest_version = latest_version_info["version"]

                    # Compare versions
                    latest_ver = Version(latest_version)

                    # Check if up to date
                    is_outdated = False
                    current_version = None
                    security_recommendation = None

                    if req.specifier:
                        # Extract the version from the specifier
                        for spec in req.specifier:  # type: ignore[assignment]
                            if spec.operator in ("==", "==="):
                                current_version = str(spec.version)
                                req_ver = Version(current_version)
                                is_outdated = latest_ver > req_ver
                            elif spec.operator == ">=":
                                # For >= constraints, check if minimum version has vulnerabilities
                                min_version = str(spec.version)
                                current_version = f"{spec.operator}{spec.version}"

                                # Check vulnerabilities for minimum allowed version
                                vuln_check = await self.check_vulnerabilities(
                                    pkg_name, min_version
                                )

                                if vuln_check.get("vulnerable", False):
                                    # Find the earliest safe version
                                    safe_version = (
                                        await self._find_earliest_safe_version(
                                            pkg_name, min_version, latest_version
                                        )
                                    )

                                    if safe_version and safe_version != min_version:
                                        is_outdated = True
                                        security_recommendation = (
                                            f"Security: Update constraint to >={safe_version} "
                                            f"(current allows vulnerable {min_version})"
                                        )
                            else:
                                # For other operators (>, <=, <, ~=), still capture the constraint
                                # but don't mark as outdated
                                if (
                                    not current_version
                                ):  # Only take the first constraint if multiple
                                    current_version = f"{spec.operator}{spec.version}"

                    # If no version info could be determined, set to latest
                    if not current_version:
                        current_version = "unspecified (latest)"

                    pkg_info = {
                        "package": pkg_name,
                        "current_version": current_version,
                        "latest_version": latest_version,
                        "constraint": str(req.specifier),
                    }

                    if security_recommendation:
                        pkg_info["recommendation"] = security_recommendation

                    if is_outdated:
                        outdated.append(pkg_info)
                    else:
                        up_to_date.append(pkg_info)
                except Exception as e:
                    logger.warning(f"Error parsing requirement '{req_line}': {e}")
                    # Try a simple extraction for unparseable requirements
                    try:
                        # Extract package name using regex
                        import re

                        match = re.match(
                            r"^([a-zA-Z0-9_.-]+)(?:[<>=~!]=?|@)(.+)?", req_line
                        )

                        if match:
                            pkg_name = match.group(1)
                            version_spec = (
                                match.group(2).strip() if match.group(2) else None
                            )

                            # Get latest version
                            latest_version_info = await self.get_latest_version(
                                pkg_name
                            )

                            if "error" not in latest_version_info:
                                latest_version = latest_version_info["version"]

                                if version_spec:
                                    # Add as potentially outdated
                                    outdated.append(
                                        {
                                            "package": pkg_name,
                                            "current_version": version_spec,
                                            "latest_version": latest_version,
                                            "constraint": version_spec,
                                        }
                                    )
                                else:
                                    # No specific version required
                                    up_to_date.append(
                                        {
                                            "package": pkg_name,
                                            "current_version": "unspecified (latest)",
                                            "latest_version": latest_version,
                                            "constraint": "",
                                        }
                                    )
                        else:
                            # Raw package name without version specifier
                            pkg_name = req_line

                            # Get latest version
                            latest_version_info = await self.get_latest_version(
                                pkg_name
                            )

                            if "error" not in latest_version_info:
                                latest_version = latest_version_info["version"]
                                up_to_date.append(
                                    {
                                        "package": pkg_name,
                                        "current_version": "unspecified (latest)",
                                        "latest_version": latest_version,
                                        "constraint": "",
                                    }
                                )
                    except Exception:
                        # Skip lines we can't parse at all
                        continue

            # Check if other dependency files exist in the same directory
            from pathlib import Path
            req_path = Path(str(path))
            project_dir = req_path.parent
            
            other_dep_files = []
            for pattern in ["pyproject.toml", "setup.py", "setup.cfg", "Pipfile"]:
                if (project_dir / pattern).exists() and pattern != req_path.name:
                    other_dep_files.append(str(project_dir / pattern))
            
            result = {"outdated": outdated, "up_to_date": up_to_date}
            
            # Add actionable next steps if vulnerabilities found
            if outdated and any("recommendation" in pkg for pkg in outdated):
                result["action_required"] = True
                
                # Check if pyproject.toml exists (it's the primary source)
                has_pyproject = any("pyproject.toml" in f for f in other_dep_files)
                
                if has_pyproject:
                    # requirements.txt is secondary - suggest updating pyproject.toml first
                    result["next_steps"] = [
                        "CHECK pyproject.toml FIRST - it's the primary dependency source",
                        "UPDATE pyproject.toml with the recommended secure versions",
                        "THEN update this requirements.txt to match pyproject.toml",
                        f"VERIFY consistency with other files: {', '.join(f for f in other_dep_files if 'pyproject.toml' not in f)}" if any(f for f in other_dep_files if 'pyproject.toml' not in f) else None,
                        "COMMIT changes with message: 'chore: Update dependencies for security (all files)'"
                    ]
                else:
                    # No pyproject.toml - requirements.txt is primary
                    result["next_steps"] = [
                        "UPDATE this file with the recommended secure versions",
                        f"CHECK other dependency files for consistency: {', '.join(other_dep_files)}" if other_dep_files else None,
                        "COMMIT changes with message mentioning all updated files"
                    ]
                
                result["next_steps"] = [step for step in result["next_steps"] if step]
                
            return result
        except Exception as e:
            logger.exception(f"Error checking requirements.txt file: {e}")
            return cast(
                PackageRequirementsResult,
                format_error(
                    ErrorCode.UNKNOWN_ERROR,
                    f"Error checking requirements file: {str(e)}",
                ),
            )

    def _extract_dependencies_from_pyproject(
        self, pyproject_data: Dict[str, Any]
    ) -> List[str]:
        """Extract dependencies from various pyproject.toml formats.

        Args:
            pyproject_data: Parsed pyproject.toml data

        Returns:
            List of dependency strings
        """
        dependencies = []

        # 1. PEP 621 format - project.dependencies
        if "project" in pyproject_data and "dependencies" in pyproject_data["project"]:
            dependencies.extend(pyproject_data["project"]["dependencies"])

        # 2. Poetry format - tool.poetry.dependencies
        if "tool" in pyproject_data and "poetry" in pyproject_data["tool"]:
            if "dependencies" in pyproject_data["tool"]["poetry"]:
                poetry_deps = pyproject_data["tool"]["poetry"]["dependencies"]
                for name, constraint in poetry_deps.items():
                    if name == "python":  # Skip python dependency
                        continue
                    if isinstance(constraint, str):
                        dependencies.append(f"{name}{constraint}")
                    elif isinstance(constraint, dict) and "version" in constraint:
                        dependencies.append(f"{name}{constraint['version']}")

        # 3. PDM format - tool.pdm.dependencies
        if "tool" in pyproject_data and "pdm" in pyproject_data["tool"]:
            if "dependencies" in pyproject_data["tool"]["pdm"]:
                pdm_deps = pyproject_data["tool"]["pdm"]["dependencies"]
                for name, constraint in pdm_deps.items():
                    if isinstance(constraint, str):
                        dependencies.append(f"{name}{constraint}")
                    elif isinstance(constraint, dict) and "version" in constraint:
                        dependencies.append(f"{name}{constraint['version']}")

        # 4. Flit format - tool.flit.metadata.requires
        if "tool" in pyproject_data and "flit" in pyproject_data["tool"]:
            if (
                "metadata" in pyproject_data["tool"]["flit"]
                and "requires" in pyproject_data["tool"]["flit"]["metadata"]
            ):
                dependencies.extend(
                    pyproject_data["tool"]["flit"]["metadata"]["requires"]
                )

        return dependencies

    def _load_toml_module(self):
        """Load the appropriate TOML parsing module.

        Returns:
            The tomllib or tomli module, or None if not available
        """
        try:
            import tomllib

            return tomllib
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore[import-not-found]

                return tomllib
            except ImportError:
                return None

    async def _check_pyproject_toml(self, path: Path) -> PackageRequirementsResult:
        """Check a pyproject.toml file for outdated packages."""
        # Load TOML module
        tomllib = self._load_toml_module()
        if not tomllib:
            return cast(
                PackageRequirementsResult,
                format_error(
                    ErrorCode.MISSING_DEPENDENCY,
                    "Parsing pyproject.toml requires tomli package. Please install with: pip install tomli",
                ),
            )

        # Read and parse the TOML file
        try:
            with path.open("rb") as f:
                pyproject_data = tomllib.load(f)
        except PermissionError:
            return cast(
                PackageRequirementsResult,
                format_error(
                    ErrorCode.PERMISSION_ERROR,
                    f"Permission denied when reading file: {str(path)}",
                ),
            )
        except Exception as e:
            return cast(
                PackageRequirementsResult,
                format_error(
                    ErrorCode.FILE_ERROR, f"Error reading TOML file: {str(e)}"
                ),
            )

        # Extract dependencies using helper method
        dependencies = self._extract_dependencies_from_pyproject(pyproject_data)

        # Process dependencies
        outdated = []
        up_to_date = []

        for req_str in dependencies:
            try:
                req = Requirement(req_str)
                package_name = sanitize_package_name(req.name)

                # Get package info from PyPI
                info_result = await self.get_latest_version(package_name)

                # Check if we got a valid result
                if "error" in info_result:
                    logger.warning(
                        f"Could not get latest version for {package_name}: {info_result['error']['message']}"
                    )
                    continue

                latest_version = info_result.get("version", "")
                if not latest_version:
                    logger.warning(f"No version information found for {package_name}")
                    continue

                # Get current version from requirement specifier
                current_version = ""
                is_outdated = False

                # Handle different types of version specifiers
                if req.specifier:
                    for spec in req.specifier:
                        if spec.operator in ("==", "==="):
                            # Exact version match
                            current_version = str(spec.version)

                            # Check if outdated
                            try:
                                current_ver = Version(current_version)
                                latest_ver = Version(latest_version)
                                is_outdated = latest_ver > current_ver
                            except Exception as e:
                                logger.warning(
                                    f"Error comparing versions for {package_name}: {e}"
                                )
                                continue
                        else:
                            # For other operators (>=, >, etc.) use as constraint but don't mark as outdated
                            if not current_version:
                                current_version = f"{spec.operator}{spec.version}"

                # If no version info could be determined, set to latest
                if not current_version:
                    current_version = "unspecified (latest)"

                # Add to appropriate list
                pkg_info = {
                    "package": req.name,
                    "current_version": current_version,
                    "latest_version": latest_version,
                    "constraint": str(req.specifier),
                }

                if security_recommendation:
                    pkg_info["recommendation"] = security_recommendation

                if is_outdated:
                    outdated.append(pkg_info)
                else:
                    up_to_date.append(pkg_info)

            except Exception as e:
                logger.warning(f"Error processing dependency {req_str}: {e}")
                continue

        # Check if other dependency files exist in the same directory
        from pathlib import Path
        toml_path = Path(str(path))
        project_dir = toml_path.parent
        
        other_dep_files = []
        for pattern in ["requirements.txt", "requirements-*.txt", "setup.py", "setup.cfg", "Pipfile"]:
            if pattern.startswith("requirements-"):
                # Handle wildcard pattern
                for req_file in project_dir.glob(pattern):
                    if req_file.exists() and req_file.name != toml_path.name:
                        other_dep_files.append(str(req_file))
            else:
                if (project_dir / pattern).exists() and pattern != toml_path.name:
                    other_dep_files.append(str(project_dir / pattern))
        
        result = {"outdated": outdated, "up_to_date": up_to_date}
        
        # Add actionable next steps if vulnerabilities found
        if outdated and any("recommendation" in pkg for pkg in outdated):
            result["action_required"] = True
            result["file_priority"] = "PRIMARY - This is the modern Python standard"
            
            # pyproject.toml is primary - changes should trickle down
            result["next_steps"] = [
                "UPDATE this pyproject.toml FIRST with the recommended secure versions",
                f"TRICKLE DOWN changes to secondary files: {', '.join(other_dep_files)}" if other_dep_files else None,
                "ENSURE all files have IDENTICAL version constraints",
                "REGENERATE requirements.txt if using pip-tools: pip-compile pyproject.toml",
                "COMMIT changes with message: 'chore: Update dependencies for security (all files)'"
            ]
            result["next_steps"] = [step for step in result["next_steps"] if step]
            
        return result

    async def get_releases_feed(self) -> ReleasesFeed:
        """Get recent releases feed from PyPI RSS."""
        try:
            # PyPI RSS feed for recent releases
            url = "https://pypi.org/rss/updates.xml"
            # For now, return empty feed as PyPI RSS parsing is not implemented
            return {
                "releases": [],
                "error": {
                    "message": "RSS feed parsing not implemented",
                    "code": "not_implemented",
                },
            }
        except Exception as e:
            logger.exception(f"Error getting releases feed: {e}")
            return {"releases": [], "error": {"message": str(e), "code": "feed_error"}}

    async def get_packages_feed(self) -> PackagesFeed:
        """Get new packages feed from PyPI RSS."""
        try:
            # PyPI RSS feed for new packages
            url = "https://pypi.org/rss/packages.xml"
            # For now, return empty feed as PyPI RSS parsing is not implemented
            return {
                "packages": [],
                "error": {
                    "message": "RSS feed parsing not implemented",
                    "code": "not_implemented",
                },
            }
        except Exception as e:
            logger.exception(f"Error getting packages feed: {e}")
            return {"packages": [], "error": {"message": str(e), "code": "feed_error"}}

    async def check_vulnerabilities(
        self, package_name: str, version: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check for vulnerabilities in a package using the OSV (Open Source Vulnerabilities) API.

        Args:
            package_name: Name of the package to check
            version: Specific version to check (optional, checks all versions if not provided)

        Returns:
            Dictionary containing vulnerability information including CVEs, severity, and fixes
        """
        try:
            # First check if the package exists
            exists_result = await self.check_package_exists(package_name)
            if not exists_result.get("exists", False):
                return cast(
                    Dict[str, Any],
                    format_error(
                        ErrorCode.NOT_FOUND, f"Package {package_name} not found on PyPI"
                    ),
                )

            sanitized_name = sanitize_package_name(package_name)

            # Create cache key for vulnerability data
            # Cache based on package + version (or "all" for all versions)
            cache_key = f"osv:vulnerabilities:{sanitized_name}:{version or 'all'}"

            # Check cache first (vulnerability data changes slowly)
            cached_result = await self.cache.get(cache_key)
            if cached_result:
                logger.debug(f"Cache hit for vulnerability check: {cache_key}")
                return cached_result

            osv_url = "https://api.osv.dev/v1/query"

            # Build the query payload
            payload = {"package": {"name": sanitized_name, "ecosystem": "PyPI"}}

            if version:
                payload["package"]["version"] = sanitize_version(version)

            # Make the API request to OSV
            logger.info(
                f"Checking vulnerabilities for {sanitized_name} {version or 'all versions'}"
            )

            # OSV API expects POST with JSON payload
            response = await self.http.fetch(
                osv_url,
                method="POST",
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload).encode(),
            )

            # Check for errors in response
            if "error" in response:
                logger.error(f"OSV API error: {response['error']}")
                return {
                    "package": package_name,
                    "version": version or "all",
                    "vulnerabilities": [],
                    "error": response["error"],
                }

            # Parse vulnerabilities from response
            vulnerabilities = []
            osv_vulns = response.get("vulns", [])

            for vuln in osv_vulns:
                # Extract affected versions
                affected_versions = []
                for affected in vuln.get("affected", []):
                    if affected.get("package", {}).get("ecosystem") == "PyPI":
                        if (
                            affected.get("package", {}).get("name", "").lower()
                            == sanitized_name.lower()
                        ):
                            for range_info in affected.get("ranges", []):
                                events = range_info.get("events", [])
                                for event in events:
                                    if "introduced" in event:
                                        affected_versions.append(
                                            f">={event['introduced']}"
                                        )
                                    if "fixed" in event:
                                        affected_versions.append(f"<{event['fixed']}")

                # Extract CVE IDs
                cve_ids = [
                    alias
                    for alias in vuln.get("aliases", [])
                    if alias.startswith("CVE-")
                ]

                # Extract severity information
                severity = None
                severity_score = None
                database_specific = vuln.get("database_specific", {})
                if "severity" in database_specific:
                    severity = database_specific["severity"]

                # Check for CVSS scores in different formats
                for detail in vuln.get("severity", []):
                    if detail.get("type") == "CVSS_V3":
                        severity_score = detail.get("score")
                        break

                vulnerability = {
                    "id": vuln.get("id", ""),
                    "summary": vuln.get(
                        "summary", vuln.get("details", "No description available")
                    ),
                    "severity": severity,
                    "severity_score": severity_score,
                    "cve": cve_ids,
                    "affected_versions": affected_versions,
                    "published": vuln.get("published", ""),
                    "modified": vuln.get("modified", ""),
                    "references": [
                        ref.get("url", "") for ref in vuln.get("references", [])
                    ],
                }

                # If a specific version was requested, only include if it's affected
                if version:
                    # Check if this version is affected
                    version_obj = Version(version)
                    is_affected = False

                    for affected in vuln.get("affected", []):
                        if affected.get("package", {}).get("ecosystem") == "PyPI":
                            if (
                                affected.get("package", {}).get("name", "").lower()
                                == sanitized_name.lower()
                            ):
                                for range_info in affected.get("ranges", []):
                                    events = range_info.get("events", [])
                                    introduced = None
                                    fixed = None

                                    for event in events:
                                        if "introduced" in event:
                                            try:
                                                introduced = Version(
                                                    event["introduced"]
                                                )
                                            except:
                                                # Skip non-version strings (like git hashes)
                                                continue
                                        if "fixed" in event:
                                            try:
                                                fixed = Version(event["fixed"])
                                            except:
                                                # Skip non-version strings (like git hashes)
                                                continue

                                    # Check if version is in affected range
                                    if introduced and version_obj >= introduced:
                                        if fixed is None or version_obj < fixed:
                                            is_affected = True
                                            break

                    if is_affected:
                        vulnerabilities.append(vulnerability)
                else:
                    # No specific version requested, include all vulnerabilities
                    vulnerabilities.append(vulnerability)

            # Sort by severity (critical > high > medium > low)
            severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

            # Helper function to extract numeric score
            def get_numeric_score(score_value):
                if not score_value:
                    return 0
                if isinstance(score_value, (int, float)):
                    return float(score_value)
                # Handle CVSS strings like "CVSS:3.1/AV:N/AC:H/PR:N/UI:R/S:U/C:H/I:N/A:N"
                if isinstance(score_value, str) and "CVSS" in score_value:
                    return 0  # Complex CVSS strings need parsing, default to 0
                try:
                    return float(score_value)
                except:
                    return 0

            vulnerabilities.sort(
                key=lambda v: (
                    severity_order.get(str(v.get("severity", "")).upper(), 999),
                    -get_numeric_score(v.get("severity_score")),
                )
            )

            # Count vulnerabilities by severity
            critical_count = sum(
                1
                for v in vulnerabilities
                if str(v.get("severity", "")).upper() == "CRITICAL"
            )
            high_count = sum(
                1
                for v in vulnerabilities
                if str(v.get("severity", "")).upper() == "HIGH"
            )
            medium_count = sum(
                1
                for v in vulnerabilities
                if str(v.get("severity", "")).upper() == "MEDIUM"
            )
            low_count = sum(
                1
                for v in vulnerabilities
                if str(v.get("severity", "")).upper() == "LOW"
            )

            # Limit vulnerability details to avoid token limits
            # Only include essential fields for each vulnerability
            limited_vulnerabilities = []
            for vuln in vulnerabilities[:20]:  # Limit to 20 vulnerabilities max
                limited_vuln = {
                    "id": vuln.get("id"),
                    "summary": vuln.get("summary", "")[:500],  # Limit summary length
                    "severity": vuln.get("severity"),
                    "cve": vuln.get("cve", [])[:5],  # Limit CVE list
                    "affected_versions": vuln.get("affected_versions", [])[
                        :10
                    ],  # Limit versions
                }
                # Only include first 3 references to save space
                if "references" in vuln and vuln["references"]:
                    limited_vuln["references"] = vuln["references"][:3]
                limited_vulnerabilities.append(limited_vuln)

            result = {
                "package": package_name,
                "version": version or "all",
                "vulnerabilities": limited_vulnerabilities,
                "vulnerable": len(vulnerabilities) > 0,
                "total_vulnerabilities": len(vulnerabilities),
                "critical_count": critical_count,
                "high_count": high_count,
                "medium_count": medium_count,
                "low_count": low_count,
            }

            # Add note if vulnerabilities were truncated
            if len(vulnerabilities) > 20:
                result["note"] = (
                    f"Showing 20 of {len(vulnerabilities)} vulnerabilities. Use specific version parameter to reduce results."
                )

            # Cache the result with configurable TTL
            # Vulnerability data doesn't change frequently, default is 1 hour
            cache_ttl = self.config.vulnerability_cache_ttl
            await self.cache.set(cache_key, result, ttl=cache_ttl)
            logger.debug(
                f"Cached vulnerability data for {cache_key} with TTL {cache_ttl}s"
            )

            return result

        except Exception as e:
            logger.exception(f"Error checking vulnerabilities for {package_name}: {e}")
            return {
                "package": package_name,
                "version": version or "all",
                "vulnerabilities": [],
                "error": {"message": str(e), "code": "vulnerability_check_error"},
            }

    async def _find_earliest_safe_version(
        self, package_name: str, min_version: str, max_version: str
    ) -> Optional[str]:
        """Find the earliest version without vulnerabilities between min and max versions.

        For efficiency, this uses a simplified approach that checks common safe versions
        rather than checking every single version.

        Args:
            package_name: Name of the package
            min_version: Minimum version (potentially vulnerable)
            max_version: Maximum version to consider (usually latest)

        Returns:
            The earliest safe version string, or None if no safe version found
        """
        try:
            # For efficiency, we'll use a heuristic approach:
            # 1. Check if the latest version is safe (most common case)
            # 2. If not, get vulnerability info to find safe ranges

            # First check if latest version is safe
            latest_vuln_check = await self.check_vulnerabilities(
                package_name, max_version
            )
            if not latest_vuln_check.get("vulnerable", True):
                # Latest is safe, now find earliest safe version
                # For most packages, security fixes come in minor/patch releases
                # So we'll recommend a reasonable minimum based on the vulnerable version

                try:
                    min_ver = Version(min_version)
                    max_ver = Version(max_version)

                    # If major version changed, recommend at least the new major version
                    if max_ver.major > min_ver.major:
                        return f"{max_ver.major}.0.0"
                    # If minor version changed significantly (>5), recommend recent minor
                    elif max_ver.minor > min_ver.minor + 5:
                        return f"{max_ver.major}.{max_ver.minor - 2}.0"
                    # Otherwise recommend the latest as safest
                    else:
                        return max_version
                except Exception:
                    return max_version

            # If latest is also vulnerable, we need to check the specific vulnerabilities
            # For now, we'll just recommend the latest version as it likely has fewer issues
            return max_version

        except Exception as e:
            logger.warning(f"Error finding safe version for {package_name}: {e}")
            return None

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
                import defusedxml.ElementTree as ET

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
                import defusedxml.ElementTree as ET

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
                import defusedxml.ElementTree as ET

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

    async def get_package_changelog(
        self, package_name: str, version: Optional[str] = None
    ) -> str:
        """Get changelog for a package.

        This method attempts to retrieve changelog information from:
        1. Package metadata project_urls for changelog link
        2. GitHub releases if the package has a GitHub repository
        3. Common changelog file names in the package distribution

        Args:
            package_name: Name of the package
            version: Specific version (optional, defaults to latest)

        Returns:
            Changelog text or appropriate message
        """
        try:
            # Get package info to find changelog URL
            info_result = await self.get_package_info(package_name)
            if "error" in info_result:
                return f"Package {package_name} not found"

            info = info_result.get("info", {})
            project_urls = info.get("project_urls") or {}

            # Check for explicit changelog URL
            changelog_url = None
            for key, url in project_urls.items():
                if any(
                    term in key.lower()
                    for term in ["changelog", "changes", "history", "release"]
                ):
                    changelog_url = url
                    break

            # If we found a changelog URL, try to fetch it
            if changelog_url:
                # Handle GitHub releases specially
                if "github.com" in changelog_url and "/releases" in changelog_url:
                    # Extract owner and repo from GitHub URL
                    import re

                    match = re.search(r"github\.com/([^/]+)/([^/]+)", changelog_url)
                    if match:
                        owner, repo = match.groups()
                        # Use GitHub API to get releases
                        # Limit to 5 releases using GitHub API parameter
                        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=5"

                        try:
                            response = await self.http.fetch(api_url)
                            if isinstance(response, dict) and "error" not in response:
                                # GitHub API returns array directly
                                releases = (
                                    response if isinstance(response, list) else []
                                )
                            else:
                                releases = (
                                    response if isinstance(response, list) else []
                                )

                            if releases:
                                # Format releases into changelog
                                changelog_parts = [f"# Changelog for {package_name}\n"]

                                # Limit to 5 releases to avoid token limits
                                for i, release in enumerate(releases[:5]):
                                    tag = release.get("tag_name", "")
                                    name = release.get("name", "")
                                    body = release.get("body", "")
                                    published = release.get("published_at", "")

                                    if tag:
                                        changelog_parts.append(f"\n## {tag}")
                                        if name and name != tag:
                                            changelog_parts.append(f" - {name}")
                                        if published:
                                            changelog_parts.append(
                                                f"\n*Released: {published[:10]}*"
                                            )
                                        if body:
                                            # Truncate long bodies to avoid token limits
                                            max_body_length = 1000
                                            if len(body) > max_body_length:
                                                body = (
                                                    body[:max_body_length]
                                                    + "\n\n... (truncated)"
                                                )
                                            changelog_parts.append(f"\n{body}")

                                # Add note about limited releases
                                changelog_parts.append(
                                    f"\n\n---\n\n*Showing up to 5 most recent releases. Visit {changelog_url} for the complete changelog.*"
                                )

                                return "\n".join(changelog_parts)
                        except Exception as e:
                            logger.debug(f"Could not fetch GitHub releases: {e}")

                # Try to fetch as regular webpage
                try:
                    response = await self.http.fetch(changelog_url)
                    if isinstance(response, dict):
                        # If it's JSON, try to extract text
                        return str(response)
                    return f"Changelog available at: {changelog_url}"
                except Exception as e:
                    logger.debug(f"Could not fetch changelog URL: {e}")
                    return f"Changelog available at: {changelog_url}"

            # Check if there's a GitHub repo to check releases
            github_url = None
            for key, url in project_urls.items():
                if "github.com" in str(url) and not "/releases" in str(url):
                    github_url = url
                    break

            if (
                not github_url
                and info.get("home_page")
                and "github.com" in str(info.get("home_page"))
            ):
                github_url = info.get("home_page")

            if github_url:
                # Extract owner and repo
                import re

                match = re.search(r"github\.com/([^/]+)/([^/]+)", github_url)
                if match:
                    owner, repo = match.groups()
                    repo = repo.rstrip("/")  # Remove trailing slash if present

                    # Construct changelog URL
                    releases_url = f"https://github.com/{owner}/{repo}/releases"
                    return f"Changelog might be available at: {releases_url}"

            # If no changelog found, return a helpful message
            available_urls = "\n".join([f"- {k}: {v}" for k, v in project_urls.items()])
            if available_urls:
                return f"No explicit changelog found. Available project URLs:\n{available_urls}"
            else:
                return f"No changelog information available for {package_name}"

        except Exception as e:
            logger.error(f"Error getting changelog for {package_name}: {e}")
            return f"Error retrieving changelog: {str(e)}"
