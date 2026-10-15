"""Tests for the package lookup tools."""

import copy
from typing import Any

import pytest

NETWORK_ERROR = {"error": {"code": "network_error", "message": "PyPI unreachable"}}
NOT_FOUND = {"error": {"code": "not_found", "message": "gone"}}


def pypi_doc(**info_overrides) -> dict[str, Any]:
    info: dict[str, Any] = {
        "name": "demo",
        "version": "2.0.0",
        "summary": "A demo",
        "requires_python": ">=3.9",
        "license": "MIT license text " * 50,
        "license_expression": "MIT",
        "author": "Ann",
        "maintainer": "Bob",
        "home_page": "https://old.example.com",
        "project_urls": {
            "Documentation": "https://docs.example.com",
            "Source Code": "https://github.com/o/demo",
            "Release Notes": "https://example.com/changes",
            "Homepage": "https://example.com",
            "Funding": "https://example.com/fund",
        },
        "classifiers": ["Programming Language :: Python :: 3"],
        "yanked": False,
        "yanked_reason": None,
        "package_url": "https://pypi.org/project/demo/",
    }
    info.update(info_overrides)
    return {
        "info": info,
        "releases": {
            "1.0.0": [
                {
                    "upload_time_iso_8601": "2020-01-01T00:00:00Z",
                    "yanked": False,
                    "yanked_reason": None,
                    "packagetype": "sdist",
                }
            ],
            "2.0.0": [
                {
                    "upload_time_iso_8601": "2021-01-01T00:00:00Z",
                    "yanked": False,
                    "yanked_reason": None,
                    "packagetype": "bdist_wheel",
                }
            ],
        },
    }


async def test_search_packages_structured(fake_client, mcp_client):
    fake_client.search_packages.return_value = {
        "query": "http",
        "results": [
            {
                "name": "httpx",
                "version": "0.27",
                "summary": "client",
                "package_url": "https://pypi.org/project/httpx/",
                "popularity_rank": 1,
            }
        ],
        "total_candidates": 3,
        "note": None,
    }
    res = await mcp_client.call_tool("search_packages", {"query": "http"}, raise_on_error=False)
    assert not res.is_error
    assert res.structured_content["results"][0]["name"] == "httpx"
    assert res.structured_content["total_candidates"] == 3


async def test_search_packages_clamps_limit(fake_client, mcp_client):
    fake_client.search_packages.return_value = {
        "query": "x",
        "results": [],
        "total_candidates": 0,
    }
    await mcp_client.call_tool("search_packages", {"query": "x", "limit": 500})
    assert fake_client.search_packages.call_args.args[1] == 50 or (
        fake_client.search_packages.call_args.kwargs.get("limit") == 50
    )


async def test_search_index_unavailable_is_tool_error(fake_client, mcp_client):
    fake_client.search_packages.return_value = NETWORK_ERROR
    res = await mcp_client.call_tool("search_packages", {"query": "x"}, raise_on_error=False)
    assert res.is_error
    assert res.content[0].text == "PyPI request failed (network_error); retry later."


async def test_get_package_maps_urls_and_license(fake_client, mcp_client):
    fake_client.get_package_info.return_value = pypi_doc()
    res = await mcp_client.call_tool("get_package", {"package_name": "demo"})
    d = res.structured_content
    assert d["license"] == "MIT"
    assert d["documentation_url"] == "https://docs.example.com"
    assert d["source_url"] == "https://github.com/o/demo"
    assert d["changelog_url"] == "https://example.com/changes"
    assert d["homepage_url"] == "https://example.com"
    assert d["latest_version"] == "2.0.0"
    assert d["release_count"] == 2
    assert d["latest_upload_time"] == "2021-01-01T00:00:00Z"
    assert d["yanked"] is False


async def test_get_package_license_fallback_truncated(fake_client, mcp_client):
    doc = pypi_doc(license_expression=None)
    doc["info"]["project_urls"] = None
    fake_client.get_package_info.return_value = doc
    res = await mcp_client.call_tool("get_package", {"package_name": "demo"})
    d = res.structured_content
    assert len(d["license"]) == 200
    assert d["homepage_url"] == "https://old.example.com"
    assert d["documentation_url"] is None


async def test_get_package_not_found_suggests(fake_client, mcp_client):
    fake_client.get_package_info.return_value = NOT_FOUND
    fake_client.suggest_names.return_value = ["beautifulsoup4"]
    res = await mcp_client.call_tool("get_package", {"package_name": "bs4x"}, raise_on_error=False)
    assert res.is_error
    assert "Did you mean 'beautifulsoup4'?" in res.content[0].text


async def test_get_package_pinned_version_reports_yanked(fake_client, mcp_client):
    pinned = pypi_doc(version="1.0.0", yanked=True, yanked_reason="broken build")
    pinned.pop("releases")
    latest = copy.deepcopy(pypi_doc())

    async def info(name, version=None):
        return pinned if version else latest

    fake_client.get_package_info.side_effect = info
    res = await mcp_client.call_tool("get_package", {"package_name": "demo", "version": "1.0.0"})
    d = res.structured_content
    assert d["version"] == "1.0.0"
    assert d["latest_version"] == "2.0.0"
    assert d["yanked"] is True
    assert d["yanked_reason"] == "broken build"
    assert d["release_count"] == 2


def versions_doc(n):
    return {
        "info": {"name": "demo"},
        "releases": {
            f"1.{i}.0": [
                {
                    "upload_time_iso_8601": f"2020-01-{i + 1:02d}T00:00:00Z",
                    "yanked": i == 3,
                    "yanked_reason": "bad" if i == 3 else None,
                    "packagetype": "sdist",
                }
            ]
            for i in range(n)
        },
    }


async def test_get_package_versions_paginates_and_sorts(fake_client, mcp_client):
    doc = versions_doc(25)
    doc["releases"]["1.99.0"] = []
    doc["releases"]["junk"] = []
    fake_client.get_package_info.return_value = doc
    res = await mcp_client.call_tool(
        "get_package_versions", {"package_name": "demo", "limit": 10, "offset": 20}
    )
    d = res.structured_content
    assert d["total"] == 27
    assert len(d["versions"]) == 7
    assert d["versions"][-1]["version"] == "junk"
    assert d["has_more"] is False

    res = await mcp_client.call_tool(
        "get_package_versions", {"package_name": "demo", "limit": 10, "offset": 15}
    )
    assert len(res.structured_content["versions"]) == 10
    assert res.structured_content["has_more"] is True

    res = await mcp_client.call_tool(
        "get_package_versions", {"package_name": "demo", "sort": "oldest", "limit": 100}
    )
    names = [v["version"] for v in res.structured_content["versions"]]
    assert names[0] == "1.0.0"
    assert names[24] == "1.24.0"
    assert names[-1] == "junk"


async def test_get_package_versions_newest_first_and_entry_fields(fake_client, mcp_client):
    doc = versions_doc(5)
    doc["releases"]["1.9.0"] = []
    fake_client.get_package_info.return_value = doc
    res = await mcp_client.call_tool("get_package_versions", {"package_name": "demo"})
    vs = res.structured_content["versions"]
    assert [v["version"] for v in vs][:2] == ["1.9.0", "1.4.0"]
    assert vs[0] == {
        "version": "1.9.0",
        "upload_time": None,
        "yanked": False,
        "yanked_reason": None,
        "file_types": [],
    }
    yanked = next(v for v in vs if v["version"] == "1.3.0")
    assert yanked["yanked"] is True and yanked["yanked_reason"] == "bad"
    assert yanked["file_types"] == ["sdist"]


async def test_get_package_versions_clamps(fake_client, mcp_client):
    fake_client.get_package_info.return_value = versions_doc(3)
    res = await mcp_client.call_tool(
        "get_package_versions", {"package_name": "demo", "limit": 0, "offset": -5}
    )
    d = res.structured_content
    assert d["limit"] == 1 and d["offset"] == 0 and len(d["versions"]) == 1


@pytest.mark.parametrize(
    ("flags", "newer"),
    [
        (
            {"is_version1_greater": False, "is_version2_greater": True, "are_equal": False},
            "version2",
        ),
        (
            {"is_version1_greater": True, "is_version2_greater": False, "are_equal": False},
            "version1",
        ),
        ({"is_version1_greater": False, "is_version2_greater": False, "are_equal": True}, "equal"),
    ],
)
async def test_compare_versions_newer_field(fake_client, mcp_client, flags, newer):
    fake_client.compare_versions.return_value = {"version1": "1.0", "version2": "2.0", **flags}
    res = await mcp_client.call_tool(
        "compare_versions", {"package_name": "demo", "version1": "1.0", "version2": "2.0"}
    )
    d = res.structured_content
    assert d["newer"] == newer
    assert d["comparison"]


async def test_changelog_passthrough(fake_client, mcp_client):
    fake_client.get_package_changelog.return_value = {
        "package_name": "demo",
        "version": None,
        "changelog": "# Changes",
    }
    res = await mcp_client.call_tool("get_package_changelog", {"package_name": "demo"})
    assert res.structured_content == {
        "package_name": "demo",
        "version": None,
        "changelog": "# Changes",
    }


async def test_download_stats_fields(fake_client, mcp_client):
    fake_client.get_package_stats.return_value = {
        "last_day": 10,
        "last_week": 70,
        "last_month": 300,
    }
    res = await mcp_client.call_tool("get_download_stats", {"package_name": "demo"})
    assert res.structured_content == {
        "package_name": "demo",
        "last_day": 10,
        "last_week": 70,
        "last_month": 300,
        "source": "pypistats.org",
    }


async def test_download_stats_network_error(fake_client, mcp_client):
    fake_client.get_package_stats.return_value = NETWORK_ERROR
    res = await mcp_client.call_tool(
        "get_download_stats", {"package_name": "demo"}, raise_on_error=False
    )
    assert res.is_error
    assert "network_error" in res.content[0].text


async def test_download_stats_parse_error_is_tool_error(fake_client, mcp_client):
    fake_client.get_package_stats.return_value = {
        "error": {"code": "parse_error", "message": "pypistats response is missing download counts"}
    }
    res = await mcp_client.call_tool(
        "get_download_stats", {"package_name": "demo"}, raise_on_error=False
    )
    assert res.is_error
    assert "parse_error" in res.content[0].text or "Unexpected error" in res.content[0].text


VERSION_MISSING = (
    "Version '99.0.0' of 'requests' not found on PyPI (latest is 2.32.3). "
    "Use get_package_versions to list versions."
)


async def test_get_package_unknown_version_is_not_reported_as_unknown_package(
    fake_client, mcp_client
):
    async def info(name, version=None):
        return NOT_FOUND if version else pypi_doc(name="requests", version="2.32.3")

    fake_client.get_package_info.side_effect = info
    fake_client.suggest_names.return_value = ["requests"]
    res = await mcp_client.call_tool(
        "get_package", {"package_name": "requests", "version": "99.0.0"}, raise_on_error=False
    )
    assert res.is_error
    assert res.content[0].text == VERSION_MISSING


async def test_get_package_unknown_package_with_version_keeps_package_message(
    fake_client, mcp_client
):
    fake_client.get_package_info.return_value = NOT_FOUND
    fake_client.suggest_names.return_value = ["requests"]
    res = await mcp_client.call_tool(
        "get_package", {"package_name": "reqests", "version": "1.0"}, raise_on_error=False
    )
    assert res.is_error
    assert res.content[0].text.startswith("Package 'reqests' not found on PyPI.")
    assert "Did you mean 'requests'?" in res.content[0].text
