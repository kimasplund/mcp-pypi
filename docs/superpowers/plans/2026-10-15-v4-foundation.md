# mcp-pypi v4.0 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn mcp-pypi 3.0 into a clean v4.0: dead code gone, one `pyproject.toml` with uv/hatchling/ruff/pyrefly, fastmcp 4.1, 11 typed tools with `ToolError` errors, and working package search.

**Architecture:** `core/` stays the framework-free PyPI/OSV layer that returns dicts (error dicts on failure). A new `server/` package built by `build_server()` wraps core in 11 FastMCP tools with Pydantic output models and an `unwrap` step that turns core error dicts into `ToolError`. The new server is built next to the old `PyPIMCPServer`; Task 9 cuts the CLI over and deletes the old one.

**Tech Stack:** Python ≥3.11, fastmcp 4.1 (mcp SDK 2.x underneath), aiohttp, packaging, typer, Pydantic 2, pytest + pytest-asyncio, uv, hatchling, ruff, pyrefly.

**Spec:** `docs/superpowers/specs/2026-10-15-v4-foundation-design.md` (read §5–§7 before Tasks 5–8)

## Global Constraints

- `requires-python = ">=3.11"`; CI matrix 3.11, 3.12, 3.13, 3.14.
- Runtime dependency `fastmcp>=4.1,<5`. **No direct `mcp` dependency**: pass tool annotations as dicts (`{"readOnlyHint": True, ...}`); never import `mcp.types` in new code.
- `__version__ = "4.0.0"` lives only in `mcp_pypi/__init__.py`; hatch reads it.
- Default User-Agent exactly: `f"mcp-pypi/{__version__} (+https://github.com/kimasplund/mcp-pypi)"`.
- The MCP surface is exactly these 11 tools: `search_packages`, `get_package`, `get_package_versions`, `compare_versions`, `get_package_changelog`, `get_download_stats`, `get_dependencies`, `check_packages`, `check_vulnerabilities`, `audit_project`, `scan_installed_packages`. The single-package parameter is always named `package_name`.
- Every tool: `title=...`, `annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": True}`, `timeout=60` (180 for `check_vulnerabilities`, `audit_project`, `scan_installed_packages`), a 5–10 line docstring, a Pydantic return type from `mcp_pypi/server/schemas.py`.
- No ANSI escape codes in any tool output. No MCP protocol logging (`ctx.info`, etc.); Python `logging` to stderr only.
- HTTP transport is streamable HTTP via `mcp.run(transport="http", host=host, port=port)`; defaults `127.0.0.1:8143`, endpoint `/mcp`. No SSE anywhere.
- Gate at the end of every task: `uv run ruff check`, `uv run ruff format --check`, `uv run pytest`, and `uv run pyrefly check <files created or rewritten in this task>`. Task 9 makes `uv run pyrefly check` (whole package) part of the gate and CI.
- Tasks 5–8: `mcp_pypi/server` is excluded from ruff's file discovery until Task 9, so also run `uv run ruff check <new/changed server files>` and `uv run ruff format --check <new/changed server files>`. Ruff lints explicitly passed paths even when they're excluded from discovery.
- `core/` keeps its contract: methods return dicts; failures are `{"error": {"code": ..., "message": ...}}` using `ErrorCode` values.
- Commit messages: conventional prefix (`feat:`, `refactor:`, `chore:`, `docs:`, `test:`), ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Name spellings:** `Django`, `zope.interface`, `typing_extensions`, `typing-extensions` must match the same project (PEP 503 normalization) in search, `check_packages`, and audit consistency checks. Pinned by `test_normalize_variants` (Task 3), `test_check_packages_normalizes_and_dedupes` (Task 7), `test_consistency_warning_uses_normalized_names` (Task 8).
2. **First run offline or unwritable cache dir:** search must raise a clear `ToolError`. An unwritable cache must fall back to in-memory instead of crashing, and other tools must keep working. Pinned by `test_index_unavailable_returns_network_error` and `test_unwritable_cache_dir_still_searches` (Task 3).
3. **Real-world requirement lines:** `requests[socks]==2.31.0`, `Django>=4.2 ; python_version>"3.8"`, `-e .`, `-r other.txt`, `--hash=...`, `git+https://...`, `# comments`, blank lines. The parsers must skip non-PyPI lines without failing the file, and `check_vulnerabilities` must accept extras. Pinned by `test_requirements_txt_real_world_lines` (Task 4) and `test_check_vulnerabilities_accepts_extras` (Task 7).
4. **Auditing a big repo:** directories like `.venv/`, `node_modules/`, `.git/`, `build/` and `site-packages/` must not be scanned or counted, and discovery must stop at the file and depth caps. Pinned by `test_discovery_skips_vendor_dirs_and_caps` (Task 4).
5. **One broken file in a project:** invalid TOML or JSON yields that file's `error` while the other files are still audited. Pinned by `test_audit_continues_past_broken_file` (Task 8).

---

### Task 1: Remove dead code and stale files

**Files:**
- Delete: `mcp_pypi/client.py`, `mcp_pypi/cli/server.py`, `mcp_pypi/utils/cache.py`, `mcp_pypi/utils/common/` (whole dir, after moving `validation.py`), `tests/utils/common/test_caching.py`, `tests/utils/common/test_hybrid_caching.py`, `examples/caching_benchmark.py`, `examples/standalone_cache_benchmark.py`, `examples/client_example.py`, `examples/debug_server.py`, `TOOL_DESCRIPTION_IMPROVEMENTS.md`, `pypi.md` (root), `docs/mcp_monitor.md`, `docs/protocol_version_negotiation.md`, `docs/diagrams/` (only `classes_caching.png` inside)
- Move: `mcp_pypi/utils/common/validation.py` → `mcp_pypi/utils/validation.py`; `mcp_pypi/utils/helpers.py` → `mcp_pypi/utils/sanitize.py`; `tests/utils/common/test_validation.py` → `tests/utils/test_validation.py`; `tests/manual/test_user_agent.py` → `tests/integration/test_user_agent.py`
- Modify: `mcp_pypi/cli/__init__.py` (drop `RPCServer`/`start_server` export), every importer of the moved modules (`grep -rn "utils.common\|utils.helpers" mcp_pypi tests`), `mcp_pypi/utils/__init__.py` (move `configure_logging` into new `mcp_pypi/utils/logging.py`; `__init__` re-exports `configure_logging` plus `sanitize_package_name`, `sanitize_version` from `sanitize`)

**Interfaces:**
- Produces: `mcp_pypi.utils.validation` (same functions as before: `validate_file_path`, `validate_pagination`, …) and `mcp_pypi.utils.sanitize` (`sanitize_package_name`, `sanitize_version`). Later tasks import from these paths.

- [ ] **Step 1: Delete and move files with `git rm` / `git mv`, fix imports.** Mark every test in `tests/integration/test_user_agent.py` with `pytestmark = pytest.mark.integration`.
- [ ] **Step 2: Verify nothing references the removed modules**
  Run: `grep -rnE "mcp_pypi\.client\b|cli\.server\b|RPCServer|utils\.cache\b|utils\.common|utils\.helpers" mcp_pypi tests examples`
  Expected: no output.
- [ ] **Step 3: Run the suite** (still on the old setuptools pyproject)
  Run: `uv run --extra dev --extra search pytest -q -m "not integration"`
  Expected: all pass; the count drops by the 27 deleted caching tests.
- [ ] **Step 4: Commit** `refactor: Remove dead legacy client, RPC server and unused caches`

---

### Task 2: Packaging and tooling (pyproject-only, uv, hatchling, ruff, fastmcp 4.1, CI)

**Files:**
- Modify: `pyproject.toml` (rewrite), `mcp_pypi/__init__.py`, `mcp_pypi/core/models/__init__.py` (drop the `typing_extensions` fallback; use `typing.NotRequired`), every `tomli` import site (use `tomllib`), `.github/dependabot.yml`, `.gitignore` (keep the existing `docs/superpowers` line)
- Create: `uv.lock`, `mcp_pypi/py.typed`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`
- Delete: `setup.cfg`, `requirements.txt`, `MANIFEST.in`, `pytest.ini`, `pyrefly.toml`, `.pylintrc`, `.github/workflows/pypi-main.yml`, `.github/workflows/pypi-test.yml`
- Test: `tests/test_packaging.py`

**Interfaces:**
- Produces: `mcp_pypi.__version__ == "4.0.0"` (a literal). `import mcp_pypi` must **not** import `mcp_pypi.server`, so remove the `PyPIMCPServer` import from `__init__.py`.

`pyproject.toml` contents decided here:
- `[build-system] requires = ["hatchling"]`, `build-backend = "hatchling.build"`. Set `[tool.hatch.version] path = "mcp_pypi/__init__.py"` and `dynamic = ["version"]`.
- `[tool.hatch.build.targets.wheel] packages = ["mcp_pypi"]`. Keep the sdist minimal: `mcp_pypi`, `README.md`, `CHANGELOG.md`, `LICENSE*`.
- `license = "MIT OR LicenseRef-Commercial"` with `license-files = ["LICENSE", "LICENSE-COMMERCIAL"]` (PEP 639). Classifiers: 3.11–3.14. Drop the `License ::` classifiers, since PEP 639 forbids them alongside `license`. Keep the other metadata, URLs and keywords.
- `dependencies = ["fastmcp>=4.1,<5", "aiohttp>=3.12", "packaging>=24.0", "typer>=0.15", "rich>=13.0", "defusedxml>=0.7.1"]`. Bump each floor to the newest release line available at implementation time, and confirm `uv lock` resolves.
- No `[project.optional-dependencies]`.
- `[dependency-groups] dev = ["pytest>=8", "pytest-asyncio>=0.24", "pytest-cov>=5", "ruff>=0.8", "pyrefly>=1.3"]`
- `[tool.ruff]` line-length 100, target-version `py311`. `[tool.ruff.lint] select = ["E","F","I","UP","B","ASYNC","SIM"]`. `extend-exclude = ["mcp_pypi/server"]` (**temporary**; Task 9 removes it, because that package is rewritten in Tasks 5–9).
- `[tool.pyrefly]`: carry over `project-includes`, `project-excludes` and `python-version = "3.11"` from `pyrefly.toml`.
- `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `asyncio_mode = "auto"`, `addopts = "-m 'not integration'"`, `markers = ["integration: needs network; run with -m integration"]`

- [ ] **Step 1: Write `tests/test_packaging.py`**
  ```python
  def test_version_is_literal_4():
      import mcp_pypi
      assert mcp_pypi.__version__ == "4.0.0"

  def test_importing_package_does_not_import_server():
      import subprocess, sys
      code = "import sys, mcp_pypi; print('mcp_pypi.server' in sys.modules)"
      out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
      assert out.stdout.strip() == "False"
  ```
- [ ] **Step 2: Rewrite `pyproject.toml`, delete the old config files, set `__version__ = "4.0.0"`, add `py.typed`, then run** `uv lock && uv sync`
  Expected: resolves with fastmcp 4.1.x, mcp 2.x, pydantic ≥2.12.
- [ ] **Step 3: Run** `uv run pytest`. Expected: all pass, including `test_packaging.py`. The old server still works on fastmcp 4.1; this was verified while writing the plan.
- [ ] **Step 4: Run** `uv run ruff check --fix && uv run ruff format`, **then fix the remaining `ruff check` findings by hand** (outside `mcp_pypi/server`). Do not suppress `B`/`ASYNC` findings with `noqa` unless the line has a one-line justification comment.
  Expected: `uv run ruff check` and `uv run ruff format --check` are both clean.
- [ ] **Step 5: Verify the build**
  Run: `uv build && unzip -l dist/*.whl | grep -E "py.typed|tests/" ; uv run --with dist/*.whl --no-project -- mcp-pypi --version`
  Expected: `mcp_pypi/py.typed` is listed, no `tests/` paths, and the CLI runs.
- [ ] **Step 6: CI workflows.**
  - `ci.yml`: trigger on `push` and `pull_request`. Use `astral-sh/setup-uv` with a matrix `python-version: ["3.11","3.12","3.13","3.14"]`. Run `uv sync --locked`, `uv run ruff check`, `uv run ruff format --check`, `uv run pytest`.
  - `release.yml`: trigger on `release: types: [published]` and `workflow_dispatch`. Steps: a `test` job (reuse ci.yml via `workflow_call`), then a `build` job (`uv build`, upload `dist/` artifact), then `publish-testpypi` (environment `testpypi`, `permissions: id-token: write`, `pypa/gh-action-pypi-publish@release/v1` with `repository-url: https://test.pypi.org/legacy/`), then `publish-pypi` (environment `pypi`, `needs: publish-testpypi`, `id-token: write`). No `password:` inputs.
  - Dependabot: add the `uv` and `github-actions` ecosystems (weekly).
- [ ] **Step 7: Commit** `chore: Move to pyproject-only packaging with uv, hatchling, ruff and fastmcp 4.1`

---

### Task 3: Search via the PyPI Simple index (core)

**Files:**
- Create: `mcp_pypi/core/search_index.py`, `tests/core/test_search_index.py`
- Modify: `mcp_pypi/core/http/__init__.py` (add `fetch_raw`), `mcp_pypi/core/search_ops.py` (replace `search_packages`, delete HTML scraping), `mcp_pypi/core/client.py` (construct the index objects; add `suggest_names`; remove `_has_bs4`/`_check_import` if now unused), `mcp_pypi/core/models/__init__.py` (`USER_AGENT`), `mcp_pypi/cli/commands/search_commands.py` (`--limit` replaces `--page`)
- Delete: `tests/core/test_bs4.py`
- Test: `tests/core/test_search_index.py`, update `tests/core/test_pypi_client.py` search tests

**Interfaces:**
- Produces (used by Tasks 5–7):
  - `AsyncHTTPClient.fetch_raw(url: str, headers: dict[str, str] | None = None) -> RawResponse`. `RawResponse` is a `NamedTuple(status: int, body: bytes, headers: dict[str, str])`. It uses the same session, User-Agent, timeout and rate limit as `fetch`, with no response caching. Network failures raise `aiohttp.ClientError`/`TimeoutError`.
  - `search_index.normalize(name: str) -> str`: PEP 503, `re.sub(r"[-_.]+", "-", name).lower()`.
  - `class NameIndex(http: AsyncHTTPClient, cache_dir: Path, max_age: timedelta = timedelta(hours=24))` with `async def names(self) -> str`. The return value is all normalized names joined by `"\n"`, with a leading and trailing `"\n"`. It raises `IndexUnavailable` when there's no network and no disk copy.
  - `class Popularity(http: AsyncHTTPClient, cache_dir: Path, max_age: timedelta = timedelta(days=7))` with `async def downloads(self) -> dict[str, int]` (normalized name → 30-day downloads). It returns `{}` on any failure.
  - `def rank_candidates(query: str, names: str, downloads: dict[str, int], pool: int = 500) -> list[Candidate]`, a pure function. `Candidate` is a `NamedTuple(name: str, tier: int, score: float)`.
  - `SearchOpsMixin.search_packages(query: str, limit: int = 10) -> dict`. It returns `{"query", "results": [{"name", "version", "summary", "package_url", "popularity_rank"}], "total_candidates", "note"}` or an error dict (`invalid_input` for an empty query, `network_error` with message `"PyPI package index unavailable; retry later"`).
  - `PyPIClient.suggest_names(name: str, limit: int = 3) -> list[str]` (async): `difflib.get_close_matches(normalize(name), popular_names, n=limit, cutoff=0.85)`, or `[]` when popularity is unavailable.
  - `PyPIClient.name_index: NameIndex`, `PyPIClient.popularity: Popularity`.

Fixed values:
- Index URL `https://pypi.org/simple/` with header `Accept: application/vnd.pypi.simple.v1+json`. Popularity URL `https://hugovk.github.io/top-pypi-packages/top-pypi-packages.min.json` (shape: `{"rows": [{"project": str, "download_count": int}]}`).
- Disk files under `config.cache_dir`: `simple-index.txt.gz` (gzipped joined names) and `simple-index.meta.json` (`{"etag": str|None, "fetched_at": iso8601}`); `popularity.json` and `popularity.meta.json`.
- Refresh rule: if the disk copy is younger than `max_age`, use it with no request. Otherwise send a conditional GET with `If-None-Match`. On `304`, rewrite `fetched_at` and reuse. On network failure, use a stale disk copy if there is one. Guard every refresh with `asyncio.Lock` so concurrent callers trigger only one download. If writing to disk fails, log a warning and keep the data in memory.
- Ranking: tier weights are exact = 1000, prefix = 500, all-tokens = 200, any-token = 50. Tokens are the query split on whitespace and `-_.`, normalized. `score = tier_weight + 25 * log10(downloads) (if known) - 0.5 * len(name)`. Cap the pool at `pool` candidates, taking the higher tiers first.
- Enrichment: take the top `min(3 * limit, 30)` candidates and call `get_package_info` on them concurrently through `asyncio.Semaphore(10)`. Drop candidates that error. Add `+40` per query token found (case-insensitive) in `info.summary`, re-sort, and return the top `limit`. Clamp `limit` to 1–50. `package_url = f"https://pypi.org/project/{name}/"`, where `name` is `info.name`. When there are no results, set `note` to `"No package names matched. Try name-like keywords (e.g. 'httpx', 'jwt', 'yaml')."`

- [ ] **Step 1: Write failing tests in `tests/core/test_search_index.py`**. Use a fake `http` whose `fetch_raw` serves fixture bytes and counts calls, and a fixture index of about 50 names that includes `httpx`, `http-client`, `requests`, `django`, `zope-interface`, `typing-extensions`, `jwt`, `pyjwt`.
  - `test_normalize_variants`: `normalize("Django") == "django"`, `normalize("zope.interface") == "zope-interface"`, `normalize("typing_extensions") == normalize("Typing-Extensions") == "typing-extensions"`
  - `test_exact_match_ranks_first`: `rank_candidates("pyjwt", ...)[0].name == "pyjwt"`
  - `test_popular_any_token_beats_obscure_all_tokens`: with `downloads={"httpx": 400_000_000}`, `rank_candidates("http client", ...)` puts `httpx` above `http-client`
  - `test_fresh_disk_copy_makes_no_request`, `test_stale_copy_sends_if_none_match_and_reuses_on_304` (asserts the header value and that `fetched_at` advances)
  - `test_concurrent_names_calls_download_once` (`asyncio.gather` of 5 calls leads to exactly 1 `fetch_raw` call)
  - `test_index_unavailable_returns_network_error`: no disk copy and `fetch_raw` raises `aiohttp.ClientError`, so `PyPIClient.search_packages("x")` returns `{"error": {"code": "network_error", "message": "PyPI package index unavailable; retry later"}}`
  - `test_unwritable_cache_dir_still_searches`: `cache_dir` is a read-only temp dir (`chmod 0o500`), and `names()` still returns the data
  - `test_search_enriches_and_reranks_by_summary`: stub `get_package_info`. A candidate whose summary contains the query token outranks an equal-tier one whose summary doesn't. Result items have exactly the keys listed above.
  - `test_empty_query_is_invalid_input`
  - `test_suggest_names_close_match`: popularity contains `beautifulsoup4`, so `suggest_names("beautifulsoup")` returns `["beautifulsoup4"]`
- [ ] **Step 2: Run** `uv run pytest tests/core/test_search_index.py -v`. Expected: it fails on the import of `mcp_pypi.core.search_index`.
- [ ] **Step 3: Implement** `fetch_raw`, `search_index.py` and the new `search_packages`/`suggest_names` with the interfaces and values above. Set `USER_AGENT` to the Global Constraints string (import `__version__` from `mcp_pypi`). Delete the BeautifulSoup and regex HTML parsing and the challenge-page handling from `search_ops.py`. Update the CLI `search` command to `search(query, --limit/-l 10)`.
- [ ] **Step 4: Run** `uv run pytest` and the gate commands. Expected: all pass. The obsolete HTML-search tests in `test_pypi_client.py` are replaced by calls to the new signature.
- [ ] **Step 5: Live check** (manual, not committed): `uv run mcp-pypi search httpx --limit 5`. Expected: `httpx` is the first row. The first run takes a few seconds to download the index; a second run is under 1 s.
- [ ] **Step 6: Commit** `fix: Replace blocked PyPI HTML search with Simple-index name search`

---

### Task 4: Dependency-file discovery and parsers (core)

**Files:**
- Create: `mcp_pypi/core/project_files.py`, `tests/core/test_project_files.py`, `tests/fixtures/projects/` (one small fixture per format)
- Read for logic to lift (do not modify yet): `mcp_pypi/server/helpers.py` (`check_setup_py`, `check_setup_cfg`, `check_pipfile`, `check_pipfile_lock`, `check_poetry_lock`, `check_conda_file`), `mcp_pypi/core/requirements_ops.py` (requirements/pyproject parsing), `mcp_pypi/server/tools/audit_tools.py:safe_glob`

**Interfaces:**
- Produces (used by Task 8):
  - `@dataclass(frozen=True) class DeclaredDependency: name: str; specifier: str; source: str; group: str | None = None`, with property `normalized_name -> str` (uses `search_index.normalize`) and property `pinned_version -> str | None` (the version when the specifier is exactly one `==X` or `===X` clause without a wildcard).
  - `def floor_version(specifier: str) -> str | None`: the lowest version allowed by a single `==`, `===`, `>=`, `~=` or `>` clause (the first such clause in a comma-separated set), otherwise `None`.
  - `class DependencyFileError(Exception)` with attributes `path: Path` and `message: str`.
  - `def discover_dependency_files(root: Path, max_files: int = 50, max_depth: int = 4) -> list[Path]`, sorted by path.
  - `def parse_dependency_file(path: Path) -> list[DeclaredDependency]`. It dispatches on the file name and raises `DependencyFileError` on read or parse failure.
  - `def file_kind(path: Path) -> str` returning one of `"requirements"`, `"pyproject"`, `"setup.py"`, `"setup.cfg"`, `"pipfile"`, `"pipfile.lock"`, `"poetry.lock"`, `"conda"`.

Fixed rules:
- Discovered names: `pyproject.toml`, `requirements*.txt`, `constraints*.txt` (kind `"requirements"`), `setup.py`, `setup.cfg`, `Pipfile`, `Pipfile.lock`, `poetry.lock`, `environment.yml`, `environment.yaml`.
- Never descend into: `.git`, `.hg`, `.venv`, `venv`, `env`, `node_modules`, `__pycache__`, `site-packages`, `build`, `dist`, `.tox`, `.nox`, `.mypy_cache`, or any directory whose name starts with `.`.
- Requirement strings are parsed with `packaging.requirements.Requirement`. Lines starting with `-`, URL or VCS requirements (`req.url` set, or a line containing `://` before any specifier), comments, blank lines and unparsable lines are skipped without error. `specifier` is `str(req.specifier)`; the name is kept as written.
- pyproject:
  - `[project].dependencies` has group `None`.
  - `[project.optional-dependencies].<x>` has group `"optional:<x>"`.
  - `[tool.poetry.dependencies]` skips the `python` key. Its value may be a string or a table with `version`; convert caret and tilde ranges into a specifier only when trivially expressible (`^1.2` → `>=1.2`, `~1.2` → `>=1.2`, `*` → `""`).
  - `[tool.poetry.group.<g>.dependencies]` has group `"poetry:<g>"`.
- Pipfile: `[packages]` gets group `None` and `[dev-packages]` gets group `"dev"`. `"*"` maps to `""`.
- Pipfile.lock: `default` and `develop` → `"==<version stripped of ==>"`.
- poetry.lock: each `[[package]]` → `==<version>`.
- setup.py: regex-extract the `install_requires=[...]` list of string literals. **Never execute or import the file.**
- conda: only the `pip:` sub-list entries; plain conda packages are ignored. Parse YAML **without** adding PyYAML: use a line-based scan for the `- pip:` block (lift the current `check_conda_file` approach).

- [ ] **Step 1: Write failing tests** in `tests/core/test_project_files.py`:
  - `test_requirements_txt_real_world_lines`: input lines `requests[socks]==2.31.0`, `Django>=4.2 ; python_version>"3.8"`, `-e .`, `-r other.txt`, `--hash=sha256:abc`, `git+https://github.com/x/y.git`, `# comment`, blank, `numpy` → exactly `[("requests","==2.31.0"),("Django",">=4.2"),("numpy","")]` as (name, specifier)
  - `test_pinned_and_floor_versions`: `pinned_version` for `==2.31.0` is `"2.31.0"`; for `==2.*` it is `None`; `floor_version(">=1.2,<2") == "1.2"`; `floor_version("~=3.1") == "3.1"`; `floor_version("<2") is None`
  - one test per format against its fixture: `test_pyproject_project_and_optional_and_poetry_groups`, `test_setup_cfg_install_requires`, `test_setup_py_is_not_executed` (the fixture contains `raise SystemExit` before `setup(...)` and parsing still returns the deps), `test_pipfile_and_lock`, `test_poetry_lock`, `test_conda_pip_section_only`
  - `test_invalid_toml_raises_dependency_file_error` (the error carries the path)
  - `test_discovery_skips_vendor_dirs_and_caps`: a tmp tree with `requirements.txt`, `sub/pyproject.toml`, `.venv/requirements.txt`, `node_modules/x/requirements.txt`, `build/setup.py`, `a/b/c/d/e/requirements.txt` (depth 5) → returns only the first two. With `max_files=1`, it returns 1 path.
- [ ] **Step 2: Run** `uv run pytest tests/core/test_project_files.py -v`. Expected: it fails on the import.
- [ ] **Step 3: Implement `mcp_pypi/core/project_files.py`** to the interfaces and rules above, lifting the parsing logic from the files listed under **Read**. Keep each parser a private function `_parse_<kind>(text: str, source: str) -> list[DeclaredDependency]`. `parse_dependency_file` reads the file (UTF-8, `errors="replace"`) and dispatches.
- [ ] **Step 4: Run** `uv run pytest` and the gate commands. Expected: all pass.
- [ ] **Step 5: Commit** `feat: Add framework-free dependency-file discovery and parsers`

---

### Task 5: New server skeleton (build_server, errors, schemas base, instructions, prompts, resources)

**Files:**
- Create: `mcp_pypi/server/app.py`, `mcp_pypi/server/errors.py`, `mcp_pypi/server/schemas.py`, `mcp_pypi/server/instructions.py`, `mcp_pypi/server/tools/packages.py`, `mcp_pypi/server/tools/dependencies.py`, `mcp_pypi/server/tools/security.py`, `mcp_pypi/server/tools/project.py` (each with an empty `register_*_tools(mcp, client) -> None`), `tests/server/conftest.py`, `tests/server/test_app.py`, `tests/server/test_errors.py`
- Rewrite: `mcp_pypi/server/prompts.py`, `mcp_pypi/server/resources.py`. They take `(mcp, client)`. The old `PyPIMCPServer` in `server/__init__.py` must keep working until Task 9, so keep thin adapters in the old call sites: `register_resources(server)` becomes `register_resources(server.mcp_server, server.client)`.

**Interfaces:**
- Produces:
  - `build_server(config: PyPIClientConfig | None = None, client: PyPIClient | None = None) -> FastMCP` in `mcp_pypi/server/app.py`. It calls `FastMCP(name="mcp-pypi", instructions=INSTRUCTIONS, version=__version__, website_url="https://github.com/kimasplund/mcp-pypi", mask_error_details=True, lifespan=_lifespan)`. `_lifespan` is an `@asynccontextmanager` taking `(server)` that yields `{}` and then `await client.close()`. It then calls the four `register_*_tools(mcp, client)`, `register_resources(mcp, client)` and `register_prompts(mcp)`.
  - `TOOL_ANNOTATIONS: dict[str, bool] = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": True}`, defined in `mcp_pypi/server/tools/__init__.py`. Tool modules import it from there. It is not defined in `app.py`, because `app.py` imports the tool modules and that would be circular.
  - `mcp_pypi/server/errors.py`:
    - `def unwrap(result: dict, *, package: str | None = None, suggestions: Sequence[str] = ()) -> dict` returns `result` unchanged or raises `ToolError`.
    - `async def checked(result: dict, *, client: PyPIClient, package: str | None = None) -> dict` fetches `await client.suggest_names(package)` only when `result["error"]["code"] == "not_found"` and `package` is set, then calls `unwrap`.
    - `def item_error(result: dict) -> str | None` returns the message for batch items.
  - The message table, verbatim from spec §7.2:
    - `not_found` → `"Package '{package}' not found on PyPI."` plus `" Did you mean '{s}'?"` if there are suggestions (first suggestion), plus `" Use search_packages to find the exact name."`
    - `invalid_input` → `"Invalid input: {message}"`
    - `network_error` / `timeout_error` / `rate_limit_error` → `"{service} request failed ({code}); retry later."`, where service is `"PyPI"` unless the message mentions `osv` (case-insensitive), in which case it's `"OSV"`
    - `file_error` / `permission_error` → `"Cannot read file: {message}"`
    - anything else → `"Unexpected error ({code})"`, with the full message logged at WARNING
  - `mcp_pypi/server/schemas.py` base: `class VulnerabilityItem(BaseModel): id: str; summary: str = ""; severity: str | None = None; aliases: list[str] = []; affected_versions: list[str] = []; references: list[str] = []`, with `@classmethod from_core(cls, v: dict) -> VulnerabilityItem` mapping core keys `id, summary, severity, cve→aliases, affected_versions, references` (each reference may be a dict with `url`, or a str).
  - `INSTRUCTIONS: str` in `instructions.py`, at most 40 lines, covering spec §4.3: the tool-choice guide (`search_packages` → `get_package` → `check_packages` before suggesting dependencies; `check_vulnerabilities` for specific versions; `audit_project` for a repository; `scan_installed_packages` for a venv) and the dependency-file authority order (pyproject.toml primary; requirements*.txt secondary/generated; setup.py/setup.cfg legacy; update the primary file first and keep constraints consistent).
  - Prompts: `analyze_dependencies(package_name: str) -> str` and `compare_packages(packages: str) -> str`, both with `title=`. The text tells the model which tools to call, per spec §4.5.
  - Resources: `pypi://recent-releases`, `pypi://new-packages`, `pypi://updated-packages`. Their content is unchanged from the current implementation, and each has `title=`.
  - `tests/server/conftest.py` fixtures: `fake_client` = `unittest.mock.create_autospec(PyPIClient, instance=True)`, so async methods become `AsyncMock`, with `suggest_names.return_value = []`; and `mcp_client` = an async fixture yielding `fastmcp.Client(build_server(client=fake_client))` entered with `async with`.

- [ ] **Step 1: Write failing tests**
  - `tests/server/test_errors.py`: one test per row of the message table, including `test_not_found_with_suggestion` (`"Package 'beautifulsoup' not found on PyPI. Did you mean 'beautifulsoup4'? Use search_packages to find the exact name."`), `test_unwrap_passes_success_through`, `test_checked_only_suggests_on_not_found` (`suggest_names` is not awaited for a `network_error`), `test_item_error_returns_message_or_none`.
  - `tests/server/test_app.py`:
    - `test_server_metadata`: the server name is `mcp-pypi` and its version is `"4.0.0"`.
    - `test_resources_listed`: the three URIs.
    - `test_prompts_have_required_args`: `analyze_dependencies` takes `package_name` and `compare_packages` takes `packages`, both required.
    - `test_prompt_mentions_tools`: the `analyze_dependencies` text contains `check_vulnerabilities`.
    - `test_lifespan_closes_client`: after `async with Client(...)` exits, `fake_client.close.assert_awaited()`.
    - `test_unexpected_exception_is_masked`: register a throwaway tool raising `RuntimeError("/secret/path")` on a `build_server` instance. Calling it gives `is_error` and the text does not contain `/secret/path`.
    - `test_instructions_cover_file_authority`: `"pyproject.toml"` and `"requirements"` both appear in `INSTRUCTIONS`.
- [ ] **Step 2: Run** `uv run pytest tests/server -v`. Expected: it fails on `ImportError: build_server`.
- [ ] **Step 3: Implement** the files above. Verify each `FastMCP(...)` keyword against the installed fastmcp (`python -c "import inspect, fastmcp; print(inspect.signature(fastmcp.FastMCP.__init__))"`). Every keyword listed exists in 4.1.0, as checked while writing this plan.
- [ ] **Step 4: Run** `uv run pytest` and the gate, including the explicit server-file ruff run from Global Constraints. Expected: all pass, and the old `tests/server/test_mcp_server.py` still passes.
- [ ] **Step 5: Commit** `feat: Add fastmcp 4 server skeleton with typed errors, prompts and resources`

---

### Task 6: Package tools (search_packages, get_package, get_package_versions, compare_versions, get_package_changelog, get_download_stats)

**Files:**
- Modify: `mcp_pypi/server/tools/packages.py`, `mcp_pypi/server/schemas.py`
- Test: `tests/server/test_package_tools.py`

**Interfaces:**
- Consumes: `checked`, `TOOL_ANNOTATIONS`, and the core client methods `search_packages(query, limit)` (Task 3), `get_package_info(name)`, `get_package_releases(name, ...)` / the raw `releases` dict from `get_package_info`, `compare_versions(name, v1, v2)`, `get_package_changelog(name, version) -> str`, `get_package_stats(name)`. For version-specific metadata, `get_package_info` hits `/pypi/<name>/json`; add a `version: str | None = None` parameter to `PackageOpsMixin.get_package_info` that uses `/pypi/<name>/<version>/json` when given, with a test in `tests/core/test_pypi_client.py`.
- Produces these models in `schemas.py` (fields exactly; all `str | None` fields default to `None`, and lists and dicts default to empty):
  - `SearchHit{name: str, version: str | None, summary: str | None, package_url: str, popularity_rank: int | None}`; `SearchResults{query: str, results: list[SearchHit], total_candidates: int, note: str | None}`
  - `PackageDetails{package_name: str, version: str, latest_version: str, summary, requires_python, license, author, maintainer, homepage_url, documentation_url, source_url, changelog_url: str | None, project_urls: dict[str, str], classifiers: list[str], yanked: bool, yanked_reason: str | None, release_count: int, latest_upload_time: str | None, package_url: str}`. License: `info.license_expression`, falling back to `info.license` truncated to 200 chars. The URLs are matched case-insensitively from the `project_urls` keys: docs is `documentation|docs`, source is `source|repository|code|github`, changelog is `changelog|changes|release notes|history`, and homepage is `homepage|home`, falling back to `info.home_page`.
  - `VersionEntry{version: str, upload_time: str | None, yanked: bool, yanked_reason: str | None, file_types: list[str]}`; `PackageVersions{package_name: str, versions: list[VersionEntry], total: int, offset: int, limit: int, has_more: bool}`. Sort by `packaging.version.Version`. Invalid versions sort last.
  - `VersionComparison{package_name: str, version1: str, version2: str, newer: Literal["version1", "version2", "equal"], comparison: str}`
  - `Changelog{package_name: str, version: str | None, changelog: str}`
  - `DownloadStats{package_name: str, last_day: int | None, last_week: int | None, last_month: int | None, source: str = "pypistats.org"}`
- Tool signatures exactly as in spec §5. Titles: "Search PyPI packages", "Get package details", "List package versions", "Compare package versions", "Get package changelog", "Get download statistics". Clamp `get_package_versions.limit` to 1–100 and `offset` to ≥ 0. `sort` is `Literal["newest", "oldest"]`.

- [ ] **Step 1: Write failing tests** (`fake_client` returns canned core dicts; build them from the real shapes in `core/package_ops.py`)
  - `test_search_packages_structured`: `structured_content["results"][0]["name"] == "httpx"`
  - `test_search_index_unavailable_is_tool_error`: the core returns a network_error dict, so the call gives `is_error` and text `"PyPI request failed (network_error); retry later."`
  - `test_get_package_maps_urls_and_license`: `license` comes from `license_expression`, and `documentation_url` is picked from the `project_urls` key `"Documentation"`
  - `test_get_package_not_found_suggests`: `suggest_names` returns `["beautifulsoup4"]`, and the error text contains `Did you mean 'beautifulsoup4'?`
  - `test_get_package_pinned_version_reports_yanked`
  - `test_get_package_versions_paginates_and_sorts`: 25 versions with `limit=10, offset=20` gives 5 entries and `has_more is False`; `sort="oldest"` returns ascending order
  - `test_compare_versions_newer_field`, `test_changelog_passthrough`, `test_download_stats_fields`
- [ ] **Step 2: Run** `uv run pytest tests/server/test_package_tools.py -v`. Expected: FAIL (tool not found).
- [ ] **Step 3: Implement** the six tools and their models. Each tool: `data = await checked(await client.<op>(...), client=client, package=package_name)`, then `return Model(...)`.
- [ ] **Step 4: Run** `uv run pytest` and the gate (ruff and pyrefly on `packages.py` and `schemas.py`). Expected: pass.
- [ ] **Step 5: Commit** `feat: Add consolidated package lookup tools with output schemas`

---

### Task 7: Dependency and security tools (get_dependencies, check_packages, check_vulnerabilities, scan_installed_packages)

**Files:**
- Modify: `mcp_pypi/server/tools/dependencies.py`, `mcp_pypi/server/tools/security.py`, `mcp_pypi/server/schemas.py`
- Move logic from: `mcp_pypi/server/tools/audit_tools.py` (`_scan_installed_packages_impl`, `_scan_dependency_vulnerabilities_impl`) into private functions in `security.py`, mapping their results to the models below. Leave the old modules in place until Task 9.
- Test: `tests/server/test_dependency_tools.py`, `tests/server/test_security_tools.py`

**Interfaces:**
- Consumes: `get_dependencies(name, version)`, `get_dependency_tree(name, version, depth)`, `check_vulnerabilities(name, version)`, `check_vulnerabilities_batch(packages: list[dict])` (read its accepted input shape in `core/vulnerability_ops.py:309`), `get_package_info`, `checked`, `item_error`, `VulnerabilityItem.from_core`, `search_index.normalize`.
- Produces models:
  - `DependencyEntry{name: str, specifier: str, extras: list[str], marker: str | None}`; `DependencyNode{name: str, version: str | None, cycle: bool = False, dependencies: list["DependencyNode"]}`; `Dependencies{package_name: str, version: str | None, depth: int, dependencies: list[DependencyEntry], tree: DependencyNode | None}`. `tree` is set only when `depth > 1`. Clamp `depth` to 1–5.
  - `PackageCheck{name: str, normalized_name: str, exists: bool, latest_version: str | None, summary: str | None, error: str | None}`; `PackageChecks{results: list[PackageCheck], total: int, missing: list[str]}`. A not_found result gives `exists=False` with `error=None`. Other failures give `exists=False` with an `error`.
  - `PackageVulnerabilities{package: str, version: str | None, vulnerable: bool, vulnerabilities: list[VulnerabilityItem], introduced_via: list[str], error: str | None}`; `VulnerabilityReport{results: list[PackageVulnerabilities], total_packages: int, vulnerable_packages: int, total_vulnerabilities: int, severity_counts: dict[str, int], transitive_checked: bool}`
  - `InstalledScan{environment_path: str | None, packages_scanned: int, vulnerable: list[PackageVulnerabilities], all_clear: bool, update_commands: list[str], recommendation: str}`
- Rules:
  - `check_packages(names)` takes 1–100 names; more raises `ToolError("Invalid input: at most 100 names per call")`. Dedupe by normalized name, keeping the first spelling. Run concurrently with `asyncio.Semaphore(10)`. Report progress with `ctx.report_progress(done, total)`.
  - `check_vulnerabilities(packages, include_transitive=False, max_depth=2)`:
    - It takes 1–100 items. Parse each with `packaging.requirements.Requirement`. Accept no specifier (meaning latest) or a single `==X`; the extras are ignored. Anything else becomes an item error `"Only 'name' or 'name==version' is supported"`.
    - More than one valid item uses `check_vulnerabilities_batch`; a single item uses `check_vulnerabilities`.
    - With `include_transitive`, clamp `max_depth` to 1–3. Resolve trees with `get_dependency_tree` and check every node. `introduced_via` is the chain of names from the root to the node, e.g. `["flask", "werkzeug"]`.
    - Severity keys are lowercase `critical|high|medium|low|unknown`.
    - Report progress.
  - `scan_installed_packages(environment_path=None)` keeps the current behaviour (auto-detection, `validate_file_path`). Its output is `InstalledScan` with no ANSI.

- [ ] **Step 1: Write failing tests**
  - `test_get_dependencies_direct`, `test_get_dependencies_tree_when_depth_gt_1`, `test_depth_clamped_to_5`
  - `test_check_packages_normalizes_and_dedupes`: `["Django", "django", "typing_extensions", "nope-xyz"]` gives 3 results; `missing == ["nope-xyz"]`; the `normalized_name` of `typing_extensions` is `"typing-extensions"`
  - `test_check_packages_partial_failure_is_per_item`: one name gets a network_error, so its `error` is set while the others succeed and the call is not `is_error`
  - `test_check_packages_rejects_over_100`
  - `test_check_vulnerabilities_single_and_batch_paths`: one item calls `check_vulnerabilities` and two items call `check_vulnerabilities_batch` (assert awaited)
  - `test_check_vulnerabilities_accepts_extras`: `"requests[socks]==2.31.0"` is checked as `("requests", "2.31.0")`
  - `test_check_vulnerabilities_rejects_ranges_per_item`: `"django>=4"` gets an item error, and the other items are still checked
  - `test_transitive_reports_introduced_via`
  - `test_scan_installed_has_no_ansi`: no `"\x1b["` in the JSON dump of the structured content
  - `test_progress_reported`: pass a `progress_handler` to `call_tool` and assert it's called at least once for a 3-item `check_packages`
- [ ] **Step 2: Run** `uv run pytest tests/server/test_dependency_tools.py tests/server/test_security_tools.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the tools and models to the rules above.
- [ ] **Step 4: Run** `uv run pytest` and the gate on the changed files. Expected: pass.
- [ ] **Step 5: Commit** `feat: Add consolidated dependency and vulnerability tools`

---

### Task 8: audit_project tool

**Files:**
- Modify: `mcp_pypi/server/tools/project.py`, `mcp_pypi/server/schemas.py`
- Test: `tests/server/test_project_tools.py` (uses `tests/fixtures/projects/` from Task 4)

**Interfaces:**
- Consumes: `discover_dependency_files`, `parse_dependency_file`, `DependencyFileError`, `file_kind`, `DeclaredDependency.pinned_version`, `floor_version` (Task 4); `check_vulnerabilities_batch`; `get_package_info` (for `info.version` as the latest version); `validate_file_path` (`mcp_pypi.utils.validation`); `VulnerabilityItem.from_core`.
- Produces models:
  - `AuditedDependency{name: str, specifier: str, group: str | None, checked_version: str | None, latest_version: str | None, outdated: bool, vulnerable: bool, vulnerabilities: list[VulnerabilityItem]}`
  - `AuditedFile{path: str, kind: str, dependencies: list[AuditedDependency], error: str | None}`
  - `ConsistencyWarning{package: str, specifiers: dict[str, str]}` (file path → specifier)
  - `AuditTotals{files: int, dependencies: int, vulnerable: int, outdated: int, vulnerabilities: int}`
  - `ProjectAudit{path: str, files: list[AuditedFile], consistency_warnings: list[ConsistencyWarning], totals: AuditTotals, recommendations: list[str], summary: str}`
- Algorithm:
  1. Validate `path` with `validate_file_path`; on failure raise `ToolError("Invalid input: ...")`. A directory gives `discover_dependency_files(path)`; a file gives `[path]`. If no files are found, raise `ToolError("Invalid input: no dependency files found under '<path>'")`.
  2. Parse each file. `DependencyFileError` becomes `AuditedFile(error=...)` with no dependencies.
  3. `checked_version` = `pinned_version`, else `floor_version(specifier)`, else `None` (meaning latest).
  4. Make one `check_vulnerabilities_batch` call over the unique `(normalized_name, checked_version)` pairs. Fetch the latest versions concurrently with `Semaphore(10)`, once per unique name.
  5. `outdated` is `checked_version` is not None and `Version(checked_version) < Version(latest)`. An invalid version gives `False`.
  6. Consistency warning: the same normalized name appears with ≥2 distinct non-empty specifiers across different files. Ignore lock files (`pipfile.lock`, `poetry.lock`) for this check, since they pin by design.
  7. Recommendations (plain strings):
     - one per vulnerable package: `"Upgrade {name} (checked {checked_version or 'latest'}) — {n} known vulnerabilities; latest is {latest}."`
     - if pyproject.toml and another non-lock file both declare dependencies: `"Update pyproject.toml first, then sync requirements/setup files to the same constraints."`
     - one per consistency warning: `"Align {package} constraints across files."`
  8. `summary` is markdown: a heading, then a totals line, then a bullet per vulnerable package (max 20), then the consistency count. No ANSI.
  9. `detail="summary"` drops dependencies that are neither vulnerable nor outdated from each `AuditedFile.dependencies`; the totals still count everything. `detail="full"` keeps them all.
  10. Report progress per file parsed and after the vulnerability batch.

- [ ] **Step 1: Write failing tests**
  - `test_audit_directory_finds_all_kinds`: the fixture project has a pyproject, requirements.txt and poetry.lock, so the result lists 3 files with their correct `kind` values
  - `test_audit_single_file_path`
  - `test_audit_continues_past_broken_file`: an invalid `pyproject.toml` alongside a valid `requirements.txt` gives the pyproject an `error` while requirements is still audited and the call is not `is_error`
  - `test_consistency_warning_uses_normalized_names`: `typing_extensions>=4` in pyproject and `typing-extensions>=4.5` in requirements give one warning for `typing-extensions`
  - `test_lock_files_excluded_from_consistency`
  - `test_summary_detail_omits_clean_packages_but_totals_count_them`
  - `test_vulnerable_recommendation_text` (the exact string above)
  - `test_audit_rejects_traversal_and_missing`: `"../../etc"` and an empty dir both give `is_error` with an `Invalid input:` prefix
  - `test_audit_output_has_no_ansi`
  - `test_audit_uses_one_batch_call`: `check_vulnerabilities_batch` is awaited exactly once
- [ ] **Step 2: Run** `uv run pytest tests/server/test_project_tools.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `audit_project` and its models to the algorithm above. Keep `project.py` under ~300 lines; put the summary/recommendation builders in private functions.
- [ ] **Step 4: Run** `uv run pytest` and the gate on the changed files. Expected: pass.
- [ ] **Step 5: Commit** `feat: Add audit_project tool built on the new dependency-file parsers`

---

### Task 9: Cut over: CLI, transports, delete the old server, full lint and type gate

**Files:**
- Rewrite: `mcp_pypi/server/__init__.py` (exports only `build_server`), `mcp_pypi/cli/server_command.py` → `mcp_pypi/cli/commands/serve.py`, `mcp_pypi/cli/main.py` (the `serve` and `stdio` commands use `build_server`; the connection-help text has no `/sse`)
- Delete: `mcp_pypi/server/helpers.py`, `mcp_pypi/server/README.md`, the old `mcp_pypi/server/tools/{audit_tools,dependency_tools,file_tools,package_tools,search_tools,vulnerability_tools}.py`, `tests/server/test_mcp_server.py`, any core code made unused by the deletion (`requirements_ops.py` only if nothing references it; the CLI `check-requirements` command must instead be reimplemented on `project_files` plus `check_vulnerabilities_batch`)
- Modify: `pyproject.toml` (remove `extend-exclude = ["mcp_pypi/server"]`), `.github/workflows/ci.yml` (add the `uv run pyrefly check` step)
- Create: `tests/server/test_contract.py`, `tests/cli/test_serve.py`, `tests/integration/test_live.py`, `examples/client_example.py`

**Interfaces:**
- Consumes: `build_server` (Task 5) and all registered tools (Tasks 6–8).
- Produces: `mcp-pypi serve [--transport stdio|http] [--host 127.0.0.1] [--port 8143] [--cache-dir] [--cache-strategy] [--cache-ttl] [--log-level] [--user-agent] [--help-connecting]` and `mcp-pypi stdio`. Any other `--transport` value raises `typer.BadParameter`. Logging is configured to stderr before `run()`.

- [ ] **Step 1: Write failing tests**
  - `tests/server/test_contract.py`:
    - `test_exact_tool_set`: the set of names equals the 11 names in Global Constraints.
    - `test_every_tool_has_title_annotations_schema`: `title` is truthy, `annotations.read_only_hint is True`, `annotations.idempotent_hint is True`, `annotations.open_world_hint is True`, and `output_schema` is not None.
    - `test_single_package_param_named_package_name`: `"package_name"` is a required property in `input_schema` for `get_package`, `get_package_versions`, `compare_versions`, `get_package_changelog`, `get_download_stats` and `get_dependencies`.
    - `test_descriptions_short_and_no_shouting`: the description is at most 1200 chars and contains no `"IMPORTANT"` or `"MUST"`.
  - `tests/cli/test_serve.py`:
    - `test_http_transport_runs_streamable_http`: patch `FastMCP.run`; `serve --transport http --port 9000` calls it with `transport="http", host="127.0.0.1", port=9000`.
    - `test_stdio_default`.
    - `test_sse_rejected`: `--transport sse` exits non-zero.
    - `test_stdio_end_to_end_lists_tools`: `fastmcp.Client(StdioTransport(command=sys.executable, args=["-m", "mcp_pypi", "serve"]))` (from `fastmcp.client.transports`) lists exactly 11 tools. No network is needed, and it proves stdout is clean.
  - `tests/integration/test_live.py` (`pytestmark = pytest.mark.integration`): search `"httpx"` returns `httpx` first; `get_package("requests")` has a `latest_version`; `check_vulnerabilities(["jinja2==2.4.1"])` reports at least 1 vulnerability.
- [ ] **Step 2: Run** `uv run pytest tests/server/test_contract.py tests/cli/test_serve.py -v`. Expected: FAIL, because the old server is still wired into the CLI.
- [ ] **Step 3: Cut over the CLI, delete the old server modules and tests, reimplement `check-requirements`,** and replace `examples/client_example.py` with about 30 lines using `fastmcp.Client` over stdio to call `search_packages` and `check_vulnerabilities`.
- [ ] **Step 4: Remove the ruff `extend-exclude`, then run** `uv run ruff check && uv run ruff format --check && uv run pyrefly check`. Fix every finding in `mcp_pypi/`. A `# pyrefly: ignore` is allowed only with a one-line reason, and at most 10 in total.
  Expected: all three are clean.
- [ ] **Step 5: Run** `uv run pytest` and then `uv run pytest -m integration`. Expected: all pass, and the integration tests pass with network access.
- [ ] **Step 6: Commit** `refactor!: Switch CLI to the v4 server and remove the v3 tool modules`

---

### Task 10: Docs, changelog and final verification

**Files:**
- Modify: `README.md`, `CHANGELOG.md`, `docs/usage.md`, `docs/server.md`, `docs/transports.md`, `docs/caching.md`, `docs/pypi.md`, `.osv-scanner.toml`

**Interfaces:**
- Consumes: the final tool set, CLI flags and transports from Tasks 6–9.

Content decided here:
- **README:**
  - Badges: the PyPI version, Python versions and license badges (dynamic shields); remove the hardcoded FastMCP version badge.
  - Install: `uvx mcp-pypi serve` and `pip install mcp-pypi`. Remove every mention of the `[http]` and `[all]` extras.
  - Client setup:
    - Claude Code: `claude mcp add mcp-pypi -- uvx mcp-pypi serve`.
    - Claude Desktop: JSON under `"mcpServers"` with `"command": "uvx", "args": ["mcp-pypi", "serve"]`.
    - Cursor: the existing section, updated to `uvx`.
  - A table of the 11 tools (name and one line each), HTTP mode (`--transport http`, `http://127.0.0.1:8143/mcp`), the configuration env vars from `PyPIClientConfig`, and a "Upgrading from 3.x" link to the CHANGELOG.
- **CHANGELOG `## [4.0.0] - <date of merge>`:**
  - The breaking changes.
  - The v3→v4 tool mapping table copied from spec §5.
  - The removed Python modules (`mcp_pypi.client`, `mcp_pypi.cli.server`, `mcp_pypi.utils.cache`, `mcp_pypi.utils.common`, `PyPIMCPServer`), the SSE removal, Python ≥3.11 and the honest User-Agent.
  - Fixed: search works again.
- **docs/:** describe the v4 behaviour (index caching files and refresh in `caching.md`, streamable HTTP only in `transports.md`). Remove any mention of deleted features.
- **`.osv-scanner.toml`:** run `uvx osv-scanner --lockfile uv.lock` (or `osv-scanner scan source -L uv.lock`). Drop ignore entries that no longer match a finding.

- [ ] **Step 1: Update the docs and changelog** as above.
- [ ] **Step 2: Verify the docs don't reference removed things**
  Run: `grep -rnE "sse|/sse|\[http\]|\[all\]|PyPIMCPServer|FastMCP 2\.|get_package_info|batch_check|security_audit_project|check_requirements_txt" README.md docs/ CHANGELOG.md | grep -v "CHANGELOG.md.*\(3\.\|2\.\|mapping\)"`
  Expected: nothing outside the CHANGELOG's history and mapping table.
- [ ] **Step 3: Final verification**
  Run: `uv sync --locked && uv run ruff check && uv run ruff format --check && uv run pyrefly check && uv run pytest && uv build`
  Expected: all succeed.
- [ ] **Step 4: Commit** `docs: Document v4.0 tools, setup and migration`
