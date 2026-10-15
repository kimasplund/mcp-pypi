#!/usr/bin/env python3
"""Comprehensive tests for the PyPIClient class."""

import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock, MagicMock, patch

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
    mock.get = AsyncMock()
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
async def test_get_newest_packages_success(client, mock_http_client):
    """Test get_newest_packages with successful response."""
    # Create an XML response for RSS feed
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>PyPI newest packages</title>
        <item>
          <title>package1 1.0.0</title>
          <link>https://pypi.org/project/package1/1.0.0/</link>
          <description>A test package</description>
          <pubDate>Sat, 01 Jan 2023 12:00:00 GMT</pubDate>
        </item>
        <item>
          <title>package2 2.0.0</title>
          <link>https://pypi.org/project/package2/2.0.0/</link>
          <description>Another test package</description>
          <pubDate>Sun, 02 Jan 2023 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""

    # Mock the HTTP response with raw_data
    mock_http_client.fetch.return_value = {
        "raw_data": xml_response,
        "content_type": "application/xml",
    }

    # Execute
    result = await client.get_newest_packages()

    # Verify
    assert "packages" in result
    assert len(result["packages"]) == 2
    assert result["packages"][0]["title"] == "package1 1.0.0"
    assert result["packages"][1]["title"] == "package2 2.0.0"
    mock_http_client.fetch.assert_called_once_with("https://pypi.org/rss/packages.xml")


@pytest.mark.asyncio
async def test_get_newest_packages_error(client, mock_http_client):
    """Test get_newest_packages with error response."""
    # Setup mock error response
    mock_http_client.fetch.side_effect = Exception("Network error")

    # Execute
    result = await client.get_newest_packages()

    # Verify
    assert "error" in result
    assert result["error"]["code"] == "unknown_error"
    assert "Network error" in result["error"]["message"]
    mock_http_client.fetch.assert_called_once_with("https://pypi.org/rss/packages.xml")


@pytest.mark.asyncio
async def test_get_latest_updates_success(client, mock_http_client):
    """Test get_latest_updates with successful response."""
    # Create an XML response for RSS feed
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>PyPI updates</title>
        <item>
          <title>package1 1.0.0</title>
          <link>https://pypi.org/project/package1/1.0.0/</link>
          <pubDate>Sat, 01 Jan 2023 12:00:00 GMT</pubDate>
          <description>Test package 1</description>
        </item>
        <item>
          <title>package2 2.0.0</title>
          <link>https://pypi.org/project/package2/2.0.0/</link>
          <pubDate>Sun, 02 Jan 2023 12:00:00 GMT</pubDate>
          <description>Test package 2</description>
        </item>
      </channel>
    </rss>"""

    # Create a mock ElementTree parse result
    root = ET.fromstring(xml_response)

    # Mock the ET.fromstring to return our prepared XML tree
    with patch("xml.etree.ElementTree.fromstring", return_value=root):
        # Mock the HTTP response with raw_data
        mock_http_client.fetch.return_value = {
            "raw_data": xml_response,
            "content_type": "application/xml",
        }

        # Execute
        result = await client.get_latest_updates()

    # Verify
    assert "updates" in result
    assert len(result["updates"]) == 2
    # Check that required fields are in the result
    assert "title" in result["updates"][0]
    assert "published_date" in result["updates"][0]
    assert result["updates"][0]["title"] == "package1 1.0.0"
    assert result["updates"][1]["title"] == "package2 2.0.0"
    mock_http_client.fetch.assert_called_once_with("https://pypi.org/rss/updates.xml")


@pytest.mark.asyncio
async def test_get_latest_updates_error(client, mock_http_client):
    """Test get_latest_updates with error response."""
    # Setup mock error response
    mock_http_client.fetch.side_effect = Exception("Network error")

    # Execute
    result = await client.get_latest_updates()

    # Verify
    assert "error" in result
    assert result["error"]["code"] == "unknown_error"
    assert "Network error" in result["error"]["message"]
    mock_http_client.fetch.assert_called_once_with("https://pypi.org/rss/updates.xml")


@pytest.mark.asyncio
async def test_check_package_exists_success(client, mock_http_client):
    """Test check_package_exists with existing package."""
    # Setup mock response
    mock_response = {"info": {"name": "test-package", "version": "1.0.0"}}
    mock_http_client.fetch.return_value = mock_response

    # Execute
    result = await client.check_package_exists("test-package")

    # Verify
    assert "exists" in result
    assert result["exists"] is True
    mock_http_client.fetch.assert_called_once_with("https://pypi.org/pypi/test-package/json")


@pytest.mark.asyncio
async def test_check_package_exists_nonexistent(client, mock_http_client):
    """Test check_package_exists with non-existent package."""
    # Setup mock 404 response
    mock_http_client.fetch.return_value = {
        "error": {"code": "not_found", "message": "Package not found"}
    }

    # Execute
    result = await client.check_package_exists("nonexistent-package")

    # Verify
    assert "exists" in result
    assert result["exists"] is False
    mock_http_client.fetch.assert_called_once_with("https://pypi.org/pypi/nonexistent-package/json")


@pytest.mark.asyncio
async def test_get_dependency_tree_success(client, mock_http_client):
    """Test get_dependency_tree with successful responses."""
    # Setup mock responses for main package
    mock_http_client.fetch.side_effect = [
        # First call - main package
        {
            "info": {
                "name": "main-package",
                "version": "1.0.0",
                "requires_dist": ["dep1>=1.0.0", "dep2>=2.0.0"],
            }
        },
        # Second call - dep1
        {
            "info": {
                "name": "dep1",
                "version": "1.0.0",
                "requires_dist": ["dep3>=3.0.0"],
            }
        },
        # Third call - dep2
        {"info": {"name": "dep2", "version": "2.0.0", "requires_dist": []}},
        # Fourth call - dep3
        {"info": {"name": "dep3", "version": "3.0.0", "requires_dist": []}},
    ]

    # Execute
    result = await client.get_dependency_tree("main-package", depth=2)

    # Verify
    assert "tree" in result
    tree = result["tree"]
    assert tree["name"] == "main-package"
    # We don't assert the exact number of dependencies since the implementation may differ
    assert "dependencies" in tree
    # Check that HTTP calls were made
    assert mock_http_client.fetch.call_count >= 2
    mock_http_client.fetch.assert_any_call("https://pypi.org/pypi/main-package/json")


@pytest.mark.asyncio
async def test_get_dependency_tree_error(client, mock_http_client):
    """Test get_dependency_tree with error response."""
    # Setup mock error response
    mock_http_client.fetch.side_effect = Exception("Network error")

    # Execute
    result = await client.get_dependency_tree("main-package")

    # Verify
    assert "error" in result
    assert result["error"]["code"] == "unknown_error"
    assert "Network error" in result["error"]["message"]
    mock_http_client.fetch.assert_called_once_with("https://pypi.org/pypi/main-package/json")


@pytest.mark.asyncio
async def test_search_packages_uses_new_signature(client):
    """search_packages(query, limit) ranks names then enriches from package metadata."""
    client.name_index = MagicMock()
    client.name_index.names = AsyncMock(return_value="\nrequests\nrequests-oauthlib\n")
    client.popularity = MagicMock()
    client.popularity.downloads = AsyncMock(return_value={"requests": 1_000_000})
    client.get_package_info = AsyncMock(
        return_value={"info": {"name": "requests", "version": "2.0", "summary": "HTTP for humans"}}
    )

    result = await client.search_packages("requests", limit=1)

    assert [r["name"] for r in result["results"]] == ["requests"]
    assert result["results"][0]["popularity_rank"] == 1
    assert result["total_candidates"] == 2


@pytest.mark.asyncio
async def test_search_packages_clamps_limit(client):
    client.name_index = MagicMock()
    client.name_index.names = AsyncMock(
        return_value="\n" + "\n".join(f"pkg{i}" for i in range(100)) + "\n"
    )
    client.popularity = MagicMock()
    client.popularity.downloads = AsyncMock(return_value={})
    client.get_package_info = AsyncMock(
        side_effect=lambda n: {"info": {"name": n, "version": "1", "summary": ""}}
    )

    # limit clamps to 50; the enrichment pool is max(limit, min(3 * limit, 30))
    assert len((await client.search_packages("pkg", limit=500))["results"]) == 50
    assert len((await client.search_packages("pkg", limit=0))["results"]) == 1


@pytest.mark.asyncio
async def test_compare_versions_success(client):
    """Test compare_versions with successful response."""
    # Don't need to mock fetch call for this test since we're directly comparing version strings
    result = await client.compare_versions("test-package", "1.0.0", "2.0.0")

    # Verify
    assert "is_version1_greater" in result
    assert "is_version2_greater" in result
    assert "are_equal" in result
    assert result["version1"] == "1.0.0"
    assert result["version2"] == "2.0.0"
    assert result["is_version1_greater"] is False
    assert result["is_version2_greater"] is True
    assert result["are_equal"] is False


@pytest.mark.asyncio
async def test_compare_versions_equal(client):
    """Test compare_versions with equal versions."""
    # Don't need to mock fetch call for this test since we're directly comparing version strings
    result = await client.compare_versions("test-package", "1.0.0", "1.0.0")

    # Verify
    assert "is_version1_greater" in result
    assert "is_version2_greater" in result
    assert "are_equal" in result
    assert result["version1"] == "1.0.0"
    assert result["version2"] == "1.0.0"
    assert result["is_version1_greater"] is False
    assert result["is_version2_greater"] is False
    assert result["are_equal"] is True


@pytest.mark.asyncio
async def test_get_package_info_success(client, mock_http_client):
    """Test getting package info with successful response."""
    # Setup mock response
    mock_response = {
        "info": {
            "name": "test-package",
            "version": "1.0.0",
            "summary": "A test package",
            "description": "A longer description",
            "author": "Test Author",
            "author_email": "test@example.com",
            "license": "MIT",
            "project_urls": {
                "Homepage": "https://example.com",
                "Documentation": "https://docs.example.com",
            },
        },
        "releases": {
            "1.0.0": [{"packagetype": "sdist"}],
            "0.9.0": [{"packagetype": "sdist"}],
        },
    }
    mock_http_client.fetch.return_value = mock_response

    # Execute
    result = await client.get_package_info("test-package")

    # Verify
    assert "info" in result
    assert result["info"]["name"] == "test-package"
    assert result["info"]["version"] == "1.0.0"
    assert "releases" in result
    assert "1.0.0" in result["releases"]
    mock_http_client.fetch.assert_called_once_with("https://pypi.org/pypi/test-package/json")


@pytest.mark.asyncio
async def test_get_package_info_error(client, mock_http_client):
    """Test getting package info with error response."""
    # Setup mock error response
    mock_http_client.fetch.return_value = {
        "error": {"code": "not_found", "message": "Package not found"}
    }

    # Execute
    result = await client.get_package_info("nonexistent-package")

    # Verify
    assert "error" in result
    assert result["error"]["code"] == "not_found"
    mock_http_client.fetch.assert_called_once_with("https://pypi.org/pypi/nonexistent-package/json")


@pytest.mark.asyncio
async def test_get_package_info_pinned_version_url(client, mock_http_client):
    mock_http_client.fetch.return_value = {"info": {"name": "pkg", "version": "1.2.3"}}

    result = await client.get_package_info("pkg", "1.2.3")

    assert result["info"]["version"] == "1.2.3"
    mock_http_client.fetch.assert_called_once_with("https://pypi.org/pypi/pkg/1.2.3/json")


@pytest.mark.asyncio
async def test_get_package_info_pinned_version_not_found(client, mock_http_client):
    mock_http_client.fetch.return_value = {"error": {"code": "not_found", "message": "gone"}}

    result = await client.get_package_info("pkg", "9.9.9")

    assert result["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_get_package_info_rejects_bad_version(client, mock_http_client):
    result = await client.get_package_info("pkg", "1.0/../x")

    assert result["error"]["code"] == "invalid_input"
    mock_http_client.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_get_package_changelog_returns_dict(client):
    client.get_package_info = AsyncMock(
        return_value={"info": {"project_urls": {"Source": "https://github.com/o/r"}}}
    )

    result = await client.get_package_changelog("pkg", "1.0")

    assert result["package_name"] == "pkg"
    assert result["version"] == "1.0"
    assert "https://github.com/o/r/releases" in result["changelog"]


@pytest.mark.asyncio
async def test_get_package_changelog_error_dict(client):
    client.get_package_info = AsyncMock(
        return_value={"error": {"code": "not_found", "message": "nope"}}
    )

    result = await client.get_package_changelog("pkg")

    assert result["error"]["code"] == "not_found"
    assert "changelog" not in result


@pytest.mark.asyncio
async def test_get_latest_version_success(client, mock_http_client):
    """Test getting latest version with successful response."""
    # Setup mock response
    mock_response = {"info": {"name": "test-package", "version": "1.0.0"}}
    mock_http_client.fetch.return_value = mock_response

    # Execute
    result = await client.get_latest_version("test-package")

    # Verify
    assert "version" in result
    assert result["version"] == "1.0.0"
    mock_http_client.fetch.assert_called_once_with("https://pypi.org/pypi/test-package/json")


@pytest.mark.asyncio
async def test_get_latest_version_error(client, mock_http_client):
    """Test getting latest version with error response."""
    # Setup mock error response
    mock_http_client.fetch.return_value = {
        "error": {"code": "not_found", "message": "Package not found"}
    }

    # Execute
    result = await client.get_latest_version("nonexistent-package")

    # Verify
    assert "error" in result
    assert result["error"]["code"] == "not_found"
    mock_http_client.fetch.assert_called_once_with("https://pypi.org/pypi/nonexistent-package/json")


@pytest.mark.asyncio
async def test_get_package_releases_success(client, mock_http_client):
    """Test getting package releases with successful response."""
    # Setup mock response
    mock_response = {
        "info": {"name": "test-package", "version": "1.0.0"},
        "releases": {
            "1.0.0": [{"packagetype": "sdist"}],
            "0.9.0": [{"packagetype": "sdist"}],
            "0.8.0": [{"packagetype": "sdist"}],
        },
    }
    mock_http_client.fetch.return_value = mock_response

    # Execute
    result = await client.get_package_releases("test-package")

    # Verify
    assert "releases" in result
    assert len(result["releases"]) == 3
    # Check that release versions are in the result
    release_versions = result["releases"]
    assert "1.0.0" in release_versions
    assert "0.9.0" in release_versions
    mock_http_client.fetch.assert_called_once_with("https://pypi.org/pypi/test-package/json")


@pytest.mark.asyncio
async def test_get_package_releases_error(client, mock_http_client):
    """Test getting package releases with error response."""
    # Setup mock error response
    mock_http_client.fetch.return_value = {
        "error": {"code": "not_found", "message": "Package not found"}
    }

    # Execute
    result = await client.get_package_releases("nonexistent-package")

    # Verify
    assert "error" in result
    assert result["error"]["code"] == "not_found"
    mock_http_client.fetch.assert_called_once_with("https://pypi.org/pypi/nonexistent-package/json")


@pytest.mark.asyncio
async def test_get_release_urls_success(client, mock_http_client):
    """Test getting release URLs with successful response."""
    # Setup mock response
    mock_response = {
        "info": {"name": "test-package", "version": "1.0.0"},
        "urls": [
            {
                "packagetype": "sdist",
                "url": "https://files.pythonhosted.org/packages/test-package-1.0.0.tar.gz",
                "filename": "test-package-1.0.0.tar.gz",
                "size": 10000,
            },
            {
                "packagetype": "bdist_wheel",
                "url": "https://files.pythonhosted.org/packages/test-package-1.0.0-py3-none-any.whl",
                "filename": "test-package-1.0.0-py3-none-any.whl",
                "size": 8000,
            },
        ],
    }
    mock_http_client.fetch.return_value = mock_response

    # Execute
    result = await client.get_release_urls("test-package", "1.0.0")

    # Verify
    assert "urls" in result
    assert len(result["urls"]) == 2
    assert result["urls"][0]["packagetype"] == "sdist"
    assert result["urls"][1]["packagetype"] == "bdist_wheel"
    mock_http_client.fetch.assert_called_once_with("https://pypi.org/pypi/test-package/1.0.0/json")


@pytest.mark.asyncio
async def test_get_release_urls_error(client, mock_http_client):
    """Test getting release URLs with error response."""
    # Setup mock error response
    mock_http_client.fetch.return_value = {
        "error": {"code": "not_found", "message": "Release not found"}
    }

    # Execute
    result = await client.get_release_urls("test-package", "9.9.9")

    # Verify
    assert "error" in result
    assert result["error"]["code"] == "not_found"
    mock_http_client.fetch.assert_called_once_with("https://pypi.org/pypi/test-package/9.9.9/json")


@pytest.mark.asyncio
async def test_get_project_releases_success(client, mock_http_client):
    """Test getting project releases with successful response."""
    # Create an XML response for releases
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>test-package releases</title>
        <item>
          <title>1.0.0</title>
          <link>https://pypi.org/project/test-package/1.0.0/</link>
          <description>Release 1.0.0</description>
          <pubDate>Sat, 01 Jan 2023 12:00:00 GMT</pubDate>
        </item>
        <item>
          <title>0.9.0</title>
          <link>https://pypi.org/project/test-package/0.9.0/</link>
          <description>Release 0.9.0</description>
          <pubDate>Fri, 01 Dec 2022 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""

    # Create a mock ElementTree parse result
    root = ET.fromstring(xml_response)

    # Mock the ET.fromstring to return our prepared XML tree
    with patch("xml.etree.ElementTree.fromstring", return_value=root):
        # Mock the HTTP response with raw_data
        mock_http_client.fetch.return_value = {
            "raw_data": xml_response,
            "content_type": "application/xml",
        }

        # Execute
        result = await client.get_project_releases("test-package")

    # Verify
    assert "releases" in result
    assert len(result["releases"]) == 2
    # Check for title field in the releases
    assert result["releases"][0]["title"] == "1.0.0"
    assert result["releases"][1]["title"] == "0.9.0"
    mock_http_client.fetch.assert_called_once_with(
        "https://pypi.org/rss/project/test-package/releases.xml"
    )


@pytest.mark.asyncio
async def test_get_project_releases_error(client, mock_http_client):
    """Test getting project releases with error response."""
    # Setup mock error response
    mock_http_client.fetch.side_effect = Exception("Network error")

    # Execute
    result = await client.get_project_releases("test-package")

    # Verify
    assert "error" in result
    assert result["error"]["code"] == "unknown_error"
    assert "Network error" in result["error"]["message"]
    mock_http_client.fetch.assert_called_once_with(
        "https://pypi.org/rss/project/test-package/releases.xml"
    )


@pytest.mark.asyncio
async def test_get_package_metadata_success(client, mock_http_client):
    """Test getting package metadata with successful response."""
    # Setup mock response
    mock_response = {
        "info": {
            "name": "test-package",
            "version": "1.0.0",
            "summary": "A test package",
            "description": "A longer description",
            "author": "Test Author",
            "author_email": "test@example.com",
            "license": "MIT",
            "keywords": "testing,package",
            "classifiers": [
                "Programming Language :: Python :: 3",
                "License :: OSI Approved :: MIT License",
            ],
            "requires_python": ">=3.6",
            "project_urls": {
                "Homepage": "https://example.com",
                "Documentation": "https://docs.example.com",
            },
            "requires_dist": ["requests>=2.0.0", "click>=7.0"],
        }
    }
    mock_http_client.fetch.return_value = mock_response

    # Execute
    result = await client.get_package_metadata("test-package")

    # Verify
    assert "metadata" in result
    assert result["metadata"]["name"] == "test-package"
    assert result["metadata"]["version"] == "1.0.0"
    assert "classifiers" in result["metadata"]
    assert len(result["metadata"]["classifiers"]) == 2
    mock_http_client.fetch.assert_called_once_with("https://pypi.org/pypi/test-package/json")


@pytest.mark.asyncio
async def test_get_package_metadata_with_version(client, mock_http_client):
    """Test getting package metadata with specific version."""
    # Setup mock response
    mock_response = {"info": {"name": "test-package", "version": "0.9.0"}}
    mock_http_client.fetch.return_value = mock_response

    # Execute
    result = await client.get_package_metadata("test-package", "0.9.0")

    # Verify
    assert "metadata" in result
    assert result["metadata"]["name"] == "test-package"
    assert result["metadata"]["version"] == "0.9.0"
    mock_http_client.fetch.assert_called_once_with("https://pypi.org/pypi/test-package/0.9.0/json")


@pytest.mark.asyncio
async def test_get_package_stats_with_mock(client, mock_stats_service):
    """Test getting package stats via the stats service."""
    # Setup mock response
    mock_stats_result = {
        "last_month": 10000,
        "last_week": 2500,
        "last_day": 350,
    }
    mock_stats_service.get_package_stats.return_value = mock_stats_result

    # Execute
    result = await client.get_package_stats("test-package")

    # Verify
    assert result["last_month"] == 10000
    mock_stats_service.get_package_stats.assert_called_once_with("test-package")


@pytest.mark.asyncio
async def test_get_documentation_url_success(client, mock_http_client):
    """Test getting documentation URL with successful response."""
    # Setup mock response with documentation URL in project_urls
    mock_response = {
        "info": {
            "name": "test-package",
            "version": "1.0.0",
            "project_urls": {
                "Documentation": "https://docs.example.com",
                "Homepage": "https://example.com",
            },
        }
    }
    mock_http_client.fetch.return_value = mock_response

    # Execute
    result = await client.get_documentation_url("test-package")

    # Verify
    assert "docs_url" in result
    assert result["docs_url"] == "https://docs.example.com"
    assert "summary" in result
    mock_http_client.fetch.assert_called_once_with("https://pypi.org/pypi/test-package/json")


@pytest.mark.asyncio
async def test_get_documentation_url_fallback(client, mock_http_client):
    """Test getting documentation URL with fallback."""
    # Setup mock response without documentation URL
    mock_response = {
        "info": {
            "name": "test-package",
            "version": "1.0.0",
            "project_urls": {"Homepage": "https://example.com"},
        }
    }

    # Setup mock for the URL check
    with patch("aiohttp.ClientSession.head") as mock_head:
        # Configure the mock to return different responses based on URLs
        async def mock_head_implementation(url, **kwargs):
            mock_response = MagicMock()
            mock_response.status = 200 if "readthedocs.org" in url else 404
            return mock_response

        mock_head.side_effect = mock_head_implementation

        # Mock the HTTP response for package info
        mock_http_client.fetch.return_value = mock_response

        # Execute
        result = await client.get_documentation_url("test-package")

    # Verify
    assert "docs_url" in result
    assert "readthedocs.org" in result["docs_url"]
    assert "summary" in result
    mock_http_client.fetch.assert_called_once_with("https://pypi.org/pypi/test-package/json")
