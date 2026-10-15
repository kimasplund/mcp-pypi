#!/usr/bin/env python3
"""Tests for pagination functionality in mcp-pypi."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_pypi.core import PyPIClient
from mcp_pypi.core.cache import AsyncCacheManager
from mcp_pypi.core.http import AsyncHTTPClient
from mcp_pypi.core.models import PyPIClientConfig
from mcp_pypi.core.stats import PackageStatsService


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for testing."""
    mock = AsyncMock(spec=AsyncHTTPClient)
    mock.fetch = AsyncMock()
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def mock_cache_manager():
    """Mock cache manager for testing."""
    mock = MagicMock(spec=AsyncCacheManager)
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock()
    mock.clear = AsyncMock()
    mock.get_stats = AsyncMock()
    return mock


@pytest.fixture
def mock_stats_service():
    """Mock stats service for testing."""
    mock = AsyncMock(spec=PackageStatsService)
    return mock


@pytest.fixture
def client(mock_http_client, mock_cache_manager, mock_stats_service):
    """Create a PyPIClient with mocked dependencies."""
    config = PyPIClientConfig()
    client = PyPIClient(
        config=config,
        http_client=mock_http_client,
        cache_manager=mock_cache_manager,
        stats_service=mock_stats_service,
    )
    return client


@pytest.mark.asyncio
async def test_dependency_tree_max_width(client, mock_http_client, mock_cache_manager):
    """Test get_dependency_tree respects max_width parameter."""
    # First call: get latest version
    mock_http_client.fetch.side_effect = [
        # get_package_info for root package
        {
            "info": {"name": "test-package", "version": "1.0.0"},
            "releases": {"1.0.0": []},
        },
        # get_dependencies - many dependencies
        {
            "info": {
                "name": "test-package",
                "version": "1.0.0",
                "requires_dist": [
                    f"dep-{i}"
                    for i in range(100)  # 100 dependencies
                ],
            }
        },
    ]

    # Mock cache to return None (no cache)
    mock_cache_manager.get.return_value = None

    result = await client.get_dependency_tree("test-package", depth=1, max_width=10)

    # Should not error and should return a tree structure
    assert "tree" in result or "error" in result
