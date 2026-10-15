# Caching

mcp-pypi caches what it fetches on local disk so repeated lookups are fast and a large scan does not hammer PyPI or OSV. There are two independent parts: a general response cache, and the package-name index used by `search_packages`.

## Cache directory

Everything lives in one directory:

| Setting | Default |
|---------|---------|
| `--cache-dir` / `PYPI_CACHE_DIR` | the per-user cache directory (`~/.cache/mcp-pypi` on Linux, `~/Library/Caches/mcp-pypi` on macOS, `%LOCALAPPDATA%\mcp-pypi\Cache` on Windows) |

The default is private to your user account and survives restarts. Earlier versions used a shared `<system temp dir>/pypi_mcp_cache`; it is no longer read and can be deleted.

## Response cache

API responses (PyPI JSON, pypistats, feeds, OSV results) are stored as one JSON file per request, named by a SHA-256 hash of the request key. Each file holds the response, a timestamp, an optional ETag and a TTL.

| Setting | Default | Notes |
|---------|---------|-------|
| `PYPI_CACHE_TTL` / `--cache-ttl` | `604800` (1 week) | Seconds |
| `PYPI_VULNERABILITY_CACHE_TTL` | `3600` (1 hour) | Seconds; applies to vulnerability results |
| `PYPI_CACHE_MAX_SIZE` | `104857600` (100 MB) | Bytes; when exceeded, the least recently accessed files in the directory are pruned (this includes the search index files, which are downloaded again when needed). A single response larger than 80% of the limit is not cached. |

Expired entries are ignored and refetched. When a cached entry has an ETag, the refetch is conditional, so an unchanged resource costs a small request instead of a full download.

`--cache-strategy` / `PYPI_CACHE_STRATEGY` (`memory`, `disk`, `hybrid`) is accepted for compatibility with earlier versions. In 4.x responses are always cached on disk, and the setting does not change behaviour.

Network calls are retried with exponential backoff (`PYPI_MAX_RETRIES`, default 3; `PYPI_RETRY_DELAY`, default 1.0 s) and time out after `PYPI_TIMEOUT` seconds (default 30). The Simple index download has its own 120 second limit.

## Search index files

`search_packages` needs the list of all PyPI project names. PyPI's own search page cannot be used (it is behind a JavaScript challenge), so mcp-pypi downloads the [Simple index](https://peps.python.org/pep-0691/) and searches it locally. Two data sets are kept in the cache directory:

| Files | Source | Refreshed after |
|-------|--------|-----------------|
| `simple-index.txt.gz`, `simple-index.meta.json` | `https://pypi.org/simple/` (about 4 MB compressed; roughly 900,000 normalized names) | 24 hours |
| `popularity.json`, `popularity.meta.json` | [top-pypi-packages](https://hugovk.github.io/top-pypi-packages/) 30-day download counts | 7 days |

How refreshing works:

- The first search after startup loads the on-disk copy if there is one, and downloads a fresh copy only when it is older than the refresh interval. A cold start with no cached copy needs network access.
- Refreshes send `If-None-Match` with the stored ETag; a `304 Not Modified` just renews the timestamp.
- Only one refresh runs at a time; concurrent searches wait for it.
- If a refresh fails and a stale copy exists, the stale copy is used. After a failed refresh, mcp-pypi does not retry for 60 seconds. With no network and no cached copy, `search_packages` fails with an error; other tools are unaffected.
- A corrupt or unreadable cache file is treated as missing and replaced on the next refresh.
- Files are written atomically (temp file, then rename), so a crash cannot leave a half-written index.
- Popularity data is optional: if it is unavailable, results are ranked by name match alone.

## Managing the cache

```bash
mcp-pypi cache stats   # file count, size, location, TTL
mcp-pypi cache clear   # delete every file in the cache directory
```

`cache clear` also deletes the search index files, so the next search downloads them again. To use a different directory for one run: `mcp-pypi --cache-dir /path cache stats` or `mcp-pypi serve --cache-dir /path`.
