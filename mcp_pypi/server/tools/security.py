"""Security tools: OSV vulnerability checks and installed-environment scans."""

from __future__ import annotations

import asyncio
import importlib.metadata
import shlex
from collections import deque
from pathlib import Path
from typing import Any, NamedTuple, cast

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from packaging.requirements import InvalidRequirement, Requirement

from mcp_pypi.core import PyPIClient
from mcp_pypi.core.search_index import normalize
from mcp_pypi.server.schemas import (
    InstalledScan,
    PackageVulnerabilities,
    VulnerabilityReport,
)
from mcp_pypi.server.tools import TOOL_ANNOTATIONS
from mcp_pypi.server.tools.osv import (
    SEVERITIES,
    Key,
    core_error,
    query_osv,
    severity_bucket,
    to_item,
    vulnerability_totals,
)
from mcp_pypi.utils.validation import validate_file_path

MAX_PACKAGES = 100
BAD_SPEC = "Only 'name' or 'name==version' is supported"


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


def _dedupe_installed(installed: list[tuple[str, str]]) -> list[Key]:
    """One entry per PEP 503 name, keeping the first (the one Python imports from sys.path)."""
    first: dict[str, Key] = {}
    for name, version in installed:
        first.setdefault(normalize(name), (name, version))
    return list(first.values())


ENV_DIR_NAMES = (".venv", "venv", "env", ".env", "virtualenv")


class Environment(NamedTuple):
    path: str  # as given, or the auto-detected directory
    site_packages: list[Path]
    python: Path  # only shown in update commands; never executed
    has_pip: bool


def _is_environment(root: Path) -> bool:
    """A venv (pyvenv.cfg) or conda env (conda-meta/) root."""
    return (root / "pyvenv.cfg").is_file() or (root / "conda-meta").is_dir()


def _site_packages(root: Path) -> list[Path]:
    found = sorted(root.glob("lib/python3*/site-packages")) + [root / "Lib" / "site-packages"]
    unique: dict[Path, Path] = {}
    for site in found:
        if site.is_dir():
            unique.setdefault(site.resolve(), site)
    return list(unique.values())


def _environment(root: Path, shown: str) -> Environment | None:
    if not _is_environment(root):
        return None
    sites = _site_packages(root)
    if not sites:
        return None
    pythons = (root / "bin" / "python", root / "Scripts" / "python.exe", root / "python.exe")
    python = next((p for p in pythons if p.exists()), pythons[0])
    has_pip = any((site / "pip").is_dir() for site in sites)
    return Environment(shown, sites, python, has_pip)


def _find_environment(environment_path: str | None) -> Environment:
    """The environment to scan; never the server's own environment."""
    if environment_path:
        root = Path(environment_path).expanduser()
        if not _is_environment(root):
            raise ToolError(
                f"'{environment_path}' is not a Python environment "
                "(no pyvenv.cfg or conda-meta found)."
            )
        env = _environment(root, environment_path)
        if env is None:
            raise ToolError(f"No site-packages directory found in '{environment_path}'.")
        return env
    for name in ENV_DIR_NAMES:
        env = _environment(Path.cwd() / name, str(Path.cwd() / name))
        if env is not None:
            return env
    raise ToolError(
        "No virtual environment found in the working directory; "
        "pass environment_path to say which environment to scan."
    )


def _list_installed(site_dirs: list[Path]) -> list[tuple[str, str]]:
    """(name, version) of every distribution in `site_dirs`, read from metadata files.

    Nothing from the environment is imported or executed (no interpreter, no .pth files).
    """
    found: list[tuple[str, str]] = []
    for dist in importlib.metadata.distributions(path=[str(d) for d in site_dirs]):
        try:
            meta = dist.metadata
            name = meta["Name"] if meta is not None and "Name" in meta else None
            version = meta["Version"] if meta is not None and "Version" in meta else None
        except (OSError, UnicodeDecodeError, ValueError):  # unreadable metadata: skip it
            continue
        if name and version:
            found.append((name, version))
    return found


def _update_command(env: Environment, package: str) -> str:
    python = shlex.quote(str(env.python))
    if env.has_pip:
        return f"{python} -m pip install --upgrade {shlex.quote(package)}"
    return f"uv pip install --python {python} --upgrade {shlex.quote(package)}"


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
        resolved are reported as errors, never checked across all versions. Items that
        could not be checked are listed in `unchecked` (never counted as clean); the call
        fails only if no item could be checked.
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
                return None, core_error(res, name) or unresolved
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
            queried = await query_osv(client, list(unique.values()))
            outcomes = {(normalize(n), v): r for (n, v), r in queried.items()}

        results: list[PackageVulnerabilities] = []
        for name, version, err in roots:
            key = (normalize(name), version)
            if err is not None:
                results.append(PackageVulnerabilities(package=name, version=version, error=err))
            else:
                item = to_item(name, version, outcomes[key], [])
                item.note = notes.get(key)
                results.append(item)
        for key in extra_order:
            name, version = unique[key]
            item = to_item(name, version, outcomes[key], via[key])
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

        unchecked = [r.package for r in results if r.error]
        if results and len(unchecked) == len(results):
            raise ToolError(f"Could not check any of the packages: {results[0].error}")

        severity_counts = dict.fromkeys(SEVERITIES, 0)
        vulnerable_packages = 0
        total_vulns = 0
        for res in outcomes.values():
            if isinstance(res, str):
                continue
            total, counts = vulnerability_totals(res)
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
            unchecked=unchecked,
        )

    @mcp.tool(title="Scan installed packages", annotations=TOOL_ANNOTATIONS, timeout=180)
    async def scan_installed_packages(
        ctx: Context, environment_path: str | None = None
    ) -> InstalledScan:
        """Scan a Python environment's installed packages for known vulnerabilities.

        `environment_path` must be a venv (has pyvenv.cfg) or conda environment (has
        conda-meta/). Without it a .venv, venv, env, .env or virtualenv directory in the
        working directory is used; if none exists the call fails and asks for a path.
        Installed packages are read from the environment's site-packages metadata; nothing
        in the environment is executed. Packages that could not be checked are listed in
        `unchecked` and prevent `all_clear`. No terminal colours.
        """
        if environment_path:
            valid, message = validate_file_path(environment_path)
            if not valid:
                raise ToolError(f"Cannot read file: {message or 'Invalid environment path'}")
        env = _find_environment(environment_path)
        installed = await asyncio.to_thread(_list_installed, env.site_packages)
        pairs = _dedupe_installed(installed)
        await ctx.report_progress(0, max(1, len(pairs)))

        vulnerable: list[PackageVulnerabilities] = []
        unchecked: list[str] = []
        first_error = ""
        for start in range(0, len(pairs), MAX_PACKAGES):
            chunk = pairs[start : start + MAX_PACKAGES]
            outcomes = await query_osv(client, chunk)
            for name, version in chunk:
                item = to_item(name, version, outcomes[(name, version)], [])
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
                min((rank[severity_bucket(v.severity)] for v in p.vulnerabilities), default=9),
                -p.total_vulnerabilities,
            )
        )
        commands = [_update_command(env, p.package) for p in vulnerable]
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
            environment_path=env.path,
            packages_scanned=len(pairs),
            vulnerable=vulnerable,
            all_clear=not vulnerable and not unchecked,
            unchecked=unchecked,
            update_commands=commands,
            recommendation=" ".join(parts),
        )
