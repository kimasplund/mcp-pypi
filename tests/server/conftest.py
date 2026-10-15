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
