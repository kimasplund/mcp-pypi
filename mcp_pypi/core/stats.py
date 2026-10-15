"""
Package statistics service for the MCP-PyPI client.

Download counts come straight from the pypistats.org "recent" endpoint and are
reported as-is. Nothing is estimated, derived or filled in when the upstream
data is missing: callers get an error dict instead.
"""

import json
import logging
from typing import Any, cast

from mcp_pypi.core.http import AsyncHTTPClient
from mcp_pypi.core.models import ErrorCode, StatsResult, format_error
from mcp_pypi.utils.sanitize import sanitize_package_name

logger = logging.getLogger("mcp-pypi.stats")

_PERIODS = ("last_day", "last_week", "last_month")


class PackageStatsService:
    """Service for retrieving package download statistics."""

    def __init__(self, http_client: AsyncHTTPClient):
        self.http_client = http_client

    async def get_package_stats(self, package_name: str) -> StatsResult:
        """Get last day/week/month download counts for a package from pypistats.org."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            url = f"https://pypistats.org/api/packages/{sanitized_name}/recent"

            result: Any = await self.http_client.fetch(url)
            if isinstance(result, dict) and "error" in result:
                return cast(StatsResult, result)

            if isinstance(result, dict) and "raw_data" in result:
                content_type = result.get("content_type", "")
                raw_data = result["raw_data"]
                if "application/json" not in content_type or not isinstance(raw_data, str):
                    return cast(
                        StatsResult,
                        format_error(
                            ErrorCode.PARSE_ERROR, f"Unexpected content type: {content_type}"
                        ),
                    )
                try:
                    result = json.loads(raw_data)
                except json.JSONDecodeError as e:
                    return cast(
                        StatsResult,
                        format_error(ErrorCode.PARSE_ERROR, f"Invalid JSON response: {e}"),
                    )

            data = result.get("data") if isinstance(result, dict) else None
            if not isinstance(data, dict) or not all(
                isinstance(data.get(p), int) and not isinstance(data.get(p), bool) for p in _PERIODS
            ):
                return cast(
                    StatsResult,
                    format_error(
                        ErrorCode.PARSE_ERROR, "pypistats response is missing download counts"
                    ),
                )

            return {
                "package_name": sanitized_name,
                "last_day": data["last_day"],
                "last_week": data["last_week"],
                "last_month": data["last_month"],
            }
        except ValueError as e:
            return cast(StatsResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Unexpected error getting package stats: {e}")
            return cast(StatsResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))
