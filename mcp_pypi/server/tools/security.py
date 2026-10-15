"""Security tools: OSV vulnerability checks and installed-environment scans."""

from __future__ import annotations

import asyncio
import contextlib
import json
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
from mcp_pypi.utils.sanitize import sanitize_package_name, sanitize_version
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
    """Check unique (name, version) pairs: one core call for a single pair, else one batch.

    A pair without a resolvable version or with characters core rejects becomes a
    per-pair error string; it is never queried as "all versions" and never fails the call.
    """
    out: dict[Key, dict[str, Any] | str] = {}
    valid: list[Key] = []
    for name, version in pairs:
        if not version:
            out[(name, version)] = f"Could not resolve version for '{name}'."
            continue
        try:
            sanitize_package_name(name)
            sanitize_version(version)
        except ValueError as exc:
            out[(name, version)] = str(exc)
            continue
        valid.append((name, version))
    if not valid:
        return out
    try:
        if len(valid) == 1:
            name, version = valid[0]
            res = await client.check_vulnerabilities(name, version)
            out[valid[0]] = _core_error(res, name) or res
            return out
        batch = await client.check_vulnerabilities_batch(valid)
    except Exception as exc:  # one bad item must not fail the whole call
        for pair in valid:
            out[pair] = f"OSV request failed: {exc}"
        return out
    errors = {e.get("package"): str(e.get("error")) for e in batch.get("errors", [])}
    for name, version in valid:
        key = f"{normalize(name)}:{version}"  # core keys results by the PEP 503 name
        res = batch.get("results", {}).get(key)
        out[(name, version)] = res if res is not None else errors.get(key, _NO_RESULT)
    return out


_NO_RESULT = "No result returned from OSV"


def _totals(res: Mapping[str, Any]) -> tuple[int, dict[str, int]]:
    """True vulnerability total and per-severity counts, as computed by core."""
    listed = res.get("vulnerabilities", [])
    total = int(res.get("total_vulnerabilities", len(listed)))
    counts = dict.fromkeys(SEVERITIES, 0)
    if "critical_count" in res or "high_count" in res:
        for sev in SEVERITIES[:4]:
            counts[sev] = int(res.get(f"{sev}_count", 0))
        counts["unknown"] = max(0, total - sum(counts[s] for s in SEVERITIES[:4]))
    else:
        for v in listed:
            counts[_severity_bucket(v.get("severity"))] += 1
    return total, counts


def _to_item(
    name: str, version: str | None, res: dict[str, Any] | str, via: list[str]
) -> PackageVulnerabilities:
    if isinstance(res, str):
        return PackageVulnerabilities(package=name, version=version, error=res, introduced_via=via)
    vulns = [VulnerabilityItem.from_core(v) for v in res.get("vulnerabilities", [])]
    total, _ = _totals(res)
    return PackageVulnerabilities(
        package=name,
        version=version,
        vulnerable=total > 0,
        vulnerabilities=vulns,
        total_vulnerabilities=total,
        vulnerabilities_truncated=total > len(vulns),
        introduced_via=via,
    )


def _dedupe_installed(installed: list[tuple[str, str]]) -> list[Key]:
    """One entry per PEP 503 name, keeping the first (the one Python imports from sys.path)."""
    first: dict[str, Key] = {}
    for name, version in installed:
        first.setdefault(normalize(name), (name, version))
    return list(first.values())


_LIST_SCRIPT = (
    "import importlib.metadata as m, json\n"
    "print(json.dumps([[d.metadata.get('Name'), d.version] for d in m.distributions()"
    " if d.metadata.get('Name') and d.version]))"
)


async def _list_installed(python_exe: str) -> list[tuple[str, str]]:
    """List (name, version) of an environment's distributions using its own interpreter."""
    try:
        proc = await asyncio.create_subprocess_exec(
            python_exe,
            "-I",
            "-c",
            _LIST_SCRIPT,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        raise ToolError(f"Cannot run Python at '{python_exe}': {exc}") from exc
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), PIP_TIMEOUT)
    except TimeoutError as exc:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        await proc.wait()
        raise ToolError(
            f"Listing installed packages timed out after {PIP_TIMEOUT} seconds"
        ) from exc
    if proc.returncode != 0:
        detail = stderr.decode(errors="replace").strip()[:300]
        raise ToolError(f"Failed to list installed packages (exit {proc.returncode}). {detail}")
    try:
        rows = json.loads(stdout)
        return [(str(n), str(v)) for n, v in rows]
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ToolError("Failed to list installed packages: invalid output") from exc


def _python_in(env: str) -> Path | None:
    for rel in (("bin", "python"), ("Scripts", "python.exe")):
        candidate = Path(env, *rel)
        if candidate.exists():
            return candidate
    return None


def _find_environment(environment_path: str | None) -> tuple[str, str]:
    """Return (environment path, its Python executable); never the server's own environment."""
    if environment_path:
        python = _python_in(environment_path)
        if python is None:
            raise ToolError(f"No Python interpreter found in environment '{environment_path}'.")
        return environment_path, str(python)
    for venv_name in (".venv", "venv", "env", ".env", "virtualenv"):
        venv = Path.cwd() / venv_name
        python = _python_in(str(venv))
        if python is not None:
            return str(venv), str(python)
    raise ToolError(
        "No virtual environment found in the working directory; "
        "pass environment_path to say which environment to scan."
    )


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
        shortest root-to-dependency chain of names. Items whose version cannot be
        resolved are reported as errors, never checked across all versions.
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
            unresolved = f"Could not resolve version for '{name}'."
            try:
                async with sem:
                    res = await client.get_package_info(name)
            except Exception:
                return None, unresolved
            if not isinstance(res, dict):
                return None, unresolved
            if res.get("error"):
                return None, _core_error(res, name) or unresolved
            latest = (res.get("info") or {}).get("version")
            return (str(latest), None) if latest else (None, unresolved)

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
        for name, version, err in roots:
            if err is None:
                unique.setdefault((normalize(name), version), (name, version))

        via: dict[Key, list[str]] = {}
        extra_order: list[Key] = []
        unresolved_nodes: dict[Key, tuple[str, list[str]]] = {}
        notes: dict[Key, str] = {}
        if include_transitive:
            ok_roots = [(n, v) for n, v, e in roots if e is None]

            async def tree_of(name: str, version: str | None) -> dict[str, Any] | None:
                try:
                    async with sem:
                        res = await client.get_dependency_tree(name, version, max_depth)
                except Exception:
                    return None
                return None if res.get("error") else cast(dict[str, Any] | None, res.get("tree"))

            trees = await asyncio.gather(*(tree_of(n, v) for n, v in ok_roots))
            for (root_name, root_version), tree in zip(ok_roots, trees, strict=True):
                if not tree:
                    notes[(normalize(root_name), root_version)] = (
                        "The dependency tree could not be resolved; "
                        "transitive dependencies were not checked."
                    )
                    continue
                for name, version, path in _walk_tree(tree):
                    key = (normalize(name), version)
                    if version is None:
                        unresolved_nodes.setdefault(key, (name, path))
                    elif key not in unique:
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
            key = (normalize(name), version)
            if err is not None:
                results.append(PackageVulnerabilities(package=name, version=version, error=err))
            else:
                item = _to_item(name, version, outcomes[key], [])
                item.note = notes.get(key)
                results.append(item)
        for key in extra_order:
            name, version = unique[key]
            item = _to_item(name, version, outcomes[key], via[key])
            if item.vulnerable or item.error:
                results.append(item)
        for name, path in unresolved_nodes.values():
            results.append(
                PackageVulnerabilities(
                    package=name,
                    introduced_via=path,
                    error=f"Could not resolve version for '{name}'.",
                )
            )

        severity_counts = dict.fromkeys(SEVERITIES, 0)
        vulnerable_packages = 0
        total_vulns = 0
        for res in outcomes.values():
            if isinstance(res, str):
                continue
            total, counts = _totals(res)
            vulnerable_packages += 1 if total else 0
            total_vulns += total
            for sev, n in counts.items():
                severity_counts[sev] += n
        await ctx.report_progress(total_steps, total_steps)
        return VulnerabilityReport(
            results=results,
            total_packages=len(unique) + len(unresolved_nodes),
            vulnerable_packages=vulnerable_packages,
            total_vulnerabilities=total_vulns,
            severity_counts=severity_counts,
            transitive_checked=include_transitive and not notes,
        )

    @mcp.tool(title="Scan installed packages", annotations=TOOL_ANNOTATIONS, timeout=180)
    async def scan_installed_packages(
        ctx: Context, environment_path: str | None = None
    ) -> InstalledScan:
        """Scan a Python environment's installed packages for known vulnerabilities.

        Without `environment_path` a virtualenv (.venv, venv, env, .env or virtualenv) in
        the working directory is used; if none exists the call fails and asks for a
        path. Packages are listed with the environment's own interpreter (no pip needed,
        60 second limit) and checked against OSV in batches. Packages that could not be
        checked are listed in `unchecked` and prevent `all_clear`. No terminal colours.
        """
        if environment_path:
            valid, message = validate_file_path(environment_path)
            if not valid:
                raise ToolError(f"Cannot read file: {message or 'Invalid environment path'}")
        env_path, python_exe = _find_environment(environment_path)
        installed = await _list_installed(python_exe)
        pairs = _dedupe_installed(installed)
        await ctx.report_progress(0, max(1, len(pairs)))

        vulnerable: list[PackageVulnerabilities] = []
        unchecked: list[str] = []
        first_error = ""
        for start in range(0, len(pairs), MAX_PACKAGES):
            chunk = pairs[start : start + MAX_PACKAGES]
            outcomes = await _query_osv(client, chunk)
            for name, version in chunk:
                item = _to_item(name, version, outcomes[(name, version)], [])
                if item.error:
                    unchecked.append(name)
                    first_error = first_error or item.error
                elif item.vulnerable:
                    vulnerable.append(item)
            await ctx.report_progress(min(start + len(chunk), len(pairs)), len(pairs))
        if pairs and len(unchecked) == len(pairs):
            raise ToolError(f"Could not check any installed packages against OSV: {first_error}")

        rank = {s: i for i, s in enumerate(SEVERITIES)}
        vulnerable.sort(
            key=lambda p: (
                min((rank[_severity_bucket(v.severity)] for v in p.vulnerabilities), default=9),
                -p.total_vulnerabilities,
            )
        )
        commands = [
            f"{shlex.quote(python_exe)} -m pip install --upgrade {shlex.quote(p.package)}"
            for p in vulnerable
        ]
        parts = []
        if vulnerable:
            parts.append(
                f"{len(vulnerable)} of {len(pairs)} installed packages have known "
                "vulnerabilities. Upgrade them with the commands below and re-run the scan."
            )
        if unchecked:
            noun = "package" if len(unchecked) == 1 else "packages"
            parts.append(f"{len(unchecked)} {noun} could not be checked (see `unchecked`).")
        if not parts:
            parts.append("No known vulnerabilities found in the installed packages.")
        return InstalledScan(
            environment_path=env_path,
            packages_scanned=len(pairs),
            vulnerable=vulnerable,
            all_clear=not vulnerable and not unchecked,
            unchecked=unchecked,
            update_commands=commands,
            recommendation=" ".join(parts),
        )
