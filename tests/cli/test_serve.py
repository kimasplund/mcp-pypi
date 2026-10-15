"""Tests for the serve/stdio commands."""

import sys
from unittest.mock import patch

from fastmcp import Client, FastMCP
from fastmcp.client.transports import StdioTransport
from typer.testing import CliRunner

from mcp_pypi.cli.main import app

runner = CliRunner()


def test_http_transport_runs_streamable_http():
    with patch.object(FastMCP, "run") as run:
        result = runner.invoke(app, ["serve", "--transport", "http", "--port", "9000"])
    assert result.exit_code == 0, result.output
    run.assert_called_once_with(transport="http", host="127.0.0.1", port=9000)


def test_stdio_default():
    with patch.object(FastMCP, "run") as run:
        result = runner.invoke(app, ["serve"])
    assert result.exit_code == 0, result.output
    run.assert_called_once_with(transport="stdio")


def test_stdio_alias():
    with patch.object(FastMCP, "run") as run:
        result = runner.invoke(app, ["stdio"])
    assert result.exit_code == 0, result.output
    run.assert_called_once_with(transport="stdio")


def test_sse_rejected():
    with patch.object(FastMCP, "run") as run:
        result = runner.invoke(app, ["serve", "--transport", "sse"])
    assert result.exit_code != 0
    run.assert_not_called()


def test_help_connecting_has_no_sse():
    for args in (["serve", "--help-connecting"], ["serve", "-t", "http", "--help-connecting"]):
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        assert "/sse" not in result.output
    http = runner.invoke(app, ["serve", "-t", "http", "--help-connecting"])
    assert "http://127.0.0.1:8143/mcp" in http.output
    stdio = runner.invoke(app, ["stdio", "--help-connecting"])
    assert "uvx mcp-pypi serve" in stdio.output


async def test_stdio_end_to_end_lists_tools():
    transport = StdioTransport(command=sys.executable, args=["-m", "mcp_pypi", "serve"])
    async with Client(transport) as client:
        tools = await client.list_tools()
    assert len(tools) == 11
