"""Tests for check_vulnerabilities and scan_installed_packages."""

import json
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


def clean(name: str, version: str) -> dict[str, Any]:
    return {"package": name, "version": version, "vulnerabilities": [], "vulnerable": False}


def dirty(name: str, version: str, *vulns) -> dict[str, Any]:
    return {"package": name, "version": version, "vulnerabilities": list(vulns), "vulnerable": True}


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
    res = await mcp_client.call_tool(
        "check_vulnerabilities", {"packages": ["nope"]}, raise_on_error=False
    )
    assert not res.is_error
    assert "'nope' not found" in res.structured_content["results"][0]["error"]


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
    seen: list[str] = []

    async def fake(pip_cmd):
        seen.append(pip_cmd)
        return [{"name": "django", "version": "3.0"}, {"name": "flask", "version": "3.0"}]

    monkeypatch.setattr(security, "_pip_list", fake)
    return seen


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


async def test_pip_list_failure_and_timeout(monkeypatch, tmp_path):
    from fastmcp.exceptions import ToolError

    monkeypatch.setattr(security, "PIP_TIMEOUT", 0.2)
    slow = tmp_path / "slow-pip"
    slow.write_text("#!/bin/sh\nexec sleep 5\n")
    slow.chmod(0o755)
    with pytest.raises(ToolError, match="Cannot run pip"):
        await security._pip_list("/nonexistent/pip-xyz")
    with pytest.raises(ToolError, match="timed out"):
        await security._pip_list(str(slow))
