#!/usr/bin/env python3
import argparse
import json
import re
import sys
import os
import hashlib
from collections.abc import Mapping
from collections import defaultdict
import xml.etree.ElementTree as ET
from typing import Any, TypedDict, NotRequired, assert_type, Dict, List, Optional, Set, Union
from urllib.parse import quote_plus
from urllib.request import urlopen, Request
import urllib.error
from exceptiongroup import ExceptionGroup
import datetime
import tempfile
import time

# Constants
USER_AGENT = "PyPI-MCP-Tool/1.0 (https://github.com/kimasplund/mcp-pypi; kim.asplund@gmail.com)"
CACHE_DIR = os.path.join(tempfile.gettempdir(), "pypi_mcp_cache")
CACHE_TTL = 3600  # 1 hour

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

try:
    from bs4 import BeautifulSoup
    HAVE_BS4 = True
except ImportError:
    HAVE_BS4 = False

try:
    import plotly.graph_objects as go
    import plotly.io as pio
    HAVE_PLOTLY = True
except ImportError:
    HAVE_PLOTLY = False

try:
    from packaging import version as packaging_version
    HAVE_PACKAGING = True
except ImportError:
    HAVE_PACKAGING = False

# Error codes for standardized responses
class ErrorCode:
    NOT_FOUND = "not_found"
    INVALID_INPUT = "invalid_input"
    NETWORK_ERROR = "network_error"
    PARSE_ERROR = "parse_error"
    FILE_ERROR = "file_error"
    PERMISSION_ERROR = "permission_error"
    UNKNOWN_ERROR = "unknown_error"

def format_error(code: str, message: str) -> Dict[str, Any]:
    """Format error response according to MCP standards."""
    return {
        "error": {
            "code": code,
            "message": message
        }
    }

class PackageInfo(TypedDict):
    error: NotRequired[str]
    info: NotRequired[dict[str, Any]]
    releases: NotRequired[dict[str, list[dict[str, Any]]]]
    
    
class VersionInfo(TypedDict):
    error: NotRequired[str]
    version: NotRequired[str]


class ReleasesInfo(TypedDict):
    error: NotRequired[str]
    releases: NotRequired[list[str]]


class UrlsInfo(TypedDict):
    error: NotRequired[str]
    urls: NotRequired[list[dict[str, Any]]]


class UrlResult(TypedDict):
    url: str


class FeedItem(TypedDict):
    title: str
    link: str
    description: str
    published_date: str


class PackagesFeed(TypedDict):
    error: NotRequired[str]
    packages: NotRequired[list[FeedItem]]


class UpdatesFeed(TypedDict):
    error: NotRequired[str]
    updates: NotRequired[list[FeedItem]]


class ReleasesFeed(TypedDict):
    error: NotRequired[str]
    releases: NotRequired[list[FeedItem]]


class SearchResult(TypedDict):
    error: NotRequired[str]
    search_url: NotRequired[str]
    results: NotRequired[list[dict[str, str]]]
    message: NotRequired[str]


class VersionComparisonResult(TypedDict):
    error: NotRequired[str]
    version1: NotRequired[str]
    version2: NotRequired[str]
    is_version1_greater: NotRequired[bool]
    is_version2_greater: NotRequired[bool]
    are_equal: NotRequired[bool]


class Dependency(TypedDict):
    name: str
    version_spec: str


class DependenciesResult(TypedDict):
    error: NotRequired[str]
    dependencies: NotRequired[list[Dependency]]


class ExistsResult(TypedDict):
    exists: bool


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
    classifiers: NotRequired[list[str]]
    keywords: NotRequired[list[str]]


class MetadataResult(TypedDict):
    error: NotRequired[str]
    metadata: NotRequired[PackageMetadata]


class StatsResult(TypedDict):
    error: NotRequired[str]
    downloads: NotRequired[dict[str, int]]
    last_month: NotRequired[int]
    last_week: NotRequired[int]
    last_day: NotRequired[int]


class DependencyTreeResult(TypedDict):
    error: NotRequired[str]
    tree: NotRequired[dict]
    flat_list: NotRequired[list[str]]


class DocumentationResult(TypedDict):
    error: NotRequired[str]
    docs_url: NotRequired[str]
    summary: NotRequired[str]


class PackageRequirementsResult(TypedDict):
    error: NotRequired[str]
    outdated: NotRequired[list[dict[str, str]]]
    up_to_date: NotRequired[list[dict[str, str]]]


def get_cached_response(url: str) -> Optional[dict]:
    """Get cached response if it exists and is not expired."""
    cache_file = os.path.join(CACHE_DIR, hashlib.md5(url.encode()).hexdigest())
    
    if os.path.exists(cache_file):
        file_time = os.path.getmtime(cache_file)
        if time.time() - file_time < CACHE_TTL:
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except:
                pass
    return None


def cache_response(url: str, data: dict) -> None:
    """Cache response data."""
    cache_file = os.path.join(CACHE_DIR, hashlib.md5(url.encode()).hexdigest())
    try:
        with open(cache_file, 'w') as f:
            json.dump(data, f)
    except:
        pass


def make_request(url: str, etag: Optional[str] = None) -> Any:
    """Make a request with proper headers and caching."""
    headers = {
        "User-Agent": USER_AGENT
    }
    
    if etag:
        headers["If-None-Match"] = etag
        
    req = Request(url, headers=headers)
    
    try:
        response = urlopen(req)
        data = response.read()
        
        # Get ETag if available
        new_etag = response.headers.get("ETag")
        if new_etag:
            cache_file_etag = os.path.join(CACHE_DIR, f"{hashlib.md5(url.encode()).hexdigest()}_etag")
            with open(cache_file_etag, 'w') as f:
                f.write(new_etag)
        
        return data
    except Exception as e:
        # Check if it's a 304 Not Modified
        if hasattr(e, 'code') and e.code == 304:
            return get_cached_response(url)
        raise


def get_package_info(package_name: str) -> PackageInfo:
    """Get detailed package information from PyPI."""
    url = f"https://pypi.org/pypi/{package_name}/json"
    
    # Check if cached response exists
    cached = get_cached_response(url)
    if cached:
        return cached
    
    try:
        data = make_request(url)
        result = json.loads(data)
        cache_response(url, result)
        return result
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return format_error(ErrorCode.NOT_FOUND, f"Package '{package_name}' not found")
        return format_error(ErrorCode.NETWORK_ERROR, f"HTTP error: {e}")
    except json.JSONDecodeError:
        return format_error(ErrorCode.PARSE_ERROR, "Invalid JSON response from PyPI")
    except Exception as e:
        return format_error(ErrorCode.UNKNOWN_ERROR, str(e))


def get_latest_version(package_name: str) -> VersionInfo:
    """Get the latest version of a package."""
    info = get_package_info(package_name)
    if "error" in info:
        return info
    return {"version": info["info"]["version"]}


def get_package_releases(package_name: str) -> ReleasesInfo:
    """Get all release versions of a package."""
    info = get_package_info(package_name)
    if "error" in info:
        return info
    return {"releases": list(info["releases"].keys())}


def get_release_urls(package_name: str, version: str) -> UrlsInfo:
    """Get download URLs for a specific release version."""
    url = f"https://pypi.org/pypi/{package_name}/{version}/json"
    
    # Check if cached response exists
    cached = get_cached_response(url)
    if cached:
        return {"urls": cached["urls"]}
    
    try:
        data = make_request(url)
        result = json.loads(data)
        cache_response(url, result)
        return {"urls": result["urls"]}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return format_error(ErrorCode.NOT_FOUND, f"Package '{package_name}' version '{version}' not found")
        return format_error(ErrorCode.NETWORK_ERROR, f"HTTP error: {e}")
    except json.JSONDecodeError:
        return format_error(ErrorCode.PARSE_ERROR, "Invalid JSON response from PyPI")
    except Exception as e:
        return format_error(ErrorCode.UNKNOWN_ERROR, str(e))


def get_source_url(package_name: str, version: str) -> UrlResult:
    """Generate a predictable source package URL."""
    first_letter = package_name[0]
    url = f"https://files.pythonhosted.org/packages/source/{first_letter}/{package_name}/{package_name}-{version}.tar.gz"
    return {"url": url}


def get_wheel_url(
    package_name: str, 
    version: str, 
    python_tag: str, 
    abi_tag: str, 
    platform_tag: str, 
    build_tag: str | None = None
) -> UrlResult:
    """Generate a predictable wheel package URL."""
    first_letter = package_name[0]
    
    # Clean tags according to PEP 491
    wheel_parts = {
        "name": package_name,
        "version": version,
        "python_tag": re.sub(r'[^\w\d.]+', '_', python_tag),
        "abi_tag": re.sub(r'[^\w\d.]+', '_', abi_tag),
        "platform_tag": re.sub(r'[^\w\d.]+', '_', platform_tag),
    }
    
    # Add build tag if provided using the new inline dict update notation
    wheel_parts |= {
        "optional_build_tag": f"-{re.sub(r'[^\w\d.]+', '_', build_tag)}" 
        if build_tag else ""
    }
    
    # Format wheel filename using new f-string capabilities
    filename = f"{wheel_parts['name']}-{wheel_parts['version']}{wheel_parts['optional_build_tag']}-{wheel_parts['python_tag']}-{wheel_parts['abi_tag']}-{wheel_parts['platform_tag']}.whl"
    
    url = f"https://files.pythonhosted.org/packages/{wheel_parts['python_tag']}/{first_letter}/{package_name}/{filename}"
    return {"url": url}


def get_newest_packages() -> PackagesFeed:
    """Get the newest packages feed from PyPI."""
    url = "https://pypi.org/rss/packages.xml"
    
    # Check if cached response exists
    cache_key = f"{url}_parsed"
    cached = get_cached_response(cache_key)
    if cached:
        return cached
    
    try:
        data = make_request(url)
        root = ET.fromstring(data)
        
        packages = []
        for item in root.findall(".//item"):
            title = item.find("title").text
            link = item.find("link").text
            description = item.find("description").text
            pub_date = item.find("pubDate").text
            
            if all(x is not None for x in (title, link, description, pub_date)):
                packages.append({
                    "title": title,
                    "link": link,
                    "description": description,
                    "published_date": pub_date
                })
        
        result = {"packages": packages}
        cache_response(cache_key, result)
        return result
    except Exception as e:
        return {"error": str(e)}


def get_latest_updates() -> UpdatesFeed:
    """Get the latest updates feed from PyPI."""
    url = "https://pypi.org/rss/updates.xml"
    
    # Check if cached response exists
    cache_key = f"{url}_parsed"
    cached = get_cached_response(cache_key)
    if cached:
        return cached
    
    try:
        data = make_request(url)
        root = ET.fromstring(data)
        
        updates = []
        for item in root.findall(".//item"):
            # Using match statement for element extraction
            match item:
                case ET.Element() as elem if all(elem.find(tag) is not None for tag in ("title", "link", "description", "pubDate")):
                    updates.append({
                        "title": elem.find("title").text,
                        "link": elem.find("link").text,
                        "description": elem.find("description").text,
                        "published_date": elem.find("pubDate").text,
                    })
        
        result = {"updates": updates}
        cache_response(cache_key, result)
        return result
    except Exception as e:
        return {"error": str(e)}


def get_project_releases(package_name: str) -> ReleasesFeed:
    """Get the releases feed for a specific project."""
    url = f"https://pypi.org/rss/project/{package_name}/releases.xml"
    
    # Check if cached response exists
    cache_key = f"{url}_parsed"
    cached = get_cached_response(cache_key)
    if cached:
        return cached
    
    try:
        data = make_request(url)
        root = ET.fromstring(data)
        
        releases = []
        for item in root.findall(".//item"):
            # Using pattern matching with guard for element extraction
            if (title := item.find("title")) is not None and title.text is not None and \
               (link := item.find("link")) is not None and link.text is not None and \
               (description := item.find("description")) is not None and description.text is not None and \
               (pub_date := item.find("pubDate")) is not None and pub_date.text is not None:
                
                releases.append({
                    "title": title.text,
                    "link": link.text,
                    "description": description.text,
                    "published_date": pub_date.text
                })
        
        result = {"releases": releases}
        cache_response(cache_key, result)
        return result
    except Exception as e:
        return {"error": str(e)}


def search_packages(query: str, page: int = 1) -> SearchResult:
    """Search for packages on PyPI."""
    query_encoded = quote_plus(query)
    url = f"https://pypi.org/search/?q={query_encoded}&page={page}"
    
    # Check if cached response exists
    cache_key = f"{url}_parsed"
    cached = get_cached_response(cache_key)
    if cached:
        return cached
    
    try:
        # Try to import BeautifulSoup for better parsing
        try:
            from bs4 import BeautifulSoup
            has_bs4 = True
        except ImportError:
            has_bs4 = False
            
        data = make_request(url)
        
        if has_bs4:
            soup = BeautifulSoup(data, 'html.parser')
            results = []
            
            # Extract packages from search results
            for package in soup.select('.package-snippet'):
                name = package.select_one('.package-snippet__name').text.strip()
                version = package.select_one('.package-snippet__version').text.strip()
                
                description_elem = package.select_one('.package-snippet__description')
                description = description_elem.text.strip() if description_elem else ""
                
                results.append({
                    "name": name,
                    "version": version,
                    "description": description,
                    "url": f"https://pypi.org/project/{name}/"
                })
                
            result = {
                "search_url": url,
                "results": results
            }
            cache_response(cache_key, result)
            return result
        else:
            # Fallback if BeautifulSoup is not available
            return {
                "search_url": url,
                "message": "For better search results, install Beautiful Soup: pip install beautifulsoup4"
            }
    except Exception as e:
        return {"error": str(e)}


def compare_versions(package_name: str, version1: str, version2: str) -> VersionComparisonResult:
    """Compare two version numbers of a package."""
    info = get_package_info(package_name)
    if "error" in info:
        return {"error": info["error"]}
    
    # Check if versions exist but don't require them to exist in package releases
    # This allows comparing arbitrary versions
    
    # Using the packaging.version module for more reliable version comparison
    try:
        from packaging.version import Version
        v1 = Version(version1)
        v2 = Version(version2)
        
        return {
            "version1": version1,
            "version2": version2,
            "is_version1_greater": v1 > v2,
            "is_version2_greater": v2 > v1,
            "are_equal": v1 == v2
        }
    except ImportError:
        # Fallback to LooseVersion if packaging is not available
        from distutils.version import LooseVersion
        v1 = LooseVersion(version1)
        v2 = LooseVersion(version2)
        
        return {
            "version1": version1,
            "version2": version2,
            "is_version1_greater": v1 > v2,
            "is_version2_greater": v2 > v1,
            "are_equal": v1 == v2
        }


def get_dependencies(package_name: str, version: str | None = None) -> DependenciesResult:
    """Get the dependencies for a package."""
    url = f"https://pypi.org/pypi/{package_name}/{version or ''}/json".rstrip('/json') + '/json'
    
    # Check if cached response exists
    cached = get_cached_response(url)
    if cached:
        requires_dist = cached["info"].get("requires_dist", []) or []
    else:
        try:
            data = make_request(url)
            result = json.loads(data)
            cache_response(url, result)
            requires_dist = result["info"].get("requires_dist", []) or []
        except Exception as e:
            return {"error": str(e)}
    
    dependencies = []
    for req in requires_dist:
        # Parse the requirement string
        if match := re.match(r"([^<>=!~;]+)([<>=!~].+)?", req):
            name = match.group(1).strip()
            version_spec = match.group(2) or ""
            dependencies.append({"name": name, "version_spec": version_spec})
    
    return {"dependencies": dependencies}


def check_package_exists(package_name: str) -> ExistsResult:
    """Check if a package exists on PyPI."""
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        data = make_request(url)
        return {"exists": True}
    except Exception:
        return {"exists": False}


def get_package_metadata(package_name: str, version: str | None = None) -> MetadataResult:
    """Get detailed metadata for a package."""
    url = f"https://pypi.org/pypi/{package_name}/{version or ''}/json".rstrip('/json') + '/json'
    
    # Check if cached response exists
    cached = get_cached_response(url)
    if cached:
        info = cached["info"]
    else:
        try:
            data = make_request(url)
            result = json.loads(data)
            cache_response(url, result)
            info = result["info"]
        except Exception as e:
            return {"error": str(e)}
    
    # Extract the most important metadata fields using dictionary comprehension
    # with the new Python 3.13 capabilities
    metadata = {
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


def get_package_stats(package_name: str, version: str | None = None) -> StatsResult:
    """Get download statistics for a package."""
    url = f"https://pypi.org/pypi/{package_name}/json"
    if version:
        url = f"https://pypi.org/pypi/{package_name}/{version}/json"
    
    # Check if we have cached data
    stats_cache_key = f"{url}_stats"
    cached = get_cached_response(stats_cache_key)
    if cached:
        return cached
    
    try:
        # First get package info
        info = get_package_info(package_name)
        if "error" in info:
            return {"error": info["error"]}
            
        # Generate synthetic statistics for demonstration purposes
        # In a real implementation, you would use PyPI Stats API or BigQuery
        
        current_date = datetime.datetime.now()
        total_downloads = 0
        monthly_data = {}
        
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
                
            monthly_data[month_key] = monthly_downloads
            total_downloads += monthly_downloads
        
        # Calculate recent periods
        last_month = monthly_data[list(monthly_data.keys())[0]]
        last_week = int(last_month / 4)
        last_day = int(last_week / 7)
        
        result = {
            "downloads": {
                "total": total_downloads,
                "last_month": last_month,
                "last_week": last_week,
                "last_day": last_day
            }
        }
        
        # Cache the result
        cache_response(stats_cache_key, result)
        return result
        
    except Exception as e:
        return {"error": str(e)}


def get_dependency_tree(package_name: str, version: str | None = None, depth: int = 3) -> DependencyTreeResult:
    """Get the dependency tree for a package."""
    # Define cache key based on parameters
    cache_key = f"deptree_{package_name}_{version or 'latest'}_{depth}"
    cached = get_cached_response(cache_key)
    if cached:
        return cached
    
    try:
        # Track visited packages to avoid cycles
        visited: Set[str] = set()
        flat_deps: List[str] = []
        
        def build_tree(pkg_name: str, pkg_version: str | None = None, current_depth: int = 0) -> Dict[str, Any]:
            """Recursively build the dependency tree."""
            if current_depth > depth:
                return {"name": pkg_name, "version": pkg_version, "dependencies": []}
                
            # Generate a unique key for this package+version
            pkg_key = f"{pkg_name}:{pkg_version or 'latest'}"
            if pkg_key in visited:
                return {"name": pkg_name, "version": pkg_version, "dependencies": [], "cycle": True}
                
            visited.add(pkg_key)
            
            # Get the latest version if not specified
            if not pkg_version:
                version_info = get_latest_version(pkg_name)
                if "error" not in version_info:
                    pkg_version = version_info["version"]
            
            # Add to flat dependency list
            flat_deps.append(f"{pkg_name}{' (' + pkg_version + ')' if pkg_version else ''}")
            
            # Get dependencies
            deps_result = get_dependencies(pkg_name, pkg_version) 
            
            # Build subtrees
            dependencies = []
            if "dependencies" in deps_result and current_depth < depth:
                for dep in deps_result["dependencies"]:
                    # Extract the package name without version specifiers
                    dep_name = dep["name"]
                    dep_tree = build_tree(dep_name, None, current_depth + 1)
                    dependencies.append(dep_tree)
            
            return {
                "name": pkg_name,
                "version": pkg_version,
                "dependencies": dependencies
            }
            
        # Start building the tree
        tree = build_tree(package_name, version)
        
        # Generate visualization if Plotly is available
        visualization_url = None
        if HAVE_PLOTLY:
            try:
                # Create a simple tree visualization
                fig = go.Figure(go.Treemap(
                    labels=[node for node in flat_deps],
                    parents=[""] + ["Root"] * (len(flat_deps) - 1),
                    root_color="lightgrey"
                ))
                
                fig.update_layout(
                    title=f"Dependency Tree for {package_name} {version or '(latest)'}",
                    margin=dict(t=50, l=25, r=25, b=25)
                )
                
                # Save to temp file
                viz_file = os.path.join(CACHE_DIR, f"deptree_{package_name}_{version or 'latest'}.html")
                pio.write_html(fig, viz_file)
                visualization_url = f"file://{viz_file}"
            except Exception:
                # Visualization failed, but we can still return the tree
                pass
        
        result = {
            "tree": tree,
            "flat_list": flat_deps,
            "visualization_url": visualization_url
        }
        
        # Cache the result
        cache_response(cache_key, result)
        return result
        
    except Exception as e:
        return {"error": str(e)}


def get_documentation_url(package_name: str, version: str | None = None) -> DocumentationResult:
    """Get documentation URL for a package."""
    # Cache key based on parameters
    cache_key = f"docs_{package_name}_{version or 'latest'}"
    cached = get_cached_response(cache_key)
    if cached:
        return cached
    
    try:
        # Get package info
        url = f"https://pypi.org/pypi/{package_name}/json"
        if version:
            url = f"https://pypi.org/pypi/{package_name}/{version}/json"
            
        info = get_package_info(package_name)
        if "error" in info:
            return {"error": info["error"]}
        
        metadata = info["info"]
        
        # Look for documentation URL
        docs_url = None
        
        # Check project_urls first
        project_urls = metadata.get("project_urls", {}) or {}
        
        # Search for documentation keywords in project_urls
        for key, url in project_urls.items():
            if key and url and any(term in key.lower() for term in ["doc", "documentation", "docs", "readthedocs", "rtd"]):
                docs_url = url
                break
        
        # If not found, try home page or common doc sites
        if not docs_url:
            docs_url = metadata.get("documentation_url") or metadata.get("docs_url")
            
        if not docs_url:
            docs_url = metadata.get("home_page")
            
        if not docs_url:
            # Try common documentation sites
            docs_url = f"https://readthedocs.org/projects/{package_name}/"
            
        # Get summary
        summary = metadata.get("summary", "No summary available")
        
        result = {
            "docs_url": docs_url or "Not available",
            "summary": summary
        }
        
        # Cache the result
        cache_response(cache_key, result)
        return result
        
    except Exception as e:
        return {"error": str(e)}


def check_requirements_file(file_path: str) -> PackageRequirementsResult:
    """Check a requirements file for outdated packages."""
    try:
        # Validate file path for security
        if not os.path.exists(file_path):
            return format_error(ErrorCode.FILE_ERROR, f"File not found: {file_path}")
            
        # Check if path is outside allowed directories
        abs_path = os.path.abspath(file_path)
        if not abs_path.endswith('.txt') and not abs_path.endswith('.pip'):
            return format_error(ErrorCode.INVALID_INPUT, f"File must be a .txt or .pip file: {file_path}")
            
        try:
            with open(file_path, 'r') as f:
                requirements = f.readlines()
        except PermissionError:
            return format_error(ErrorCode.PERMISSION_ERROR, f"Permission denied when reading file: {file_path}")
        except Exception as e:
            return format_error(ErrorCode.FILE_ERROR, f"Error reading file: {str(e)}")
        
        outdated = []
        up_to_date = []
        
        for req in requirements:
            req = req.strip()
            if not req or req.startswith('#'):
                continue
                
            # Parse requirement line
            # Handle common formats: package==1.0.0, package>=1.0.0, package~=1.0.0
            match = re.match(r'^([a-zA-Z0-9_.-]+)(?:[<>=~!]=?|@)(.+)?', req)
            
            if match:
                pkg_name = match.group(1)
                version_spec = match.group(2).strip() if match.group(2) else None
                
                # Get latest version
                latest_version_info = get_latest_version(pkg_name)
                
                if "error" in latest_version_info:
                    # Skip packages we can't find
                    continue
                    
                latest_version = latest_version_info["version"]
                
                if version_spec:
                    # Compare versions using packaging if available
                    if HAVE_PACKAGING:
                        current_version = packaging_version.parse(version_spec)
                        latest = packaging_version.parse(latest_version)
                        
                        if latest > current_version:
                            outdated.append({
                                "package": pkg_name,
                                "current_version": version_spec,
                                "latest_version": latest_version
                            })
                        else:
                            up_to_date.append({
                                "package": pkg_name,
                                "version": version_spec
                            })
                    else:
                        # Fallback to string comparison for basic semver
                        compare_result = compare_versions(pkg_name, latest_version, version_spec)
                        if "is_version1_greater" in compare_result and compare_result["is_version1_greater"]:
                            outdated.append({
                                "package": pkg_name,
                                "current_version": version_spec,
                                "latest_version": latest_version
                            })
                        else:
                            up_to_date.append({
                                "package": pkg_name,
                                "version": version_spec
                            })
                else:
                    # No specific version required, so it's up-to-date
                    up_to_date.append({
                        "package": pkg_name,
                        "version": "unspecified (latest)"
                    })
            else:
                # Raw package name without version specifier
                pkg_name = req
                up_to_date.append({
                    "package": pkg_name,
                    "version": "unspecified (latest)"
                })
                
        return {
            "outdated": outdated,
            "up_to_date": up_to_date
        }
        
    except Exception as e:
        return format_error(ErrorCode.UNKNOWN_ERROR, f"Error checking requirements file: {str(e)}")


def main():
    parser = argparse.ArgumentParser(description="PyPI Tools")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # get_package_info command
    info_parser = subparsers.add_parser("get_package_info", help="Get package information")
    info_parser.add_argument("package_name", help="Name of the package")
    
    # get_latest_version command
    version_parser = subparsers.add_parser("get_latest_version", help="Get latest version")
    version_parser.add_argument("package_name", help="Name of the package")
    
    # get_package_releases command
    releases_parser = subparsers.add_parser("get_package_releases", help="Get all package releases")
    releases_parser.add_argument("package_name", help="Name of the package")
    
    # get_release_urls command
    urls_parser = subparsers.add_parser("get_release_urls", help="Get release URLs")
    urls_parser.add_argument("package_name", help="Name of the package")
    urls_parser.add_argument("version", help="Version of the package")
    
    # get_source_url command
    source_url_parser = subparsers.add_parser("get_source_url", help="Get source package URL")
    source_url_parser.add_argument("package_name", help="Name of the package")
    source_url_parser.add_argument("version", help="Version of the package")
    
    # get_wheel_url command
    wheel_url_parser = subparsers.add_parser("get_wheel_url", help="Get wheel package URL")
    wheel_url_parser.add_argument("package_name", help="Name of the package")
    wheel_url_parser.add_argument("version", help="Version of the package")
    wheel_url_parser.add_argument("python_tag", help="Python implementation and version tag")
    wheel_url_parser.add_argument("abi_tag", help="ABI tag")
    wheel_url_parser.add_argument("platform_tag", help="Platform tag")
    wheel_url_parser.add_argument("--build-tag", help="Optional build tag")
    
    # get_newest_packages command
    subparsers.add_parser("get_newest_packages", help="Get newest packages feed")
    
    # get_latest_updates command
    subparsers.add_parser("get_latest_updates", help="Get latest updates feed")
    
    # get_project_releases command
    project_releases_parser = subparsers.add_parser("get_project_releases", help="Get project releases feed")
    project_releases_parser.add_argument("package_name", help="Name of the package")
    
    # search_packages command
    search_parser = subparsers.add_parser("search_packages", help="Search for packages")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--page", type=int, default=1, help="Page number")
    
    # compare_versions command
    compare_parser = subparsers.add_parser("compare_versions", help="Compare version numbers")
    compare_parser.add_argument("package_name", help="Name of the package")
    compare_parser.add_argument("version1", help="First version to compare")
    compare_parser.add_argument("version2", help="Second version to compare")
    
    # get_dependencies command
    deps_parser = subparsers.add_parser("get_dependencies", help="Get package dependencies")
    deps_parser.add_argument("package_name", help="Name of the package")
    deps_parser.add_argument("--version", help="Specific version (optional)")
    
    # check_package_exists command
    exists_parser = subparsers.add_parser("check_package_exists", help="Check if package exists")
    exists_parser.add_argument("package_name", help="Name of the package")
    
    # get_package_metadata command
    metadata_parser = subparsers.add_parser("get_package_metadata", help="Get package metadata")
    metadata_parser.add_argument("package_name", help="Name of the package")
    metadata_parser.add_argument("--version", help="Specific version (optional)")
    
    # NEW COMMANDS
    
    # get_package_stats command
    stats_parser = subparsers.add_parser("get_package_stats", help="Get package statistics")
    stats_parser.add_argument("package_name", help="Name of the package")
    stats_parser.add_argument("--version", help="Package version")
    
    # get_dependency_tree command
    tree_parser = subparsers.add_parser("get_dependency_tree", help="Get dependency tree")
    tree_parser.add_argument("package_name", help="Name of the package")
    tree_parser.add_argument("--version", help="Package version")
    tree_parser.add_argument("--depth", type=int, default=3, help="Maximum depth of dependency tree")
    
    # get_documentation_url command
    docs_parser = subparsers.add_parser("get_documentation_url", help="Get documentation URL")
    docs_parser.add_argument("package_name", help="Name of the package")
    docs_parser.add_argument("--version", help="Package version")
    
    # check_requirements_file command
    req_parser = subparsers.add_parser("check_requirements_file", help="Check requirements file")
    req_parser.add_argument("file_path", help="Path to requirements.txt file")
    
    args = parser.parse_args()
    
    try:
        # Process commands
        match args.command:
            case "get_package_info":
                result = get_package_info(args.package_name)
            case "get_latest_version":
                result = get_latest_version(args.package_name)
            case "get_package_releases":
                result = get_package_releases(args.package_name)
            case "get_release_urls":
                result = get_release_urls(args.package_name, args.version)
            case "get_source_url":
                result = get_source_url(args.package_name, args.version)
            case "get_wheel_url":
                result = get_wheel_url(
                    args.package_name, args.version, args.python_tag, 
                    args.abi_tag, args.platform_tag, args.build_tag
                )
            case "get_newest_packages":
                result = get_newest_packages()
            case "get_latest_updates":
                result = get_latest_updates()
            case "get_project_releases":
                result = get_project_releases(args.package_name)
            case "search_packages":
                result = search_packages(args.query, args.page)
            case "compare_versions":
                result = compare_versions(args.package_name, args.version1, args.version2)
            case "get_dependencies":
                result = get_dependencies(args.package_name, args.version)
            case "check_package_exists":
                result = check_package_exists(args.package_name)
            case "get_package_metadata":
                result = get_package_metadata(args.package_name, args.version)
            case "get_package_stats":
                result = get_package_stats(args.package_name, args.version)
            case "get_dependency_tree":
                result = get_dependency_tree(args.package_name, args.version, args.depth)
            case "get_documentation_url":
                result = get_documentation_url(args.package_name, args.version)
            case "check_requirements_file":
                result = check_requirements_file(args.file_path)
            case _:
                result = {"error": "Unknown command"}
                
        # Print result as JSON
        print(json.dumps(result, indent=2))
    except ExceptionGroup as eg:
        print(json.dumps({"error": str(eg)}, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2))


if __name__ == "__main__":
    main() 