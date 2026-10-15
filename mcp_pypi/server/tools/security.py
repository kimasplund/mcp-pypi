"""Security tools: OSV vulnerability checks and installed-environment scans."""

from __future__ import annotations

import asyncio
import json
import os
import shlex
from collections import deque
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from packaging.requirements import InvalidRequirement, Requirement

from mcp_pypi.core import PyPIClient
from mcp_pypi.core.search_index import normalize
from mcp_pypi.server.schemas import (
    InstalledScan,
    PackageVulnerabilities,
    VulnerabilityItem,
    VulnerabilityReport,
)
from mcp_pypi.server.tools import TOOL_ANNOTATIONS
from mcp_pypi.utils.validation import validate_file_path

MAX_PACKAGES = 100
PIP_TIMEOUT = 60
BAD_SPEC = "Only 'name' or 'name==version' is supported"
SEVERITIES = ("critical", "high", "medium", "low", "unknown")

Key = tuple[str, str | None]


def _parse_requirement(spec: str) -> tuple[str, str | None] | str:
    """Return (name, pinned version or None) for a requirement string, or an error message."""
    try:
        req = Requirement(spec.strip())
    except InvalidRequirement:
        return BAD_SPEC
    if req.url or req.marker:
        return BAD_SPEC
    specs = list(req.specifier)
    if not specs:
        return req.name, None
    if len(specs) == 1 and specs[0].operator == "==" and "*" not in specs[0].version:
        return req.name, specs[0].version
    return BAD_SPEC


def _severity_bucket(raw: object) -> str:
    text = str(raw or "").lower()
    if text == "moderate":
        return "medium"
    return text if text in SEVERITIES else "unknown"


def _core_error(res: Mapping[str, Any], name: str) -> str | None:
    """Message for an error in a single-package core result, or None."""
    error = res.get("error")
    if not error:
        return None
    if isinstance(error, dict):
        if error.get("code") == "not_found":
            return f"Package '{name}' not found on PyPI."
        return f"OSV request failed ({error.get('code', 'unknown_error')}); retry later."
    return f"OSV request failed: {error}"


def _walk_tree(root: dict[str, Any]) -> list[tuple[str, str | None, list[str]]]:
    """Breadth-first (name, version, path-from-root) for every node below the root."""
    found: list[tuple[str, str | None, list[str]]] = []
    queue: deque[tuple[dict[str, Any], list[str]]] = deque([(root, [root.get("name", "")])])
    while queue:
        node, path = queue.popleft()
        for child in node.get("dependencies") or []:
            child_path = [*path, child.get("name", "")]
            found.append((child.get("name", ""), child.get("version"), child_path))
            if not child.get("cycle"):
                queue.append((child, child_path))
    return found


async def _query_osv(client: PyPIClient, pairs: list[Key]) -> dict[Key, dict[str, Any] | str]:
    """Check unique (name, version) pairs: one core call for a single pair, else one batch."""
    out: dict[Key, dict[str, Any] | str] = {}
    if len(pairs) == 1:
        name, version = pairs[0]
        res = await client.check_vulnerabilities(name, version)
        out[pairs[0]] = _core_error(res, name) or res
        return out
    batch = await client.check_vulnerabilities_batch(pairs)
    errors = {e.get("package"): str(e.get("error")) for e in batch.get("errors", [])}
    for name, version in pairs:
        key = f"{name}:{version or 'all'}"
        res = batch.get("results", {}).get(key)
        if res is not None:
            out[(name, version)] = res
        else:
            out[(name, version)] = errors.get(key, "No result returned from OSV")
    return out


def _to_item(
    name: str, version: str | None, res: dict[str, Any] | str, via: list[str]
) -> PackageVulnerabilities:
    if isinstance(res, str):
        return PackageVulnerabilities(package=name, version=version, error=res, introduced_via=via)
    vulns = [VulnerabilityItem.from_core(v) for v in res.get("vulnerabilities", [])]
    return PackageVulnerabilities(
        package=name,
        version=version,
        vulnerable=bool(vulns),
        vulnerabilities=vulns,
        introduced_via=via,
    )


async def _pip_list(pip_cmd: str) -> list[dict[str, Any]]:
    """Run `pip list --format=json` without blocking the event loop."""
    try:
        proc = await asyncio.create_subprocess_exec(
            pip_cmd,
            "list",
            "--format=json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        raise ToolError(f"Cannot run pip at '{pip_cmd}': {exc}") from exc
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), PIP_TIMEOUT)
    except TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise ToolError(f"pip list timed out after {PIP_TIMEOUT} seconds") from exc
    if proc.returncode != 0:
        detail = stderr.decode(errors="replace").strip()[:300]
        raise ToolError(f"Failed to get package list: pip exited with {proc.returncode}. {detail}")
    try:
        packages = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ToolError("Failed to get package list: pip returned invalid JSON") from exc
    return [p for p in packages if isinstance(p, dict) and p.get("name") and p.get("version")]


def _find_environment(environment_path: str | None) -> tuple[str | None, str]:
    """Resolve the environment path (auto-detecting a local venv) and its pip executable."""
    if not environment_path:
        for venv_name in (".venv", "venv", "env", ".env", "virtualenv"):
            venv_path = Path.cwd() / venv_name
            if (venv_path / "bin" / "pip").exists() or (venv_path / "Scripts" / "pip.exe").exists():
                environment_path = str(venv_path)
                break
    if not environment_path:
        return None, "pip"
    if os.name == "nt":
        return environment_path, os.path.join(environment_path, "Scripts", "pip.exe")
    return environment_path, os.path.join(environment_path, "bin", "pip")


def register_security_tools(mcp: FastMCP, client: PyPIClient) -> None:
    """Register the security tools."""

    @mcp.tool(title="Check package vulnerabilities", annotations=TOOL_ANNOTATIONS, timeout=180)
    async def check_vulnerabilities(
        packages: list[str],
        ctx: Context,
        include_transitive: bool = False,
        max_depth: int = 2,
    ) -> VulnerabilityReport:
        """Check up to 100 packages against OSV for known vulnerabilities.

        Each item is `name` (the latest release) or `name==version`; extras are ignored
        and any other specifier is rejected for that item only. With `include_transitive`
        the dependency tree is resolved to `max_depth` (1-3) and every dependency is
        checked too; vulnerable dependencies are listed with `introduced_via`, the
        shortest root-to-dependency chain of names.
        """
        if len(packages) > MAX_PACKAGES:
            raise ToolError(f"Invalid input: at most {MAX_PACKAGES} packages per call")
        if not packages:
            raise ToolError("Invalid input: at least 1 package is required")
        max_depth = max(1, min(max_depth, 3))
        total_steps = 3 if include_transitive else 2
        await ctx.report_progress(0, total_steps)

        parsed = [(spec, _parse_requirement(spec)) for spec in packages]
        sem = asyncio.Semaphore(10)

        async def resolve(name: str, version: str | None) -> tuple[str | None, str | None]:
            """Pin an unpinned name to its latest version; returns (version, error)."""
            if version:
                return version, None
            async with sem:
                res = await client.get_package_info(name)
            if not isinstance(res, dict):
                return None, None
            if res.get("error"):
                return None, _core_error(res, name) or "PyPI request failed; retry later."
            latest = (res.get("info") or {}).get("version")
            return (str(latest) if latest else None), None

        pending = [item for _, item in parsed if not isinstance(item, str)]
        resolved = iter(await asyncio.gather(*(resolve(n, v) for n, v in pending)))
        roots: list[tuple[str, str | None, str | None]] = []  # (name, version, error)
        for spec, item in parsed:
            if isinstance(item, str):
                roots.append((spec, None, item))
            else:
                version, err = next(resolved)
                roots.append((item[0], version, err))
        await ctx.report_progress(1, total_steps)

        unique: dict[Key, Key] = {}  # normalized key -> query pair (first spelling)
        via: dict[Key, list[str]] = {}
        for name, version, err in roots:
            if err is None:
                unique.setdefault((normalize(name), version), (name, version))

        extra_order: list[Key] = []
        if include_transitive:
            ok_roots = [(n, v) for n, v, e in roots if e is None]

            async def tree_of(name: str, version: str | None) -> dict[str, Any] | None:
                async with sem:
                    res = await client.get_dependency_tree(name, version, max_depth)
                return None if res.get("error") else cast(dict[str, Any] | None, res.get("tree"))

            trees = await asyncio.gather(*(tree_of(n, v) for n, v in ok_roots))
            for tree in trees:
                if not tree:
                    continue
                for name, version, path in _walk_tree(tree):
                    key = (normalize(name), version)
                    if key not in unique:
                        unique[key] = (name, version)
                        via[key] = path
                        extra_order.append(key)
            await ctx.report_progress(2, total_steps)

        outcomes: dict[Key, dict[str, Any] | str] = {}
        if unique:
            queried = await _query_osv(client, list(unique.values()))
            outcomes = {(normalize(n), v): r for (n, v), r in queried.items()}

        results: list[PackageVulnerabilities] = []
        for name, version, err in roots:
            if err is not None:
                results.append(PackageVulnerabilities(package=name, version=version, error=err))
            else:
                res = outcomes[(normalize(name), version)]
                results.append(_to_item(name, version, res, []))
        for key in extra_order:
            name, version = unique[key]
            item = _to_item(name, version, outcomes[key], via[key])
            if item.vulnerable or item.error:
                results.append(item)

        severity_counts = dict.fromkeys(SEVERITIES, 0)
        vulnerable_packages = 0
        total_vulns = 0
        for res in outcomes.values():
            if isinstance(res, str):
                continue
            vulns = res.get("vulnerabilities", [])
            vulnerable_packages += 1 if vulns else 0
            total_vulns += len(vulns)
            for v in vulns:
                severity_counts[_severity_bucket(v.get("severity"))] += 1
        await ctx.report_progress(total_steps, total_steps)
        return VulnerabilityReport(
            results=results,
            total_packages=len(unique),
            vulnerable_packages=vulnerable_packages,
            total_vulnerabilities=total_vulns,
            severity_counts=severity_counts,
            transitive_checked=include_transitive,
        )

    @mcp.tool(title="Scan installed packages", annotations=TOOL_ANNOTATIONS, timeout=180)
    async def scan_installed_packages(
        ctx: Context, environment_path: str | None = None
    ) -> InstalledScan:
        """Scan a Python environment's installed packages for known vulnerabilities.

        Without `environment_path` a local virtualenv (.venv, venv, env, .env or
        virtualenv in the working directory) is auto-detected, falling back to the
        system `pip`. The package list comes from `pip list` (60 second limit) and is
        checked against OSV in batches. Output has no terminal colour codes and lists
        ready-to-run upgrade commands for the vulnerable packages.
        """
        if environment_path:
            valid, message = validate_file_path(environment_path)
            if not valid:
                raise ToolError(f"Cannot read file: {message or 'Invalid environment path'}")
        env_path, pip_cmd = _find_environment(environment_path)
        installed = await _pip_list(pip_cmd)
        await ctx.report_progress(0, max(1, len(installed)))

        pairs: list[Key] = [(p["name"], p["version"]) for p in installed]
        vulnerable: list[PackageVulnerabilities] = []
        for start in range(0, len(pairs), MAX_PACKAGES):
            chunk = pairs[start : start + MAX_PACKAGES]
            outcomes = await _query_osv(client, chunk)
            for name, version in chunk:
                item = _to_item(name, version, outcomes[(name, version)], [])
                if item.vulnerable:
                    vulnerable.append(item)
            await ctx.report_progress(min(start + len(chunk), len(pairs)), len(pairs))

        rank = {s: i for i, s in enumerate(SEVERITIES)}
        vulnerable.sort(
            key=lambda p: (
                min((rank[_severity_bucket(v.severity)] for v in p.vulnerabilities), default=9),
                -len(p.vulnerabilities),
            )
        )
        pip_prefix = "pip" if pip_cmd == "pip" else shlex.quote(pip_cmd)
        commands = [f"{pip_prefix} install --upgrade {shlex.quote(p.package)}" for p in vulnerable]
        if vulnerable:
            recommendation = (
                f"{len(vulnerable)} of {len(pairs)} installed packages have known "
                "vulnerabilities. Upgrade them with the commands below and re-run the scan."
            )
        else:
            recommendation = "No known vulnerabilities found in the installed packages."
        return InstalledScan(
            environment_path=env_path,
            packages_scanned=len(pairs),
            vulnerable=vulnerable,
            all_clear=not vulnerable,
            update_commands=commands,
            recommendation=recommendation,
        )
