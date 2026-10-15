"""Shared OSV helpers: batch querying with per-pair errors, true totals, item conversion."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mcp_pypi.core import PyPIClient
from mcp_pypi.core.search_index import normalize
from mcp_pypi.server.schemas import PackageVulnerabilities, VulnerabilityItem
from mcp_pypi.utils.sanitize import sanitize_package_name, sanitize_version

SEVERITIES = ("critical", "high", "medium", "low", "unknown")
Key = tuple[str, str | None]


def severity_bucket(raw: object) -> str:
    text = str(raw or "").lower()
    if text == "moderate":
        return "medium"
    return text if text in SEVERITIES else "unknown"


def core_error(res: Mapping[str, Any], name: str) -> str | None:
    """Message for an error in a single-package core result, or None."""
    error = res.get("error")
    if not error:
        return None
    if isinstance(error, dict):
        if error.get("code") == "not_found":
            return f"Package '{name}' not found on PyPI."
        return f"OSV request failed ({error.get('code', 'unknown_error')}); retry later."
    return f"OSV request failed: {error}"


async def query_osv(client: PyPIClient, pairs: list[Key]) -> dict[Key, dict[str, Any] | str]:
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
            out[valid[0]] = core_error(res, name) or res
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
        out[(name, version)] = res if res is not None else errors.get(key, NO_RESULT)
    return out


NO_RESULT = "No result returned from OSV"


def vulnerability_totals(res: Mapping[str, Any]) -> tuple[int, dict[str, int]]:
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
            counts[severity_bucket(v.get("severity"))] += 1
    return total, counts


def to_item(
    name: str, version: str | None, res: dict[str, Any] | str, via: list[str]
) -> PackageVulnerabilities:
    if isinstance(res, str):
        return PackageVulnerabilities(package=name, version=version, error=res, introduced_via=via)
    vulns = [VulnerabilityItem.from_core(v) for v in res.get("vulnerabilities", [])]
    total, _ = vulnerability_totals(res)
    return PackageVulnerabilities(
        package=name,
        version=version,
        vulnerable=total > 0,
        vulnerabilities=vulns,
        total_vulnerabilities=total,
        vulnerabilities_truncated=total > len(vulns),
        introduced_via=via,
    )
