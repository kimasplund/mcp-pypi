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
from mcp_pypi.core.search_index import NameIndex, Popularity, normalize, rank_candidates

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

    async def fetch_raw(self, url, headers=None):
        self.calls.append((url, dict(headers or {})))
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
