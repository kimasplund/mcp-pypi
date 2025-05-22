"""
Type definitions for the MCP-PyPI client.
"""

from dataclasses import dataclass, field
import os
import sys
import tempfile
from typing import (
    Any, TypedDict, Dict, List,
    Optional, Set, Union, Literal, TypeVar, cast, 
    Awaitable, Callable, Protocol
)

# NotRequired was added in Python 3.11, import from typing_extensions for earlier versions
if sys.version_info >= (3, 11):
    from typing import NotRequired
else:
    from typing_extensions import NotRequired

# Type variables
T = TypeVar('T')

# Constants
USER_AGENT = "Mozilla/5.0 (compatible; MCP-PyPI/2.0; +https://asplund.kim)"
DEFAULT_CACHE_DIR = os.path.join(tempfile.gettempdir(), "pypi_mcp_cache")
DEFAULT_CACHE_TTL = 3600  # 1 hour
DEFAULT_CACHE_MAX_SIZE = 100 * 1024 * 1024  # 100 MB
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0  # Base delay for exponential backoff

# Error codes for standardized responses
class ErrorCode:
    NOT_FOUND = "not_found"
    INVALID_INPUT = "invalid_input"
    NETWORK_ERROR = "network_error"
    PARSE_ERROR = "parse_error"
    FILE_ERROR = "file_error"
    PERMISSION_ERROR = "permission_error"
    UNKNOWN_ERROR = "unknown_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    TIMEOUT_ERROR = "timeout_error"
    MISSING_DEPENDENCY = "missing_dependency"

# Helper function for formatting errors - moved here to break circular import
def format_error(code: str, message: str) -> "ErrorResult":
    """Format error response according to MCP standards."""
    return {"error": {"code": code, "message": message}}

# Configuration dataclass
@dataclass
class PyPIClientConfig:
    """Configuration class for PyPI client."""
    cache_dir: str = field(default_factory=lambda: os.environ.get('PYPI_CACHE_DIR', DEFAULT_CACHE_DIR))
    cache_ttl: int = field(default_factory=lambda: int(os.environ.get('PYPI_CACHE_TTL', DEFAULT_CACHE_TTL)))
    cache_max_size: int = field(default_factory=lambda: int(os.environ.get('PYPI_CACHE_MAX_SIZE', DEFAULT_CACHE_MAX_SIZE)))
    user_agent: str = field(default_factory=lambda: os.environ.get('PYPI_USER_AGENT', USER_AGENT))
    max_retries: int = field(default_factory=lambda: int(os.environ.get('PYPI_MAX_RETRIES', DEFAULT_MAX_RETRIES)))
    retry_delay: float = field(default_factory=lambda: float(os.environ.get('PYPI_RETRY_DELAY', DEFAULT_RETRY_DELAY)))
    timeout: float = field(default_factory=lambda: float(os.environ.get('PYPI_TIMEOUT', 30.0)))

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

# Protocols for dependency injection
class CacheProtocol(Protocol):
    """Protocol for cache implementations."""
    async def get(self, key: str) -> Optional[Dict[str, Any]]: ...
    async def set(self, key: str, data: Dict[str, Any], etag: Optional[str] = None) -> None: ...
    async def get_etag(self, key: str) -> Optional[str]: ...
    
class HTTPClientProtocol(Protocol):
    """Protocol for HTTP client implementations."""
    async def fetch(self, url: str, method: str = "GET") -> Dict[str, Any]: ...
