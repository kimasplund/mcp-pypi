"""Tests for check_vulnerabilities and scan_installed_packages."""

import json
import shlex
from pathlib import Path
from typing import Any

import pytest

from mcp_pypi.server.tools import security

NOT_FOUND = {"error": {"code": "not_found", "message": "gone"}}


def vuln(vid="PYSEC-1", severity="HIGH") -> dict[str, Any]:
    return {
        "id": vid,
        "summary": "bad",
        "severity": severity,
        "cve": ["CVE-2024-0001"],
        "affected_versions": [">=1", "<2"],
    }


def _counts(vulns: tuple) -> dict[str, Any]:
    out: dict[str, Any] = {"total_vulnerabilities": len(vulns)}
    for sev in ("critical", "high", "medium", "low"):
        out[f"{sev}_count"] = sum(1 for v in vulns if str(v.get("severity")).lower() == sev)
    return out


def clean(name: str, version: str) -> dict[str, Any]:
    return {
        "package": name,
        "version": version,
        "vulnerabilities": [],
        "vulnerable": False,
        "total_vulnerabilities": 0,
    }


def dirty(name: str, version: str, *vulns) -> dict[str, Any]:
    return {
        "package": name,
        "version": version,
        "vulnerabilities": list(vulns),
        "vulnerable": True,
        **_counts(vulns),
    }


def latest(version="9.9"):
    async def info(name, version_arg=None):
        return {"info": {"version": version}}

    return info


async def test_check_vulnerabilities_single_and_batch_paths(fake_client, mcp_client):
    fake_client.check_vulnerabilities.return_value = dirty("django", "4.2", vuln())
    res = await mcp_client.call_tool("check_vulnerabilities", {"packages": ["django==4.2"]})
    fake_client.check_vulnerabilities.assert_awaited_once_with("django", "4.2")
    fake_client.check_vulnerabilities_batch.assert_not_called()
    d = res.structured_content
    assert d["vulnerable_packages"] == 1
    assert d["total_vulnerabilities"] == 1
    assert d["results"][0]["vulnerabilities"][0]["aliases"] == ["CVE-2024-0001"]
    assert d["severity_counts"] == {"critical": 0, "high": 1, "medium": 0, "low": 0, "unknown": 0}

    fake_client.check_vulnerabilities.reset_mock()
    fake_client.check_vulnerabilities_batch.return_value = {
        "results": {
            "django:4.2": dirty("django", "4.2", vuln()),
            "flask:3.0": clean("flask", "3.0"),
        }
    }
    res = await mcp_client.call_tool(
        "check_vulnerabilities", {"packages": ["django==4.2", "flask==3.0"]}
    )
    fake_client.check_vulnerabilities_batch.assert_awaited_once_with(
        [("django", "4.2"), ("flask", "3.0")]
    )
    fake_client.check_vulnerabilities.assert_not_called()
    assert res.structured_content["total_packages"] == 2


async def test_check_vulnerabilities_unpinned_uses_latest(fake_client, mcp_client):
    fake_client.get_package_info.side_effect = latest("5.0")
    fake_client.check_vulnerabilities.return_value = clean("django", "5.0")
    res = await mcp_client.call_tool("check_vulnerabilities", {"packages": ["django"]})
    fake_client.check_vulnerabilities.assert_awaited_once_with("django", "5.0")
    assert res.structured_content["results"][0]["version"] == "5.0"


async def test_check_vulnerabilities_accepts_extras(fake_client, mcp_client):
    fake_client.check_vulnerabilities.return_value = clean("requests", "2.31.0")
    await mcp_client.call_tool("check_vulnerabilities", {"packages": ["requests[socks]==2.31.0"]})
    fake_client.check_vulnerabilities.assert_awaited_once_with("requests", "2.31.0")


async def test_check_vulnerabilities_rejects_ranges_per_item(fake_client, mcp_client):
    fake_client.check_vulnerabilities.return_value = clean("flask", "3.0")
    res = await mcp_client.call_tool(
        "check_vulnerabilities",
        {"packages": ["django>=4", "flask==3.0", "x==1.*"]},
        raise_on_error=False,
    )
    assert not res.is_error
    r = res.structured_content["results"]
    assert r[0]["error"] == "Only 'name' or 'name==version' is supported"
    assert r[2]["error"] == "Only 'name' or 'name==version' is supported"
    assert r[1]["error"] is None
    fake_client.check_vulnerabilities.assert_awaited_once_with("flask", "3.0")


async def test_check_vulnerabilities_item_not_found_is_per_item(fake_client, mcp_client):
    fake_client.get_package_info.return_value = NOT_FOUND
    fake_client.check_vulnerabilities.return_value = clean("flask", "3.0")
    res = await mcp_client.call_tool(
        "check_vulnerabilities", {"packages": ["nope", "flask==3.0"]}, raise_on_error=False
    )
    assert not res.is_error
    d = res.structured_content
    assert "'nope' not found" in d["results"][0]["error"]
    assert d["unchecked"] == ["nope"]


async def test_check_vulnerabilities_lists_unchecked_items(fake_client, mcp_client):
    fake_client.check_vulnerabilities.return_value = clean("flask", "3.0")
    d = (
        await mcp_client.call_tool(
            "check_vulnerabilities", {"packages": ["django>=4", "flask==3.0"]}
        )
    ).structured_content
    assert d["unchecked"] == ["django>=4"]
    assert d["results"][0]["vulnerable"] is False


async def test_check_vulnerabilities_all_items_failed_raises(fake_client, mcp_client):
    fake_client.get_package_info.return_value = NOT_FOUND
    res = await mcp_client.call_tool(
        "check_vulnerabilities", {"packages": ["nope", "x>=1"]}, raise_on_error=False
    )
    assert res.is_error
    assert res.content[0].text.startswith("Could not check any of the packages:")
    assert "'nope' not found" in res.content[0].text


async def test_invalid_version_error_reads_invalid_input(fake_client, mcp_client):
    fake_client.check_vulnerabilities.return_value = {
        "package": "django",
        "version": "4.2",
        "vulnerabilities": [],
        "error": {"code": "invalid_input", "message": "Invalid version: 4.2"},
    }
    res = await mcp_client.call_tool(
        "check_vulnerabilities", {"packages": ["django==4.2"]}, raise_on_error=False
    )
    assert res.content[0].text.endswith("Invalid input: Invalid version: 4.2")


async def test_batch_item_errors_use_the_shared_messages(fake_client, mcp_client):
    fake_client.check_vulnerabilities_batch.return_value = {
        "results": {"django:4.2": clean("django", "4.2")},
        "errors": [
            {
                "package": "flask:3.0",
                "error": "OSV query failed: Failed to fetch https://api.osv.dev/v1/query",
                "code": "network_error",
            }
        ],
    }
    d = (
        await mcp_client.call_tool(
            "check_vulnerabilities", {"packages": ["django==4.2", "flask==3.0"]}
        )
    ).structured_content
    assert d["results"][1]["error"] == "OSV request failed (network_error); retry later."
    assert d["unchecked"] == ["flask"]


async def test_check_vulnerabilities_rejects_over_100(mcp_client):
    res = await mcp_client.call_tool(
        "check_vulnerabilities",
        {"packages": [f"p{i}==1" for i in range(101)]},
        raise_on_error=False,
    )
    assert res.is_error
    assert "at most 100 packages per call" in res.content[0].text


async def test_transitive_reports_introduced_via(fake_client, mcp_client):
    fake_client.get_dependency_tree.return_value = {
        "tree": {
            "name": "flask",
            "version": "3.0",
            "dependencies": [
                {
                    "name": "werkzeug",
                    "version": "2.0",
                    "dependencies": [{"name": "markupsafe", "version": "2.1", "dependencies": []}],
                },
                {"name": "markupsafe", "version": "2.1", "dependencies": []},
            ],
        }
    }
    fake_client.check_vulnerabilities_batch.return_value = {
        "results": {
            "flask:3.0": clean("flask", "3.0"),
            "werkzeug:2.0": dirty("werkzeug", "2.0", vuln("W-1", "CRITICAL")),
            "markupsafe:2.1": dirty("markupsafe", "2.1", vuln("M-1", "weird")),
        }
    }
    res = await mcp_client.call_tool(
        "check_vulnerabilities",
        {"packages": ["flask==3.0"], "include_transitive": True, "max_depth": 9},
    )
    fake_client.get_dependency_tree.assert_awaited_once_with("flask", "3.0", 3)
    (pairs,) = fake_client.check_vulnerabilities_batch.await_args.args
    assert sorted(pairs) == [("flask", "3.0"), ("markupsafe", "2.1"), ("werkzeug", "2.0")]
    d = res.structured_content
    assert d["transitive_checked"] is True
    assert d["total_packages"] == 3
    via = {r["package"]: r["introduced_via"] for r in d["results"]}
    assert via == {
        "flask": [],
        "werkzeug": ["flask", "werkzeug"],
        "markupsafe": ["flask", "markupsafe"],
    }
    assert d["severity_counts"]["critical"] == 1
    assert d["severity_counts"]["unknown"] == 1


async def test_progress_reported(fake_client, mcp_client):
    fake_client.check_vulnerabilities.return_value = clean("a", "1")
    calls: list[Any] = []

    async def handler(progress, total, message):
        calls.append((progress, total))

    await mcp_client.call_tool(
        "check_vulnerabilities", {"packages": ["a==1"]}, progress_handler=handler
    )
    assert calls


@pytest.fixture
def pip_list(monkeypatch):
    seen: list[list] = []

    def fake(site_dirs):
        seen.append(site_dirs)
        return [("django", "3.0"), ("flask", "3.0")]

    monkeypatch.setattr(security, "_list_installed", fake)
    monkeypatch.setattr(security, "_find_environment", fake_env)
    return seen


def fake_env(path=None):
    return security.Environment(path or "/env", [], Path("/env/bin/python"), has_pip=True)


async def test_scan_installed_has_no_ansi(fake_client, mcp_client, pip_list):
    fake_client.check_vulnerabilities_batch.return_value = {
        "results": {
            "django:3.0": dirty("django", "3.0", vuln()),
            "flask:3.0": clean("flask", "3.0"),
        }
    }
    res = await mcp_client.call_tool("scan_installed_packages", {})
    d = res.structured_content
    assert "\x1b[" not in json.dumps(d)
    assert d["packages_scanned"] == 2
    assert d["all_clear"] is False
    assert [v["package"] for v in d["vulnerable"]] == ["django"]
    assert len(d["update_commands"]) == 1
    assert d["update_commands"][0].endswith("install --upgrade django")


async def test_scan_installed_rejects_traversal(mcp_client, pip_list):
    res = await mcp_client.call_tool(
        "scan_installed_packages", {"environment_path": "../x"}, raise_on_error=False
    )
    assert res.is_error
    assert pip_list == []


# --- fix round 1 -----------------------------------------------------------------------


def osv(vid: str, name: str, severity: str = "HIGH") -> dict[str, Any]:
    return {
        "id": vid,
        "summary": "bad",
        "database_specific": {"severity": severity},
        "aliases": ["CVE-2024-1"],
        "affected": [
            {
                "package": {"name": name, "ecosystem": "PyPI"},
                "ranges": [{"events": [{"introduced": "0"}, {"fixed": "99"}]}],
            }
        ],
    }


@pytest.fixture
async def real(request, fake_osv_response):
    """A server over the REAL PyPIClient batch code with a fake OSV http layer."""
    from unittest.mock import AsyncMock, MagicMock

    from fastmcp import Client

    from mcp_pypi.core import PyPIClient
    from mcp_pypi.core.cache import AsyncCacheManager
    from mcp_pypi.core.http import AsyncHTTPClient
    from mcp_pypi.core.models import PyPIClientConfig
    from mcp_pypi.core.stats import PackageStatsService
    from mcp_pypi.server.app import build_server

    osv_db: dict[str, list] = {}  # normalized OSV name -> vulns

    async def fetch(url, method="GET", headers=None, data=None, **kw):
        if data is None:  # package-exists GET made by the single-package path
            return {"info": {"name": "x", "version": "1"}}
        return fake_osv_response(url, json.loads(data), osv_db)

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
        yield client, c, osv_db


async def test_batch_lookup_handles_mixed_case_and_underscores(real):
    _client, c, db = real
    db["django"] = [osv("D-1", "Django")]
    db["pyyaml"] = [osv("Y-1", "PyYAML", "CRITICAL")]
    db["typing-extensions"] = [osv("T-1", "typing-extensions", "LOW")]
    specs = ["Django==4.2", "flask==3.0", "typing_extensions==4.0", "PyYAML==5.1", "Jinja2==3.0"]
    d = (await c.call_tool("check_vulnerabilities", {"packages": specs})).structured_content
    assert [r["error"] for r in d["results"]] == [None] * 5
    assert [r["vulnerable"] for r in d["results"]] == [True, False, True, True, False]
    assert d["vulnerable_packages"] == 3
    assert d["severity_counts"]["critical"] == 1
    assert [r["package"] for r in d["results"]][0] == "Django"


async def test_moderate_advisories_count_as_medium(real):
    _client, c, db = real
    db["django"] = [osv("D-1", "Django", "HIGH"), osv("D-2", "Django", "MODERATE")]
    db["flask"] = [osv("F-1", "flask", "MODERATE")]
    d = (
        await c.call_tool("check_vulnerabilities", {"packages": ["Django==4.2", "flask==3.0"]})
    ).structured_content
    assert d["severity_counts"] == {"critical": 0, "high": 1, "medium": 2, "low": 0, "unknown": 0}


def test_scan_dedupe_keeps_first_distribution():
    installed = [("Dup", "2.0"), ("other", "1"), ("dup", "1.0")]
    assert security._dedupe_installed(installed) == [("Dup", "2.0"), ("other", "1")]


async def test_transitive_handles_requires_dist_spelling(real):
    client, c, db = real
    client.get_dependency_tree = _tree_mock(
        {
            "name": "flask",
            "version": "3.0",
            "dependencies": [
                {"name": "Werkzeug", "version": "2.0", "dependencies": []},
                {"name": "Jinja2", "version": "3.0", "dependencies": []},
            ],
        }
    )
    db["werkzeug"] = [osv("W-1", "Werkzeug")]
    d = (
        await c.call_tool(
            "check_vulnerabilities", {"packages": ["flask==3.0"], "include_transitive": True}
        )
    ).structured_content
    hit = [r for r in d["results"] if r["vulnerable"]]
    assert [(r["package"], r["introduced_via"]) for r in hit] == [
        ("Werkzeug", ["flask", "Werkzeug"])
    ]
    assert d["transitive_checked"] is True


def _tree_mock(tree):
    from unittest.mock import AsyncMock

    return AsyncMock(return_value={"tree": tree})


async def test_scan_handles_mixed_case_installed_names(real, monkeypatch):
    _client, c, db = real
    db["django"] = [osv("D-1", "Django")]
    db["pyyaml"] = [osv("Y-1", "PyYAML")]

    def fake(site_dirs):
        return [("Django", "3.0"), ("PyYAML", "5.1"), ("flask", "3.0")]

    monkeypatch.setattr(security, "_list_installed", fake)
    monkeypatch.setattr(security, "_find_environment", fake_env)
    d = (await c.call_tool("scan_installed_packages", {})).structured_content
    assert sorted(v["package"] for v in d["vulnerable"]) == ["Django", "PyYAML"]
    assert d["unchecked"] == []


async def test_epoch_item_is_per_item_error(real):
    _client, c, db = real
    db["django"] = [osv("D-1", "Django")]
    res = await c.call_tool(
        "check_vulnerabilities",
        {"packages": ["Django==4.2", "x==1!2.0", "flask==3.0"]},
        raise_on_error=False,
    )
    assert not res.is_error
    r = res.structured_content["results"]
    assert r[0]["vulnerable"] is True
    assert "Invalid version" in r[1]["error"]
    assert r[2]["error"] is None


async def test_scan_epoch_package_is_unchecked_not_fatal(real, monkeypatch):
    _client, c, db = real
    db["django"] = [osv("D-1", "Django")]

    def fake(site_dirs):
        return [("Django", "3.0"), ("weird", "1!2.0")]

    monkeypatch.setattr(security, "_list_installed", fake)
    monkeypatch.setattr(security, "_find_environment", fake_env)
    d = (await c.call_tool("scan_installed_packages", {})).structured_content
    assert d["unchecked"] == ["weird"]
    assert d["all_clear"] is False
    assert "1 package" in d["recommendation"]


async def test_totals_use_core_counts_and_flag_truncation(fake_client, mcp_client):
    listed = [vuln(f"V-{i}", "HIGH") for i in range(20)]
    res = dirty("django", "4.2", *listed)
    res.update(
        total_vulnerabilities=25, critical_count=5, high_count=10, medium_count=5, low_count=3
    )
    fake_client.check_vulnerabilities.return_value = res
    d = (
        await mcp_client.call_tool("check_vulnerabilities", {"packages": ["django==4.2"]})
    ).structured_content
    assert d["total_vulnerabilities"] == 25
    assert d["severity_counts"] == {"critical": 5, "high": 10, "medium": 5, "low": 3, "unknown": 2}
    item = d["results"][0]
    assert item["vulnerabilities_truncated"] is True
    assert item["total_vulnerabilities"] == 25
    assert len(item["vulnerabilities"]) == 20


async def test_failed_tree_is_reported_and_not_claimed(fake_client, mcp_client):
    fake_client.check_vulnerabilities.return_value = clean("flask", "3.0")
    fake_client.get_dependency_tree.return_value = NOT_FOUND
    d = (
        await mcp_client.call_tool(
            "check_vulnerabilities", {"packages": ["flask==3.0"], "include_transitive": True}
        )
    ).structured_content
    assert d["transitive_checked"] is False
    assert "dependency tree could not be resolved" in d["results"][0]["note"]


async def test_unresolvable_versions_are_never_queried_as_all(fake_client, mcp_client):
    fake_client.get_package_info.return_value = {"info": {}}
    fake_client.get_dependency_tree.return_value = {
        "tree": {
            "name": "flask",
            "version": "3.0",
            "dependencies": [{"name": "mystery", "version": None, "dependencies": []}],
        }
    }
    fake_client.check_vulnerabilities.return_value = clean("flask", "3.0")
    d = (
        await mcp_client.call_tool(
            "check_vulnerabilities",
            {"packages": ["flask==3.0", "unpinned"], "include_transitive": True},
        )
    ).structured_content
    by = {r["package"]: r for r in d["results"]}
    assert "could not resolve version" in by["unpinned"]["error"].lower()
    assert "could not resolve version" in by["mystery"]["error"].lower()
    for call in fake_client.check_vulnerabilities.await_args_list:
        assert call.args[1] is not None
    fake_client.check_vulnerabilities_batch.assert_not_called()


async def test_scan_all_lookups_failed_raises(fake_client, mcp_client, pip_list):
    fake_client.check_vulnerabilities_batch.return_value = {"results": {}, "errors": []}
    res = await mcp_client.call_tool("scan_installed_packages", {}, raise_on_error=False)
    assert res.is_error
    assert "Could not check" in res.content[0].text


async def test_scan_partial_failure_is_not_all_clear(fake_client, mcp_client, pip_list):
    fake_client.check_vulnerabilities_batch.return_value = {
        "results": {"django:3.0": clean("django", "3.0")},
        "errors": [{"package": "flask:3.0", "error": "boom"}],
    }
    d = (await mcp_client.call_tool("scan_installed_packages", {})).structured_content
    assert d["unchecked"] == ["flask"]
    assert d["all_clear"] is False
    assert "1 package" in d["recommendation"]


def _make_venv(path):
    import subprocess
    import sys

    try:
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(path)], check=True)
    except (subprocess.CalledProcessError, OSError):
        pytest.skip("cannot create a venv here")
    sites = list(path.glob("lib/python*/site-packages")) or list(path.glob("Lib/site-packages"))
    if not sites:
        pytest.skip("unexpected venv layout")
    _add_dist(sites[0], "Foo_Bar", "1.0")
    return sites[0]


def _add_dist(site, name, version):
    dist = site / f"{name}-{version}.dist-info"
    dist.mkdir()
    (dist / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n")


@pytest.fixture
def no_subprocess(monkeypatch):
    """Call the returned function (after test setup) to fail on any process start."""
    import asyncio
    import subprocess

    def boom(*args, **kwargs):
        raise AssertionError("scan_installed_packages must not start a process")

    def arm():
        monkeypatch.setattr(asyncio, "create_subprocess_exec", boom)
        monkeypatch.setattr(asyncio, "create_subprocess_shell", boom)
        monkeypatch.setattr(subprocess, "Popen", boom)

    return arm


async def test_scan_reads_env_metadata_without_running_it(real, tmp_path, no_subprocess):
    _client, c, db = real
    venv = tmp_path / "env1"
    site = _make_venv(venv)
    _add_dist(site, "nameless", "1.0")
    (site / "nameless-1.0.dist-info" / "METADATA").write_text("Metadata-Version: 2.1\n")
    marker = tmp_path / "pth-ran"
    (site / "evil.pth").write_text(
        f"import pathlib; pathlib.Path({str(marker)!r}).write_text('x')\n"
    )
    db["foo-bar"] = [osv("F-1", "foo-bar")]
    no_subprocess()
    d = (
        await c.call_tool("scan_installed_packages", {"environment_path": str(venv)})
    ).structured_content
    assert d["environment_path"] == str(venv)
    assert d["packages_scanned"] == 1  # the entry without a Name is skipped
    assert [(v["package"], v["version"]) for v in d["vulnerable"]] == [("Foo_Bar", "1.0")]
    python = shlex.quote(
        str(
            next(
                p for p in (venv / "bin" / "python", venv / "Scripts" / "python.exe") if p.exists()
            )
        )
    )
    assert d["update_commands"] == [f"uv pip install --python {python} --upgrade Foo_Bar"]
    assert not marker.exists()


async def test_scan_suggests_pip_when_the_env_has_pip(real, tmp_path, no_subprocess):
    _client, c, db = real
    venv = tmp_path / "with pip"
    site = _make_venv(venv)
    (site / "pip").mkdir()
    db["foo-bar"] = [osv("F-1", "foo-bar")]
    no_subprocess()
    d = (
        await c.call_tool("scan_installed_packages", {"environment_path": str(venv)})
    ).structured_content
    (command,) = d["update_commands"]
    assert command.endswith(" -m pip install --upgrade Foo_Bar")
    assert command.startswith("'") and "with pip" in command  # shell-quoted path


async def test_scan_first_distribution_per_name_wins(real, tmp_path, no_subprocess):
    _client, c, _db = real
    venv = tmp_path / "env2"
    site = _make_venv(venv)
    _add_dist(site, "foo_bar", "0.5")  # a stale duplicate of Foo_Bar 1.0
    no_subprocess()
    d = (
        await c.call_tool("scan_installed_packages", {"environment_path": str(venv)})
    ).structured_content
    assert d["packages_scanned"] == 1


async def test_scan_rejects_directory_that_is_not_an_environment(real, tmp_path, no_subprocess):
    _client, c, _db = real
    fake = tmp_path / "not-a-venv"
    site = fake / "lib" / "python3.12" / "site-packages"
    site.mkdir(parents=True)
    (fake / "bin").mkdir()
    (fake / "bin" / "python").write_text("#!/bin/sh\n")
    _add_dist(site, "Foo_Bar", "1.0")
    no_subprocess()
    res = await c.call_tool(
        "scan_installed_packages", {"environment_path": str(fake)}, raise_on_error=False
    )
    assert res.is_error
    assert "not a Python environment" in res.content[0].text


async def test_scan_accepts_conda_environment(real, tmp_path, no_subprocess):
    _client, c, db = real
    env = tmp_path / "conda-env"
    (env / "conda-meta").mkdir(parents=True)
    site = env / "lib" / "python3.12" / "site-packages"
    site.mkdir(parents=True)
    _add_dist(site, "Foo_Bar", "1.0")
    db["foo-bar"] = [osv("F-1", "foo-bar")]
    no_subprocess()
    d = (
        await c.call_tool("scan_installed_packages", {"environment_path": str(env)})
    ).structured_content
    assert [v["package"] for v in d["vulnerable"]] == ["Foo_Bar"]


async def test_scan_autodetects_venv_in_cwd(real, tmp_path, monkeypatch, no_subprocess):
    _client, c, _db = real
    _make_venv(tmp_path / ".venv")
    monkeypatch.chdir(tmp_path)
    no_subprocess()
    d = (await c.call_tool("scan_installed_packages", {})).structured_content
    assert d["environment_path"] == str(tmp_path / ".venv")
    assert d["packages_scanned"] == 1


async def test_scan_ignores_cwd_dir_named_venv_without_pyvenv_cfg(
    fake_client, mcp_client, tmp_path, monkeypatch
):
    (tmp_path / ".venv" / "lib" / "python3.12" / "site-packages").mkdir(parents=True)
    (tmp_path / ".venv" / "bin").mkdir()
    (tmp_path / ".venv" / "bin" / "python").write_text("#!/bin/sh\necho '[]'\n")
    (tmp_path / ".venv" / "bin" / "python").chmod(0o755)
    monkeypatch.chdir(tmp_path)
    res = await mcp_client.call_tool("scan_installed_packages", {}, raise_on_error=False)
    assert res.is_error
    assert "environment_path" in res.content[0].text


async def test_scan_without_environment_requires_path(
    fake_client, mcp_client, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    res = await mcp_client.call_tool("scan_installed_packages", {}, raise_on_error=False)
    assert res.is_error
    assert "environment_path" in res.content[0].text
