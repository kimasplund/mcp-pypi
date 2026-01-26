"""
Core client for interacting with PyPI.

This module provides the PyPIClient class and all related types for working
with the PyPI API. The client is composed of multiple operation mixins that
provide different categories of functionality.
"""

# Re-export the main client class
from mcp_pypi.core.client import PyPIClient

# Re-export all types from models for backward compatibility
from mcp_pypi.core.models import (
    BatchVulnerabilityResult,
    CacheProtocol,
    DEFAULT_CACHE_DIR,
    DEFAULT_CACHE_MAX_SIZE,
    DEFAULT_CACHE_TTL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY,
    DependenciesResult,
    Dependency,
    DependencyTreeResult,
    DocumentationResult,
    ErrorCode,
    ErrorDict,
    ErrorResult,
    ExistsResult,
    FeedItem,
    HTTPClientProtocol,
    MetadataResult,
    PackageInfo,
    PackageMetadata,
    PackageRequirement,
    PackageRequirementsResult,
    PackagesFeed,
    PaginationInfo,
    PyPIClientConfig,
    ReleasesFeed,
    ReleasesInfo,
    SearchResult,
    StatsResult,
    TreeNode,
    UpdatesFeed,
    UrlResult,
    UrlsInfo,
    USER_AGENT,
    VersionComparisonResult,
    VersionInfo,
    format_error,
)

# Re-export cache and http for direct access
from mcp_pypi.core.cache import AsyncCacheManager
from mcp_pypi.core.http import AsyncHTTPClient
from mcp_pypi.core.stats import PackageStatsService

# Define what gets exported with `from mcp_pypi.core import *`
__all__ = [
    # Main client
    "PyPIClient",
    # Configuration
    "PyPIClientConfig",
    # Constants
    "DEFAULT_CACHE_DIR",
    "DEFAULT_CACHE_MAX_SIZE",
    "DEFAULT_CACHE_TTL",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_RETRY_DELAY",
    "USER_AGENT",
    # Error handling
    "ErrorCode",
    "ErrorDict",
    "ErrorResult",
    "format_error",
    # Result types
    "BatchVulnerabilityResult",
    "DependenciesResult",
    "Dependency",
    "DependencyTreeResult",
    "DocumentationResult",
    "ExistsResult",
    "FeedItem",
    "MetadataResult",
    "PackageInfo",
    "PackageMetadata",
    "PackageRequirement",
    "PackageRequirementsResult",
    "PackagesFeed",
    "PaginationInfo",
    "ReleasesFeed",
    "ReleasesInfo",
    "SearchResult",
    "StatsResult",
    "TreeNode",
    "UpdatesFeed",
    "UrlResult",
    "UrlsInfo",
    "VersionComparisonResult",
    "VersionInfo",
    # Protocols
    "CacheProtocol",
    "HTTPClientProtocol",
    # Services
    "AsyncCacheManager",
    "AsyncHTTPClient",
    "PackageStatsService",
]
