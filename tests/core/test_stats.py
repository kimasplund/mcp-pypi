"""Tests for the PackageStatsService class (real pypistats data only, no estimates)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_pypi.core.models import ErrorCode, format_error
from mcp_pypi.core.stats import PackageStatsService

RECENT_URL = "https://pypistats.org/api/packages/test-package/recent"


@pytest.fixture
def mock_http_client():
    client = MagicMock()
    client.fetch = AsyncMock()
    return client


@pytest.fixture
def stats_service(mock_http_client):
    return PackageStatsService(mock_http_client)


@pytest.mark.asyncio
async def test_recent_values_pass_through_exactly(stats_service, mock_http_client):
    mock_http_client.fetch.return_value = {
        "data": {"last_day": 11, "last_month": 3333, "last_week": 777},
        "package": "test-package",
        "type": "recent_downloads",
    }

    result = await stats_service.get_package_stats("test-package")

    assert result == {
        "package_name": "test-package",
        "last_day": 11,
        "last_week": 777,
        "last_month": 3333,
    }
    mock_http_client.fetch.assert_called_once_with(RECENT_URL)


@pytest.mark.asyncio
async def test_recent_raw_json_values_pass_through(stats_service, mock_http_client):
    body = json.dumps({"data": {"last_day": 0, "last_week": 5, "last_month": 9}})
    mock_http_client.fetch.return_value = {"raw_data": body, "content_type": "application/json"}

    result = await stats_service.get_package_stats("test-package")

    assert (result["last_day"], result["last_week"], result["last_month"]) == (0, 5, 9)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        {},
        {"data": {}},
        {"data": []},
        {"data": None},
        {"data": {"last_day": 1, "last_week": 2}},
        {"data": {"last_day": 1, "last_week": 2, "last_month": None}},
        {"data": {"last_day": "1", "last_week": 2, "last_month": 3}},
        {"data": [{"category": "without_mirrors", "date": "2026-01-01", "downloads": 5}]},
    ],
)
async def test_missing_or_malformed_data_is_parse_error_without_numbers(
    stats_service, mock_http_client, response
):
    mock_http_client.fetch.return_value = response

    result = await stats_service.get_package_stats("test-package")

    assert result["error"]["code"] == ErrorCode.PARSE_ERROR
    assert not {"last_day", "last_week", "last_month"} & set(result)


@pytest.mark.asyncio
async def test_invalid_json_is_parse_error(stats_service, mock_http_client):
    mock_http_client.fetch.return_value = {
        "raw_data": "invalid json data",
        "content_type": "application/json",
    }

    result = await stats_service.get_package_stats("test-package")

    assert result["error"]["code"] == ErrorCode.PARSE_ERROR


@pytest.mark.asyncio
async def test_wrong_content_type_is_parse_error(stats_service, mock_http_client):
    mock_http_client.fetch.return_value = {
        "raw_data": "<html>Not JSON</html>",
        "content_type": "text/html",
    }

    result = await stats_service.get_package_stats("test-package")

    assert result["error"]["code"] == ErrorCode.PARSE_ERROR
    assert "Unexpected content type" in result["error"]["message"]


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [ErrorCode.NETWORK_ERROR, ErrorCode.NOT_FOUND])
async def test_http_error_dict_is_propagated(stats_service, mock_http_client, code):
    mock_http_client.fetch.return_value = format_error(code, "upstream failure")

    result = await stats_service.get_package_stats("test-package")

    assert result["error"]["code"] == code
    assert "last_month" not in result


@pytest.mark.asyncio
async def test_exception_is_unknown_error(stats_service, mock_http_client):
    mock_http_client.fetch.side_effect = Exception("Test exception")

    result = await stats_service.get_package_stats("test-package")

    assert result["error"]["code"] == ErrorCode.UNKNOWN_ERROR
    assert "last_month" not in result


@pytest.mark.asyncio
async def test_invalid_name_is_invalid_input(stats_service):
    with patch("mcp_pypi.core.stats.sanitize_package_name") as mock_sanitize:
        mock_sanitize.side_effect = ValueError("Invalid package name")

        result = await stats_service.get_package_stats("invalid-package")

    assert result["error"]["code"] == ErrorCode.INVALID_INPUT


def test_no_synthetic_generator_remains(stats_service):
    assert not hasattr(stats_service, "_generate_synthetic_stats")
