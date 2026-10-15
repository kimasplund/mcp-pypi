# MCP-PyPI Tool Reference

Reference for the 11 tools of mcp-pypi 4.x. All tools are read-only: they never modify files or environments. Every tool returns structured output that matches an `outputSchema` published in the tool listing, so MCP clients can read results as typed data rather than text.

## Contents

- [Package tools](#package-tools): `search_packages`, `get_package`, `get_package_versions`, `compare_versions`, `get_package_changelog`, `get_download_stats`
- [Dependency tools](#dependency-tools): `get_dependencies`, `check_packages`
- [Security tools](#security-tools): `check_vulnerabilities`, `scan_installed_packages`
- [Project tool](#project-tool): `audit_project`
- [Errors](#errors)
- [Prompts and resources](#prompts-and-resources)

## Package tools

### search_packages

Search PyPI package names and return ranked matches with summaries.

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `query` | string | required | Name-like keywords work best |
| `limit` | integer | `10` | Clamped to 1-50 |

PyPI's HTML search is behind a JavaScript challenge, so mcp-pypi matches against the PyPI Simple index of package names and ranks hits by name similarity and download popularity. It matches names, not descriptions. Result: `query`, `results` (each with `name`, `version`, `summary`, `package_url`, `popularity_rank`), `total_candidates` and an optional `note`. See [caching.md](caching.md) for how the index is stored.

### get_package

Get metadata for a package: versions, license, URLs, classifiers and yank status.

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `package_name` | string | required | |
| `version` | string | latest | Describe this release instead |

Without `version` it describes the latest release. With `version` it describes that release (including whether it was yanked) while `latest_version` still reports the newest release. Result fields include `package_name`, `version`, `latest_version`, `summary`, `requires_python`, `license`, `author`, `maintainer`, `homepage_url`, `documentation_url`, `source_url`, `changelog_url`, `project_urls`, `classifiers`, `yanked`, `yanked_reason`, `release_count`, `latest_upload_time` and `package_url`. An unknown package returns a "did you mean" suggestion in the error message.

### get_package_versions

List released versions with upload time, yank status and file types.

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `package_name` | string | required | |
| `limit` | integer | `20` | Clamped to 1-100 |
| `offset` | integer | `0` | 0 or more |
| `sort` | `"newest"` or `"oldest"` | `"newest"` | |

Ordered by PEP 440 version (versions that do not parse sort last). Result: `versions` (each with `version`, `upload_time`, `yanked`, `yanked_reason`, `file_types`), `total`, `offset`, `limit` and `has_more`.

### compare_versions

Compare two versions of a package using PEP 440 ordering.

| Parameter | Type |
|-----------|------|
| `package_name` | string |
| `version1` | string |
| `version2` | string |

Result: `newer` (`"version1"`, `"version2"` or `"equal"`) and a `comparison` sentence. The comparison is purely on version numbers and does not check that either release exists.

### get_package_changelog

Get changelog text for a package from its project links or GitHub releases.

| Parameter | Type | Default |
|-----------|------|---------|
| `package_name` | string | required |
| `version` | string | latest |

Uses the changelog link in the package metadata when present and falls back to the repository's releases page. When nothing is found it returns a short note listing the available project URLs. Result: `package_name`, `version`, `changelog`.

### get_download_stats

Get recent download counts (last day, week and month) from pypistats.org.

| Parameter | Type |
|-----------|------|
| `package_name` | string |

Result: `last_day`, `last_week`, `last_month` and `source`. When pypistats is unavailable the tool fails with an error; it never returns made-up numbers. Counts include mirrors and CI traffic, so compare packages against each other rather than reading absolute numbers.

## Dependency tools

### get_dependencies

List the requirements of a package, optionally as a transitive tree.

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `package_name` | string | required | |
| `version` | string | latest | |
| `depth` | integer | `1` | Clamped to 1-5 |

With `depth=1` it returns the direct requirements (`name`, `specifier`, `extras`, `marker`). With `depth` 2-5 it also returns `tree`, the resolved dependency tree down to that depth, with repeated packages flagged as `cycle`.

### check_packages

Check up to 100 package names on PyPI and report latest version and summary. Use it to verify that names exist before suggesting them.

| Parameter | Type | Notes |
|-----------|------|-------|
| `names` | list of strings | 1-100 names |

Names are de-duplicated by PEP 503 normalization (the first spelling is kept) and checked concurrently. A name that does not exist is listed in `missing`; any other failure is reported in that item's `error` without failing the call. Result: `results` (each with `name`, `normalized_name`, `exists`, `latest_version`, `summary`, `error`), `total` and `missing`.

## Security tools

### check_vulnerabilities

Check up to 100 packages against [OSV](https://osv.dev/) for known vulnerabilities.

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `packages` | list of strings | required | `name` (latest release) or `name==version` |
| `include_transitive` | boolean | `false` | Also check dependencies |
| `max_depth` | integer | `2` | Clamped to 1-3; used with `include_transitive` |

Extras are ignored and any other specifier is rejected for that item only. With `include_transitive` the dependency tree is resolved to `max_depth` and every dependency is checked too; vulnerable dependencies are listed with `introduced_via`, the shortest root-to-dependency chain of names. Items whose version cannot be resolved are reported as errors, never checked across all versions. Package names match OSV case- and separator-insensitively (`Django`, `PyYAML`, `typing_extensions`).

Result: `results` (per package: `package`, `version`, `vulnerable`, `vulnerabilities`, `total_vulnerabilities`, `vulnerabilities_truncated`, `introduced_via`, `note`, `error`), `total_packages`, `vulnerable_packages`, `total_vulnerabilities`, `severity_counts` and `transitive_checked`. Each vulnerability has `id`, `summary`, `severity`, `aliases`, `affected_versions` and `references`. GitHub advisory severity `MODERATE` is counted as `medium`.

### scan_installed_packages

Scan a Python environment's installed packages for known vulnerabilities.

| Parameter | Type | Default |
|-----------|------|---------|
| `environment_path` | string | a `.venv`, `venv`, `env`, `.env` or `virtualenv` directory in the working directory |

If no environment path is given and none of those directories exists, the call fails and asks for a path; it never scans an unrelated environment. Packages are listed with the environment's own interpreter (no `pip` needed, so uv-created venvs work; 60 second limit) and checked against OSV in batches. Result: `environment_path`, `packages_scanned`, `vulnerable`, `all_clear`, `unchecked`, `update_commands` and `recommendation`. Packages that could not be checked are listed in `unchecked` and prevent `all_clear`.

## Project tool

### audit_project

Audit a project's dependency files for vulnerabilities, outdated pins and drift.

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `path` | string | required | A directory or a single dependency file |
| `detail` | `"summary"` or `"full"` | `"summary"` | `summary` lists only vulnerable, outdated or unchecked dependencies per file |

Supported files: `requirements*.txt`, `constraints*.txt`, `pyproject.toml` (PEP 621 and Poetry), `setup.py` (parsed statically, never executed), `setup.cfg`, `Pipfile`, `Pipfile.lock`, `poetry.lock` and conda `environment.yml` / `environment.yaml` (the `pip:` section). A directory is searched up to 4 levels deep, at most 50 files.

Each dependency is checked at its pinned version; otherwise at its lowest allowed version; otherwise, for upper-bound-only constraints such as `urllib3<2`, at the highest non-yanked allowed release; otherwise at the latest release. A dependency that could not be checked carries an `error`, is counted in `totals.unchecked`, and is never reported as clean. Unreadable files appear in `files` with an `error` and are counted in `totals.files_with_errors`.

Result: `path`, `files` (each with `path`, `kind`, `dependencies`, `error`), `consistency_warnings` (the same package with different specifiers across files), `totals` (`files`, `dependencies`, `vulnerable`, `outdated`, `vulnerabilities`, `unchecked`, `files_with_errors`; always cover everything regardless of `detail`), `recommendations` and a plain-markdown `summary`. The `mcp-pypi check-requirements` command runs the same audit.

## Errors

Failures are returned as MCP tool errors (`isError: true` on the tool result) with a short, actionable message, not as an `{"error": ...}` result. For example:

- `Package 'reqests' not found on PyPI. Did you mean 'requests'? Use search_packages to find the exact name.`
- `Invalid input: at most 100 names per call`
- `PyPI request failed (network_error); retry later.` (also for OSV)
- `Cannot read file: <reason>`

Batch tools (`check_packages`, `check_vulnerabilities`, `audit_project`) report a problem with one item in that item's `error` field and still return the others. Internal details of unexpected failures are masked.

## Prompts and resources

Prompts (both take arguments):

- `analyze_dependencies(package_name)`: analyze a package's dependencies for security and freshness.
- `compare_packages(packages)`: compare candidate packages and recommend one.

Resources (read-only PyPI feeds): `pypi://recent-releases`, `pypi://new-packages`, `pypi://updated-packages`.

## Rate limits and etiquette

Requests to PyPI, OSV and pypistats are cached and retried with exponential backoff (see [caching.md](caching.md) and the `PYPI_*` variables in the [README](../README.md#-configuration)). The User-Agent identifies the project: `mcp-pypi/<version> (+https://github.com/kimasplund/mcp-pypi)`.
