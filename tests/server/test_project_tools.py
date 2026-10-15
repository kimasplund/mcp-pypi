"""Tests for audit_project."""

import json
import os
from pathlib import Path
from typing import Any

import pytest

NO_VULNS: dict[str, Any] = {"vulnerabilities": [], "total_vulnerabilities": 0}


def vuln(vid="PYSEC-1", severity="HIGH") -> dict[str, Any]:
    return {"id": vid, "summary": "bad", "severity": severity, "cve": ["CVE-1"]}


def result(name: str, version: str, *vulns: dict) -> dict[str, Any]:
    out: dict[str, Any] = {
        "package": name,
        "version": version,
        "vulnerabilities": list(vulns),
        "total_vulnerabilities": len(vulns),
        "vulnerable": bool(vulns),
    }
    for sev in ("critical", "high", "medium", "low"):
        out[f"{sev}_count"] = sum(1 for v in vulns if v["severity"].lower() == sev)
    return out


def batch_of(vulns_by_key: dict[str, list[dict]] | None = None):
    """A fake check_vulnerabilities_batch keyed by core's normalized `name:version`."""
    vulns_by_key = vulns_by_key or {}

    async def fake(pairs):
        results = {}
        for name, version in pairs:
            key = f"{name.lower().replace('_', '-')}:{version}"
            results[key] = result(name, version, *vulns_by_key.get(key, []))
        return {"results": results, "errors": []}

    return fake


@pytest.fixture
def setup_client(fake_client):
    """Latest version of every package is 9.0 unless overridden."""
    latest: dict[str, str] = {}

    async def info(name, *a, **kw):
        return {"info": {"version": latest.get(name.lower(), "9.0")}}

    fake_client.get_package_info.side_effect = info
    fake_client.check_vulnerabilities_batch.side_effect = batch_of()
    return fake_client, latest


def project(tmp_path: Path, **files: str) -> Path:
    for name, text in files.items():
        (tmp_path / name.replace("__", ".")).write_text(text)
    return tmp_path


PYPROJECT = '[project]\nname = "x"\ndependencies = ["requests>=2.31", "Flask==3.0.0"]\n'
LOCK = '[[package]]\nname = "requests"\nversion = "2.31.0"\n'


async def audit(c, path, **args):
    return (await c.call_tool("audit_project", {"path": str(path), **args})).structured_content


async def test_audit_directory_finds_all_kinds(setup_client, mcp_client, tmp_path):
    project(
        tmp_path,
        pyproject__toml=PYPROJECT,
        requirements__txt="requests>=2.31\n",
        poetry__lock=LOCK,
    )
    d = await audit(mcp_client, tmp_path, detail="full")
    assert sorted(f["kind"] for f in d["files"]) == ["poetry.lock", "pyproject", "requirements"]
    assert d["totals"]["files"] == 3


async def test_audit_single_file_path(setup_client, mcp_client, tmp_path):
    project(tmp_path, requirements__txt="requests==2.0\nflask\n")
    d = await audit(mcp_client, tmp_path / "requirements.txt", detail="full")
    assert [f["kind"] for f in d["files"]] == ["requirements"]
    assert d["totals"]["dependencies"] == 2


async def test_audit_continues_past_broken_file(setup_client, mcp_client, tmp_path):
    project(
        tmp_path,
        pyproject__toml="[project\nbroken",
        requirements__txt="requests==2.0\nflask==3.0\n",
    )
    res = await mcp_client.call_tool("audit_project", {"path": str(tmp_path)})
    assert not res.is_error
    files = {f["kind"]: f for f in res.structured_content["files"]}
    assert files["pyproject"]["error"]
    assert files["pyproject"]["dependencies"] == []
    assert files["requirements"]["error"] is None
    assert files["requirements"]["dependencies"]


async def test_consistency_warning_uses_normalized_names(setup_client, mcp_client, tmp_path):
    project(
        tmp_path,
        pyproject__toml='[project]\nname="x"\ndependencies=["typing_extensions>=4"]\n',
        requirements__txt="typing-extensions>=4.5\n",
    )
    d = await audit(mcp_client, tmp_path)
    assert [w["package"] for w in d["consistency_warnings"]] == ["typing-extensions"]
    assert sorted(d["consistency_warnings"][0]["specifiers"].values()) == [">=4", ">=4.5"]
    assert "Align typing-extensions constraints across files." in d["recommendations"]
    assert (
        "Update pyproject.toml first, then sync requirements/setup files to the same constraints."
        in d["recommendations"]
    )


async def test_lock_files_excluded_from_consistency(setup_client, mcp_client, tmp_path):
    project(
        tmp_path,
        pyproject__toml='[project]\nname="x"\ndependencies=["requests>=2.31"]\n',
        poetry__lock=LOCK,
    )
    d = await audit(mcp_client, tmp_path)
    assert d["consistency_warnings"] == []


async def test_summary_detail_omits_clean_packages_but_totals_count_them(
    setup_client, mcp_client, tmp_path
):
    client, latest = setup_client
    latest["flask"] = "3.0.0"  # up to date and clean
    project(tmp_path, requirements__txt="requests==2.0\nflask==3.0.0\n")
    brief = await audit(mcp_client, tmp_path)
    full = await audit(mcp_client, tmp_path, detail="full")
    assert [x["name"] for x in brief["files"][0]["dependencies"]] == ["requests"]
    assert len(full["files"][0]["dependencies"]) == 2
    assert brief["totals"] == full["totals"]
    assert brief["totals"]["dependencies"] == 2
    assert brief["totals"]["outdated"] == 1


async def test_vulnerable_recommendation_text(setup_client, mcp_client, tmp_path):
    client, _ = setup_client
    client.check_vulnerabilities_batch.side_effect = batch_of(
        {"flask:3.0.0": [vuln("A"), vuln("B", "MODERATE")]}
    )
    project(tmp_path, requirements__txt="Flask==3.0.0\nrequests==2.0\n")
    d = await audit(mcp_client, tmp_path)
    assert (
        "Upgrade Flask (checked 3.0.0) — 2 known vulnerabilities; latest is 9.0."
        in d["recommendations"]
    )
    assert d["totals"]["vulnerable"] == 1
    assert d["totals"]["vulnerabilities"] == 2
    assert "Flask" in d["summary"]


async def test_audit_rejects_traversal_and_missing(setup_client, mcp_client, tmp_path):
    for bad in ("../../etc", str(tmp_path)):
        res = await mcp_client.call_tool("audit_project", {"path": bad}, raise_on_error=False)
        assert res.is_error
        assert "Invalid input:" in res.content[0].text


async def test_audit_output_has_no_ansi(setup_client, mcp_client, tmp_path):
    project(tmp_path, requirements__txt="requests==2.0\nflask==3.0\n")
    res = await mcp_client.call_tool("audit_project", {"path": str(tmp_path)})
    assert "\x1b" not in json.dumps(res.structured_content)


async def test_audit_uses_one_batch_call(setup_client, mcp_client, tmp_path):
    client, _ = setup_client
    project(
        tmp_path,
        pyproject__toml=PYPROJECT,
        requirements__txt="requests>=2.31\nflask==3.0.0\n",
    )
    await audit(mcp_client, tmp_path)
    client.check_vulnerabilities_batch.assert_awaited_once()


async def test_errored_lookup_is_reported_and_counted_unchecked(setup_client, mcp_client, tmp_path):
    client, _ = setup_client

    async def partial(pairs):
        results = {}
        for name, version in pairs:
            if name == "requests":
                continue
            results[f"{name}:{version}"] = result(name, version)
        return {"results": results, "errors": [{"package": "requests:2.0", "error": "boom"}]}

    client.check_vulnerabilities_batch.side_effect = partial
    project(tmp_path, requirements__txt="requests==2.0\nflask==3.0.0\n")
    d = await audit(mcp_client, tmp_path)  # summary detail keeps the errored dependency
    deps = d["files"][0]["dependencies"]
    bad = next(x for x in deps if x["name"] == "requests")
    assert bad["error"] and bad["vulnerable"] is False
    assert d["totals"]["unchecked"] == 1
    assert "1 dependencies could not be checked; see per-dependency errors." in d["recommendations"]
    assert "unchecked" in d["summary"].lower()


async def test_all_lookups_failed_raises(setup_client, mcp_client, tmp_path):
    client, _ = setup_client
    client.check_vulnerabilities_batch.side_effect = RuntimeError("down")
    project(tmp_path, requirements__txt="requests==2.0\nflask==3.0.0\n")
    res = await mcp_client.call_tool("audit_project", {"path": str(tmp_path)}, raise_on_error=False)
    assert res.is_error
    assert (
        "OSV request failed; no dependencies could be checked. Retry later." in res.content[0].text
    )


async def test_unconstrained_dependency_checked_at_resolved_latest(
    setup_client, mcp_client, tmp_path
):
    client, latest = setup_client
    latest["flask"] = "3.1.0"
    project(tmp_path, requirements__txt="flask\nrequests==2.0\n")
    d = await audit(mcp_client, tmp_path, detail="full")
    flask = next(x for x in d["files"][0]["dependencies"] if x["name"] == "flask")
    assert flask["checked_version"] == "3.1.0"
    assert flask["outdated"] is False
    pairs = client.check_vulnerabilities_batch.await_args.args[0]
    assert ("flask", "3.1.0") in pairs
    assert all(v is not None for _, v in pairs)


async def test_unresolvable_latest_for_unconstrained_is_unchecked(
    setup_client, mcp_client, tmp_path
):
    client, _ = setup_client

    async def info(name, *a, **kw):
        if name == "flask":
            return {"error": {"code": "not_found", "message": "gone"}}
        return {"info": {"version": "9.0"}}

    client.get_package_info.side_effect = info
    project(tmp_path, requirements__txt="flask\nrequests==2.0\ndjango==4.2\n")
    d = await audit(mcp_client, tmp_path)
    flask = next(x for x in d["files"][0]["dependencies"] if x["name"] == "flask")
    assert flask["error"]
    assert d["totals"]["unchecked"] == 1
    pairs = client.check_vulnerabilities_batch.await_args.args[0]
    assert all(v is not None for _, v in pairs)


INFOS: dict[str, dict[str, Any]] = {}


def releases(*versions: str, yanked: tuple[str, ...] = ()) -> dict[str, list[dict]]:
    return {v: [{"yanked": v in yanked}] for v in versions}


@pytest.fixture
async def real_osv():
    INFOS.clear()
    """A server over the REAL PyPIClient batch code with a fake OSV http layer."""
    from unittest.mock import AsyncMock, MagicMock

    from fastmcp import Client

    from mcp_pypi.core import PyPIClient
    from mcp_pypi.core.cache import AsyncCacheManager
    from mcp_pypi.core.http import AsyncHTTPClient
    from mcp_pypi.core.models import PyPIClientConfig
    from mcp_pypi.core.stats import PackageStatsService
    from mcp_pypi.server.app import build_server

    osv_db: dict[str, list] = {}

    async def fetch(url, method="GET", headers=None, data=None, **kw):
        if data is None:
            for pkg, info in INFOS.items():
                if f"/{pkg}/" in url:
                    return info
            return {"info": {"name": "x", "version": "9.0"}}
        payload = json.loads(data)
        queries = payload["queries"]
        return {"results": [{"vulns": osv_db.get(q["package"]["name"], [])} for q in queries]}

    http = AsyncMock(spec=AsyncHTTPClient)
    http.fetch = AsyncMock(side_effect=fetch)
    cache = MagicMock(spec=AsyncCacheManager)
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    client = PyPIClient(
        config=PyPIClientConfig(),
        http_client=http,
        cache_manager=cache,
        stats_service=AsyncMock(spec=PackageStatsService),
    )
    async with Client(build_server(client=client)) as c:
        yield c, osv_db


async def test_mixed_case_names_found_vulnerable_via_real_batch(real_osv, tmp_path):
    c, db = real_osv

    def osv(vid, name, sev="HIGH"):
        return {
            "id": vid,
            "summary": "bad",
            "database_specific": {"severity": sev},
            "affected": [
                {
                    "package": {"name": name, "ecosystem": "PyPI"},
                    "ranges": [{"events": [{"introduced": "0"}, {"fixed": "99"}]}],
                }
            ],
        }

    db["django"] = [osv("D-1", "Django")]
    db["typing-extensions"] = [osv("T-1", "typing-extensions", "LOW")]
    db["pyyaml"] = [osv("Y-1", "PyYAML", "CRITICAL")]
    project(
        tmp_path,
        requirements__txt="Django==4.2\ntyping_extensions==4.0\nPyYAML==5.1\nflask==3.0\n",
    )
    d = await audit(c, tmp_path)
    assert d["totals"]["unchecked"] == 0
    assert d["totals"]["vulnerable"] == 3
    assert sorted(x["name"] for x in d["files"][0]["dependencies"] if x["vulnerable"]) == [
        "Django",
        "PyYAML",
        "typing_extensions",
    ]


async def test_upper_bound_only_checks_highest_allowed_release(real_osv, tmp_path):
    c, db = real_osv
    INFOS["urllib3"] = {
        "info": {"name": "urllib3", "version": "2.2.0"},
        "releases": releases("1.25.0", "1.26.18", "2.2.0", "1.27.0rc1"),
    }
    db["urllib3"] = [
        {
            "id": "U-1",
            "summary": "bad",
            "database_specific": {"severity": "HIGH"},
            "affected": [
                {
                    "package": {"name": "urllib3", "ecosystem": "PyPI"},
                    "ranges": [{"events": [{"introduced": "0"}, {"fixed": "99"}]}],
                }
            ],
        }
    ]
    project(tmp_path, requirements__txt="urllib3<2\nflask==3.0\n")
    d = await audit(c, tmp_path)
    dep = next(x for x in d["files"][0]["dependencies"] if x["name"] == "urllib3")
    assert dep["checked_version"] == "1.26.18"
    assert dep["vulnerable"] is True and dep["error"] is None


async def test_not_equal_specifier_skips_excluded_latest(setup_client, mcp_client, tmp_path):
    client, _ = setup_client

    async def info(name, *a, **kw):
        return {"info": {"version": "2.0"}, "releases": releases("1.0", "2.0")}

    client.get_package_info.side_effect = info
    project(tmp_path, requirements__txt="pkg!=2.0\nflask==3.0\n")
    d = await audit(mcp_client, tmp_path, detail="full")
    pkg = next(x for x in d["files"][0]["dependencies"] if x["name"] == "pkg")
    assert pkg["checked_version"] == "1.0"


async def test_unsatisfiable_specifier_is_unchecked(setup_client, mcp_client, tmp_path):
    client, _ = setup_client

    async def info(name, *a, **kw):
        return {"info": {"version": "2.0"}, "releases": releases("1.0", "2.0", yanked=("1.0",))}

    client.get_package_info.side_effect = info
    project(tmp_path, requirements__txt="pkg<1.0\nflask==3.0\nrequests==2.0\npkg2<2\n")
    d = await audit(mcp_client, tmp_path)
    pkg = next(x for x in d["files"][0]["dependencies"] if x["name"] == "pkg")
    assert "No release satisfies '<1.0'" in pkg["error"]
    pkg2 = next(x for x in d["files"][0]["dependencies"] if x["name"] == "pkg2")
    assert pkg2["error"]  # only a yanked release matches, and pre/yanked fallback is not used
    assert d["totals"]["unchecked"] == 2


async def test_broken_only_directory_is_visible_in_totals(setup_client, mcp_client, tmp_path):
    project(tmp_path, pyproject__toml="[project\nbroken")
    d = await audit(mcp_client, tmp_path)
    assert d["totals"]["files_with_errors"] == 1
    assert "1 files could not be read or parsed" in d["summary"]
    assert "1 dependency files could not be read; see per-file errors." in d["recommendations"]


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root reads anything")
async def test_unreadable_file_next_to_good_one(setup_client, mcp_client, tmp_path):
    project(tmp_path, requirements__txt="requests==2.0\nflask==3.0\n")
    bad = tmp_path / "requirements-dev.txt"
    bad.write_text("pytest\n")
    bad.chmod(0)
    try:
        d = await audit(mcp_client, tmp_path)
    finally:
        bad.chmod(0o600)
    assert d["totals"]["files_with_errors"] == 1
    assert "1 dependency files could not be read; see per-file errors." in d["recommendations"]


async def test_truncated_vulnerability_list_reports_true_total(setup_client, mcp_client, tmp_path):
    fake, _ = setup_client

    async def big(name, version):
        res = result(name, version, *[vuln(f"V-{i}") for i in range(20)])
        res["total_vulnerabilities"] = 120
        return res

    fake.check_vulnerabilities.side_effect = big
    project(tmp_path, requirements__txt="jinja2==2.4.1\n")
    d = await audit(mcp_client, tmp_path)
    dep = d["files"][0]["dependencies"][0]
    assert len(dep["vulnerabilities"]) == 20
    assert dep["total_vulnerabilities"] == 120
    assert dep["vulnerabilities_truncated"] is True
    assert d["totals"]["vulnerabilities"] == 120
