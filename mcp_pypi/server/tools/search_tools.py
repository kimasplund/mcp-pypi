"""Search tools for PyPI MCP Server.

Contains tools for searching PyPI packages.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mcp.types import ToolAnnotations

from mcp_pypi.core.models import SearchResult
from mcp_pypi.utils.common.validation import validate_pagination

if TYPE_CHECKING:
    from mcp_pypi.server import PyPIMCPServer

logger = logging.getLogger("mcp-pypi.server")


def register_search_tools(server: "PyPIMCPServer") -> None:
    """Register search-related tools with the MCP server.

    Args:
        server: The PyPIMCPServer instance to register tools with.
    """

    @server.mcp_server.tool(
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
        tags={"search", "packages"},
    )
    async def search_packages(
        query: str, limit: int = 10, offset: int = 0
    ) -> SearchResult:
        """Search PyPI to discover Python packages for any task.

        Find the perfect library from 500,000+ packages. Returns ranked results
        with names, descriptions, and versions to help you choose the best option.

        Pro tip: After finding interesting packages, use get_package_info for details
        and check_vulnerabilities to ensure they're safe to recommend.

        Args:
            query (str, required): Search terms describing what you're looking for.
                Examples: "web scraping", "machine learning", "async http client"
            limit (int, optional): Maximum number of results to return.
                Default: 10, Min: 1, Max: 100
            offset (int, optional): Number of results to skip for pagination.
                Default: 0

        Returns:
            SearchResult with packages sorted by relevance, including:
            - packages: List of matching packages with name, description, version
            - total: Total number of matching packages found
            - offset: Current offset for pagination
            - limit: Number of results returned
            - has_more: Whether there are more results available

        Example usage:
            search_packages("data visualization")
            -> Returns: matplotlib, plotly, seaborn, bokeh, altair...

            search_packages("testing framework", limit=5, offset=0)
            -> Returns first 5 results

            search_packages("testing framework", limit=5, offset=5)
            -> Returns next 5 results
        """
        try:
            # Validate pagination parameters
            limit, offset = validate_pagination(limit, offset, max_limit=100)

            page = (offset // 20) + 1 if offset > 0 else 1
            result = await server.client.search_packages(query, page=page)

            if not result.get("error"):
                results = result.get("results", [])
                total_results = len(results)

                page_offset = offset % 20
                paginated_results = results[page_offset : page_offset + limit]

                result["results"] = paginated_results
                result["offset"] = offset
                result["limit"] = limit
                result["has_more"] = (
                    page_offset + limit
                ) < total_results or total_results >= 20
                if "total" not in result:
                    result["total"] = total_results

            return result
        except Exception as e:
            logger.error(f"Error searching packages: {e}")
            return {
                "query": query,
                "packages": [],
                "total": 0,
                "offset": offset,
                "limit": limit,
                "has_more": False,
                "error": {"message": str(e), "code": "search_error"},
            }
