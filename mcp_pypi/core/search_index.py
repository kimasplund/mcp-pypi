"""Local package search over PyPI's Simple index plus a popularity dataset.

pypi.org/search sits behind a JS challenge, so we search names locally: the PEP 691
index (~900k names) is cached on disk and ranked together with 30-day download counts.
"""

import asyncio
import gzip
import json
import logging
import math
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple

import aiohttp

from mcp_pypi.core.http import AsyncHTTPClient

logger = logging.getLogger("mcp-pypi.search_index")

INDEX_URL = "https://pypi.org/simple/"
INDEX_ACCEPT = "application/vnd.pypi.simple.v1+json"
POPULARITY_URL = "https://hugovk.github.io/top-pypi-packages/top-pypi-packages.min.json"

TIER_EXACT, TIER_PREFIX, TIER_ALL_TOKENS, TIER_ANY_TOKEN = 4, 3, 2, 1
TIER_WEIGHTS = {TIER_EXACT: 1000, TIER_PREFIX: 500, TIER_ALL_TOKENS: 200, TIER_ANY_TOKEN: 50}
_SCAN_CAP = 50_000  # max raw substring hits gathered per query term


def normalize(name: str) -> str:
    """PEP 503 name normalization."""
    return re.sub(r"[-_.]+", "-", name).lower()


class IndexUnavailable(Exception):
    """No network and no cached copy of the package index."""


class Candidate(NamedTuple):
    name: str
    tier: int
    score: float


class _DiskBacked:
    """Data fetched over HTTP, cached on disk, refreshed at most once at a time."""

    url: str
    headers: dict[str, str] = {}
    data_file: str
    meta_file: str

    def __init__(self, http: AsyncHTTPClient, cache_dir: Path, max_age: timedelta):
        self.http = http
        self.cache_dir = Path(cache_dir)
        self.max_age = max_age
        self._lock = asyncio.Lock()
        self._data: Any = None
        self._etag: str | None = None
        self._fetched_at: datetime | None = None

    # Subclass hooks. All run in a worker thread.
    def _parse(self, body: bytes) -> tuple[Any, bytes]:
        """Response body -> (in-memory data, bytes to store on disk)."""
        raise NotImplementedError

    def _load(self, stored: bytes) -> Any:
        raise NotImplementedError

    def _fresh(self) -> bool:
        return (
            self._data is not None
            and self._fetched_at is not None
            and datetime.now(UTC) - self._fetched_at < self.max_age
        )

    async def _get(self) -> Any:
        if self._fresh():
            return self._data
        async with self._lock:
            if self._fresh():
                return self._data
            if self._data is None:
                await asyncio.to_thread(self._read_disk)
                if self._fresh():
                    return self._data
            return await self._refresh()

    def _read_disk(self) -> None:
        try:
            meta = json.loads((self.cache_dir / self.meta_file).read_text())
            fetched_at = datetime.fromisoformat(meta["fetched_at"])
            data = self._load((self.cache_dir / self.data_file).read_bytes())
        except (OSError, ValueError, KeyError, TypeError, EOFError) as e:
            logger.debug(f"No usable disk copy of {self.data_file}: {e}")
            return
        self._data, self._etag = data, meta.get("etag")
        self._fetched_at = fetched_at if fetched_at.tzinfo else fetched_at.replace(tzinfo=UTC)

    async def _refresh(self) -> Any:
        headers = dict(self.headers)
        if self._data is not None and self._etag:
            headers["If-None-Match"] = self._etag
        try:
            response = await self.http.fetch_raw(self.url, headers)
            if response.status == 200:
                data, stored = await asyncio.to_thread(self._parse, response.body)
                etag = response.headers.get("etag")
                self._data, self._etag = data, etag
                self._fetched_at = datetime.now(UTC)
                await asyncio.to_thread(self._write_disk, stored)
                return self._data
            if response.status == 304 and self._data is not None:
                self._fetched_at = datetime.now(UTC)
                await asyncio.to_thread(self._write_meta)
                return self._data
            raise IndexUnavailable(f"{self.url} returned HTTP {response.status}")
        except (
            aiohttp.ClientError,
            TimeoutError,
            IndexUnavailable,
            ValueError,
            KeyError,
            TypeError,
        ) as e:
            if self._data is not None:
                logger.warning(f"Refresh of {self.url} failed ({e}); using stale copy")
                return self._data
            raise IndexUnavailable(str(e)) from e

    def _write_disk(self, stored: bytes) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._atomic_write(self.data_file, stored)
            self._write_meta()
        except OSError as e:
            logger.warning(f"Could not cache {self.data_file} on disk ({e}); keeping in memory")

    def _write_meta(self) -> None:
        meta = {"etag": self._etag, "fetched_at": (self._fetched_at or datetime.now()).isoformat()}
        try:
            self._atomic_write(self.meta_file, json.dumps(meta).encode())
        except OSError as e:
            logger.warning(f"Could not write {self.meta_file} ({e})")

    def _atomic_write(self, name: str, content: bytes) -> None:
        tmp = self.cache_dir / f".{name}.{os.getpid()}.tmp"
        try:
            tmp.write_bytes(content)
            tmp.replace(self.cache_dir / name)
        finally:
            tmp.unlink(missing_ok=True)


class NameIndex(_DiskBacked):
    """All normalized PyPI project names, from the PEP 691 Simple index."""

    url = INDEX_URL
    headers = {"Accept": INDEX_ACCEPT}
    data_file = "simple-index.txt.gz"
    meta_file = "simple-index.meta.json"

    def __init__(
        self,
        http: AsyncHTTPClient,
        cache_dir: Path,
        max_age: timedelta = timedelta(hours=24),
    ):
        super().__init__(http, cache_dir, max_age)

    def _parse(self, body: bytes) -> tuple[str, bytes]:
        projects = json.loads(body)["projects"]
        names = sorted({normalize(p["name"]) for p in projects})
        del projects  # the 900k-entry list must not outlive this call
        joined = "\n" + "\n".join(names) + "\n"
        return joined, gzip.compress(joined.encode())

    def _load(self, stored: bytes) -> str:
        return gzip.decompress(stored).decode()

    async def names(self) -> str:
        """All names joined by newlines, with a leading and trailing newline.

        Raises IndexUnavailable if there is neither network nor a disk copy.
        """
        return await self._get()


class Popularity(_DiskBacked):
    """30-day download counts for the most popular projects."""

    url = POPULARITY_URL
    data_file = "popularity.json"
    meta_file = "popularity.meta.json"

    def __init__(
        self,
        http: AsyncHTTPClient,
        cache_dir: Path,
        max_age: timedelta = timedelta(days=7),
    ):
        super().__init__(http, cache_dir, max_age)

    def _parse(self, body: bytes) -> tuple[dict[str, int], bytes]:
        rows = json.loads(body)["rows"]
        downloads = {normalize(r["project"]): int(r["download_count"]) for r in rows}
        return downloads, json.dumps(downloads).encode()

    def _load(self, stored: bytes) -> dict[str, int]:
        return json.loads(stored)

    async def downloads(self) -> dict[str, int]:
        """Normalized name -> downloads; empty when unavailable."""
        try:
            return await self._get()
        except Exception as e:
            logger.warning(f"Popularity data unavailable: {e}")
            return {}


def query_tokens(query: str) -> list[str]:
    return [normalize(t) for t in re.split(r"[\s\-_.]+", query) if t]


def _lines_with(names: str, needle: str, cap: int = _SCAN_CAP) -> set[str]:
    """Distinct lines of `names` containing `needle` (stops after `cap` hits)."""
    found: set[str] = set()
    pos = 0
    while len(found) < cap:
        i = names.find(needle, pos)
        if i < 0:
            break
        start = names.rfind("\n", 0, i) + 1
        end = names.find("\n", i)
        found.add(names[start:end])
        pos = end + 1
    return found


def _names_starting_with(names: str, prefix: str, cap: int = _SCAN_CAP) -> set[str]:
    found: set[str] = set()
    pos = 0
    while len(found) < cap:
        i = names.find("\n" + prefix, pos)
        if i < 0:
            break
        end = names.find("\n", i + 1)
        found.add(names[i + 1 : end])
        pos = end
    return found


def rank_candidates(
    query: str, names: str, downloads: dict[str, int], pool: int = 500
) -> list[Candidate]:
    """Rank index names against a query; best score first, at most `pool` results."""
    q = normalize(query.strip())
    tokens = query_tokens(query)
    if not q or not tokens:
        return []

    hits: set[str] = set()
    if f"\n{q}\n" in names:
        hits.add(q)
    hits |= _names_starting_with(names, q)
    for token in tokens:
        hits |= _lines_with(names, token)
    # Popular names always get a look, however many obscure hits there are.
    hits |= {n for n in downloads if any(t in n for t in tokens)}

    scored: list[Candidate] = []
    for name in hits:
        matched = sum(t in name for t in tokens)
        if name == q:
            tier = TIER_EXACT
        elif name.startswith(q):
            tier = TIER_PREFIX
        elif matched == len(tokens):
            tier = TIER_ALL_TOKENS
        elif matched:
            tier = TIER_ANY_TOKEN
        else:
            continue
        score = TIER_WEIGHTS[tier] - 0.5 * len(name)
        if downloads.get(name, 0) > 0:
            score += 25 * math.log10(downloads[name])
        scored.append(Candidate(name, tier, score))

    scored.sort(key=lambda c: (c.tier, c.score), reverse=True)
    pooled = scored[:pool]
    pooled.sort(key=lambda c: c.score, reverse=True)
    return pooled
