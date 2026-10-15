"""Shared fixtures for the fastmcp 4 server tests."""

from collections.abc import AsyncIterator
from unittest.mock import create_autospec

import pytest
from fastmcp import Client

from mcp_pypi.core import PyPIClient
from mcp_pypi.server.app import build_server


@pytest.fixture
def fake_client():
    client = create_autospec(PyPIClient, instance=True)
    client.suggest_names.return_value = []
    return client


@pytest.fixture
async def mcp_client(fake_client) -> AsyncIterator[Client]:
    async with Client(build_server(client=fake_client)) as c:
        yield c


def _fake_osv_response(url: str, payload: dict, osv_db: dict[str, list]) -> dict:
    """Answer like the real OSV API: full records from /v1/query, ids only from querybatch."""
    if url.endswith("/querybatch"):
        return {
            "results": [
                {
                    "vulns": [
                        {"id": v["id"], "modified": "x"}
                        for v in osv_db.get(q["package"]["name"], [])
                    ]
                }
                for q in payload["queries"]
            ]
        }
    assert "version" not in payload["package"], "OSV ignores a version nested in package"
    return {"vulns": osv_db.get(payload["package"]["name"], [])}


@pytest.fixture
def fake_osv_response():
    """`(url, payload, osv_db) -> response` emulating OSV's real response shapes."""
    return _fake_osv_response
