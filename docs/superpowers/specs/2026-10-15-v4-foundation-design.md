# mcp-pypi v4.0 Foundation — Design Spec

- **Date:** 2026-10-15
- **Status:** Approved in conversation (sections 1–5); awaiting written-spec review
- **Branch:** `feat/v4-foundation`
- **Follow-up:** Spec 2 "Safety intelligence" (separate spec → plan → implementation cycle)

## 1. Intent

### What the owner asked for
"Check and organise this properly and set it up as it should be, then research latest
features and update functions."

### Agreed decisions
| Decision | Choice |
|---|---|
| Compatibility | **Major 4.0, clean break.** Legacy Python modules may be removed; tools may be merged/renamed. `serve` and `stdio` CLI commands must keep working. CHANGELOG documents migration. |
| Deployment target | **Local stdio first** (Claude Code / Desktop / Cursor via `mcp-pypi serve` or `uvx mcp-pypi serve`). HTTP stays a simple localhost streamable-http option. No auth, Docker, or hosting work. |
| Sequencing | **Two specs.** This spec = v4.0 foundation (cleanup, tooling, fastmcp 4, typed outputs, consolidated tools, search fix). Spec 2 = new safety features. |

### Success criteria
1. `search_packages` returns real results again (it currently always returns `results: []`
   because PyPI serves a Fastly JS challenge on `/search/` — verified 2026-10-15).
2. The server runs on `fastmcp>=4.1,<5` over stdio and streamable HTTP; SSE is gone.
3. The MCP surface is 11 tools, each with `title`, read-only annotations, an `outputSchema`,
   and errors reported as `isError` tool results.
4. One config file (`pyproject.toml`), uv + hatchling + ruff + pyrefly, CI on every push/PR.
5. No dead modules remain; all tests pass (`ruff check`, `ruff format --check`, `pyrefly check`,
   `pytest`) on Python 3.11–3.14.
6. README, CHANGELOG (with v3→v4 tool mapping) and `docs/` describe v4 accurately.

### Non-goals (this spec)
- New safety features (deferred to Spec 2, see §9).
- Refactoring `core/` to raise exceptions instead of returning error dicts.
- Hosting concerns: OAuth/bearer auth, Docker, MCP Registry `server.json`, `.mcpb` bundles.
- Tagging, releasing, or publishing to PyPI (owner does this).

## 2. Current state (baseline, verified 2026-10-15)

- `fastmcp==3.2.0`, `mcp>=1.9.4`; latest are fastmcp 4.1.0 (built on `mcp` SDK 2.x) and mcp 2.3.0.
- 148 tests pass on Python 3.12 with fastmcp 3.2.0.
- 23 MCP tools with heavy overlap (5 security-audit variants, 4 package-info variants).
  Docstrings are long, contain uppercase "IMPORTANT ACTIONS" blocks.
- `get_security_report` returns ANSI escape codes (`\033[91m`) to the LLM.
- Tools return `{"error": {...}}` dicts as *successful* results — clients never see `isError`.
- HTTP mode uses `transport="sse"` / `run_sse_async` (SSE deprecated in the MCP spec;
  `run_sse_async` removed in fastmcp 4). `PROTOCOL_VERSION = "2025-06-18"` is hardcoded.
- `PyPIClient`'s aiohttp session is never closed by the server.
- User-Agent impersonates a browser: `Mozilla/5.0 (compatible; MCP-PyPI/2.0; ...)`.
- Dead / duplicate code (≈3,000 lines): `mcp_pypi/client.py` (legacy hand-rolled MCP client),
  `mcp_pypi/cli/server.py` (aiohttp JSON-RPC `RPCServer`), `mcp_pypi/utils/cache.py`
  (1,371 lines, imported by nothing), `mcp_pypi/utils/common/{caching,error_handling,constants}.py`
  (used only by tests/benchmarks).
- Config split across `pyproject.toml`, `setup.cfg` (empty stub), `requirements.txt` (copy),
  `MANIFEST.in` (lists files that don't exist), `pytest.ini`, `pyrefly.toml`, `.pylintrc`.
- CI only runs on release creation; publishing uses stored API-token secrets.
- README advertises a non-existent `[http]` extra and "FastMCP 2.14.4".

## 3. Repository layout & tooling

### 3.1 Deletions
| Path | Reason |
|---|---|
| `mcp_pypi/client.py` | Legacy MCP client; superseded by `fastmcp.Client` |
| `mcp_pypi/cli/server.py` (+ its export in `cli/__init__.py`) | Legacy JSON-RPC server, unused by `serve` |
| `mcp_pypi/utils/cache.py` | Imported by nothing |
| `mcp_pypi/utils/common/` (`caching.py`, `error_handling.py`, `constants.py`, `__init__.py`) | Used only by tests/benchmarks; real cache is `core/cache`. `validation.py` moves to `utils/validation.py` |
| `tests/utils/common/test_caching.py`, `tests/utils/common/test_hybrid_caching.py` | Test deleted code |
| `examples/caching_benchmark.py`, `examples/standalone_cache_benchmark.py`, `examples/client_example.py`, `examples/debug_server.py` | Use deleted code; replaced by one `examples/client_example.py` using `fastmcp.Client` |
| `setup.cfg`, `requirements.txt`, `MANIFEST.in`, `pytest.ini`, `pyrefly.toml`, `.pylintrc` | Folded into `pyproject.toml` or obsolete under hatchling/ruff |
| `TOOL_DESCRIPTION_IMPROVEMENTS.md` | Guidance moves into server `instructions` (§4.3) |
| root `pypi.md` | Duplicate of `docs/pypi.md`; no code references it (`cli/main.py:get_markdown_file` only loads `README.md`/`CHANGELOG.md`) |
| `docs/mcp_monitor.md`, `docs/protocol_version_negotiation.md` | Describe code that no longer exists |
| `docs/diagrams/classes_caching.png` | Diagrams deleted caching classes (verify) |
| `.osv-scanner.toml` ignore entries | Re-evaluate after dependency bump; drop entries for pydantic <2.4 advisories if the scanner no longer flags them |

### 3.2 Target package layout
```
mcp_pypi/
  __init__.py          __version__ = "4.0.0" (single source of truth)
  __main__.py
  py.typed
  core/                PyPI + OSV access; framework-free; returns dicts (unchanged contract)
    client.py  http/  cache/  models/  stats.py
    package_ops.py  search_ops.py  dependency_ops.py  vulnerability_ops.py
    requirements_ops.py  feed_ops.py
    search_index.py    NEW: Simple-index name index + ranking (§6)
    project_files.py   NEW: pure dependency-file discovery + parsers (requirements*.txt,
                       pyproject.toml, setup.py/cfg, Pipfile(.lock), poetry.lock, conda),
                       extracted from server/helpers.py and requirements_ops.py; framework-free
                       so the CLI and Spec 2 parsers (pylock.toml, uv.lock) can reuse it
  server/
    __init__.py        re-exports build_server
    app.py             build_server(config=None, client=None) -> FastMCP
    errors.py          unwrap() + error-code → ToolError mapping
    schemas.py         Pydantic output models for all tools
    instructions.py    server instructions text
    prompts.py  resources.py
    tools/
      packages.py      search_packages, get_package, get_package_versions,
                       compare_versions, get_package_changelog, get_download_stats
      dependencies.py  get_dependencies
      security.py      check_packages, check_vulnerabilities, scan_installed_packages
      project.py       audit_project
  cli/
    main.py  commands/{serve,package,feed,cache,search}.py  utils.py
  utils/
    __init__.py  validation.py  sanitize.py (from utils/helpers.py)  logging.py
```
Files may be split further during implementation if any exceeds ~400 lines; module
boundaries above are the contract.

### 3.3 Packaging (`pyproject.toml` only)
- Build backend: **hatchling**; version read from `mcp_pypi/__init__.py`
  (`[tool.hatch.version] path = "mcp_pypi/__init__.py"`).
- `requires-python = ">=3.11"` (3.10 reached end-of-life October 2026); classifiers 3.11–3.14.
  Drop `tomli` and `typing_extensions` conditional deps; use `tomllib` and `typing.NotRequired`.
- Runtime deps: `fastmcp>=4.1,<5`, `aiohttp`, `packaging`, `typer`, `rich`, `defusedxml`,
  each with a floor at the current release line. Add `mcp>=2,<3` **only if** code still imports
  `mcp.types` after the migration (prefer fastmcp re-exports).
- Remove extras `all`, `viz`, `search`, `docs` (bs4 no longer needed; plotly/kaleido never
  imported; sphinx unused). Dev tooling moves to PEP 735 `[dependency-groups] dev = [...]`:
  pytest, pytest-asyncio, pytest-cov, ruff, pyrefly.
- `[project.scripts] mcp-pypi = "mcp_pypi.cli.main:app"` (unchanged), so `uvx mcp-pypi serve` works.
- Commit `uv.lock`.
- Tool config in `pyproject.toml`: `[tool.ruff]` (line-length 100, target py311, rules
  `E,F,I,UP,B,ASYNC,SIM`), `[tool.pyrefly]` (from current `pyrefly.toml`),
  `[tool.pytest.ini_options]` (asyncio_mode=auto, markers, `-m "not integration"` default).

### 3.4 CI / release
- **New `.github/workflows/ci.yml`** on `push` and `pull_request`: `astral-sh/setup-uv`,
  `uv sync --locked`, `ruff check`, `ruff format --check`, `pyrefly check`,
  `pytest` on a 3.11/3.12/3.13/3.14 matrix.
- **Replace** `pypi-main.yml` and `pypi-test.yml` with one `release.yml`: on release
  `published` (and manual dispatch) → run CI job → `uv build` → publish to TestPyPI → publish to
  PyPI, using **Trusted Publishing** (`permissions: id-token: write`, no token secrets).
  Owner must register the Trusted Publisher on pypi.org and test.pypi.org (documented in PR).
- Keep `osv-scanner.yml` and `dependabot.yml`; add the `uv` ecosystem and `github-actions`
  ecosystem to dependabot.
- `tests/manual/` content becomes `@pytest.mark.integration` tests under `tests/integration/`.

## 4. Framework & server wiring

### 4.1 Server construction
- `server/app.py`:
  ```python
  def build_server(config: PyPIClientConfig | None = None,
                   client: PyPIClient | None = None) -> FastMCP: ...
  ```
  - If `client` is given (tests), use it; otherwise create `PyPIClient(config)`.
  - A FastMCP **lifespan** closes the client (`await client.close()`) on shutdown.
  - Calls `register_package_tools(mcp, client)`, `register_dependency_tools(mcp, client)`,
    `register_security_tools(mcp, client)`, `register_project_tools(mcp, client)`,
    `register_resources(mcp, client)`, `register_prompts(mcp)`.
- `PyPIMCPServer` class is removed (clean break). `mcp_pypi.server` exports `build_server`.
- `FastMCP(name="mcp-pypi", version=__version__, instructions=INSTRUCTIONS,
  website_url="https://github.com/kimasplund/mcp-pypi", mask_error_details=True, lifespan=...)`.
  Confirm each kwarg against the installed fastmcp 4.1 source during implementation; drop any
  that do not exist rather than guessing.

### 4.2 Tool registration conventions
Every tool:
- `title=` human-readable title.
- annotations: `readOnlyHint=True`, `idempotentHint=True`, `openWorldHint=True` on all 11
  tools (every tool queries PyPI, OSV, or pypistats, including the local-file tools).
- `timeout=`: 60 s for lookups; 180 s for `audit_project`, `scan_installed_packages`, and
  `check_vulnerabilities` with `include_transitive=True` (set at the tool level: 180 s).
- Docstring 5–10 lines: purpose, when to use, args. No uppercase action blocks.
- Return annotation is a Pydantic model from `server/schemas.py` → FastMCP emits `outputSchema`.
- Long-running tools (`check_vulnerabilities` with >1 package or transitive, `audit_project`,
  `scan_installed_packages`) call `ctx.report_progress(done, total)`.
- No MCP protocol logging (`ctx.info` etc.); Python `logging` to **stderr** only.

### 4.3 Instructions
`server/instructions.py` holds a ≤40-line string covering: which tool to use when
(search → get_package → check_packages before suggesting deps; audit_project for a repo),
and the dependency-file authority order (pyproject.toml primary; requirements*.txt secondary/
generated; setup.py/setup.cfg legacy — update the primary first and keep constraints
consistent across files). This replaces `TOOL_DESCRIPTION_IMPROVEMENTS.md` and the docstring
"IMPORTANT ACTIONS" blocks.

### 4.4 Transports & CLI
- `mcp-pypi serve [--transport stdio|http] [--host 127.0.0.1] [--port 8143] [cache/log/UA opts]`
  and `mcp-pypi stdio` both remain.
- `stdio` → `mcp.run(transport="stdio")`.
- `http` → `mcp.run(transport="http", host=host, port=port)`; endpoint `http://127.0.0.1:8143/mcp`.
  Help text and `--help-connecting` output updated (no `/sse`).
- `sse` transport, `run_sse_async`, `run_async` method, and `PROTOCOL_VERSION` are removed.
- Logging configured to stderr before the server starts (stdio stdout must stay clean).

### 4.5 Resources & prompts
- Resources unchanged in URI and content: `pypi://recent-releases`, `pypi://new-packages`,
  `pypi://updated-packages`.
- Prompts gain arguments:
  - `analyze_dependencies(package_name: str)` — asks the model to use `get_dependencies`,
    `check_vulnerabilities(include_transitive=True)` and report outdated/vulnerable deps.
  - `compare_packages(packages: str)` (comma-separated names) — asks the model to use
    `get_package`, `get_download_stats`, `check_vulnerabilities` and recommend one.
  Prompts return plain message content using the fastmcp 4 prompt API (verify return type).

### 4.6 HTTP etiquette
- Default User-Agent: `mcp-pypi/{__version__} (+https://github.com/kimasplund/mcp-pypi)`.
  Still overridable via `PYPI_USER_AGENT` / `--user-agent`.
- No fastmcp response-caching middleware: `core/cache` already caches HTTP responses.

## 5. Tool surface (23 → 11)

| # | v4.0 tool | Signature | Replaces (v3) |
|---|---|---|---|
| 1 | `search_packages` | `(query: str, limit: int = 10)` | `search_packages` |
| 2 | `get_package` | `(package_name: str, version: str \| None = None)` | `get_package_info`, `get_package_metadata`, `get_latest_version`, `check_package_exists`, `get_package_documentation` |
| 3 | `get_package_versions` | `(package_name: str, limit: int = 20, offset: int = 0, sort: Literal["newest","oldest"] = "newest")` | `get_package_releases`, `list_package_versions` |
| 4 | `compare_versions` | `(package_name: str, version1: str, version2: str)` | `compare_versions` |
| 5 | `get_package_changelog` | `(package_name: str, version: str \| None = None)` | `get_package_changelog` |
| 6 | `get_download_stats` | `(package_name: str)` | `get_package_stats` |
| 7 | `get_dependencies` | `(package_name: str, version: str \| None = None, depth: int = 1)` | `get_dependencies`, `get_dependency_tree` |
| 8 | `check_packages` | `(names: list[str])` | `batch_check_packages` |
| 9 | `check_vulnerabilities` | `(packages: list[str], include_transitive: bool = False, max_depth: int = 2)` | `check_vulnerabilities`, `batch_check_vulnerabilities`, `scan_dependency_vulnerabilities` |
| 10 | `audit_project` | `(path: str, detail: Literal["summary","full"] = "summary")` | `security_audit_project`, `quick_security_check`, `get_security_report`, `check_requirements_txt`, `check_pyproject_toml` |
| 11 | `scan_installed_packages` | `(environment_path: str \| None = None)` | `scan_installed_packages` |

### 5.1 Tool behaviour
1. **search_packages** — see §6. `limit` clamped to 1–50.
2. **get_package** — one call to `/pypi/<name>/json` (or `/<name>/<version>/json`). Returns
   name, version, latest_version, summary, requires_python, license (prefer
   `license_expression`, fall back to `license`), author/maintainer, homepage/docs/source/
   changelog URLs from `project_urls`, classifiers, yanked flag (for a pinned version),
   release_count, latest_upload_time. Not found → `ToolError` with suggestion (§7.2).
3. **get_package_versions** — paginated list of `{version, upload_time, yanked,
   yanked_reason, file_types}`; plus `total`, `offset`, `limit`, `has_more`. `limit` 1–100.
4. **compare_versions** — unchanged semantics (PEP 440 comparison; which is newer).
5. **get_package_changelog** — unchanged semantics.
6. **get_download_stats** — pypistats recent (day/week/month); unchanged source.
7. **get_dependencies** — `depth=1`: direct requirements (name, specifier, extras, markers).
   `depth` 2–5: tree (existing tree code). `depth` clamped 1–5.
8. **check_packages** — 1–100 names, concurrent. Per item: `{name, exists, normalized_name,
   latest_version, summary, error}`. Never raises for a single bad name. (Spec 2 extends this
   item with a safety verdict.)
9. **check_vulnerabilities** — items are requirement strings: `"django"` (latest version) or
   `"requests==2.31.0"`; other specifiers rejected per-item with a clear error. 1–100 items.
   Uses OSV `querybatch` for >1 item. `include_transitive=True` resolves each package's
   dependency tree to `max_depth` (1–3) and checks every node, reporting the path that
   introduces each vulnerable dependency. Per item: `{package, version, vulnerable,
   vulnerabilities:[{id, summary, severity, aliases, affected_versions, references}],
   introduced_via, error}` plus totals. (`fixed_versions` needs OSV `affected[].ranges`
   parsing, which core does not do yet — deferred to Spec 2 with the other OSV work.)
10. **audit_project** — `path` is a directory or a single dependency file. Directory mode
    discovers: `pyproject.toml`, `requirements*.txt`, `setup.py`, `setup.cfg`, `Pipfile`,
    `Pipfile.lock`, `poetry.lock`, `environment.yml`/`environment.yaml`. Path validated with
    existing `validate_file_path` (no traversal). Result: per-file packages with
    `{name, constraint, resolved_version, latest_version, outdated, vulnerable,
    vulnerabilities}`, `consistency_warnings` (same package, different constraints across
    files), `totals`, `recommendations` (list of strings), and `summary` (plain markdown,
    no ANSI). `detail="summary"` omits clean packages from per-file lists.
11. **scan_installed_packages** — unchanged behaviour (venv auto-detection, path validation);
    output moved to a schema model; no ANSI.

### 5.2 Removed without replacement
- ANSI-colour report formatting (`format_security_report` colours).
- `output_format` parameters (replaced by `detail` on `audit_project`; others always structured).

## 6. Search fix

### 6.1 Why
`https://pypi.org/search/` serves a Fastly JS "Client Challenge" page (HTTP 200, ~3 KB) to
non-browser clients; the current scraper detects it and returns `results: []`. PyPI states
search is for interactive use; XML-RPC search is disabled. Verified 2026-10-15.

### 6.2 Data sources (verified live 2026-10-15)
| Source | Use | Size / freshness |
|---|---|---|
| `GET https://pypi.org/simple/` with `Accept: application/vnd.pypi.simple.v1+json` | All project names (PEP 691) | 914,200 projects; ~10 MB gzip; `ETag`; `cache-control: max-age=600` |
| `https://hugovk.github.io/top-pypi-packages/top-pypi-packages.min.json` | Popularity ranking (top 15,000 by 30-day downloads) | ~787 KB; updated monthly (last 2026-10-01) |
| `GET https://pypi.org/pypi/<name>/json` | Enrich top candidates (summary, latest version) | Existing, cached by `core/cache` |

### 6.3 `core/search_index.py`
- `class NameIndex`: loads/refreshes the simple index.
  - Disk cache: `<cache_dir>/simple-index.json.gz` + `<cache_dir>/simple-index.etag`.
  - Refresh policy: if cached copy is <24 h old, use it; else conditional GET with
    `If-None-Match`; `304` → touch timestamp and reuse.
  - In memory: one `"\n"`-joined string of PEP 503-normalized names (≈15 MB), plus a dict
    `normalized → display name` built lazily only for returned candidates.
  - Concurrency: an `asyncio.Lock` so concurrent searches trigger one download.
- `class Popularity`: same caching pattern for the top-packages JSON (refresh ≤ weekly);
  maps normalized name → download rank. Failure to fetch is non-fatal (ranking degrades).
- `search(query, limit) -> list[Candidate]`:
  1. Normalize query; tokens = split on whitespace/`-_.`; drop empty.
  2. Candidates in tiers: exact name match → prefix match on full normalized query →
     names containing all tokens → names containing any token. Cap candidate pool at 500.
  3. Score = tier weight + popularity boost (`log10(downloads)` scaled) − length penalty.
  4. Take top `min(3*limit, 30)`; enrich concurrently via `get_package_info` (cached);
     add a bonus for query tokens present in the summary; re-sort; return top `limit`.
- Failure to obtain the index (network error and no disk copy) → error dict with code
  `network_error` → `ToolError` ("PyPI package index unavailable; retry later").

### 6.4 Result model
`SearchResults{query, results:[{name, version, summary, package_url, popularity_rank|None}],
total_candidates, note|None}`. When nothing matches, `note` suggests name-like keywords.
Tool docstring states that matching is on package **names** (with summary re-ranking of top
candidates), not full-text descriptions.

### 6.5 Removed
`beautifulsoup4` dependency (used only by search), `PyPIClient._has_bs4`, HTML-scraping code
in `core/search_ops.py`, challenge-page detection, `tests/core/test_bs4.py` (a manual script,
not a pytest test).

## 7. Outputs & errors

### 7.1 Output models
- `server/schemas.py` defines one Pydantic `BaseModel` per tool result (and shared item
  models). snake_case fields; `package_name`/`latest_version` naming consistent everywhere.
- Tools construct models from core dicts via small `from_core(...)` mappers in the tool
  modules; models are the only shape clients see.

### 7.2 Error mapping (`server/errors.py`)
```python
def unwrap(result: dict, *, package: str | None = None) -> dict:
    """Return result unchanged, or raise ToolError if it is a core error dict."""
```
| core `error.code` | ToolError message pattern |
|---|---|
| `not_found` | `Package '{x}' not found on PyPI. Use search_packages to find the exact name.` + "Did you mean '{y}'?" when the name index has a close match (difflib ratio ≥ 0.85 against top-15k popular names; best effort, skipped if index not loaded) |
| `invalid_input` | the core message, prefixed `Invalid input: ` |
| `network_error` / `timeout_error` / `rate_limit_error` | `{service} request failed ({code}); retry later.` |
| `file_error` / `permission_error` | `Cannot read file: {message}` (core messages already name the path) |
| other | `Unexpected error ({code})` — details logged to stderr only |
- Batch tools (`check_packages`, `check_vulnerabilities`, per-file failures in
  `audit_project`) never call `unwrap` per item; they place `error: str` on the item.
- Unexpected exceptions: `mask_error_details=True` → generic message to client, traceback to
  stderr.

## 8. Testing & delivery

### 8.1 Tests
- **Keep & update:** `tests/core/{test_cache,test_http,test_client,test_pypi_client,
  test_stats,test_batch_vulnerabilities,test_pagination}.py`, `tests/utils/test_utils.py`,
  `tests/utils/common/test_validation.py` (moved to `tests/utils/test_validation.py`),
  `tests/cli/*`, `tests/test_main_entry.py`.
- **Delete:** tests of deleted modules (§3.1), `tests/core/test_bs4.py`,
  `tests/server/test_mcp_server.py` (replaced).
- **New `tests/server/`** using in-memory `fastmcp.Client(build_server(client=FakePyPIClient()))`:
  - `test_contract.py`: tool names == the 11 in §5; each has `title`, `readOnlyHint=True`,
    and an `outputSchema`; resources and prompts listed with expected names/arguments.
  - One test module per tool group: happy path returns `structuredContent` validating against
    the schema; not-found → `isError` with hint; batch partial failure → per-item `error`.
- **New `tests/core/test_search_index.py`** with a fixture index (≈50 names) and fixture
  popularity: tier ordering, popularity boost, summary re-rank, `304` reuse, missing index →
  error dict, concurrent searches download once.
- **CLI:** `serve --transport http` invokes `run(transport="http", host, port)` (mocked);
  `stdio` command still works.
- **Integration (`-m integration`, network):** search `httpx` returns `httpx` first;
  `get_package("requests")`; `check_vulnerabilities(["jinja2==2.4.1"])` reports ≥1 vuln.
- Implementation follows TDD (failing test first per behaviour).

### 8.2 Docs
- README rewritten: correct badges, `uvx mcp-pypi serve` / `pip install mcp-pypi`, Claude Code
  (`claude mcp add mcp-pypi -- uvx mcp-pypi serve`), Claude Desktop (`mcpServers` key), Cursor,
  11-tool table, HTTP mode, configuration env vars, migration pointer.
- `CHANGELOG.md` `4.0.0` entry: breaking changes + v3→v4 tool mapping table (§5) + removed
  Python modules + Python ≥3.11.
- `docs/usage.md`, `docs/server.md`, `docs/transports.md`, `docs/caching.md`, `docs/pypi.md`
  updated to v4; `mcp_pypi/server/README.md` removed or reduced to a pointer.
- Version `4.0.0` in `mcp_pypi/__init__.py` only.

### 8.3 Delivery
- Branch `feat/v4-foundation`; small commits per plan task; each task ends green
  (`ruff check`, `ruff format --check`, `pyrefly check`, `pytest`).
- Finish with a PR to `main`. No tag, release, or PyPI publish. PR description lists the
  owner's manual step: register Trusted Publishers on pypi.org and test.pypi.org.

## 9. Deferred to Spec 2 (safety intelligence)
- Safety verdict on `check_packages`: PEP 792 status (archived/quarantined via Simple JSON
  `project-status`), OSV `MAL-*` advisories as hard block, yanked state, project age.
- Provenance: PEP 740 attestations via Simple JSON `provenance` + Integrity API; Trusted
  Publisher identity.
- Typosquat detection against the top-15k popularity list (reuses §6 `Popularity`).
- Parsers: PEP 751 `pylock.toml`, `uv.lock`, PEP 735 `[dependency-groups]`, PEP 723 inline
  script metadata; PEP 639 `License-Expression` in audits.
- OSV: `next_page_token` pagination, full records via `/v1/vulns/{id}`, CVSS v4/v3 vectors
  and scores, CWE, fixed versions from `affected[].ranges`.

## 10. Risks
| Risk | Mitigation |
|---|---|
| fastmcp 4.1 API differs from research notes (kwargs, annotation types, prompt return types) | Plan's first task pins fastmcp 4.1, ports the server, and gets the existing contract green before other work; verify every kwarg against installed source |
| 10 MB index download on first search is slow on poor networks | Disk cache + daily conditional refresh; first-search latency documented; index fetch has its own 60 s timeout |
| Name-only search misses packages whose names don't contain the query words | Documented in tool description; summary re-ranking; popularity boost; `note` hint |
| Third-party popularity dataset disappears | Non-fatal: ranking falls back to tier + length |
| Clean break surprises v3 users | CHANGELOG mapping table; major version bump |
