"""
Search and comparison operations mixin for PyPI client.
"""

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any, cast
from urllib.parse import urlparse

from packaging.version import Version

from mcp_pypi.core.http import AsyncHTTPClient
from mcp_pypi.core.models import (
    ChangelogResult,
    DocumentationResult,
    ErrorCode,
    VersionComparisonResult,
    format_error,
)
from mcp_pypi.core.search_index import (
    TIER_EXACT,
    Candidate,
    IndexUnavailable,
    NameIndex,
    Popularity,
    enrichment_pool,
    normalize,
    query_tokens,
    rank_candidates,
)
from mcp_pypi.utils.sanitize import sanitize_package_name, sanitize_version

logger = logging.getLogger("mcp-pypi.client")

_MAX_RELEASE_BODY = 1000
_GITHUB_HOSTS = frozenset({"github.com", "www.github.com"})
_GITHUB_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def _github_repo(url: object) -> tuple[str, str] | None:
    """Return (owner, repo) when url is an http(s) URL on github.com, else None.

    Matches on the parsed hostname, not a substring, so lookalikes such as
    ``https://evil.example/github.com/a/b`` or ``https://github.com.evil.example``
    are rejected.
    """
    if not isinstance(url, str):
        return None
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or (parsed.hostname or "").lower() not in (
        _GITHUB_HOSTS
    ):
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1].removesuffix(".git")
    if not (_GITHUB_NAME.match(owner) and _GITHUB_NAME.match(repo)):
        return None
    return owner, repo


class SearchOpsMixin:
    """Mixin providing search and comparison operations."""

    http: AsyncHTTPClient
    name_index: NameIndex
    popularity: Popularity
    get_package_info: Callable[[str], Awaitable[Any]]  # provided by PackageOpsMixin

    async def search_packages(self, query: str, limit: int = 10) -> dict[str, Any]:
        """Search package names (Simple index + popularity), enriched from package metadata."""
        tokens = query_tokens(query)
        if not tokens:
            return cast(
                dict[str, Any],
                format_error(ErrorCode.INVALID_INPUT, "Search query must not be empty"),
            )
        limit = max(1, min(50, limit))

        try:
            names = await self.name_index.names()
        except IndexUnavailable as e:
            logger.warning(f"Package index unavailable: {e}")
            return cast(
                dict[str, Any],
                format_error(
                    ErrorCode.NETWORK_ERROR, "PyPI package index unavailable; retry later"
                ),
            )

        try:
            downloads = await self.popularity.downloads()
            candidates = await asyncio.to_thread(rank_candidates, query, names, downloads)
            # The best few by score, plus the most popular matching names however they scored.
            top = enrichment_pool(candidates, downloads, max(limit, min(3 * limit, 30)))

            by_downloads = sorted(downloads, key=downloads.__getitem__, reverse=True)
            ranks = {name: rank for rank, name in enumerate(by_downloads, 1)}
            semaphore = asyncio.Semaphore(10)

            errors: list[dict[str, Any]] = []

            async def enrich(
                candidate: Candidate,
            ) -> tuple[tuple[bool, float], dict[str, Any]] | None:
                async with semaphore:
                    data = await self.get_package_info(candidate.name)
                info = data.get("info") if isinstance(data, dict) else None
                if "error" in data or not isinstance(info, dict):
                    if "error" in data:
                        errors.append(data)
                    return None
                summary = info.get("summary") or ""
                boost = 40 * sum(t in summary.lower() for t in tokens)
                name = info.get("name") or candidate.name
                exact = candidate.tier == TIER_EXACT  # the exact name match stays first
                return (exact, candidate.score + boost), {
                    "name": name,
                    "version": info.get("version") or "",
                    "summary": summary,
                    "package_url": f"https://pypi.org/project/{name}/",
                    "popularity_rank": ranks.get(normalize(name)),
                }

            enriched = [r for r in await asyncio.gather(*(enrich(c) for c in top)) if r]
            enriched.sort(key=lambda r: r[0], reverse=True)
            results = [item for _, item in enriched[:limit]]
            if top and not enriched and errors:
                return errors[0]

            response: dict[str, Any] = {
                "query": query,
                "results": results,
                "total_candidates": len(candidates),
                "note": None,
            }
            if not results:
                response["note"] = (
                    "No package names matched. "
                    "Try name-like keywords (e.g. 'httpx', 'jwt', 'yaml')."
                )
            return response
        except Exception as e:
            logger.exception(f"Error searching packages: {e}")
            return cast(dict[str, Any], format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

    async def compare_versions(
        self, package_name: str, version1: str, version2: str
    ) -> VersionComparisonResult:
        """Compare two version numbers of a package."""
        try:
            sanitize_package_name(package_name)
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
            return cast(VersionComparisonResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Error comparing versions: {e}")
            return cast(VersionComparisonResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

    async def get_documentation_url(
        self, package_name: str, version: str | None = None
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
            return cast(DocumentationResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Error getting documentation URL: {e}")
            return cast(DocumentationResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

    async def get_package_changelog(
        self, package_name: str, version: str | None = None
    ) -> ChangelogResult:
        """Get changelog for a package.

        Returns {"package_name", "version", "changelog"} on success, or an error dict
        (not_found, network_error, ...) when the package cannot be looked up. The text
        covers the package as a whole; `version` does not filter it and is returned as None.
        """
        try:
            sanitized_name = sanitize_package_name(package_name)
            info_result = await self.get_package_info(sanitized_name)
            if "error" in info_result:
                return cast(ChangelogResult, info_result)
            text = await self._changelog_text(package_name, info_result)
            # `version` is not used to filter the changelog, so it is not echoed back.
            return {"package_name": package_name, "version": None, "changelog": text}
        except ValueError as e:
            return cast(ChangelogResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.error(f"Error getting changelog for {package_name}: {e}")
            return cast(ChangelogResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

    async def _github_releases_changelog(
        self, owner: str, repo: str, *, package_name: str, changelog_url: str
    ) -> str | None:
        """Format the 5 most recent GitHub releases, or None if none could be fetched."""
        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=5"
        try:
            response = await self.http.fetch(api_url)
        except Exception as e:
            logger.debug(f"Could not fetch GitHub releases: {e}")
            return None
        releases = response if isinstance(response, list) else []
        if not releases:
            return None

        parts = [f"# Changelog for {package_name}\n"]
        for release in releases[:5]:
            tag = release.get("tag_name", "")
            if not tag:
                continue
            name = release.get("name", "")
            body = release.get("body", "")
            published = release.get("published_at", "")
            parts.append(f"\n## {tag}")
            if name and name != tag:
                parts.append(f" - {name}")
            if published:
                parts.append(f"\n*Released: {published[:10]}*")
            if body:
                # Truncate long bodies to keep responses small
                if len(body) > _MAX_RELEASE_BODY:
                    body = body[:_MAX_RELEASE_BODY] + "\n\n... (truncated)"
                parts.append(f"\n{body}")
        parts.append(
            f"\n\n---\n\n*Showing up to 5 most recent releases. Visit "
            f"{changelog_url} for the complete changelog.*"
        )
        return "\n".join(parts)

    async def _changelog_text(self, package_name: str, info_result: Any) -> str:
        """Find changelog text from package metadata, GitHub releases or project URLs.

        Tries project_urls for a changelog link, GitHub releases for that link,
        then a GitHub repository hint, then lists the available URLs.
        """
        try:
            info = info_result.get("info", {})
            project_urls = info.get("project_urls") or {}

            # Check for explicit changelog URL
            changelog_url = None
            for key, url in project_urls.items():
                if any(
                    term in key.lower() for term in ["changelog", "changes", "history", "release"]
                ):
                    changelog_url = url
                    break

            # Project URLs are untrusted package metadata: only the GitHub API is ever
            # requested (for real github.com release pages); other URLs are returned
            # as links, never fetched.
            if changelog_url:
                github = _github_repo(changelog_url)
                if github and "/releases" in urlparse(str(changelog_url)).path:
                    text = await self._github_releases_changelog(
                        *github, package_name=package_name, changelog_url=str(changelog_url)
                    )
                    if text:
                        return text
                return f"Changelog available at: {changelog_url}"

            # Fall back to a releases link for a GitHub repository URL
            candidates = [*project_urls.values(), info.get("home_page")]
            for url in candidates:
                github = _github_repo(url)
                if github:
                    owner, repo = github
                    releases_url = f"https://github.com/{owner}/{repo}/releases"
                    return f"Changelog might be available at: {releases_url}"

            # If no changelog found, return a helpful message
            available_urls = "\n".join([f"- {k}: {v}" for k, v in project_urls.items()])
            if available_urls:
                return f"No explicit changelog found. Available project URLs:\n{available_urls}"
            else:
                return f"No changelog information available for {package_name}"

        except Exception as e:
            logger.error(f"Error building changelog for {package_name}: {e}")
            raise
