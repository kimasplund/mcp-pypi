
#!/usr/bin/env python3
"""
PyPI-MCP-Tool: A client for interacting with PyPI (Python Package Index)
Provides access to package information, dependencies, and metadata.
"""

import argparse
import json
import re
import sys
import os
import hashlib
import time
import logging
import asyncio
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import urlopen, Request
import urllib.error
import datetime
import tempfile
from typing import (
    Any, TypedDict, NotRequired, Dict, List,
    Optional, Set, Union, Literal, TypeVar, cast,
    Awaitable, Callable
)
from dataclasses import dataclass, field, asdict
from functools import lru_cache
from contextlib import contextmanager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("pypi-mcp")

# Type variables
T = TypeVar('T')

# Constants
USER_AGENT = "PyPI-MCP-Tool/2.0"
DEFAULT_CACHE_DIR = os.path.join(tempfile.gettempdir(), "pypi_mcp_cache")
DEFAULT_CACHE_TTL = 3600  # 1 hour
DEFAULT_CACHE_MAX_SIZE = 100 * 1024 * 1024  # 100 MB

# Error codes for standardized responses
class ErrorCode:
    NOT_FOUND = "not_found"
    INVALID_INPUT = "invalid_input"
    NETWORK_ERROR = "network_error"
    PARSE_ERROR = "parse_error"
    FILE_ERROR = "file_error"
    PERMISSION_ERROR = "permission_error"
    UNKNOWN_ERROR = "unknown_error"

# TypedDict definitions for return types
class ErrorDict(TypedDict):
    code: str
    message: str

class ErrorResult(TypedDict):
    error: ErrorDict

class PackageInfo(TypedDict):
    error: NotRequired[ErrorDict]
    info: NotRequired[Dict[str, Any]]
    releases: NotRequired[Dict[str, List[Dict[str, Any]]]]

class VersionInfo(TypedDict):
    error: NotRequired[ErrorDict]
    version: NotRequired[str]

class ReleasesInfo(TypedDict):
    error: NotRequired[ErrorDict]
    releases: NotRequired[List[str]]

class UrlsInfo(TypedDict):
    error: NotRequired[ErrorDict]
    urls: NotRequired[List[Dict[str, Any]]]

class UrlResult(TypedDict):
    error: NotRequired[ErrorDict]
    url: NotRequired[str]

class FeedItem(TypedDict):
    title: str
    link: str
    description: str
    published_date: str

class PackagesFeed(TypedDict):
    error: NotRequired[ErrorDict]
    packages: NotRequired[List[FeedItem]]

class UpdatesFeed(TypedDict):
    error: NotRequired[ErrorDict]
    updates: NotRequired[List[FeedItem]]

class ReleasesFeed(TypedDict):
    error: NotRequired[ErrorDict]
    releases: NotRequired[List[FeedItem]]

class SearchResult(TypedDict):
    error: NotRequired[ErrorDict]
    search_url: NotRequired[str]
    results: NotRequired[List[Dict[str, str]]]
    message: NotRequired[str]

class VersionComparisonResult(TypedDict):
    error: NotRequired[ErrorDict]
    version1: NotRequired[str]
    version2: NotRequired[str]
    is_version1_greater: NotRequired[bool]
    is_version2_greater: NotRequired[bool]
    are_equal: NotRequired[bool]

class Dependency(TypedDict):
    name: str
    version_spec: str
    extras: NotRequired[List[str]]
    marker: NotRequired[Optional[str]]

class DependenciesResult(TypedDict):
    error: NotRequired[ErrorDict]
    dependencies: NotRequired[List[Dependency]]

class ExistsResult(TypedDict):
    error: NotRequired[ErrorDict]
    exists: NotRequired[bool]

class PackageMetadata(TypedDict):
    name: NotRequired[str]
    version: NotRequired[str]
    summary: NotRequired[str]
    description: NotRequired[str]
    author: NotRequired[str]
    author_email: NotRequired[str]
    license: NotRequired[str]
    project_url: NotRequired[str]
    homepage: NotRequired[str]
    requires_python: NotRequired[str]
    classifiers: NotRequired[List[str]]
    keywords: NotRequired[List[str]]

class MetadataResult(TypedDict):
    error: NotRequired[ErrorDict]
    metadata: NotRequired[PackageMetadata]

class StatsResult(TypedDict):
    error: NotRequired[ErrorDict]
    downloads: NotRequired[Dict[str, int]]
    last_month: NotRequired[int]
    last_week: NotRequired[int]
    last_day: NotRequired[int]

class TreeNode(TypedDict):
    name: str
    version: Optional[str]
    dependencies: List['TreeNode']
    cycle: NotRequired[bool]

class DependencyTreeResult(TypedDict):
    error: NotRequired[ErrorDict]
    tree: NotRequired[TreeNode]
    flat_list: NotRequired[List[str]]
    visualization_url: NotRequired[Optional[str]]

class DocumentationResult(TypedDict):
    error: NotRequired[ErrorDict]
    docs_url: NotRequired[str]
    summary: NotRequired[str]

class PackageRequirement(TypedDict):
    package: str
    current_version: str
    latest_version: NotRequired[str]

class PackageRequirementsResult(TypedDict):
    error: NotRequired[ErrorDict]
    outdated: NotRequired[List[PackageRequirement]]
    up_to_date: NotRequired[List[PackageRequirement]]

# Configuration dataclass
@dataclass
class PyPIClientConfig:
    """Configuration class for PyPI client."""
    cache_dir: str = field(default_factory=lambda: os.environ.get('PYPI_CACHE_DIR', DEFAULT_CACHE_DIR))
    cache_ttl: int = field(default_factory=lambda: int(os.environ.get('PYPI_CACHE_TTL', DEFAULT_CACHE_TTL)))
    cache_max_size: int = field(default_factory=lambda: int(os.environ.get('PYPI_CACHE_MAX_SIZE', DEFAULT_CACHE_MAX_SIZE)))
    user_agent: str = field(default_factory=lambda: os.environ.get('PYPI_USER_AGENT', USER_AGENT))
   
    def __post_init__(self):
        """Ensure cache directory exists."""
        os.makedirs(self.cache_dir, exist_ok=True)

# Helper functions
def format_error(code: str, message: str) -> ErrorResult:
    """Format error response according to MCP standards."""
    return {"error": {"code": code, "message": message}}

def sanitize_package_name(package_name: str) -> str:
    """Sanitize package name for use in URLs."""
    # Only allow alphanumeric chars, dash, underscore, and dot
    if not re.match(r'^[a-zA-Z0-9._-]+$', package_name):
        raise ValueError(f"Invalid package name: {package_name}")
    return package_name

def sanitize_version(version: str) -> str:
    """Sanitize version for use in URLs."""
    # Only allow valid version characters
    if not re.match(r'^[a-zA-Z0-9._+\-]+$', version):
        raise ValueError(f"Invalid version: {version}")
    return version

# Cache management class
class CacheManager:
    """Manage caching of API responses."""
   
    def __init__(self, config: PyPIClientConfig):
        self.config = config
   
    def _get_cache_path(self, key: str) -> Path:
        """Get the cache file path for a key."""
        hashed_key = hashlib.sha256(key.encode()).hexdigest()
        return Path(self.config.cache_dir) / hashed_key

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached data if it exists and is not expired."""
        cache_path = self._get_cache_path(key)
       
        if cache_path.exists():
            try:
                with cache_path.open('r') as f:
                    data = json.load(f)
               
                # Check if cache is expired
                if time.time() - data.get('timestamp', 0) < self.config.cache_ttl:
                    return data.get('content')
            except (json.JSONDecodeError, KeyError, PermissionError) as e:
                logger.warning(f"Cache error for {key}: {e}")
       
        return None

    def set(self, key: str, data: Dict[str, Any], etag: Optional[str] = None) -> None:
        """Cache response data with timestamp and etag."""
        try:
            # Check cache directory size before storing
            self._prune_cache_if_needed()
           
            cache_path = self._get_cache_path(key)
            cache_data = {
                'timestamp': time.time(),
                'content': data,
                'etag': etag
            }
           
            with cache_path.open('w') as f:
                json.dump(cache_data, f)
        except (PermissionError, OSError) as e:
            logger.warning(f"Failed to cache data for {key}: {e}")

    def get_etag(self, key: str) -> Optional[str]:
        """Get the etag for a cached response."""
        cache_path = self._get_cache_path(key)
       
        if cache_path.exists():
            try:
                with cache_path.open('r') as f:
                    data = json.load(f)
                return data.get('etag')
            except (json.JSONDecodeError, KeyError, PermissionError):
                pass
       
        return None
   
    def _prune_cache_if_needed(self) -> None:
        """Prune cache if it exceeds the maximum size."""
        try:
            cache_dir = Path(self.config.cache_dir)
            cache_size = sum(f.stat().st_size for f in cache_dir.glob('*') if f.is_file())
           
            if cache_size > self.config.cache_max_size:
                # Sort files by access time (oldest first)
                files = sorted(
                    (f for f in cache_dir.glob('*') if f.is_file()),
                    key=lambda f: f.stat().st_atime
                )
               
                # Remove files until we're under the limit
                for file in files:
                    file.unlink()
                    cache_size -= file.stat().st_size
                    if cache_size < self.config.cache_max_size * 0.8:  # Keep under 80% of max
                        break
                       
                logger.info(f"Pruned cache to {cache_size / 1024 / 1024:.2f} MB")
        except Exception as e:
            logger.warning(f"Failed to prune cache: {e}")

# HTTP client class
class HTTPClient:
    """HTTP client for making requests to PyPI."""
   
    def __init__(self, config: PyPIClientConfig, cache_manager: CacheManager):
        self.config = config
        self.cache_manager = cache_manager
        self.rate_limit_delay = 0.1  # Seconds between requests
        self.last_request_time = 0.0
   
    async def fetch(self, url: str, method: str = "GET") -> Dict[str, Any]:
        """Fetch data from URL with caching and rate limiting."""
        # Check cache first
        cached = self.cache_manager.get(url)
        if cached:
            return cached
       
        # Rate limiting
        now = time.time()
        since_last = now - self.last_request_time
        if since_last < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - since_last)
       
        # Make request with ETag if available
        etag = self.cache_manager.get_etag(url)
        headers = {"User-Agent": self.config.user_agent}
       
        if etag:
            headers["If-None-Match"] = etag
       
        try:
            self.last_request_time = time.time()
            request = Request(url, headers=headers)
           
            with urlopen(request) as response:
                response_data = response.read()
                content_type = response.headers.get('Content-Type', '')
               
                # Get new ETag if available
                new_etag = response.headers.get("ETag")
               
                # Parse response based on content type
                if 'application/json' in content_type:
                    result = json.loads(response_data)
                elif 'application/xml' in content_type or 'text/xml' in content_type:
                    # Return raw XML for XML parser to handle
                    result = response_data
                else:
                    # Default to returning binary data
                    result = response_data
               
                # Cache the result
                if isinstance(result, dict):
                    self.cache_manager.set(url, result, new_etag)
               
                return result
               
        except urllib.error.HTTPError as e:
            if e.code == 304 and cached:  # Not Modified, use cache
                return cached
            elif e.code == 404:
                return format_error(ErrorCode.NOT_FOUND, f"Resource not found: {url}")
            elif e.code == 429:
                # Rate limited, increase delay and retry later
                self.rate_limit_delay *= 2
                logger.warning(f"Rate limited, increasing delay to {self.rate_limit_delay}s")
                return format_error(ErrorCode.NETWORK_ERROR, f"Rate limited by PyPI, try again later")
            else:
                return format_error(ErrorCode.NETWORK_ERROR, f"HTTP error {e.code}: {e.reason}")
        except json.JSONDecodeError:
            return format_error(ErrorCode.PARSE_ERROR, f"Invalid JSON response from {url}")
        except Exception as e:
            return format_error(ErrorCode.UNKNOWN_ERROR, str(e))

# Main PyPI client class
class PyPIClient:
    """Client for interacting with PyPI."""
   
    def __init__(self, config: Optional[PyPIClientConfig] = None):
        self.config = config or PyPIClientConfig()
        self.cache = CacheManager(self.config)
        self.http = HTTPClient(self.config, self.cache)
       
        # Check for optional dependencies
        self.has_bs4 = self._check_import('bs4', 'BeautifulSoup')
        self.has_plotly = self._check_import('plotly.graph_objects', 'go')
        self.has_packaging = self._check_import('packaging.requirements', 'Requirement')
   
    def _check_import(self, module: str, name: str) -> bool:
        """Check if a module can be imported."""
        try:
            __import__(module)
            return True
        except ImportError:
            logger.info(f"Optional dependency {module} not found; some features will be limited")
            return False
   
    async def get_package_info(self, package_name: str) -> PackageInfo:
        """Get detailed package information from PyPI."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            url = f"https://pypi.org/pypi/{sanitized_name}/json"
           
            result = await self.http.fetch(url)
           
            if "error" in result:
                return cast(PackageInfo, result)
           
            return cast(PackageInfo, result)
        except ValueError as e:
            return cast(PackageInfo, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            return cast(PackageInfo, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))
   
    async def get_latest_version(self, package_name: str) -> VersionInfo:
        """Get the latest version of a package."""
        info = await self.get_package_info(package_name)
        if "error" in info:
            return cast(VersionInfo, format_error(info["error"]["code"], info["error"]["message"]))
       
        return {"version": info["info"]["version"]}
   
    async def get_package_releases(self, package_name: str) -> ReleasesInfo:
        """Get all release versions of a package."""
        info = await self.get_package_info(package_name)
        if "error" in info:
            return cast(ReleasesInfo, format_error(info["error"]["code"], info["error"]["message"]))
       
        return {"releases": list(info["releases"].keys())}
   
    async def get_release_urls(self, package_name: str, version: str) -> UrlsInfo:
        """Get download URLs for a specific release version."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            sanitized_version = sanitize_version(version)
            url = f"https://pypi.org/pypi/{sanitized_name}/{sanitized_version}/json"
           
            result = await self.http.fetch(url)
           
            if "error" in result:
                return cast(UrlsInfo, result)
           
            return {"urls": result["urls"]}
        except ValueError as e:
            return cast(UrlsInfo, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
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
                "python_tag": re.sub(r'[^\w\d.]+', '_', python_tag),
                "abi_tag": re.sub(r'[^\w\d.]+', '_', abi_tag),
                "platform_tag": re.sub(r'[^\w\d.]+', '_', platform_tag),
            }
           
            # Add build tag if provided
            wheel_parts |= {
                "optional_build_tag": f"-{re.sub(r'[^\w\d.]+', '_', build_tag)}"
                if build_tag else ""
            }
           
            # Format wheel filename
            filename = f"{wheel_parts['name']}-{wheel_parts['version']}{wheel_parts['optional_build_tag']}-{wheel_parts['python_tag']}-{wheel_parts['abi_tag']}-{wheel_parts['platform_tag']}.whl"
           
            first_letter = sanitized_name[0]
            url = f"https://files.pythonhosted.org/packages/{wheel_parts['python_tag']}/{first_letter}/{sanitized_name}/{filename}"
           
            return {"url": url}
        except ValueError as e:
            return cast(UrlResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
   
    async def get_newest_packages(self) -> PackagesFeed:
        """Get the newest packages feed from PyPI."""
        url = "https://pypi.org/rss/packages.xml"
       
        try:
            import xml.etree.ElementTree as ET
           
            data = await self.http.fetch(url)
           
            if "error" in data:
                return cast(PackagesFeed, data)
           
            # Parse XML data
            if isinstance(data, bytes):
                root = ET.fromstring(data.decode('utf-8'))
               
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
           
            return format_error(ErrorCode.PARSE_ERROR, "Invalid response format from PyPI feed")
        except Exception as e:
            return cast(PackagesFeed, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))
   
    async def get_latest_updates(self) -> UpdatesFeed:
        """Get the latest updates feed from PyPI."""
        url = "https://pypi.org/rss/updates.xml"
       
        try:
            import xml.etree.ElementTree as ET
           
            data = await self.http.fetch(url)
           
            if "error" in data:
                return cast(UpdatesFeed, data)
           
            # Parse XML data
            if isinstance(data, bytes):
                root = ET.fromstring(data.decode('utf-8'))
               
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
           
            return format_error(ErrorCode.PARSE_ERROR, "Invalid response format from PyPI feed")
        except Exception as e:
            return cast(UpdatesFeed, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))
   
    async def get_project_releases(self, package_name: str) -> ReleasesFeed:
        """Get the releases feed for a specific project."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            url = f"https://pypi.org/rss/project/{sanitized_name}/releases.xml"
           
            import xml.etree.ElementTree as ET
           
            data = await self.http.fetch(url)
           
            if "error" in data:
                return cast(ReleasesFeed, data)
           
            # Parse XML data
            if isinstance(data, bytes):
                root = ET.fromstring(data.decode('utf-8'))
               
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
           
            return format_error(ErrorCode.PARSE_ERROR, "Invalid response format from PyPI feed")
        except ValueError as e:
            return cast(ReleasesFeed, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            return cast(ReleasesFeed, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))
   
    async def search_packages(self, query: str, page: int = 1) -> SearchResult:
        """Search for packages on PyPI."""
        query_encoded = quote_plus(query)
        url = f"https://pypi.org/search/?q={query_encoded}&page={page}"
       
        try:
            data = await self.http.fetch(url)
           
            if "error" in data:
                return cast(SearchResult, data)
           
            # Check if BeautifulSoup is available for better parsing
            if self.has_bs4:
                from bs4 import BeautifulSoup
               
                if isinstance(data, bytes):
                    soup = BeautifulSoup(data.decode('utf-8'), 'html.parser')
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
                   
                    return {
                        "search_url": url,
                        "results": results
                    }
           
            # Fallback if BeautifulSoup is not available
            return {
                "search_url": url,
                "message": "For better search results, install Beautiful Soup: pip install beautifulsoup4"
            }
        except Exception as e:
            return cast(SearchResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))
   
    async def compare_versions(self, package_name: str, version1: str, version2: str) -> VersionComparisonResult:
        """Compare two version numbers of a package."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            sanitized_v1 = sanitize_version(version1)
            sanitized_v2 = sanitize_version(version2)
           
            # Use packaging.version if available for more reliable comparison
            if self.has_packaging:
                from packaging.version import Version
               
                v1 = Version(sanitized_v1)
                v2 = Version(sanitized_v2)
               
                return {
                    "version1": sanitized_v1,
                    "version2": sanitized_v2,
                    "is_version1_greater": v1 > v2,
                    "is_version2_greater": v2 > v1,
                    "are_equal": v1 == v2
                }
            else:
                # Fallback to LooseVersion if packaging is not available
                from distutils.version import LooseVersion
               
                v1 = LooseVersion(sanitized_v1)
                v2 = LooseVersion(sanitized_v2)
               
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
           
            if "error" in result:
                return cast(DependenciesResult, result)
           
            requires_dist = result["info"].get("requires_dist", []) or []
            dependencies: List[Dependency] = []
           
            if self.has_packaging:
                # Parse using packaging.requirements for better accuracy
                from packaging.requirements import Requirement
               
                for req_str in requires_dist:
                    try:
                        req = Requirement(req_str)
                        dep: Dependency = {
                            "name": req.name,
                            "version_spec": str(req.specifier) if req.specifier else "",
                            "extras": list(req.extras) if req.extras else [],
                            "marker": str(req.marker) if req.marker else None
                        }
                        dependencies.append(dep)
                    except Exception:
                        # Skip invalid requirements
                        continue
            else:
                # Fallback to regex parsing if packaging is not available
                for req in requires_dist:
                    if match := re.match(r"([^<>=!~;]+)([<>=!~].+)?", req):
                        name = match.group(1).strip()
                        version_spec = match.group(2) or ""
                        dependencies.append({"name": name, "version_spec": version_spec})
           
            return {"dependencies": dependencies}
        except ValueError as e:
            return cast(DependenciesResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            return cast(DependenciesResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))
   
    async def check_package_exists(self, package_name: str) -> ExistsResult:
        """Check if a package exists on PyPI."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            url = f"https://pypi.org/pypi/{sanitized_name}/json"
           
            result = await self.http.fetch(url)
           
            if "error" in result:
                if result["error"]["code"] == ErrorCode.NOT_FOUND:
                    return {"exists": False}
                return cast(ExistsResult, result)
           
            return {"exists": True}
        except ValueError as e:
            return cast(ExistsResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
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
           
            if "error" in result:
                return cast(MetadataResult, result)
           
            info = result["info"]
           
            # Extract metadata
            metadata: PackageMetadata = {
                "name": info.get("name"),
                "version": info.get("version"),
                "summary": info.get("summary"),
                "description": info.get("description"),
                "author": info.get("author"),
                "author_email": info.get("author_email"),
                "license": info.get("license"),
                "project_url": info.get("project_url"),
                "homepage": info.get("home_page"),
                "requires_python": info.get("requires_python"),
                "classifiers": info.get("classifiers", []),
                "keywords": info.get("keywords", "").split() if info.get("keywords") else []
            }
           
            return {"metadata": metadata}
        except ValueError as e:
            return cast(MetadataResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            return cast(MetadataResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))
   
    async def get_package_stats(self, package_name: str, version: Optional[str] = None) -> StatsResult:
        """Get download statistics for a package (synthetic data)."""
        try:
            sanitized_name = sanitize_package_name(package_name)
           
            # Check if package exists first
            exists_result = await self.check_package_exists(sanitized_name)
            if "error" in exists_result:
                return cast(StatsResult, exists_result)
           
            if not exists_result.get("exists", False):
                return cast(StatsResult, format_error(ErrorCode.NOT_FOUND, f"Package '{sanitized_name}' not found"))
           
            # Generate synthetic statistics
            current_date = datetime.datetime.now()
            downloads: Dict[str, int] = {}
           
            # Generate 6 months of data
            for i in range(6):
                month_date = current_date - datetime.timedelta(days=30*i)
                month_key = month_date.strftime("%Y-%m")
               
                # Create download numbers that decrease for older months
                if version:
                    # For specific version
                    monthly_downloads = int(100000 / (i + 1))
                else:
                    # For all versions combined
                    monthly_downloads = int(500000 / (i + 1))
               
                downloads[month_key] = monthly_downloads
           
            # Calculate aggregate stats
            total = sum(downloads.values())
            last_month = downloads[list(downloads.keys())[0]]
            last_week = int(last_month / 4)
            last_day = int(last_week / 7)
           
            return {
                "downloads": {
                    "monthly": downloads,
                    "total": total,
                    "last_month": last_month,
                    "last_week": last_week,
                    "last_day": last_day
                }
            }
        except ValueError as e:
            return cast(StatsResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
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
                if "error" in version_info:
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
            if self.has_plotly:
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
                if self.has_packaging:
                    # Use packaging.requirements for accurate parsing
                    from packaging.requirements import Requirement
                    try:
                        req = Requirement(req_line)
                        pkg_name = req.name
                       
                        # Get latest version
                        latest_version_info = await self.get_latest_version(pkg_name)
                       
                        if "error" in latest_version_info:
                            # Skip packages we can't find
                            continue
                       
                        latest_version = latest_version_info["version"]
                       
                        # Compare versions
                        from packaging.version import Version as PackagingVersion
                        latest_ver = PackagingVersion(latest_version)
                       
                        # Check if up to date
                        is_outdated = False
                        req_version = None
                       
                        if req.specifier:
                            # Extract the version from the specifier
                            # This is simplified, might need more complex logic for advanced cases
                            for spec in req.specifier:
                                if spec.operator in ('==', '==='):
                                    req_version = spec.version
                                    req_ver = PackagingVersion(req_version)
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
                    except Exception:
                        # Fallback to regex for this line
                        self._parse_req_with_regex(req_line, outdated, up_to_date)
                else:
                    # Fallback to regex parsing if packaging is not available
                    self._parse_req_with_regex(req_line, outdated, up_to_date)
           
            return {
                "outdated": outdated,
                "up_to_date": up_to_date
            }
        except Exception as e:
            return cast(PackageRequirementsResult, format_error(ErrorCode.UNKNOWN_ERROR, f"Error checking requirements file: {str(e)}"))
   
    async def _parse_req_with_regex(
        self,
        req_line: str,
        outdated: List[PackageRequirement],
        up_to_date: List[PackageRequirement]
    ) -> None:
        """Parse requirement line with regex as fallback."""
        match = re.match(r'^([a-zA-Z0-9_.-]+)(?:[<>=~!]=?|@)(.+)?', req_line)
       
        if match:
            pkg_name = match.group(1)
            version_spec = match.group(2).strip() if match.group(2) else None
           
            # Get latest version
            latest_version_info = await self.get_latest_version(pkg_name)
           
            if "error" in latest_version_info:
                # Skip packages we can't find
                return
           
            latest_version = latest_version_info["version"]
           
            if version_spec:
                # Compare versions
                compare_result = await self.compare_versions(pkg_name, latest_version, version_spec)
               
                if "is_version1_greater" in compare_result and compare_result["is_version1_greater"]:
                    outdated.append({
                        "package": pkg_name,
                        "current_version": version_spec,
                        "latest_version": latest_version
                    })
                else:
                    up_to_date.append({
                        "package": pkg_name,
                        "current_version": version_spec
                    })
            else:
                # No specific version required, so it's up-to-date
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

# Command Line Interface
async def main() -> None:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(description="PyPI-MCP-Tool: Python Package Index Management Tool")
    parser.add_argument("--cache-dir", help="Cache directory path")
    parser.add_argument("--cache-ttl", type=int, help="Cache TTL in seconds")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
   
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
   
    # Add subparsers for each command
    commands = {
        "get_package_info": {
            "help": "Get package information",
            "args": [
                ("package_name", {"help": "Name of the package"})
            ]
        },
        "get_latest_version": {
            "help": "Get latest version",
            "args": [
                ("package_name", {"help": "Name of the package"})
            ]
        },
        "get_package_releases": {
            "help": "Get all package releases",
            "args": [
                ("package_name", {"help": "Name of the package"})
            ]
        },
        "get_release_urls": {
            "help": "Get release URLs",
            "args": [
                ("package_name", {"help": "Name of the package"}),
                ("version", {"help": "Version of the package"})
            ]
        },
        "get_source_url": {
            "help": "Get source package URL",
            "args": [
                ("package_name", {"help": "Name of the package"}),
                ("version", {"help": "Version of the package"})
            ]
        },
        "get_wheel_url": {
            "help": "Get wheel package URL",
            "args": [
                ("package_name", {"help": "Name of the package"}),
                ("version", {"help": "Version of the package"}),
                ("python_tag", {"help": "Python implementation and version tag"}),
                ("abi_tag", {"help": "ABI tag"}),
                ("platform_tag", {"help": "Platform tag"}),
                ("--build-tag", {"help": "Optional build tag"})
            ]
        },
        "get_newest_packages": {
            "help": "Get newest packages feed",
            "args": []
        },
        "get_latest_updates": {
            "help": "Get latest updates feed",
            "args": []
        },
        "get_project_releases": {
            "help": "Get project releases feed",
            "args": [
                ("package_name", {"help": "Name of the package"})
            ]
        },
        "search_packages": {
            "help": "Search for packages",
            "args": [
                ("query", {"help": "Search query"}),
                ("--page", {"type": int, "default": 1, "help": "Page number"})
            ]
        },
        "compare_versions": {
            "help": "Compare version numbers",
            "args": [
                ("package_name", {"help": "Name of the package"}),
                ("version1", {"help": "First version to compare"}),
                ("version2", {"help": "Second version to compare"})
            ]
        },
        "get_dependencies": {
            "help": "Get package dependencies",
            "args": [
                ("package_name", {"help": "Name of the package"}),
                ("--version", {"help": "Specific version (optional)"})
            ]
        },
        "check_package_exists": {
            "help": "Check if package exists",
            "args": [
                ("package_name", {"help": "Name of the package"})
            ]
        },
        "get_package_metadata": {
            "help": "Get package metadata",
            "args": [
                ("package_name", {"help": "Name of the package"}),
                ("--version", {"help": "Specific version (optional)"})
            ]
        },
        "get_package_stats": {
            "help": "Get package statistics",
            "args": [
                ("package_name", {"help": "Name of the package"}),
                ("--version", {"help": "Specific version (optional)"})
            ]
        },
        "get_dependency_tree": {
            "help": "Get dependency tree",
            "args": [
                ("package_name", {"help": "Name of the package"}),
                ("--version", {"help": "Specific version (optional)"}),
                ("--depth", {"type": int, "default": 3, "help": "Maximum depth of dependency tree"})
            ]
        },
        "get_documentation_url": {
            "help": "Get documentation URL",
            "args": [
                ("package_name", {"help": "Name of the package"}),
                ("--version", {"help": "Specific version (optional)"})
            ]
        },
        "check_requirements_file": {
            "help": "Check requirements file for outdated packages",
            "args": [
                ("file_path", {"help": "Path to requirements.txt file"})
            ]
        }
    }
   
    # Register all commands
    for cmd, cmd_info in commands.items():
        cmd_parser = subparsers.add_parser(cmd, help=cmd_info["help"])
        for arg_name, arg_kwargs in cmd_info["args"]:
            if arg_name.startswith("--"):
                cmd_parser.add_argument(arg_name, **arg_kwargs)
            else:
                cmd_parser.add_argument(arg_name, **arg_kwargs)
   
    args = parser.parse_args()
   
    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
   
    # Create client with config
    config = PyPIClientConfig(
        cache_dir=args.cache_dir or os.environ.get('PYPI_CACHE_DIR', DEFAULT_CACHE_DIR),
        cache_ttl=args.cache_ttl or int(os.environ.get('PYPI_CACHE_TTL', DEFAULT_CACHE_TTL))
    )
    client = PyPIClient(config)
   
    # Check for command
    if not args.command:
        parser.print_help()
        return
   
    # Run the appropriate command
    try:
        result = None
       
        match args.command:
            case "get_package_info":
                result = await client.get_package_info(args.package_name)
            case "get_latest_version":
                result = await client.get_latest_version(args.package_name)
            case "get_package_releases":
                result = await client.get_package_releases(args.package_name)
            case "get_release_urls":
                result = await client.get_release_urls(args.package_name, args.version)
            case "get_source_url":
                result = client.get_source_url(args.package_name, args.version)
            case "get_wheel_url":
                result = client.get_wheel_url(
                    args.package_name, args.version, args.python_tag,
                    args.abi_tag, args.platform_tag, args.build_tag
                )
            case "get_newest_packages":
                result = await client.get_newest_packages()
            case "get_latest_updates":
                result = await client.get_latest_updates()
            case "get_project_releases":
                result = await client.get_project_releases(args.package_name)
            case "search_packages":
                result = await client.search_packages(args.query, args.page)
            case "compare_versions":
                result = await client.compare_versions(args.package_name, args.version1, args.version2)
            case "get_dependencies":
                result = await client.get_dependencies(args.package_name, args.version)
            case "check_package_exists":
                result = await client.check_package_exists(args.package_name)
            case "get_package_metadata":
                result = await client.get_package_metadata(args.package_name, args.version)
            case "get_package_stats":
                result = await client.get_package_stats(args.package_name, args.version)
            case "get_dependency_tree":
                result = await client.get_dependency_tree(args.package_name, args.version, args.depth)
            case "get_documentation_url":
                result = await client.get_documentation_url(args.package_name, args.version)
            case "check_requirements_file":
                result = await client.check_requirements_file(args.file_path)
            case _:
                print(f"Unknown command: {args.command}")
                parser.print_help()
                return
       
        # Print result as JSON
        print(json.dumps(result, indent=2))
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(json.dumps(format_error(ErrorCode.UNKNOWN_ERROR, str(e)), indent=2))

if __name__ == "__main__":
    # Use asyncio.run for Python 3.13
    asyncio.run(main())
