"""
Core client for interacting with PyPI.
"""

import logging
import asyncio
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote_plus
from typing import Dict, List, Any, Optional, Tuple, Union, cast
import json
import datetime

from packaging.version import Version
from packaging.requirements import Requirement

from mcp_pypi.core.models import (
    PyPIClientConfig, PackageInfo, VersionInfo, ReleasesInfo,
    UrlsInfo, UrlResult, PackagesFeed, UpdatesFeed, ReleasesFeed,
    SearchResult, VersionComparisonResult, DependenciesResult,
    ExistsResult, MetadataResult, StatsResult, DependencyTreeResult,
    DocumentationResult, PackageRequirementsResult, TreeNode,
    ErrorCode, PackageRequirement, FeedItem, format_error
)
from mcp_pypi.core.cache import AsyncCacheManager
from mcp_pypi.core.http import AsyncHTTPClient
from mcp_pypi.core.stats import PackageStatsService
from mcp_pypi.utils.helpers import sanitize_package_name, sanitize_version

logger = logging.getLogger("mcp-pypi.client")

class PyPIClient:
    """Client for interacting with PyPI."""
    
    def __init__(
        self, 
        config: Optional[PyPIClientConfig] = None,
        cache_manager: Optional[AsyncCacheManager] = None,
        http_client: Optional[AsyncHTTPClient] = None,
        stats_service: Optional[PackageStatsService] = None
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
        self._has_bs4 = self._check_import('bs4', 'BeautifulSoup')
        self._has_plotly = self._check_import('plotly.graph_objects', 'go')
    
    def _check_import(self, module: str, name: str) -> bool:
        """Check if a module can be imported."""
        try:
            __import__(module)
            return True
        except ImportError:
            logger.info(f"Optional dependency {module} not found; some features will be limited")
            return False
    
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
                    return cast(PackageInfo, format_error(ErrorCode.PARSE_ERROR, "Received empty response"))
                
                # If we got JSON content, parse it
                if "application/json" in content_type and isinstance(raw_data, str):
                    try:
                        parsed_data = json.loads(raw_data)
                        return cast(PackageInfo, parsed_data)
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding JSON from raw_data: {e}")
                        return cast(PackageInfo, format_error(ErrorCode.PARSE_ERROR, f"Invalid JSON response: {e}"))
                else:
                    logger.warning(f"Received non-JSON content: {content_type}")
                    return cast(PackageInfo, format_error(ErrorCode.PARSE_ERROR, f"Unexpected content type: {content_type}"))
            
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
                        return cast(VersionInfo, format_error(ErrorCode.PARSE_ERROR, f"Invalid JSON response: {e}"))
                else:
                    logger.warning(f"Received non-JSON content: {content_type}")
                    return cast(VersionInfo, format_error(ErrorCode.PARSE_ERROR, f"Unexpected content type: {content_type}"))
            
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
                        return cast(ReleasesInfo, format_error(ErrorCode.PARSE_ERROR, f"Invalid JSON response: {e}"))
                else:
                    logger.warning(f"Received non-JSON content: {content_type}")
                    return cast(ReleasesInfo, format_error(ErrorCode.PARSE_ERROR, f"Unexpected content type: {content_type}"))
            
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
                        return cast(UrlsInfo, format_error(ErrorCode.PARSE_ERROR, f"Invalid JSON response: {e}"))
                else:
                    logger.warning(f"Received non-JSON content: {content_type}")
                    return cast(UrlsInfo, format_error(ErrorCode.PARSE_ERROR, f"Unexpected content type: {content_type}"))
            
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
        build_tag: Optional[str] = None
    ) -> UrlResult:
        """Generate a predictable wheel package URL."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            sanitized_version = sanitize_version(version)
            
            # Clean tags according to PEP 491
            wheel_parts = {
                "name": sanitized_name,
                "version": sanitized_version,
                "python_tag": python_tag.replace('.', '_'),
                "abi_tag": abi_tag.replace('.', '_'),
                "platform_tag": platform_tag.replace('.', '_'),
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
                    data_str = raw_data.decode('utf-8')
                elif isinstance(raw_data, str):
                    data_str = raw_data
                else:
                    return format_error(ErrorCode.PARSE_ERROR, f"Unexpected data type: {type(raw_data)}")
            elif isinstance(data, (str, bytes)):
                # Legacy format
                if isinstance(data, bytes):
                    data_str = data.decode('utf-8')
                else:
                    data_str = data
            else:
                return format_error(ErrorCode.PARSE_ERROR, f"Unexpected data type: {type(data)}")
            
            # Parse the XML string
            try:
                root = ET.fromstring(data_str)
                
                packages: List[FeedItem] = []
                for item in root.findall(".//item"):
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    desc_elem = item.find("description")
                    date_elem = item.find("pubDate")
                    
                    if all(elem is not None for elem in (title_elem, link_elem, desc_elem, date_elem)):
                        packages.append({
                            "title": title_elem.text or "",
                            "link": link_elem.text or "",
                            "description": desc_elem.text or "",
                            "published_date": date_elem.text or ""
                        })
                
                return {"packages": packages}
            except ET.ParseError as e:
                logger.error(f"XML parse error: {e}")
                return format_error(ErrorCode.PARSE_ERROR, f"Invalid XML response: {e}")
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
                    data_str = raw_data.decode('utf-8')
                elif isinstance(raw_data, str):
                    data_str = raw_data
                else:
                    return format_error(ErrorCode.PARSE_ERROR, f"Unexpected data type: {type(raw_data)}")
            elif isinstance(data, (str, bytes)):
                # Legacy format
                if isinstance(data, bytes):
                    data_str = data.decode('utf-8')
                else:
                    data_str = data
            else:
                return format_error(ErrorCode.PARSE_ERROR, f"Unexpected data type: {type(data)}")
            
            # Parse the XML string
            try:
                root = ET.fromstring(data_str)
                
                updates: List[FeedItem] = []
                for item in root.findall(".//item"):
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    desc_elem = item.find("description")
                    date_elem = item.find("pubDate")
                    
                    if all(elem is not None for elem in (title_elem, link_elem, desc_elem, date_elem)):
                        updates.append({
                            "title": title_elem.text or "",
                            "link": link_elem.text or "",
                            "description": desc_elem.text or "",
                            "published_date": date_elem.text or ""
                        })
                
                return {"updates": updates}
            except ET.ParseError as e:
                logger.error(f"XML parse error: {e}")
                return format_error(ErrorCode.PARSE_ERROR, f"Invalid XML response: {e}")
        except Exception as e:
            logger.exception(f"Error parsing latest updates feed: {e}")
            return cast(UpdatesFeed, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))
    
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
                    data_str = raw_data.decode('utf-8')
                elif isinstance(raw_data, str):
                    data_str = raw_data
                else:
                    return format_error(ErrorCode.PARSE_ERROR, f"Unexpected data type: {type(raw_data)}")
            elif isinstance(data, (str, bytes)):
                # Legacy format
                if isinstance(data, bytes):
                    data_str = data.decode('utf-8')
                else:
                    data_str = data
            else:
                return format_error(ErrorCode.PARSE_ERROR, f"Unexpected data type: {type(data)}")
            
            # Parse the XML string
            try:
                root = ET.fromstring(data_str)
                
                releases: List[FeedItem] = []
                for item in root.findall(".//item"):
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    desc_elem = item.find("description")
                    date_elem = item.find("pubDate")
                    
                    if all(elem is not None for elem in (title_elem, link_elem, desc_elem, date_elem)):
                        releases.append({
                            "title": title_elem.text or "",
                            "link": link_elem.text or "",
                            "description": desc_elem.text or "",
                            "published_date": date_elem.text or ""
                        })
                
                return {"releases": releases}
            except ET.ParseError as e:
                logger.error(f"XML parse error: {e}")
                return format_error(ErrorCode.PARSE_ERROR, f"Invalid XML response: {e}")
        except Exception as e:
            logger.exception(f"Error parsing project releases feed: {e}")
            return cast(ReleasesFeed, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))
    
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
                    html_content = raw_data.decode('utf-8', errors='ignore')
                elif isinstance(raw_data, str):
                    html_content = raw_data
                else:
                    return format_error(ErrorCode.PARSE_ERROR, f"Unexpected data type: {type(raw_data)}")
            elif isinstance(data, (str, bytes)):
                # Legacy format
                if isinstance(data, bytes):
                    html_content = data.decode('utf-8', errors='ignore')
                else:
                    html_content = data
            else:
                return format_error(ErrorCode.PARSE_ERROR, f"Unexpected data type: {type(data)}")
            
            # Handle case when we receive a Client Challenge page instead of search results
            if "Client Challenge" in html_content:
                logger.warning("Received a security challenge page from PyPI instead of search results")
                return {
                    "search_url": url,
                    "message": "PyPI returned a security challenge page. Try using a web browser to search PyPI directly.",
                    "results": []
                }
            
            # Check if BeautifulSoup is available for better parsing
            if self._has_bs4:
                from bs4 import BeautifulSoup
                
                soup = BeautifulSoup(html_content, 'html.parser')
                results = []
                
                # Extract packages from search results
                for package in soup.select('.package-snippet'):
                    name_elem = package.select_one('.package-snippet__name')
                    version_elem = package.select_one('.package-snippet__version')
                    desc_elem = package.select_one('.package-snippet__description')
                    
                    if name_elem and version_elem:
                        name = name_elem.text.strip()
                        version = version_elem.text.strip()
                        description = desc_elem.text.strip() if desc_elem else ""
                        
                        results.append({
                            "name": name,
                            "version": version,
                            "description": description,
                            "url": f"https://pypi.org/project/{name}/"
                        })
                
                # Check if we found any results
                if results:
                    return {
                        "search_url": url,
                        "results": results
                    }
                else:
                    # We have BeautifulSoup but couldn't find any packages
                    # This could be a format change or we're not getting the expected HTML
                    return {
                        "search_url": url,
                        "message": "No packages found or PyPI search page format has changed",
                        "results": []
                    }
            
            # Fallback if BeautifulSoup is not available
            return {
                "search_url": url,
                "message": "For better search results, install Beautiful Soup: pip install beautifulsoup4",
                "results": []  # Return empty results rather than raw HTML
            }
        except Exception as e:
            logger.exception(f"Error searching packages: {e}")
            return cast(SearchResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))
    
    async def compare_versions(self, package_name: str, version1: str, version2: str) -> VersionComparisonResult:
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
                "are_equal": v1 == v2
            }
        except ValueError as e:
            return cast(VersionComparisonResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Error comparing versions: {e}")
            return cast(VersionComparisonResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))
    
    async def get_dependencies(self, package_name: str, version: Optional[str] = None) -> DependenciesResult:
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
                        return cast(DependenciesResult, format_error(ErrorCode.PARSE_ERROR, f"Invalid JSON response: {e}"))
                else:
                    logger.warning(f"Received non-JSON content: {content_type}")
                    return cast(DependenciesResult, format_error(ErrorCode.PARSE_ERROR, f"Unexpected content type: {content_type}"))
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
                        "marker": str(req.marker) if req.marker else None
                    }
                    dependencies.append(dep)
                except Exception as e:
                    logger.warning(f"Couldn't parse requirement '{req_str}': {e}")
                    # Add a simplified entry for unparseable requirements
                    if ':' in req_str:
                        name = req_str.split(':')[0].strip()
                    elif ';' in req_str:
                        name = req_str.split(';')[0].strip()
                    else:
                        name = req_str.split()[0].strip()
                    
                    dependencies.append({
                        "name": name,
                        "version_spec": "",
                        "extras": [],
                        "marker": "Parse error"
                    })
            
            return {"dependencies": dependencies}
        except ValueError as e:
            return cast(DependenciesResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Error getting dependencies: {e}")
            return cast(DependenciesResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))
    
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
    
    async def get_package_metadata(self, package_name: str, version: Optional[str] = None) -> MetadataResult:
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
                        return cast(MetadataResult, format_error(ErrorCode.PARSE_ERROR, f"Invalid JSON response: {e}"))
                else:
                    logger.warning(f"Received non-JSON content: {content_type}")
                    return cast(MetadataResult, format_error(ErrorCode.PARSE_ERROR, f"Unexpected content type: {content_type}"))
            else:
                # Already parsed JSON data
                info = result.get("info", {})
            
            metadata = {
                "name": info.get("name", ""),
                "version": info.get("version", ""),
                "summary": info.get("summary", ""),
                "description": info.get("description", ""),
                "author": info.get("author", ""),
                "author_email": info.get("author_email", ""),
                "maintainer": info.get("maintainer", ""),
                "maintainer_email": info.get("maintainer_email", ""),
                "license": info.get("license", ""),
                "keywords": info.get("keywords", ""),
                "classifiers": info.get("classifiers", []),
                "platform": info.get("platform", ""),
                "home_page": info.get("home_page", ""),
                "download_url": info.get("download_url", ""),
                "requires_python": info.get("requires_python", ""),
                "requires_dist": info.get("requires_dist", []),
                "project_urls": info.get("project_urls", {}),
                "package_url": info.get("package_url", "")
            }
            
            return {"metadata": metadata}
        except ValueError as e:
            return cast(MetadataResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Error getting package metadata: {e}")
            return cast(MetadataResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))
    
    async def get_package_stats(self, package_name: str, version: Optional[str] = None) -> StatsResult:
        """Get download statistics for a package."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            sanitized_version = sanitize_version(version) if version else None
            
            # Check if package exists first
            exists_result = await self.check_package_exists(sanitized_name)
            if isinstance(exists_result, dict) and "error" in exists_result:
                return cast(StatsResult, exists_result)
            
            if not exists_result.get("exists", False):
                return cast(StatsResult, format_error(ErrorCode.NOT_FOUND, f"Package '{sanitized_name}' not found"))
            
            # Use the stats service to get real download stats
            return await self.stats.get_package_stats(sanitized_name, sanitized_version)
            
        except ValueError as e:
            return cast(StatsResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Error getting package stats: {e}")
            return cast(StatsResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))
    
    async def get_dependency_tree(
        self,
        package_name: str,
        version: Optional[str] = None,
        depth: int = 3
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
            visited: Dict[str, str] = {}
            flat_list: List[str] = []
            
            # Build dependency tree iteratively
            async def build_tree() -> TreeNode:
                queue = [(sanitized_name, sanitized_version, 0, None)]
                nodes: Dict[str, TreeNode] = {}
                
                # Root node
                root: TreeNode = {
                    "name": sanitized_name,
                    "version": sanitized_version,
                    "dependencies": []
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
                                    "cycle": True
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
                            "dependencies": []
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
                                dep_version_info = await self.get_latest_version(dep_name)
                                dep_version = dep_version_info.get("version") if "error" not in dep_version_info else None
                                
                                # Add to queue
                                queue.append((dep_name, dep_version, level + 1, pkg_key))
                
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
                    
                    fig = go.Figure(go.Treemap(
                        labels=labels,
                        parents=parents,
                        root_color="lightgrey"
                    ))
                    
                    fig.update_layout(
                        title=f"Dependency Tree for {sanitized_name} {sanitized_version}",
                        margin=dict(t=50, l=25, r=25, b=25)
                    )
                    
                    # Save to temp file
                    viz_file = os.path.join(self.config.cache_dir, f"deptree_{sanitized_name}_{sanitized_version}.html")
                    pio.write_html(fig, viz_file)
                    visualization_url = f"file://{viz_file}"
                except Exception as e:
                    logger.warning(f"Failed to generate visualization: {e}")
            
            result: DependencyTreeResult = {
                "tree": tree,
                "flat_list": flat_list
            }
            
            if visualization_url:
                result["visualization_url"] = visualization_url
            
            return result
        except ValueError as e:
            return cast(DependencyTreeResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Error getting dependency tree: {e}")
            return cast(DependencyTreeResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))
    
    async def get_documentation_url(self, package_name: str, version: Optional[str] = None) -> DocumentationResult:
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
                    
                if any(term in key.lower() for term in ["doc", "documentation", "docs", "readthedocs", "rtd"]):
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
            
            return {
                "docs_url": docs_url or "Not available",
                "summary": summary
            }
        except ValueError as e:
            return cast(DocumentationResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Error getting documentation URL: {e}")
            return cast(DocumentationResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))
    
    async def check_requirements_file(self, file_path: str) -> PackageRequirementsResult:
        """Check a requirements file for outdated packages."""
        try:
            # Validate file path for security
            path = Path(file_path).resolve()
            
            # Check if file exists
            if not path.exists():
                return cast(PackageRequirementsResult, format_error(ErrorCode.FILE_ERROR, f"File not found: {file_path}"))
            
            # Check file extension
            if not path.name.endswith(('.txt', '.pip')):
                return cast(PackageRequirementsResult, format_error(ErrorCode.INVALID_INPUT, f"File must be a .txt or .pip file: {file_path}"))
            
            # Read file
            try:
                with path.open('r') as f:
                    requirements = f.readlines()
            except PermissionError:
                return cast(PackageRequirementsResult, format_error(ErrorCode.PERMISSION_ERROR, f"Permission denied when reading file: {file_path}"))
            except Exception as e:
                return cast(PackageRequirementsResult, format_error(ErrorCode.FILE_ERROR, f"Error reading file: {str(e)}"))
            
            outdated: List[PackageRequirement] = []
            up_to_date: List[PackageRequirement] = []
            
            for req_line in requirements:
                req_line = req_line.strip()
                if not req_line or req_line.startswith('#'):
                    continue
                
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
                    req_version = None
                    
                    if req.specifier:
                        # Extract the version from the specifier
                        for spec in req.specifier:
                            if spec.operator in ('==', '==='):
                                req_version = spec.version
                                req_ver = Version(req_version)
                                is_outdated = latest_ver > req_ver
                    
                    if is_outdated:
                        outdated.append({
                            "package": pkg_name,
                            "current_version": req_version or "",
                            "latest_version": latest_version
                        })
                    else:
                        up_to_date.append({
                            "package": pkg_name,
                            "current_version": req_version or "unspecified (latest)"
                        })
                except Exception as e:
                    logger.warning(f"Error parsing requirement '{req_line}': {e}")
                    # Try a simple extraction for unparseable requirements
                    try:
                        # Extract package name using regex
                        import re
                        match = re.match(r'^([a-zA-Z0-9_.-]+)(?:[<>=~!]=?|@)(.+)?', req_line)
                        
                        if match:
                            pkg_name = match.group(1)
                            version_spec = match.group(2).strip() if match.group(2) else None
                            
                            # Get latest version
                            latest_version_info = await self.get_latest_version(pkg_name)
                            
                            if "error" not in latest_version_info:
                                latest_version = latest_version_info["version"]
                                
                                if version_spec:
                                    # Add as potentially outdated
                                    outdated.append({
                                        "package": pkg_name,
                                        "current_version": version_spec,
                                        "latest_version": latest_version
                                    })
                                else:
                                    # No specific version required
                                    up_to_date.append({
                                        "package": pkg_name,
                                        "current_version": "unspecified (latest)"
                                    })
                        else:
                            # Raw package name without version specifier
                            pkg_name = req_line
                            up_to_date.append({
                                "package": pkg_name,
                                "current_version": "unspecified (latest)"
                            })
                    except Exception:
                        # Skip lines we can't parse at all
                        continue
            
            return {
                "outdated": outdated,
                "up_to_date": up_to_date
            }
        except Exception as e:
            logger.exception(f"Error checking requirements file: {e}")
            return cast(PackageRequirementsResult, format_error(ErrorCode.UNKNOWN_ERROR, f"Error checking requirements file: {str(e)}"))
