"""Live tests against PyPI and OSV; run with `-m integration`."""

import pytest
from fastmcp import Client

from mcp_pypi.server.app import build_server

pytestmark = pytest.mark.integration


@pytest.fixture
async def live():
    async with Client(build_server()) as client:
        yield client


async def test_search_httpx_first(live):
    result = await live.call_tool("search_packages", {"query": "httpx"})
    assert result.data.results[0].name.lower() == "httpx"


async def test_get_package_has_latest_version(live):
    result = await live.call_tool("get_package", {"package_name": "requests"})
    assert result.data.latest_version


async def test_check_vulnerabilities_reports_known_vuln(live):
    result = await live.call_tool("check_vulnerabilities", {"packages": ["jinja2==2.4.1"]})
    assert result.data.total_vulnerabilities >= 1


async def test_check_vulnerabilities_two_pins_each_vulnerable(live):
    """Two items take the batch path; each pin has known advisories."""
    result = await live.call_tool(
        "check_vulnerabilities", {"packages": ["jinja2==2.4.1", "django==3.2.5"]}
    )
    by_name = {r.package: r for r in result.data.results}
    assert by_name["jinja2"].vulnerable and by_name["jinja2"].total_vulnerabilities >= 1
    assert by_name["django"].vulnerable and by_name["django"].total_vulnerabilities >= 1
    assert result.data.vulnerable_packages == 2


async def test_audit_project_reports_vulnerable_pin(live, tmp_path):
    (tmp_path / "requirements.txt").write_text("django==3.2.5\n")
    result = await live.call_tool("audit_project", {"path": str(tmp_path)})
    (dep,) = result.data.files[0].dependencies
    assert dep.name == "django" and dep.vulnerable
    assert dep.total_vulnerabilities >= 1
    assert result.data.totals.vulnerable == 1
