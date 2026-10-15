"""
Main PyPI client that composes all operation mixins.
"""

import difflib
import logging
from pathlib import Path
from typing import cast

from mcp_pypi.core.cache import AsyncCacheManager
from mcp_pypi.core.dependency_ops import DependencyOpsMixin
from mcp_pypi.core.feed_ops import FeedOpsMixin
from mcp_pypi.core.http import AsyncHTTPClient
from mcp_pypi.core.models import ErrorCode, PyPIClientConfig, StatsResult, format_error
from mcp_pypi.core.package_ops import PackageOpsMixin
from mcp_pypi.core.search_index import NameIndex, Popularity, normalize
from mcp_pypi.core.search_ops import SearchOpsMixin
from mcp_pypi.core.stats import PackageStatsService
from mcp_pypi.core.vulnerability_ops import VulnerabilityOpsMixin
from mcp_pypi.utils.sanitize import sanitize_package_name

logger = logging.getLogger("mcp-pypi.client")


class PyPIClient(
    PackageOpsMixin,
    DependencyOpsMixin,
    VulnerabilityOpsMixin,
    FeedOpsMixin,
    SearchOpsMixin,
):
    """Client for interacting with PyPI.

    This class composes multiple operation mixins to provide a full-featured
    PyPI client with the following capabilities:

    - Package operations (info, versions, releases, metadata)
    - Dependency operations (dependencies, dependency tree)
    - Vulnerability checking (OSV API integration)
    - RSS feed operations (newest packages, updates, releases)
    - Search and comparison operations
    """

    def __init__(
        self,
        config: PyPIClientConfig | None = None,
        cache_manager: AsyncCacheManager | None = None,
        http_client: AsyncHTTPClient | None = None,
        stats_service: PackageStatsService | None = None,
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

        self.name_index = NameIndex(self.http, Path(self.config.cache_dir))
        self.popularity = Popularity(self.http, Path(self.config.cache_dir))

    def set_user_agent(self, user_agent: str) -> None:
        """Set a custom User-Agent for all subsequent requests.

        Args:
            user_agent: The User-Agent string to use for PyPI requests
        """
        self.config.user_agent = user_agent
        logger.info(f"User-Agent updated to: {user_agent}")

    async def suggest_names(self, name: str, limit: int = 3) -> list[str]:
        """Popular package names close to `name` (for "did you mean" hints)."""
        popular = await self.popularity.downloads()
        if not popular:
            return []
        return difflib.get_close_matches(normalize(name), list(popular), n=limit, cutoff=0.85)

    async def close(self) -> None:
        """Close the client and release resources."""
        await self.http.close()

    async def get_package_stats(self, package_name: str) -> StatsResult:
        """Get download statistics for a package."""
        try:
            sanitized_name = sanitize_package_name(package_name)

            # Check if package exists first
            exists_result = await self.check_package_exists(sanitized_name)
            if isinstance(exists_result, dict) and "error" in exists_result:
                return cast(StatsResult, exists_result)

            if not exists_result.get("exists", False):
                return cast(
                    StatsResult,
                    format_error(ErrorCode.NOT_FOUND, f"Package '{sanitized_name}' not found"),
                )

            # Use the stats service to get real download stats
            return await self.stats.get_package_stats(sanitized_name)

        except ValueError as e:
            return cast(StatsResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Error getting package stats: {e}")
            return cast(StatsResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))
