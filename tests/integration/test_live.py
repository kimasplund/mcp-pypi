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
