"""Dependency tools: direct requirements, dependency trees and batch package checks."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from mcp_pypi.core import PyPIClient
from mcp_pypi.core.search_index import normalize
from mcp_pypi.server.errors import checked, item_error
from mcp_pypi.server.schemas import (
    Dependencies,
    DependencyEntry,
    DependencyNode,
    PackageCheck,
    PackageChecks,
)
from mcp_pypi.server.tools import TOOL_ANNOTATIONS

MAX_NAMES = 100


def _node(raw: dict[str, Any]) -> DependencyNode:
    return DependencyNode(
        name=str(raw.get("name", "")),
        version=raw.get("version"),
        cycle=bool(raw.get("cycle", False)),
        dependencies=[_node(child) for child in raw.get("dependencies") or []],
    )


def register_dependency_tools(mcp: FastMCP, client: PyPIClient) -> None:
    """Register the dependencies tools."""

    @mcp.tool(title="Get package dependencies", annotations=TOOL_ANNOTATIONS, timeout=60)
    async def get_dependencies(
        package_name: str, version: str | None = None, depth: int = 1
    ) -> Dependencies:
        """List the requirements of a package, optionally as a transitive tree.

        With `depth=1` it returns the direct requirements (name, specifier, extras and
        environment marker). With `depth` 2-5 it also returns `tree`, the resolved
        dependency tree down to that depth, with repeated packages flagged as `cycle`.
        `depth` is clamped to 1-5 and `version` defaults to the latest release.
        """
        depth = max(1, min(depth, 5))
        data = await checked(
            await client.get_dependencies(package_name, version),
            client=client,
            package=package_name,
        )
        entries = [
            DependencyEntry(
                name=str(d.get("name", "")),
                specifier=str(d.get("version_spec") or ""),
                extras=list(d.get("extras") or []),
                marker=d.get("marker"),
            )
            for d in data.get("dependencies", [])
        ]
        tree = None
        if depth > 1:
            tree_data = await checked(
                await client.get_dependency_tree(package_name, version, depth),
                client=client,
                package=package_name,
            )
            tree = _node(tree_data["tree"])
        return Dependencies(
            package_name=package_name,
            version=version or (tree.version if tree else None),
            depth=depth,
            dependencies=entries,
            tree=tree,
        )

    @mcp.tool(title="Check packages exist", annotations=TOOL_ANNOTATIONS, timeout=60)
    async def check_packages(names: list[str], ctx: Context) -> PackageChecks:
        """Check up to 100 package names on PyPI and report latest version and summary.

        Names are de-duplicated by PEP 503 normalization (the first spelling is kept) and
        checked concurrently. A name that does not exist is listed in `missing`; any
        other failure is reported in that item's `error` without failing the call.
        """
        if len(names) > MAX_NAMES:
            raise ToolError(f"Invalid input: at most {MAX_NAMES} names per call")
        unique: dict[str, str] = {}
        for name in names:
            unique.setdefault(normalize(name), name)
        if not unique:
            raise ToolError("Invalid input: at least 1 name is required")

        sem = asyncio.Semaphore(10)
        done = 0
        total = len(unique)

        async def check(name: str) -> PackageCheck:
            nonlocal done
            normalized = normalize(name)
            async with sem:
                try:
                    result = await client.get_package_info(name)
                except Exception as exc:  # one bad item must not fail the batch
                    result = {"error": {"code": "unknown_error", "message": str(exc)}}
            done += 1
            await ctx.report_progress(done, total)
            error = result.get("error")
            if error and error.get("code") == "not_found":
                return PackageCheck(name=name, normalized_name=normalized, exists=False)
            if error:
                return PackageCheck(
                    name=name,
                    normalized_name=normalized,
                    exists=False,
                    error=item_error(cast(dict, result)),
                )
            info = result.get("info") or {}
            return PackageCheck(
                name=name,
                normalized_name=normalized,
                exists=True,
                latest_version=info.get("version"),
                summary=info.get("summary"),
            )

        results = await asyncio.gather(*(check(n) for n in unique.values()))
        missing = [r.name for r in results if not r.exists and r.error is None]
        return PackageChecks(results=list(results), total=len(results), missing=missing)
