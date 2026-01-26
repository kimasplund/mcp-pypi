"""
Search and comparison operations mixin for PyPI client.
"""

import logging
import re
from typing import Any, Dict, Optional, cast
from urllib.parse import quote_plus

from packaging.version import Version

from mcp_pypi.core.models import (
    DocumentationResult,
    ErrorCode,
    SearchResult,
    VersionComparisonResult,
    format_error,
)
from mcp_pypi.utils.helpers import sanitize_package_name, sanitize_version

logger = logging.getLogger("mcp-pypi.client")


class SearchOpsMixin:
    """Mixin providing search and comparison operations."""

    async def search_packages(self, query: str, page: int = 1) -> SearchResult:
        """Search for packages on PyPI."""
        query_encoded = quote_plus(query)
        url = f"https://pypi.org/search/?q={query_encoded}&page={page}"

        try:
            data = await self.http.fetch(url)

            # Check for error in result
            if isinstance(data, dict) and "error" in data:
                return cast(SearchResult, data)

            # Process the raw_data if in the new format
            html_content = None
            if isinstance(data, dict) and "raw_data" in data:
                raw_data = data["raw_data"]

                if isinstance(raw_data, bytes):
                    html_content = raw_data.decode("utf-8", errors="ignore")
                elif isinstance(raw_data, str):
                    html_content = raw_data
                else:
                    return {
                        "results": [],
                        "error": {
                            "code": ErrorCode.PARSE_ERROR,
                            "message": f"Unexpected data type: {type(raw_data)}",
                        },
                    }
            elif isinstance(data, (str, bytes)):
                # Legacy format
                if isinstance(data, bytes):
                    html_content = data.decode("utf-8", errors="ignore")
                else:
                    html_content = data
            else:
                return {
                    "results": [],
                    "error": {
                        "code": ErrorCode.PARSE_ERROR,
                        "message": f"Unexpected data type: {type(data)}",
                    },
                }

            # Handle case when we receive a Client Challenge page instead of search results
            if "Client Challenge" in html_content:
                logger.warning(
                    "Received a security challenge page from PyPI instead of search results"
                )
                return {
                    "search_url": url,
                    "message": "PyPI returned a security challenge page. Try using a web browser to search PyPI directly.",
                    "results": [],
                }

            # Check if BeautifulSoup is available for better parsing
            if self._has_bs4:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(html_content, "html.parser")
                results = []

                # Extract packages from search results
                for package in soup.select(".package-snippet"):
                    name_elem = package.select_one(".package-snippet__name")
                    version_elem = package.select_one(".package-snippet__version")
                    desc_elem = package.select_one(".package-snippet__description")

                    if name_elem and version_elem:
                        name = name_elem.text.strip()
                        version = version_elem.text.strip()
                        description = desc_elem.text.strip() if desc_elem else ""

                        results.append(
                            {
                                "name": name,
                                "version": version,
                                "description": description,
                                "url": f"https://pypi.org/project/{name}/",
                            }
                        )

                # Check if we found any results
                if results:
                    return {"search_url": url, "results": results}
                else:
                    # We have BeautifulSoup but couldn't find any packages
                    # This could be a format change or we're not getting the expected HTML
                    return {
                        "search_url": url,
                        "message": "No packages found or PyPI search page format has changed",
                        "results": [],
                    }

            # Fallback if BeautifulSoup is not available
            return {
                "search_url": url,
                "message": "For better search results, install Beautiful Soup: pip install beautifulsoup4",
                "results": [],  # Return empty results rather than raw HTML
            }
        except Exception as e:
            logger.exception(f"Error searching packages: {e}")
            return {
                "results": [],
                "error": {"code": ErrorCode.UNKNOWN_ERROR, "message": str(e)},
            }

    async def compare_versions(
        self, package_name: str, version1: str, version2: str
    ) -> VersionComparisonResult:
        """Compare two version numbers of a package."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            sanitized_v1 = sanitize_version(version1)
            sanitized_v2 = sanitize_version(version2)

            # Use packaging.version for reliable comparison
            v1 = Version(sanitized_v1)
            v2 = Version(sanitized_v2)

            return {
                "version1": sanitized_v1,
                "version2": sanitized_v2,
                "is_version1_greater": v1 > v2,
                "is_version2_greater": v2 > v1,
                "are_equal": v1 == v2,
            }
        except ValueError as e:
            return cast(
                VersionComparisonResult, format_error(ErrorCode.INVALID_INPUT, str(e))
            )
        except Exception as e:
            logger.exception(f"Error comparing versions: {e}")
            return cast(
                VersionComparisonResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e))
            )

    async def get_documentation_url(
        self, package_name: str, version: Optional[str] = None
    ) -> DocumentationResult:
        """Get documentation URL for a package."""
        try:
            sanitized_name = sanitize_package_name(package_name)

            # Get package info
            info = await self.get_package_info(sanitized_name)

            if "error" in info:
                return cast(DocumentationResult, info)

            metadata = info["info"]

            # Look for documentation URL
            docs_url = None

            # Check project_urls first
            project_urls = metadata.get("project_urls", {}) or {}

            # Search for documentation keywords in project_urls
            for key, url in project_urls.items():
                if not key or not url:
                    continue

                if any(
                    term in key.lower()
                    for term in ["doc", "documentation", "docs", "readthedocs", "rtd"]
                ):
                    docs_url = url
                    break

            # If not found, try home page or common doc sites
            if not docs_url:
                docs_url = metadata.get("documentation_url") or metadata.get("docs_url")

            if not docs_url:
                docs_url = metadata.get("home_page")

            if not docs_url:
                # Try common documentation sites
                docs_url = f"https://readthedocs.org/projects/{sanitized_name}/"

            # Get summary
            summary = metadata.get("summary", "No summary available")

            return {"docs_url": docs_url or "Not available", "summary": summary}
        except ValueError as e:
            return cast(
                DocumentationResult, format_error(ErrorCode.INVALID_INPUT, str(e))
            )
        except Exception as e:
            logger.exception(f"Error getting documentation URL: {e}")
            return cast(
                DocumentationResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e))
            )

    async def get_package_changelog(
        self, package_name: str, version: Optional[str] = None
    ) -> str:
        """Get changelog for a package.

        This method attempts to retrieve changelog information from:
        1. Package metadata project_urls for changelog link
        2. GitHub releases if the package has a GitHub repository
        3. Common changelog file names in the package distribution

        Args:
            package_name: Name of the package
            version: Specific version (optional, defaults to latest)

        Returns:
            Changelog text or appropriate message
        """
        try:
            # Get package info to find changelog URL
            info_result = await self.get_package_info(package_name)
            if "error" in info_result:
                return f"Package {package_name} not found"

            info = info_result.get("info", {})
            project_urls = info.get("project_urls") or {}

            # Check for explicit changelog URL
            changelog_url = None
            for key, url in project_urls.items():
                if any(
                    term in key.lower()
                    for term in ["changelog", "changes", "history", "release"]
                ):
                    changelog_url = url
                    break

            # If we found a changelog URL, try to fetch it
            if changelog_url:
                # Handle GitHub releases specially
                if "github.com" in changelog_url and "/releases" in changelog_url:
                    # Extract owner and repo from GitHub URL
                    match = re.search(r"github\.com/([^/]+)/([^/]+)", changelog_url)
                    if match:
                        owner, repo = match.groups()
                        # Use GitHub API to get releases
                        # Limit to 5 releases using GitHub API parameter
                        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=5"

                        try:
                            response = await self.http.fetch(api_url)
                            if isinstance(response, dict) and "error" not in response:
                                # GitHub API returns array directly
                                releases = (
                                    response if isinstance(response, list) else []
                                )
                            else:
                                releases = (
                                    response if isinstance(response, list) else []
                                )

                            if releases:
                                # Format releases into changelog
                                changelog_parts = [f"# Changelog for {package_name}\n"]

                                # Limit to 5 releases to avoid token limits
                                for i, release in enumerate(releases[:5]):
                                    tag = release.get("tag_name", "")
                                    name = release.get("name", "")
                                    body = release.get("body", "")
                                    published = release.get("published_at", "")

                                    if tag:
                                        changelog_parts.append(f"\n## {tag}")
                                        if name and name != tag:
                                            changelog_parts.append(f" - {name}")
                                        if published:
                                            changelog_parts.append(
                                                f"\n*Released: {published[:10]}*"
                                            )
                                        if body:
                                            # Truncate long bodies to avoid token limits
                                            max_body_length = 1000
                                            if len(body) > max_body_length:
                                                body = (
                                                    body[:max_body_length]
                                                    + "\n\n... (truncated)"
                                                )
                                            changelog_parts.append(f"\n{body}")

                                # Add note about limited releases
                                changelog_parts.append(
                                    f"\n\n---\n\n*Showing up to 5 most recent releases. Visit {changelog_url} for the complete changelog.*"
                                )

                                return "\n".join(changelog_parts)
                        except Exception as e:
                            logger.debug(f"Could not fetch GitHub releases: {e}")

                # Try to fetch as regular webpage
                try:
                    response = await self.http.fetch(changelog_url)
                    if isinstance(response, dict):
                        # If it's JSON, try to extract text
                        return str(response)
                    return f"Changelog available at: {changelog_url}"
                except Exception as e:
                    logger.debug(f"Could not fetch changelog URL: {e}")
                    return f"Changelog available at: {changelog_url}"

            # Check if there's a GitHub repo to check releases
            github_url = None
            for key, url in project_urls.items():
                if "github.com" in str(url) and not "/releases" in str(url):
                    github_url = url
                    break

            if (
                not github_url
                and info.get("home_page")
                and "github.com" in str(info.get("home_page"))
            ):
                github_url = info.get("home_page")

            if github_url:
                # Extract owner and repo
                match = re.search(r"github\.com/([^/]+)/([^/]+)", github_url)
                if match:
                    owner, repo = match.groups()
                    repo = repo.rstrip("/")  # Remove trailing slash if present

                    # Construct changelog URL
                    releases_url = f"https://github.com/{owner}/{repo}/releases"
                    return f"Changelog might be available at: {releases_url}"

            # If no changelog found, return a helpful message
            available_urls = "\n".join([f"- {k}: {v}" for k, v in project_urls.items()])
            if available_urls:
                return f"No explicit changelog found. Available project URLs:\n{available_urls}"
            else:
                return f"No changelog information available for {package_name}"

        except Exception as e:
            logger.error(f"Error getting changelog for {package_name}: {e}")
            return f"Error retrieving changelog: {str(e)}"
