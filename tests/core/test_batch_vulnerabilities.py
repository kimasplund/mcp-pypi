#!/usr/bin/env python3
"""Tests for batch vulnerability checking functionality."""

import json
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
async def test_check_vulnerabilities_batch_basic(client, mock_http_client, mock_cache_manager):
    """Test basic batch vulnerability check."""
    # Mock the OSV batch API response
    mock_http_client.fetch.return_value = {
        "results": [
            {"vulns": []},  # requests - no vulnerabilities
            {
                "vulns": [
                    {
                        "id": "GHSA-test-1234",
                        "summary": "Test vulnerability",
                        "database_specific": {"severity": "HIGH"},
                        "affected": [
                            {
                                "package": {"name": "flask", "ecosystem": "PyPI"},
                                "ranges": [{"events": [{"introduced": "1.0.0"}, {"fixed": "2.0.0"}]}],
                            }
                        ],
                        "aliases": ["CVE-2021-1234"],
                    }
                ]
            },  # flask - 1 vulnerability
        ]
    }

    packages = [("requests", "2.28.0"), ("flask", "1.5.0")]
    result = await client.check_vulnerabilities_batch(packages)

    assert result["total_packages"] == 2
    assert result["queried_count"] == 2
    assert result["cached_count"] == 0
    # Check that at least one package was checked
    assert "results" in result


@pytest.mark.asyncio
async def test_check_vulnerabilities_batch_with_cache(client, mock_http_client, mock_cache_manager):
    """Test batch vulnerability check uses cache."""
    # Mock cache returning a cached result for requests
    cached_result = {
        "package": "requests",
        "version": "2.28.0",
        "vulnerable": False,
        "total_vulnerabilities": 0,
        "critical_count": 0,
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "vulnerabilities": [],
    }

    async def cache_get(key):
        if "requests" in key:
            return cached_result
        return None

    mock_cache_manager.get = AsyncMock(side_effect=cache_get)

    # Mock OSV response for flask only
    mock_http_client.fetch.return_value = {"results": [{"vulns": []}]}

    packages = [("requests", "2.28.0"), ("flask", "2.0.0")]
    result = await client.check_vulnerabilities_batch(packages)

    assert result["total_packages"] == 2
    assert result["cached_count"] == 1  # requests was cached
    assert result["queried_count"] == 1  # flask was queried


@pytest.mark.asyncio
async def test_check_vulnerabilities_batch_empty_list(client):
    """Test batch vulnerability check with empty list."""
    result = await client.check_vulnerabilities_batch([])

    assert result["total_packages"] == 0
    assert result["queried_count"] == 0
    assert result["vulnerable_count"] == 0


@pytest.mark.asyncio
async def test_check_vulnerabilities_batch_chunking(client, mock_http_client, mock_cache_manager):
    """Test that batch processing handles chunking correctly."""
    # Create a large batch response
    mock_http_client.fetch.return_value = {"results": [{"vulns": []} for _ in range(50)]}

    # Create 50 packages to check
    packages = [(f"package-{i}", "1.0.0") for i in range(50)]
    result = await client.check_vulnerabilities_batch(packages, batch_size=50)

    assert result["total_packages"] == 50
    assert result["queried_count"] == 50


@pytest.mark.asyncio
async def test_check_vulnerabilities_batch_error_handling(client, mock_http_client, mock_cache_manager):
    """Test batch vulnerability check handles API errors gracefully."""
    mock_http_client.fetch.return_value = {"error": "API rate limit exceeded"}

    packages = [("requests", "2.28.0")]
    result = await client.check_vulnerabilities_batch(packages)

    # Should return with errors list
    assert "errors" in result
    assert len(result["errors"]) > 0


@pytest.mark.asyncio
async def test_check_vulnerabilities_pagination(client, mock_http_client, mock_cache_manager):
    """Test check_vulnerabilities with pagination parameters."""
    # Mock the OSV response with multiple vulnerabilities
    mock_http_client.fetch.side_effect = [
        # First call: check_package_exists
        {"info": {"name": "test-package", "version": "1.0.0"}},
        # Second call: OSV API
        {
            "vulns": [
                {
                    "id": f"GHSA-test-{i}",
                    "summary": f"Vulnerability {i}",
                    "database_specific": {"severity": "MEDIUM"},
                    "affected": [
                        {
                            "package": {"name": "test-package", "ecosystem": "PyPI"},
                            "ranges": [{"events": [{"introduced": "0.1.0"}]}],
                        }
                    ],
                    "aliases": [],
                }
                for i in range(25)  # 25 vulnerabilities
            ]
        },
    ]

    # Get first 10 vulnerabilities
    result = await client.check_vulnerabilities("test-package", limit=10, offset=0)

    assert result["limit"] == 10
    assert result["offset"] == 0
    assert result["total_vulnerabilities"] == 25
    assert len(result["vulnerabilities"]) <= 10
    assert result["has_more"] == True


@pytest.mark.asyncio
async def test_check_vulnerabilities_pagination_last_page(client, mock_http_client, mock_cache_manager):
    """Test check_vulnerabilities pagination on last page."""
    mock_http_client.fetch.side_effect = [
        {"info": {"name": "test-package", "version": "1.0.0"}},
        {
            "vulns": [
                {
                    "id": f"GHSA-test-{i}",
                    "summary": f"Vulnerability {i}",
                    "database_specific": {"severity": "LOW"},
                    "affected": [
                        {
                            "package": {"name": "test-package", "ecosystem": "PyPI"},
                            "ranges": [{"events": [{"introduced": "0.1.0"}]}],
                        }
                    ],
                    "aliases": [],
                }
                for i in range(5)  # Only 5 vulnerabilities
            ]
        },
    ]

    # Request offset=3, limit=5, but only 5 total
    result = await client.check_vulnerabilities("test-package", limit=5, offset=3)

    assert result["limit"] == 5
    assert result["offset"] == 3
    assert result["has_more"] == False
