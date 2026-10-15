"""OSV vulnerability checks against the REAL OSV response shapes.

`/v1/query` returns full advisory records; `/v1/querybatch` returns only
`{"id", "modified"}` per advisory, so the core must not depend on it. OSV matches
the version server-side only when `version` is at the top level of the query.
"""

import asyncio
import copy
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_pypi.core import PyPIClient
from mcp_pypi.core.cache import AsyncCacheManager
from mcp_pypi.core.http import AsyncHTTPClient
from mcp_pypi.core.models import PyPIClientConfig
from mcp_pypi.core.stats import PackageStatsService

QUERY_URL = "https://api.osv.dev/v1/query"

# Trimmed copies of real records returned by POST /v1/query for django 3.2.5.
# PYSEC-2022-1 has no summary/severity and three range pairs in ONE range.
PYSEC_2022_1 = {
    "id": "PYSEC-2022-1",
    "details": "An issue was discovered in Django 2.2 before 2.2.26, 3.2 before 3.2.11, "
    "and 4.0 before 4.0.1. UserAttributeSimilarityValidator incurred significant overhead.",
    "aliases": ["BIT-django-2021-45115", "CVE-2021-45115", "GHSA-53qw-q765-4fww"],
    "modified": "2023-12-06T01:01:43.028018Z",
    "published": "2022-01-05T00:15:00Z",
    "references": [
        {"type": "WEB", "url": "https://docs.djangoproject.com/en/4.0/releases/security/"},
        {"type": "ADVISORY", "url": "https://github.com/advisories/GHSA-53qw-q765-4fww"},
    ],
    "affected": [
        {
            "package": {"name": "django", "ecosystem": "PyPI", "purl": "pkg:pypi/django"},
            "ranges": [
                {
                    "type": "ECOSYSTEM",
                    "events": [
                        {"introduced": "2.2"},
                        {"fixed": "2.2.26"},
                        {"introduced": "3.2"},
                        {"fixed": "3.2.11"},
                        {"introduced": "4.0"},
                        {"fixed": "4.0.1"},
                    ],
                }
            ],
            "versions": ["2.2", "3.2", "3.2.5", "4.0"],
        }
    ],
    "schema_version": "1.7.3",
}
GHSA_2GWJ = {
    "id": "GHSA-2gwj-7jmv-h26r",
    "summary": "SQL Injection in Django",
    "details": "An issue was discovered in Django ...",
    "aliases": ["BIT-django-2022-28346", "CVE-2022-28346", "PYSEC-2022-190"],
    "modified": "2025-02-21T05:41:10.759178Z",
    "published": "2022-04-13T00:00:33Z",
    "database_specific": {"cwe_ids": ["CWE-89"], "severity": "CRITICAL"},
    "references": [{"type": "ADVISORY", "url": "https://nvd.nist.gov/vuln/detail/CVE-2022-28346"}],
    "affected": [
        {
            "package": {"name": "django", "ecosystem": "PyPI", "purl": "pkg:pypi/django"},
            "ranges": [
                {"type": "ECOSYSTEM", "events": [{"introduced": "2.2"}, {"fixed": "2.2.28"}]}
            ],
        },
        {
            "package": {"name": "django", "ecosystem": "PyPI", "purl": "pkg:pypi/django"},
            "ranges": [
                {"type": "ECOSYSTEM", "events": [{"introduced": "3.2"}, {"fixed": "3.2.13"}]}
            ],
        },
    ],
    "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}],
}
JINJA2_GHSA = {
    "id": "GHSA-462w-v97r-4m45",
    "summary": "Jinja2 sandbox escape via string formatting",
    "aliases": ["CVE-2019-10906"],
    "database_specific": {"severity": "HIGH"},
    "affected": [
        {
            "package": {"name": "jinja2", "ecosystem": "PyPI"},
            "ranges": [{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "2.10.1"}]}],
        }
    ],
}


class FakeOSV:
    """Records POST bodies; answers like the real OSV API (full records on /v1/query)."""

    def __init__(self, db: dict[str, list[dict]] | None = None, fail: set[str] = frozenset()):
        self.db = db or {}
        self.fail = fail
        self.posts: list[tuple[str, dict]] = []
        self.in_flight = 0
        self.max_in_flight = 0

    async def fetch(self, url, method="GET", headers=None, data=None):
        if data is None:  # package-exists GET of the single-package path
            return {"info": {"name": url.split("/")[-3], "version": "1"}}
        payload = json.loads(data)
        self.posts.append((url, payload))
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0)
            if url.endswith("/querybatch"):  # real shape: ids only
                return {
                    "results": [
                        {
                            "vulns": [
                                {"id": v["id"], "modified": "2025-01-01T00:00:00Z"}
                                for v in self.db.get(q["package"]["name"], [])
                            ]
                        }
                        for q in payload["queries"]
                    ]
                }
            name = payload["package"]["name"]
            if name in self.fail:
                return {"error": {"code": "network_error", "message": f"Failed to fetch {url}"}}
            vulns = copy.deepcopy(self.db.get(name, []))
            return {"vulns": vulns} if vulns else {}
        finally:
            self.in_flight -= 1


def make_client(osv: FakeOSV, cache_get=None) -> tuple[PyPIClient, MagicMock]:
    http = AsyncMock(spec=AsyncHTTPClient)
    http.fetch = AsyncMock(side_effect=osv.fetch)
    cache = MagicMock(spec=AsyncCacheManager)
    cache.get = AsyncMock(side_effect=cache_get or (lambda key: None))
    cache.set = AsyncMock()
    client = PyPIClient(
        config=PyPIClientConfig(),
        http_client=http,
        cache_manager=cache,
        stats_service=AsyncMock(spec=PackageStatsService),
    )
    return client, cache


# --- request shape ----------------------------------------------------------------------


async def test_single_query_puts_version_at_top_level():
    osv = FakeOSV({"django": [PYSEC_2022_1, GHSA_2GWJ]})
    client, _ = make_client(osv)
    await client.check_vulnerabilities("Django", "3.2.5")
    ((url, payload),) = osv.posts
    assert url == QUERY_URL
    assert payload == {"version": "3.2.5", "package": {"name": "django", "ecosystem": "PyPI"}}


async def test_batch_uses_one_query_per_unique_pair_never_querybatch():
    osv = FakeOSV({"django": [PYSEC_2022_1, GHSA_2GWJ], "jinja2": [JINJA2_GHSA]})
    client, _ = make_client(osv)
    await client.check_vulnerabilities_batch(
        [("Django", "3.2.5"), ("jinja2", "2.4.1"), ("django", "3.2.5")]
    )
    assert {url for url, _ in osv.posts} == {QUERY_URL}
    assert sorted(json.dumps(p, sort_keys=True) for _, p in osv.posts) == sorted(
        json.dumps(p, sort_keys=True)
        for p in (
            {"version": "3.2.5", "package": {"name": "django", "ecosystem": "PyPI"}},
            {"version": "2.4.1", "package": {"name": "jinja2", "ecosystem": "PyPI"}},
        )
    )


async def test_unversioned_query_has_no_version_key():
    osv = FakeOSV({"django": [GHSA_2GWJ]})
    client, _ = make_client(osv)
    await client.check_vulnerabilities_batch([("django", None)])
    assert osv.posts[0][1] == {"package": {"name": "django", "ecosystem": "PyPI"}}


# --- results ----------------------------------------------------------------------------


async def test_batch_reports_full_records_for_pinned_versions():
    osv = FakeOSV({"django": [PYSEC_2022_1, GHSA_2GWJ], "jinja2": [JINJA2_GHSA]})
    client, _ = make_client(osv)
    result = await client.check_vulnerabilities_batch([("Django", "3.2.5"), ("Jinja2", "2.4.1")])
    assert result["queried_count"] == 2
    assert result["vulnerable_count"] == 2
    assert "errors" not in result
    django = result["results"]["django:3.2.5"]
    assert django["vulnerable"] is True
    assert django["total_vulnerabilities"] == 2
    assert django["critical_count"] == 1
    assert [v["id"] for v in django["vulnerabilities"]] == ["GHSA-2gwj-7jmv-h26r", "PYSEC-2022-1"]
    pysec = django["vulnerabilities"][1]
    assert pysec["summary"].startswith("An issue was discovered in Django 2.2")
    assert "CVE-2021-45115" in pysec["cve"]
    assert result["results"]["jinja2:2.4.1"]["high_count"] == 1


async def test_multi_range_record_is_not_dropped_by_client_side_filtering():
    """3.2.5 sits in the 3.2 -> 3.2.11 pair, not the last (4.0 -> 4.0.1) one."""
    osv = FakeOSV({"django": [PYSEC_2022_1]})
    client, _ = make_client(osv)
    single = await client.check_vulnerabilities("django", "3.2.5")
    assert single["total_vulnerabilities"] == 1
    assert single["vulnerabilities"][0]["affected_versions"] == [
        ">=2.2, <2.2.26",
        ">=3.2, <3.2.11",
        ">=4.0, <4.0.1",
    ]
    batch = await client.check_vulnerabilities_batch([("django", "3.2.5"), ("flask", "3.0")])
    assert batch["results"]["django:3.2.5"]["total_vulnerabilities"] == 1


async def test_batch_caps_listed_vulnerabilities_at_20_with_true_totals():
    many = [dict(copy.deepcopy(GHSA_2GWJ), id=f"GHSA-{i}") for i in range(25)]
    osv = FakeOSV({"django": many})
    client, _ = make_client(osv)
    result = await client.check_vulnerabilities_batch([("django", "3.2.5"), ("flask", "3.0")])
    res = result["results"]["django:3.2.5"]
    assert res["total_vulnerabilities"] == 25
    assert res["critical_count"] == 25
    assert len(res["vulnerabilities"]) == 20


def _osv_vuln(vid: str, severity: str) -> dict:
    return {"id": vid, "summary": "s", "database_specific": {"severity": severity}}


async def test_batch_counts_moderate_as_medium_and_sorts_it_before_low():
    osv = FakeOSV(
        {"django": [_osv_vuln("L", "LOW"), _osv_vuln("M", "MODERATE"), _osv_vuln("H", "HIGH")]}
    )
    client, _ = make_client(osv)
    result = await client.check_vulnerabilities_batch([("Django", "4.2"), ("flask", "3.0")])
    res = result["results"]["django:4.2"]
    assert (res["high_count"], res["medium_count"], res["low_count"]) == (1, 1, 1)
    assert [v["id"] for v in res["vulnerabilities"]] == ["H", "M", "L"]


async def test_single_counts_moderate_as_medium_and_sorts_it_before_low():
    osv = FakeOSV({"django": [_osv_vuln("L", "LOW"), _osv_vuln("M", "MODERATE")]})
    client, _ = make_client(osv)
    res = await client.check_vulnerabilities("django", "4.2")
    assert res["medium_count"] == 1
    assert [v["id"] for v in res["vulnerabilities"]] == ["M", "L"]


async def test_batch_errors_are_per_item():
    osv = FakeOSV({"django": [GHSA_2GWJ]}, fail={"flask"})
    client, cache = make_client(osv)
    result = await client.check_vulnerabilities_batch([("django", "3.2.5"), ("flask", "3.0")])
    assert result["results"]["django:3.2.5"]["vulnerable"] is True
    assert "flask:3.0" not in result["results"]
    (error,) = result["errors"]
    assert error["package"] == "flask:3.0"
    assert error["code"] == "network_error"
    assert "Failed to fetch" in error["error"]
    cached_keys = [c.args[0] for c in cache.set.await_args_list]
    assert not any("flask" in key for key in cached_keys)  # failures are never cached


async def test_batch_limits_concurrency_to_10():
    osv = FakeOSV()
    client, _ = make_client(osv)
    result = await client.check_vulnerabilities_batch([(f"pkg-{i}", "1.0") for i in range(30)])
    assert result["queried_count"] == 30
    assert 1 < osv.max_in_flight <= 10


async def test_check_vulnerabilities_batch_empty_list():
    client, _ = make_client(FakeOSV())
    result = await client.check_vulnerabilities_batch([])
    assert result["total_packages"] == 0
    assert result["queried_count"] == 0
    assert result["vulnerable_count"] == 0


# --- cache ------------------------------------------------------------------------------


async def test_cache_key_prefix_changed_so_old_false_cleans_are_never_read():
    osv = FakeOSV({"django": [GHSA_2GWJ]})
    seen: list[str] = []

    async def cache_get(key):
        seen.append(key)
        if key.startswith("osv:vulnerabilities:"):  # a poisoned pre-4.0 entry
            return {"vulnerable": False, "total_vulnerabilities": 0, "vulnerabilities": []}
        return None

    client, cache = make_client(osv, cache_get)
    single = await client.check_vulnerabilities("django", "3.2.5")
    batch = await client.check_vulnerabilities_batch([("django", "3.2.5"), ("flask", "3.0")])
    assert single["total_vulnerabilities"] == 1
    assert batch["results"]["django:3.2.5"]["total_vulnerabilities"] == 1
    assert seen and all(key.startswith("osv:v2:") for key in seen)
    assert all(c.args[0].startswith("osv:v2:") for c in cache.set.await_args_list)


async def test_single_and_batch_share_cache_entries():
    store: dict[str, dict] = {}
    osv = FakeOSV({"django": [GHSA_2GWJ, PYSEC_2022_1]})

    async def cache_get(key):
        return store.get(key)

    client, cache = make_client(osv, cache_get)

    async def cache_set(key, data, etag=None, ttl=None):
        store[key] = data

    cache.set.side_effect = cache_set
    batch = await client.check_vulnerabilities_batch([("django", "3.2.5"), ("flask", "3.0")])
    posts = len(osv.posts)
    single = await client.check_vulnerabilities("django", "3.2.5", limit=1, offset=1)
    again = await client.check_vulnerabilities("django", "3.2.5")
    assert len(osv.posts) == posts  # served from the batch's cache entries
    assert batch["results"]["django:3.2.5"]["total_vulnerabilities"] == 2
    assert [v["id"] for v in single["vulnerabilities"]] == ["PYSEC-2022-1"]
    assert single["has_more"] is False
    assert again["total_vulnerabilities"] == 2  # a paginated call never poisons the cache
    assert len(again["vulnerabilities"]) == 2
    second = await client.check_vulnerabilities_batch([("django", "3.2.5"), ("flask", "3.0")])
    assert second["cached_count"] == 2 and second["queried_count"] == 0


# --- pagination of the single path --------------------------------------------------------


@pytest.mark.parametrize(
    ("offset", "limit", "listed", "has_more"), [(0, 10, 10, True), (3, 5, 2, False)]
)
async def test_check_vulnerabilities_pagination(offset, limit, listed, has_more):
    vulns = [_osv_vuln(f"GHSA-{i}", "MEDIUM") for i in range(25 if limit == 10 else 5)]
    client, _ = make_client(FakeOSV({"test-package": vulns}))
    result = await client.check_vulnerabilities("test-package", "1.0", limit=limit, offset=offset)
    assert (result["limit"], result["offset"]) == (limit, offset)
    assert result["total_vulnerabilities"] == len(vulns)
    assert len(result["vulnerabilities"]) == listed
    assert result["has_more"] is has_more


async def test_osv_result_pages_are_followed():
    pages = [
        {"vulns": [_osv_vuln("A", "HIGH")], "next_page_token": "t1"},
        {"vulns": [_osv_vuln("B", "LOW")]},
    ]
    bodies: list[dict] = []

    async def fetch(url, method="GET", headers=None, data=None):
        if data is None:
            return {"info": {"name": "django", "version": "1"}}
        bodies.append(json.loads(data))
        return pages[len(bodies) - 1]

    client, _ = make_client(FakeOSV())
    client.http.fetch = AsyncMock(side_effect=fetch)
    result = await client.check_vulnerabilities("django", "3.2.5")
    assert result["total_vulnerabilities"] == 2
    assert "page_token" not in bodies[0] and bodies[1]["page_token"] == "t1"
    assert bodies[1]["version"] == "3.2.5"
