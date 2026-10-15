"""Package lookup tools: search, details, versions, comparison, changelog, downloads."""

from __future__ import annotations

from typing import Any, Literal

from fastmcp import FastMCP
from packaging.version import InvalidVersion, Version

from mcp_pypi.core import PyPIClient
from mcp_pypi.server.errors import checked, checked_release
from mcp_pypi.server.schemas import (
    Changelog,
    DownloadStats,
    PackageDetails,
    PackageVersions,
    SearchHit,
    SearchResults,
    VersionComparison,
    VersionEntry,
)
from mcp_pypi.server.tools import TOOL_ANNOTATIONS

_URL_KEYS = {
    "documentation_url": ("documentation", "docs"),
    "source_url": ("source", "repository", "code", "github"),
    "changelog_url": ("changelog", "changes", "release notes", "history"),
    "homepage_url": ("homepage", "home"),
}


def _find_url(project_urls: dict[str, str], terms: tuple[str, ...]) -> str | None:
    """First project URL whose key (case-insensitive) contains a term; terms in priority order."""
    for term in terms:
        for key, url in project_urls.items():
            if url and term in key.lower():
                return url
    return None


def _upload_time(files: list[dict[str, Any]]) -> str | None:
    times = [f["upload_time_iso_8601"] for f in files if f.get("upload_time_iso_8601")]
    return min(times) if times else None


def _version_key(entry: VersionEntry) -> tuple[int, Version | str]:
    try:
        return (0, Version(entry.version))
    except InvalidVersion:
        return (1, entry.version)


def _version_entry(version: str, files: list[dict[str, Any]]) -> VersionEntry:
    reasons = [f["yanked_reason"] for f in files if f.get("yanked_reason")]
    return VersionEntry(
        version=version,
        upload_time=_upload_time(files),
        yanked=bool(files) and all(f.get("yanked") for f in files),
        yanked_reason=reasons[0] if reasons else None,
        file_types=sorted({f["packagetype"] for f in files if f.get("packagetype")}),
    )


def register_package_tools(mcp: FastMCP, client: PyPIClient) -> None:
    """Register the package lookup tools."""

    @mcp.tool(title="Search PyPI packages", annotations=TOOL_ANNOTATIONS, timeout=60)
    async def search_packages(query: str, limit: int = 10) -> SearchResults:
        """Search PyPI package names and return ranked matches with summaries.

        Matches against the PyPI Simple index and ranks hits by name similarity and
        download popularity. Use this to find the exact name of a package or to discover
        alternatives. `limit` is clamped to 1-50.
        """
        data = await checked(
            await client.search_packages(query, max(1, min(limit, 50))), client=client
        )
        return SearchResults(
            query=data.get("query", query),
            results=[SearchHit(**hit) for hit in data.get("results", [])],
            total_candidates=data.get("total_candidates", 0),
            note=data.get("note"),
        )

    @mcp.tool(title="Get package details", annotations=TOOL_ANNOTATIONS, timeout=60)
    async def get_package(package_name: str, version: str | None = None) -> PackageDetails:
        """Get metadata for a package: versions, license, URLs, classifiers and yank status.

        Without `version` it describes the latest release. With `version` it describes
        that release (including whether it was yanked) while `latest_version` still reports
        the newest release on PyPI. Unknown packages return a "did you mean" suggestion;
        an unknown version of an existing package is reported as such, with the latest.
        """
        pinned = await checked_release(
            await client.get_package_info(package_name, version),
            client=client,
            package=package_name,
            version=version,
        )
        latest = (
            await checked(
                await client.get_package_info(package_name), client=client, package=package_name
            )
            if version
            else pinned
        )
        info = pinned.get("info") or {}
        latest_info = latest.get("info") or {}
        releases = latest.get("releases") or {}
        latest_version = str(latest_info.get("version") or info.get("version") or "")
        project_urls = {k: v for k, v in (info.get("project_urls") or {}).items() if v}
        urls = {field: _find_url(project_urls, terms) for field, terms in _URL_KEYS.items()}
        urls["homepage_url"] = urls["homepage_url"] or info.get("home_page") or None
        license_text = info.get("license_expression") or (info.get("license") or "")[:200] or None
        return PackageDetails(
            package_name=info.get("name") or package_name,
            version=str(info.get("version") or version or latest_version),
            latest_version=latest_version,
            summary=info.get("summary") or None,
            requires_python=info.get("requires_python") or None,
            license=license_text,
            author=info.get("author") or None,
            maintainer=info.get("maintainer") or None,
            project_urls=project_urls,
            classifiers=list(info.get("classifiers") or []),
            yanked=bool(info.get("yanked")) if version else False,
            yanked_reason=(info.get("yanked_reason") or None) if version else None,
            release_count=len(releases),
            latest_upload_time=_upload_time(releases.get(latest_version) or []),
            package_url=info.get("package_url") or f"https://pypi.org/project/{package_name}/",
            **urls,
        )

    @mcp.tool(title="List package versions", annotations=TOOL_ANNOTATIONS, timeout=60)
    async def get_package_versions(
        package_name: str,
        limit: int = 20,
        offset: int = 0,
        sort: Literal["newest", "oldest"] = "newest",
    ) -> PackageVersions:
        """List released versions with upload time, yank status and file types.

        Results are ordered by PEP 440 version (versions that do not parse sort last) and
        paginated: `limit` is clamped to 1-100 and `offset` to 0 or more. Check `has_more`
        to know whether another page exists.
        """
        data = await checked(
            await client.get_package_info(package_name), client=client, package=package_name
        )
        entries = [
            _version_entry(v, files or []) for v, files in (data.get("releases") or {}).items()
        ]
        valid = sorted((e for e in entries if _version_key(e)[0] == 0), key=_version_key)
        invalid = sorted((e for e in entries if _version_key(e)[0] == 1), key=_version_key)
        ordered = (valid if sort == "oldest" else valid[::-1]) + invalid
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        return PackageVersions(
            package_name=package_name,
            versions=ordered[offset : offset + limit],
            total=len(ordered),
            offset=offset,
            limit=limit,
            has_more=offset + limit < len(ordered),
        )

    @mcp.tool(title="Compare package versions", annotations=TOOL_ANNOTATIONS, timeout=60)
    async def compare_versions(
        package_name: str, version1: str, version2: str
    ) -> VersionComparison:
        """Compare two versions of a package using PEP 440 ordering.

        Reports which of the two is newer, or that they are equal. The comparison is
        purely on version numbers and does not check that either release exists.
        """
        data = await checked(
            await client.compare_versions(package_name, version1, version2),
            client=client,
            package=package_name,
        )
        v1, v2 = data.get("version1", version1), data.get("version2", version2)
        if data.get("are_equal"):
            newer, text = "equal", f"{v1} and {v2} are equal"
        elif data.get("is_version1_greater"):
            newer, text = "version1", f"{v1} is newer than {v2}"
        else:
            newer, text = "version2", f"{v2} is newer than {v1}"
        return VersionComparison(
            package_name=package_name, version1=v1, version2=v2, newer=newer, comparison=text
        )

    @mcp.tool(title="Get package changelog", annotations=TOOL_ANNOTATIONS, timeout=60)
    async def get_package_changelog(package_name: str, version: str | None = None) -> Changelog:
        """Get changelog text for a package from its project links or GitHub releases.

        Uses the changelog link in the package metadata when present and falls back to
        the repository's releases page. When nothing is found it returns a short note
        listing the project URLs that are available.
        """
        data = await checked(
            await client.get_package_changelog(package_name, version),
            client=client,
            package=package_name,
        )
        return Changelog(
            package_name=data.get("package_name", package_name),
            version=data.get("version"),
            changelog=data.get("changelog", ""),
        )

    @mcp.tool(title="Get download statistics", annotations=TOOL_ANNOTATIONS, timeout=60)
    async def get_download_stats(package_name: str) -> DownloadStats:
        """Get recent download counts (last day, week and month) from pypistats.org.

        Useful as a rough popularity signal. Counts include mirrors and CI traffic, so
        compare packages against each other rather than reading absolute numbers.
        """
        data = await checked(
            await client.get_package_stats(package_name), client=client, package=package_name
        )
        return DownloadStats(
            package_name=package_name,
            last_day=data.get("last_day"),
            last_week=data.get("last_week"),
            last_month=data.get("last_month"),
        )
