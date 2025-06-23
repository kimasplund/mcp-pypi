"""
Tests for the PackageStatsService class.
"""

import datetime
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_pypi.core.stats import PackageStatsService
from mcp_pypi.core.models import ErrorCode, format_error


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client for testing."""
    client = MagicMock()
    # Make fetch an AsyncMock to handle awaits
    client.fetch = AsyncMock()
    return client


@pytest.fixture
def stats_service(mock_http_client):
    """Create a stats service with a mock HTTP client."""
    return PackageStatsService(mock_http_client)


@pytest.mark.asyncio
async def test_get_package_stats_success(stats_service, mock_http_client):
    """Test getting package stats with a successful response."""
    # Mock HTTP responses
    mock_overall_response = {
        "data": [
            {"category": "last_day", "downloads": 1000},
            {"category": "last_week", "downloads": 7000},
            {"category": "last_month", "downloads": 30000},
        ]
    }

    mock_detailed_response = {
        "data": [
            {"date": datetime.date.today().strftime("%Y-%m-%d"), "downloads": 1000},
            {
                "date": (datetime.date.today() - datetime.timedelta(days=1)).strftime(
                    "%Y-%m-%d"
                ),
                "downloads": 1100,
            },
            {
                "date": (datetime.date.today() - datetime.timedelta(days=6)).strftime(
                    "%Y-%m-%d"
                ),
                "downloads": 1200,
            },
            {
                "date": (datetime.date.today() - datetime.timedelta(days=29)).strftime(
                    "%Y-%m-%d"
                ),
                "downloads": 1300,
            },
        ]
    }

    mock_http_client.fetch.side_effect = [mock_overall_response, mock_detailed_response]

    # Call the method
    result = await stats_service.get_package_stats("test-package")

    # Verify
    assert "downloads" in result
    assert "last_day" in result
    assert "last_week" in result
    assert "last_month" in result

    # Check that the correct URLs were called
    mock_http_client.fetch.assert_any_call(
        "https://pypistats.org/api/packages/test-package/overall"
    )

    # Check that the aggregated stats are correct
    assert result["last_day"] >= 1000
    assert result["last_week"] >= 1000 + 1100 + 1200
    assert result["last_month"] >= 1000 + 1100 + 1200 + 1300


@pytest.mark.asyncio
async def test_get_package_stats_with_version(stats_service, mock_http_client):
    """Test getting package stats with a specific version."""
    # Mock HTTP responses
    mock_overall_response = {
        "data": [
            {"category": "last_day", "downloads": 500},
            {"category": "last_week", "downloads": 3500},
            {"category": "last_month", "downloads": 15000},
        ]
    }

    mock_detailed_response = {
        "data": [{"date": datetime.date.today().strftime("%Y-%m-%d"), "downloads": 500}]
    }

    mock_http_client.fetch.side_effect = [mock_overall_response, mock_detailed_response]

    # Call the method
    result = await stats_service.get_package_stats("test-package", version="1.0.0")

    # Verify
    assert "downloads" in result

    # Check that the correct URLs were called with version
    mock_http_client.fetch.assert_any_call(
        "https://pypistats.org/api/packages/test-package/overall"
    )
    mock_http_client.fetch.assert_any_call(
        "https://pypistats.org/api/packages/test-package/python_major?version=1.0.0"
    )


@pytest.mark.asyncio
async def test_get_package_stats_http_error(stats_service, mock_http_client):
    """Test error handling when HTTP request fails."""
    # Mock HTTP error response with proper format
    error_response = format_error(ErrorCode.NOT_FOUND, "Not Found")
    mock_http_client.fetch.return_value = error_response

    # Call the method
    result = await stats_service.get_package_stats("nonexistent-package")

    # Verify error is propagated
    assert "error" in result
    assert result["error"]["code"] == ErrorCode.NOT_FOUND


@pytest.mark.asyncio
async def test_get_package_stats_invalid_json(stats_service, mock_http_client):
    """Test error handling with invalid JSON response."""
    # Mock raw invalid JSON response
    mock_http_client.fetch.return_value = {
        "raw_data": "invalid json data",
        "content_type": "application/json",
    }

    # Call the method
    result = await stats_service.get_package_stats("test-package")

    # Verify parsing error
    assert "error" in result
    assert result["error"]["code"] == ErrorCode.PARSE_ERROR


@pytest.mark.asyncio
async def test_get_package_stats_wrong_content_type(stats_service, mock_http_client):
    """Test error handling with wrong content type."""
    # Mock response with wrong content type
    mock_http_client.fetch.return_value = {
        "raw_data": "<html>Not JSON</html>",
        "content_type": "text/html",
    }

    # Call the method
    result = await stats_service.get_package_stats("test-package")

    # Verify content type error
    assert "error" in result
    assert result["error"]["code"] == ErrorCode.PARSE_ERROR
    assert "Unexpected content type" in result["error"]["message"]


@pytest.mark.asyncio
async def test_get_package_stats_exception(stats_service, mock_http_client):
    """Test error handling when an exception occurs."""
    # Make HTTP client raise an exception
    mock_http_client.fetch.side_effect = Exception("Test exception")

    # Call the method
    result = await stats_service.get_package_stats("test-package")

    # Verify unknown error
    assert "error" in result
    assert result["error"]["code"] == ErrorCode.UNKNOWN_ERROR
    assert "Test exception" in result["error"]["message"]


@pytest.mark.asyncio
async def test_get_package_stats_value_error(stats_service, mock_http_client):
    """Test error handling with ValueError."""
    # Make sanitize_package_name raise a ValueError
    with patch("mcp_pypi.core.stats.sanitize_package_name") as mock_sanitize:
        mock_sanitize.side_effect = ValueError("Invalid package name")

        # Call the method
        result = await stats_service.get_package_stats("invalid-package")

        # Verify input validation error
        assert "error" in result
        assert result["error"]["code"] == ErrorCode.INVALID_INPUT
        assert "Invalid package name" in result["error"]["message"]


@pytest.mark.asyncio
async def test_get_package_stats_fallback_to_synthetic(stats_service, mock_http_client):
    """Test fallback to synthetic stats when processing fails."""
    # Mock response with valid but incomplete data
    mock_http_client.fetch.side_effect = [
        {"data": []},  # Empty overall data
        {"data": []},  # Empty detailed data
    ]

    # Call the method
    result = await stats_service.get_package_stats("test-package")

    # Verify we got synthetic data
    assert "downloads" in result
    assert "last_day" in result
    assert "last_week" in result
    assert "last_month" in result

    # Verify at least 1 month of data
    assert len(result["downloads"]) > 0


def test_generate_synthetic_stats(stats_service):
    """Test synthetic stats generation directly."""
    # Call the method
    result = stats_service._generate_synthetic_stats("test-package", periods=3)

    # Verify structure
    assert "downloads" in result
    assert "last_day" in result
    assert "last_week" in result
    assert "last_month" in result

    # Verify correct number of periods
    assert len(result["downloads"]) == 3

    # Verify decreasing trend in historical data
    months = sorted(result["downloads"].keys(), reverse=True)
    assert result["downloads"][months[0]] > result["downloads"][months[1]]
    assert result["downloads"][months[1]] > result["downloads"][months[2]]


@pytest.mark.asyncio
async def test_get_package_stats_handle_raw_json_data(stats_service, mock_http_client):
    """Test handling raw JSON data in HTTP response."""
    # Mock raw JSON responses
    overall_json = json.dumps({"data": [{"category": "last_day", "downloads": 1000}]})

    detailed_json = json.dumps(
        {
            "data": [
                {"date": datetime.date.today().strftime("%Y-%m-%d"), "downloads": 1000}
            ]
        }
    )

    mock_http_client.fetch.side_effect = [
        {"raw_data": overall_json, "content_type": "application/json"},
        {"raw_data": detailed_json, "content_type": "application/json"},
    ]

    # Call the method
    result = await stats_service.get_package_stats("test-package")

    # Verify
    assert "downloads" in result
    assert "last_day" in result
    assert result["last_day"] >= 1000
