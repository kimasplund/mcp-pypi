"""Project tools: audit the dependency files of a project."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Literal

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from packaging.version import InvalidVersion, Version

from mcp_pypi.core import PyPIClient
from mcp_pypi.core.project_files import (
    DeclaredDependency,
    DependencyFileError,
    discover_dependency_files,
    file_kind,
    floor_version,
    parse_dependency_file,
)
from mcp_pypi.server.schemas import (
    AuditedDependency,
    AuditedFile,
    AuditTotals,
    ConsistencyWarning,
    ProjectAudit,
    VulnerabilityItem,
)
from mcp_pypi.server.tools import TOOL_ANNOTATIONS
from mcp_pypi.server.tools.osv import Key, query_osv, vulnerability_totals
from mcp_pypi.utils.validation import validate_file_path

LOCK_KINDS = frozenset({"pipfile.lock", "poetry.lock"})
MAX_SUMMARY_PACKAGES = 20
ALL_FAILED = "OSV request failed; no dependencies could be checked. Retry later."


def _is_outdated(checked: str | None, latest: str | None) -> bool:
    if not checked or not latest:
        return False
    try:
        return Version(checked) < Version(latest)
    except InvalidVersion:
        return False


async def _latest_versions(client: PyPIClient, names: set[str]) -> dict[str, str | None]:
    """Latest version per normalized name (None when it cannot be resolved)."""
    sem = asyncio.Semaphore(10)

    async def one(name: str) -> str | None:
        try:
            async with sem:
                res = await client.get_package_info(name)
        except Exception:
            return None
        if not isinstance(res, dict) or res.get("error"):
            return None
        version = (res.get("info") or {}).get("version")
        return str(version) if version else None

    ordered = sorted(names)
    return dict(zip(ordered, await asyncio.gather(*(one(n) for n in ordered)), strict=True))


def _consistency_warnings(parsed: list[tuple[Path, str, list[DeclaredDependency]]]):
    by_name: dict[str, dict[str, str]] = {}
    for path, kind, deps in parsed:
        if kind in LOCK_KINDS:
            continue
        for dep in deps:
            if dep.specifier:
                by_name.setdefault(dep.normalized_name, {}).setdefault(str(path), dep.specifier)
    return [
        ConsistencyWarning(package=name, specifiers=specs)
        for name, specs in sorted(by_name.items())
        if len(set(specs.values())) >= 2
    ]


def _recommendations(
    vulnerable: dict[str, tuple[AuditedDependency, int]],
    parsed: list[tuple[Path, str, list[DeclaredDependency]]],
    warnings: list[ConsistencyWarning],
    unchecked: int,
) -> list[str]:
    recs = [
        f"Upgrade {dep.name} (checked {dep.checked_version or 'latest'}) — {total} known "
        f"vulnerabilities; latest is {dep.latest_version}."
        for dep, total in vulnerable.values()
    ]
    declaring = {kind for _, kind, deps in parsed if deps and kind not in LOCK_KINDS}
    if "pyproject" in declaring and len(declaring) > 1:
        recs.append(
            "Update pyproject.toml first, then sync requirements/setup files to the "
            "same constraints."
        )
    recs += [f"Align {w.package} constraints across files." for w in warnings]
    if unchecked:
        recs.append(f"{unchecked} dependencies could not be checked; see per-dependency errors.")
    return recs


def _summary(
    totals: AuditTotals,
    vulnerable: dict[str, tuple[AuditedDependency, int]],
    warnings: list[ConsistencyWarning],
) -> str:
    lines = [
        "## Project dependency audit",
        "",
        f"{totals.files} files, {totals.dependencies} dependencies: {totals.vulnerable} "
        f"vulnerable ({totals.vulnerabilities} known vulnerabilities), {totals.outdated} "
        f"outdated, {totals.unchecked} unchecked.",
        "",
    ]
    shown = list(vulnerable.values())[:MAX_SUMMARY_PACKAGES]
    lines += [
        f"- {dep.name} {dep.checked_version}: {total} known vulnerabilities" for dep, total in shown
    ]
    if len(vulnerable) > len(shown):
        lines.append(f"- ...and {len(vulnerable) - len(shown)} more vulnerable packages")
    if shown:
        lines.append("")
    lines.append(f"Consistency warnings: {len(warnings)}")
    return "\n".join(lines)


def _resolve_targets(path: str) -> tuple[Path, list[Path]]:
    valid, message = validate_file_path(path)
    if not valid:
        raise ToolError(f"Invalid input: {message}")
    root = Path(path).expanduser()
    if root.is_file():
        try:
            file_kind(root)
        except ValueError as exc:
            raise ToolError(f"Invalid input: {exc}") from exc
        return root, [root]
    files = discover_dependency_files(root) if root.is_dir() else []
    if not files:
        raise ToolError(f"Invalid input: no dependency files found under '{path}'")
    return root, files


def register_project_tools(mcp: FastMCP, client: PyPIClient) -> None:
    """Register the project tools."""

    @mcp.tool(title="Audit project dependencies", annotations=TOOL_ANNOTATIONS, timeout=180)
    async def audit_project(
        path: str, ctx: Context, detail: Literal["summary", "full"] = "summary"
    ) -> ProjectAudit:
        """Audit a project's dependency files for vulnerabilities, outdated pins and drift.

        `path` is a directory (searched up to 4 levels deep, at most 50 files:
        pyproject.toml, requirements*.txt, setup.py/cfg, Pipfile(.lock), poetry.lock,
        conda environment files) or a single such file. Files are only parsed, never
        executed. Each dependency is checked at its pinned version, else its lowest
        allowed version, else the latest release. A dependency that could not be
        checked carries an `error`, is counted in `totals.unchecked` and is never
        reported as clean. `detail="summary"` lists only vulnerable, outdated or
        unchecked dependencies per file; totals always cover everything.
        """
        root, files = _resolve_targets(path)
        steps = len(files) + 1
        parsed: list[tuple[Path, str, list[DeclaredDependency]]] = []
        audited: list[AuditedFile] = []
        for i, file in enumerate(files):
            kind = file_kind(file)
            try:
                parsed.append((file, kind, parse_dependency_file(file)))
            except DependencyFileError as exc:
                audited.append(AuditedFile(path=str(file), kind=kind, error=str(exc)))
            await ctx.report_progress(i + 1, steps)

        names = {d.normalized_name for _, _, deps in parsed for d in deps}
        latest = await _latest_versions(client, names)
        checked: dict[tuple[Path, int], str | None] = {}
        pairs: dict[Key, Key] = {}
        for file, _, deps in parsed:
            for i, dep in enumerate(deps):
                version = dep.pinned_version or floor_version(dep.specifier)
                version = version or latest[dep.normalized_name]
                checked[(file, i)] = version
                if version:
                    pairs.setdefault((dep.normalized_name, version), (dep.normalized_name, version))
        outcomes: dict[Key, dict[str, Any] | str] = {}
        if pairs:
            outcomes = await query_osv(client, list(pairs.values()))
        await ctx.report_progress(steps, steps)

        totals = AuditTotals(files=len(files))
        vulnerable: dict[str, tuple[AuditedDependency, int]] = {}
        for file, kind, deps in parsed:
            out: list[AuditedDependency] = []
            for i, dep in enumerate(deps):
                norm, version = dep.normalized_name, checked[(file, i)]
                item = AuditedDependency(
                    name=dep.name,
                    specifier=dep.specifier,
                    group=dep.group,
                    checked_version=version,
                    latest_version=latest[norm],
                    outdated=_is_outdated(version, latest[norm]),
                )
                res = outcomes.get((norm, version)) if version else None
                total = 0
                if version is None:
                    item.error = f"Could not resolve the latest version of '{dep.name}'."
                elif res is None or isinstance(res, str):
                    item.error = res or "No result returned from OSV"
                else:
                    total, _ = vulnerability_totals(res)
                    item.vulnerable = total > 0
                    item.vulnerabilities = [
                        VulnerabilityItem.from_core(v) for v in res.get("vulnerabilities", [])
                    ]
                totals.dependencies += 1
                totals.unchecked += 1 if item.error else 0
                totals.outdated += 1 if item.outdated else 0
                totals.vulnerable += 1 if item.vulnerable else 0
                totals.vulnerabilities += total
                if item.vulnerable:
                    vulnerable.setdefault(norm, (item, total))
                if detail == "full" or item.vulnerable or item.outdated or item.error:
                    out.append(item)
            audited.append(AuditedFile(path=str(file), kind=kind, dependencies=out))
        if totals.dependencies and totals.unchecked == totals.dependencies:
            raise ToolError(ALL_FAILED)

        audited.sort(key=lambda f: f.path)
        warnings = _consistency_warnings(parsed)
        return ProjectAudit(
            path=str(root),
            files=audited,
            consistency_warnings=warnings,
            totals=totals,
            recommendations=_recommendations(vulnerable, parsed, warnings, totals.unchecked),
            summary=_summary(totals, vulnerable, warnings),
        )
