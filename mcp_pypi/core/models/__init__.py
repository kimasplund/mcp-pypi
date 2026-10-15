"""
Type definitions for the MCP-PyPI client.
"""

import os
import tempfile
from dataclasses import dataclass, field
from typing import (
    Any,
    NotRequired,
    Protocol,
    TypedDict,
    TypeVar,
)

from mcp_pypi import __version__

# Type variables
T = TypeVar("T")

# Constants
USER_AGENT = f"mcp-pypi/{__version__} (+https://github.com/kimasplund/mcp-pypi)"
DEFAULT_CACHE_DIR = os.path.join(tempfile.gettempdir(), "pypi_mcp_cache")
DEFAULT_CACHE_TTL = 604800  # 1 week
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

    cache_dir: str = field(
        default_factory=lambda: os.environ.get("PYPI_CACHE_DIR", DEFAULT_CACHE_DIR)
    )
    cache_ttl: int = field(
        default_factory=lambda: int(os.environ.get("PYPI_CACHE_TTL", DEFAULT_CACHE_TTL))
    )
    cache_max_size: int = field(
        default_factory=lambda: int(os.environ.get("PYPI_CACHE_MAX_SIZE", DEFAULT_CACHE_MAX_SIZE))
    )
    user_agent: str = field(default_factory=lambda: os.environ.get("PYPI_USER_AGENT", USER_AGENT))
    max_retries: int = field(
        default_factory=lambda: int(os.environ.get("PYPI_MAX_RETRIES", DEFAULT_MAX_RETRIES))
    )
    retry_delay: float = field(
        default_factory=lambda: float(os.environ.get("PYPI_RETRY_DELAY", DEFAULT_RETRY_DELAY))
    )
    timeout: float = field(default_factory=lambda: float(os.environ.get("PYPI_TIMEOUT", 30.0)))
    vulnerability_cache_ttl: int = field(
        default_factory=lambda: int(
            os.environ.get("PYPI_VULNERABILITY_CACHE_TTL", 3600)  # 1 hour default
        )
    )
    cache_strategy: str = field(
        default_factory=lambda: os.environ.get("PYPI_CACHE_STRATEGY", "hybrid")
    )


# TypedDict definitions for return types
class ErrorDict(TypedDict):
    code: str
    message: str


class ErrorResult(TypedDict):
    error: ErrorDict


class PackageInfo(TypedDict):
    error: NotRequired[ErrorDict]
    info: NotRequired[dict[str, Any]]
    releases: NotRequired[dict[str, list[dict[str, Any]]]]


class VersionInfo(TypedDict):
    error: NotRequired[ErrorDict]
    version: NotRequired[str]
    package_name: NotRequired[str]


class ReleasesInfo(TypedDict):
    error: NotRequired[ErrorDict]
    releases: NotRequired[list[str]]
    package_name: NotRequired[str]


class UrlsInfo(TypedDict):
    error: NotRequired[ErrorDict]
    urls: NotRequired[list[dict[str, Any]]]


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
    packages: NotRequired[list[FeedItem]]


class UpdatesFeed(TypedDict):
    error: NotRequired[ErrorDict]
    updates: NotRequired[list[FeedItem]]


class ReleasesFeed(TypedDict):
    error: NotRequired[ErrorDict]
    releases: NotRequired[list[FeedItem]]


class SearchResult(TypedDict):
    error: NotRequired[ErrorDict]
    search_url: NotRequired[str]
    results: NotRequired[list[dict[str, str]]]
    message: NotRequired[str]
    total: NotRequired[int]
    query: NotRequired[str]
    packages: NotRequired[list[Any]]
    # Pagination fields
    offset: NotRequired[int]
    limit: NotRequired[int]
    has_more: NotRequired[bool]


class VersionComparisonResult(TypedDict):
    error: NotRequired[ErrorDict]
    version1: NotRequired[str]
    version2: NotRequired[str]
    is_version1_greater: NotRequired[bool]
    is_version2_greater: NotRequired[bool]
    are_equal: NotRequired[bool]
    package_name: NotRequired[str]
    comparison: NotRequired[str]


class Dependency(TypedDict):
    name: str
    version_spec: str
    extras: NotRequired[list[str]]
    marker: NotRequired[str | None]


class DependenciesResult(TypedDict):
    error: NotRequired[ErrorDict]
    dependencies: NotRequired[list[Dependency]]
    package: NotRequired[str]
    version: NotRequired[str]
    install_requires: NotRequired[list[str]]
    extras_require: NotRequired[dict[str, list[str]]]


class ExistsResult(TypedDict):
    error: NotRequired[ErrorDict]
    exists: NotRequired[bool]
    package_name: NotRequired[str]


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
    error: NotRequired[ErrorDict]
    metadata: NotRequired[PackageMetadata]
    package_name: NotRequired[str]
    version: NotRequired[str]


class StatsResult(TypedDict):
    error: NotRequired[ErrorDict]
    downloads: NotRequired[dict[str, int]]
    last_month: NotRequired[int]
    last_week: NotRequired[int]
    last_day: NotRequired[int]
    package_name: NotRequired[str]


class TreeNode(TypedDict):
    name: str
    version: str | None
    dependencies: list["TreeNode"]
    cycle: NotRequired[bool]


class DependencyTreeResult(TypedDict):
    error: NotRequired[ErrorDict]
    tree: NotRequired[TreeNode]
    flat_list: NotRequired[list[str]]
    visualization_url: NotRequired[str | None]
    package: NotRequired[str]
    version: NotRequired[str]


class DocumentationResult(TypedDict):
    error: NotRequired[ErrorDict]
    docs_url: NotRequired[str]
    summary: NotRequired[str]
    package_name: NotRequired[str]
    documentation_url: NotRequired[str | None]


class PackageRequirement(TypedDict):
    package: str
    current_version: str
    latest_version: NotRequired[str]
    constraint: NotRequired[str]


class PackageRequirementsResult(TypedDict):
    error: NotRequired[ErrorDict]
    file_path: NotRequired[str]
    requirements: NotRequired[list[PackageRequirement]]
    outdated: NotRequired[list[PackageRequirement]]
    up_to_date: NotRequired[list[PackageRequirement]]


class BatchVulnerabilityResult(TypedDict):
    """Result from batch vulnerability check."""

    results: dict[str, dict[str, Any]]  # Maps "pkg:version" to vulnerability data
    total_packages: int
    vulnerable_count: int
    cached_count: int
    queried_count: int
    errors: NotRequired[list[dict[str, str]]]


class PaginationInfo(TypedDict):
    """Pagination metadata for list responses."""

    offset: int
    limit: int
    total: int
    has_more: bool


# Protocols for dependency injection
class CacheProtocol(Protocol):
    """Protocol for cache implementations."""

    async def get(self, key: str) -> dict[str, Any] | None: ...
    async def set(self, key: str, data: dict[str, Any], etag: str | None = None) -> None: ...
    async def get_etag(self, key: str) -> str | None: ...


class HTTPClientProtocol(Protocol):
    """Protocol for HTTP client implementations."""

    async def fetch(self, url: str, method: str = "GET") -> dict[str, Any]: ...
