"""Tests for the Simple-index backed package search."""

import asyncio
import gzip
import json
import os
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from mcp_pypi.core import PyPIClient
from mcp_pypi.core.http import RawResponse
from mcp_pypi.core.models import PyPIClientConfig
from mcp_pypi.core.search_index import (
    IndexUnavailable,
    NameIndex,
    Popularity,
    normalize,
    rank_candidates,
)

NAMES = [
    "httpx", "http-client", "requests", "django", "zope-interface", "typing-extensions",
    "jwt", "pyjwt", "flask", "numpy", "pandas", "scipy", "pytest", "click", "rich",
    "beautifulsoup4", "lxml", "attrs", "six", "idna", "urllib3", "certifi", "charset-normalizer",
    "pyyaml", "jinja2", "markupsafe", "werkzeug", "itsdangerous", "boto3", "botocore",
    "s3transfer", "jmespath", "cryptography", "cffi", "pycparser", "packaging", "setuptools",
    "wheel", "pip", "tomli", "aiohttp", "aiosignal", "frozenlist", "multidict", "yarl",
    "async-timeout", "sqlalchemy", "greenlet", "pydantic", "starlette",
]  # fmt: skip


def index_body(names=NAMES) -> bytes:
    projects = [{"name": n.title(), "_last-serial": i} for i, n in enumerate(names)]
    projects.append({"name": "Zope.Interface", "_last-serial": 1})
    return json.dumps({"meta": {"api-version": "1.4"}, "projects": projects}).encode()


class FakeHTTP:
    """Serves fixture bytes through fetch_raw and records the calls."""

    def __init__(self, body=None, etag='"v1"', error=None):
        self.body = index_body() if body is None else body
        self.etag = etag
        self.error = error
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.timeouts: list[float | None] = []

    async def fetch_raw(self, url, headers=None, total_timeout=None):
        self.calls.append((url, dict(headers or {})))
        self.timeouts.append(total_timeout)
        await asyncio.sleep(0)
        if self.error:
            raise self.error
        if (headers or {}).get("If-None-Match") == self.etag:
            return RawResponse(304, b"", {"etag": self.etag})
        return RawResponse(200, self.body, {"etag": self.etag})


def test_normalize_variants():
    assert normalize("Django") == "django"
    assert normalize("zope.interface") == "zope-interface"
    assert normalize("typing_extensions") == normalize("Typing-Extensions") == "typing-extensions"


def joined(names=NAMES) -> str:
    return "\n" + "\n".join(sorted(normalize(n) for n in names)) + "\n"


def test_exact_match_ranks_first():
    assert rank_candidates("pyjwt", joined(), {})[0].name == "pyjwt"


def test_popular_any_token_beats_obscure_all_tokens():
    ranked = [c.name for c in rank_candidates("http client", joined(), {"httpx": 400_000_000})]
    assert ranked.index("httpx") < ranked.index("http-client")


async def test_names_downloads_normalizes_and_joins(tmp_path):
    names = await NameIndex(FakeHTTP(), tmp_path).names()
    assert names.startswith("\n") and names.endswith("\n")
    assert "\nzope-interface\n" in names
    assert "\nhttpx\n" in names


async def test_fresh_disk_copy_makes_no_request(tmp_path):
    await NameIndex(FakeHTTP(), tmp_path).names()
    http = FakeHTTP()
    names = await NameIndex(http, tmp_path).names()
    assert "\nhttpx\n" in names
    assert http.calls == []


async def test_stale_copy_sends_if_none_match_and_reuses_on_304(tmp_path):
    await NameIndex(FakeHTTP(), tmp_path).names()
    meta_path = tmp_path / "simple-index.meta.json"
    old = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    meta_path.write_text(json.dumps({"etag": '"v1"', "fetched_at": old}))

    http = FakeHTTP()
    names = await NameIndex(http, tmp_path).names()

    assert len(http.calls) == 1
    assert http.calls[0][1]["If-None-Match"] == '"v1"'
    assert http.calls[0][1]["Accept"] == "application/vnd.pypi.simple.v1+json"
    assert "\nhttpx\n" in names
    new = json.loads(meta_path.read_text())["fetched_at"]
    assert datetime.fromisoformat(new) > datetime.fromisoformat(old)


async def test_stale_copy_used_on_network_failure(tmp_path):
    await NameIndex(FakeHTTP(), tmp_path).names()
    meta_path = tmp_path / "simple-index.meta.json"
    old = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    meta_path.write_text(json.dumps({"etag": '"v1"', "fetched_at": old}))
    http = FakeHTTP(error=aiohttp.ClientError("down"))
    assert "\nhttpx\n" in await NameIndex(http, tmp_path).names()


async def test_concurrent_names_calls_download_once(tmp_path):
    http = FakeHTTP()
    index = NameIndex(http, tmp_path)
    results = await asyncio.gather(*(index.names() for _ in range(5)))
    assert len(http.calls) == 1
    assert all(r == results[0] for r in results)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
async def test_unwritable_cache_dir_still_searches(tmp_path):
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        names = await NameIndex(FakeHTTP(), ro).names()
    finally:
        ro.chmod(stat.S_IRWXU)
    assert "\nhttpx\n" in names


async def test_popularity_parses_rows_and_fails_soft(tmp_path):
    body = json.dumps(
        {
            "rows": [
                {"project": "Boto3", "download_count": 5},
                {"project": "x_y", "download_count": 1},
            ]
        }
    ).encode()
    assert await Popularity(FakeHTTP(body=body), tmp_path).downloads() == {"boto3": 5, "x-y": 1}
    broken = FakeHTTP(error=aiohttp.ClientError("down"))
    assert await Popularity(broken, tmp_path / "other").downloads() == {}
    assert await Popularity(FakeHTTP(body=b"not json"), tmp_path / "third").downloads() == {}


def make_client(tmp_path, http, downloads=None):
    client = PyPIClient(
        config=PyPIClientConfig(cache_dir=str(tmp_path)),
        http_client=http,
        cache_manager=MagicMock(),
        stats_service=MagicMock(),
    )
    client.popularity = MagicMock()
    client.popularity.downloads = AsyncMock(return_value=downloads or {})
    return client


async def test_index_unavailable_returns_network_error(tmp_path):
    client = make_client(tmp_path, FakeHTTP(error=aiohttp.ClientError("down")))
    result = await client.search_packages("x")
    assert result == {
        "error": {"code": "network_error", "message": "PyPI package index unavailable; retry later"}
    }


async def test_search_enriches_and_reranks_by_summary(tmp_path):
    client = make_client(tmp_path, FakeHTTP())
    summaries = {"jwt": "Unrelated thing", "pyjwt": "JSON Web Token implementation"}

    async def info(name):
        if name not in summaries:
            return {"error": {"code": "not_found", "message": "nope"}}
        return {"info": {"name": name.upper(), "version": "1.0", "summary": summaries[name]}}

    client.get_package_info = AsyncMock(side_effect=info)
    result = await client.search_packages("json jwt", limit=5)

    names = [r["name"] for r in result["results"]]
    assert names == ["PYJWT", "JWT"]
    assert set(result["results"][0]) == {
        "name", "version", "summary", "package_url", "popularity_rank",
    }  # fmt: skip
    assert result["results"][0]["package_url"] == "https://pypi.org/project/PYJWT/"
    assert result["results"][0]["popularity_rank"] is None
    assert result["query"] == "json jwt"
    assert result["total_candidates"] == 2
    assert "note" in result


async def test_search_no_match_sets_note(tmp_path):
    client = make_client(tmp_path, FakeHTTP())
    client.get_package_info = AsyncMock()
    result = await client.search_packages("qqqqzzzz")
    assert result["results"] == []
    assert result["note"].startswith("No package names matched.")


@pytest.mark.parametrize("query", ["", "   ", "-_."])
async def test_empty_query_is_invalid_input(tmp_path, query):
    client = make_client(tmp_path, FakeHTTP())
    result = await client.search_packages(query)
    assert result["error"]["code"] == "invalid_input"


async def test_suggest_names_close_match(tmp_path):
    client = make_client(tmp_path, FakeHTTP(), {"beautifulsoup4": 10, "requests": 9})
    assert await client.suggest_names("beautifulsoup") == ["beautifulsoup4"]


async def test_suggest_names_without_popularity(tmp_path):
    client = make_client(tmp_path, FakeHTTP(), {})
    assert await client.suggest_names("beautifulsoup") == []


def test_cache_files_are_gzip(tmp_path):
    asyncio.run(NameIndex(FakeHTTP(), tmp_path).names())
    text = gzip.decompress(Path(tmp_path, "simple-index.txt.gz").read_bytes()).decode()
    assert text.startswith("\n") and "\nhttpx\n" in text


async def test_all_enrichment_failures_return_the_error(tmp_path):
    client = make_client(tmp_path, FakeHTTP())
    err = {"error": {"code": "network_error", "message": "boom"}}
    client.get_package_info = AsyncMock(return_value=err)
    assert await client.search_packages("jwt") == err


async def test_partial_enrichment_failure_drops_candidates(tmp_path):
    client = make_client(tmp_path, FakeHTTP())

    async def info(name):
        if name == "jwt":
            return {"error": {"code": "network_error", "message": "boom"}}
        return {"info": {"name": name, "version": "1", "summary": ""}}

    client.get_package_info = AsyncMock(side_effect=info)
    result = await client.search_packages("jwt")
    assert [r["name"] for r in result["results"]] == ["pyjwt"]


def test_search_result_accepts_new_item_shape():
    from mcp_pypi.core.models import SearchResult

    hints = SearchResult.__annotations__
    assert "total_candidates" in hints and "note" in hints
    assert "dict[str, str]" not in str(hints["results"])


async def test_corrupt_disk_copy_is_replaced(tmp_path):
    (tmp_path / "simple-index.txt.gz").write_bytes(b"\x1f\x8b garbage")
    fresh = datetime.now(UTC).isoformat()
    (tmp_path / "simple-index.meta.json").write_text(
        json.dumps({"etag": None, "fetched_at": fresh})
    )
    http = FakeHTTP()
    assert "\nhttpx\n" in await NameIndex(http, tmp_path).names()
    assert len(http.calls) == 1
    assert gzip.decompress((tmp_path / "simple-index.txt.gz").read_bytes())


async def test_concurrent_failures_fetch_once(tmp_path):
    http = FakeHTTP(error=aiohttp.ClientError("down"))
    index = NameIndex(http, tmp_path)
    results = await asyncio.gather(*(index.names() for _ in range(5)), return_exceptions=True)
    assert len(http.calls) == 1
    assert all(isinstance(r, IndexUnavailable) for r in results)


async def test_concurrent_failures_with_stale_copy_fetch_once(tmp_path):
    await NameIndex(FakeHTTP(), tmp_path).names()
    old = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    (tmp_path / "simple-index.meta.json").write_text(
        json.dumps({"etag": '"v1"', "fetched_at": old})
    )
    http = FakeHTTP(error=aiohttp.ClientError("down"))
    index = NameIndex(http, tmp_path)
    results = await asyncio.gather(*(index.names() for _ in range(5)))
    assert len(http.calls) == 1
    assert all("\nhttpx\n" in r for r in results)


async def test_popularity_failure_backs_off(tmp_path):
    http = FakeHTTP(error=aiohttp.ClientError("down"))
    pop = Popularity(http, tmp_path)
    assert await pop.downloads() == {}
    assert await pop.downloads() == {}
    assert len(http.calls) == 1


# --- ranking with realistic popularity (R27) -----------------------------------------

# 30-day downloads from top-pypi-packages (October 2026), rounded.
REAL_DOWNLOADS = {
    "pyjwt": 565_000_000,
    "djangorestframework-simplejwt": 6_470_000,
    "flask-jwt-extended": 5_560_000,
    "jwt": 2_710_000,
    "types-pyjwt": 341_000,
    "python-jwt": 301_000,
    "pyyaml": 911_000_000,
    "ruamel-yaml": 155_000_000,
    "types-pyyaml": 73_800_000,
    "yamllint": 24_900_000,
    "strictyaml": 22_300_000,
    "pyyaml-env-tag": 13_300_000,
    "yaml-config": 2_520_000,
    "yamlfix": 1_280_000,
    "httpx": 617_000_000,
    "httpcore": 614_000_000,
    "aiohttp": 456_000_000,
    "httpx2": 222_000_000,
    "httptools": 212_000_000,
    "websocket-client": 166_000_000,
    "prometheus-client": 137_000_000,
    "google-api-python-client": 126_000_000,
    "httplib2": 119_000_000,
    "opentelemetry-instrumentation-aiohttp-client": 22_200_000,
    "python-http-client": 20_800_000,
    "geventhttpclient": 10_900_000,
    "ndg-httpsclient": 5_310_000,
    "aiohttp-client-cache": 1_270_000,
    "vonage-http-client": 232_000,
    "ipfshttpclient": 187_000,
    "http-client": 131_000,
    "aiohttp-sse-client": 104_000,
    "types-python-http-client": 82_000,
    "cube-http-client": 57_000,
    "yamlordereddictloader": 346_000,
    "yamlloader": 207_000,
    "yamlable": 113_000,
    "yaml-rs": 93_000,
    "yamlcore": 90_000,
    "yamlpath": 87_000,
    "requests": 1_210_000_000,
    "urllib3": 1_320_000_000,
    "boto3": 2_460_000_000,
}
# Real names without download data that ranked first before R27, plus filler hits.
OBSCURE = [
    "yaml", "jwts", "jwtee", "jwtpy", "jwtv2", "jwtlib", "jwtpie", "jwtgen", "jwt-py",
    "jwt-kms", "jwtools", "jwt-pro", "yamld", "yamlu",
    *(f"jwt-tool-{i}" for i in range(200)),
    *(f"yaml-thing-{i}" for i in range(200)),
    *(f"http-client-{i}" for i in range(200)),
]  # fmt: skip
SUMMARIES = {
    "pyjwt": "JSON Web Token implementation in Python",
    "jwt": "JSON Web Token library for Python 3.",
    "pyyaml": "YAML parser and emitter for Python",
    "yamllint": "A linter for YAML files.",
    "ruamel-yaml": "a YAML parser/emitter that supports roundtrip preservation",
    "httpx": "The next generation HTTP client.",
    "httpcore": "A minimal low-level HTTP client.",
    "aiohttp": "Async http client/server framework (asyncio)",
    "python-http-client": "HTTP REST client, simplified for Python",
}


def realistic_names() -> str:
    return joined([*REAL_DOWNLOADS, *OBSCURE])


def realistic_summary(name: str) -> str:
    # Worst case: every obscure name's summary repeats the query words.
    return SUMMARIES.get(name, f"{name}: a JWT YAML HTTP client helper")


def realistic_client(tmp_path) -> PyPIClient:
    http = FakeHTTP(body=index_body([*REAL_DOWNLOADS, *OBSCURE]))
    client = make_client(tmp_path, http, REAL_DOWNLOADS)

    async def info(name):
        return {"info": {"name": name, "version": "1.0", "summary": realistic_summary(name)}}

    client.get_package_info = AsyncMock(side_effect=info)
    return client


@pytest.mark.parametrize(
    ("query", "expected", "within"),
    [("jwt", "pyjwt", 3), ("yaml", "pyyaml", 3), ("http client", "httpx", 5)],
)
def test_rank_candidates_lets_popularity_cross_tiers(query, expected, within):
    ranked = [c.name for c in rank_candidates(query, realistic_names(), REAL_DOWNLOADS)]
    assert expected in ranked[:within], ranked[:10]


@pytest.mark.parametrize(
    ("query", "expected", "within"),
    [("jwt", "pyjwt", 3), ("yaml", "pyyaml", 3), ("http client", "httpx", 5)],
)
async def test_search_finds_the_main_package_for_common_queries(tmp_path, query, expected, within):
    result = await realistic_client(tmp_path).search_packages(query, limit=10)
    names = [r["name"] for r in result["results"]]
    assert expected in names[:within], names


@pytest.mark.parametrize("query", ["jwt", "yaml"])
async def test_exact_match_is_always_first_even_when_outscored(tmp_path, query):
    client = realistic_client(tmp_path)
    ranked = rank_candidates(query, realistic_names(), REAL_DOWNLOADS)
    assert ranked[0].name == query
    assert ranked[1].score > ranked[0].score  # pyjwt / pyyaml outscore the exact name
    result = await client.search_packages(query, limit=10)
    assert result["results"][0]["name"] == query


async def test_enrichment_always_includes_most_popular_token_matches(tmp_path):
    client = realistic_client(tmp_path)
    await client.search_packages("http client", limit=1)
    enriched = {c.args[0] for c in client.get_package_info.await_args_list}
    popular = sorted(
        (n for n in REAL_DOWNLOADS if "http" in n or "client" in n),
        key=REAL_DOWNLOADS.__getitem__,
        reverse=True,
    )[:10]
    assert set(popular) <= enriched


async def test_index_download_has_its_own_long_timeout(tmp_path):
    http = FakeHTTP()
    await NameIndex(http, tmp_path).names()
    assert http.timeouts == [120]
    body = json.dumps({"rows": [{"project": "x", "download_count": 1}]}).encode()
    pop_http = FakeHTTP(body=body)
    await Popularity(pop_http, tmp_path).downloads()
    assert pop_http.timeouts == [None]
