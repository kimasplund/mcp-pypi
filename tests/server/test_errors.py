"""Tests for typed core-error to ToolError mapping."""

import pytest
from fastmcp.exceptions import ToolError

from mcp_pypi.server.errors import checked, item_error, unwrap


def err(code: str, message: str = "boom") -> dict:
    return {"error": {"code": code, "message": message}}


def test_unwrap_passes_success_through():
    result = {"name": "requests"}
    assert unwrap(result) is result


def test_not_found_plain():
    with pytest.raises(ToolError) as exc:
        unwrap(err("not_found"), package="nopkg")
    assert str(exc.value) == (
        "Package 'nopkg' not found on PyPI. Use search_packages to find the exact name."
    )


def test_not_found_with_suggestion():
    with pytest.raises(ToolError) as exc:
        unwrap(err("not_found"), package="beautifulsoup", suggestions=["beautifulsoup4", "x"])
    assert str(exc.value) == (
        "Package 'beautifulsoup' not found on PyPI. Did you mean 'beautifulsoup4'? "
        "Use search_packages to find the exact name."
    )


def test_invalid_input():
    with pytest.raises(ToolError, match=r"^Invalid input: bad name$"):
        unwrap(err("invalid_input", "bad name"))


@pytest.mark.parametrize("code", ["network_error", "timeout_error", "rate_limit_error"])
def test_transient_errors_pypi(code):
    with pytest.raises(ToolError) as exc:
        unwrap(err(code, "connection reset"))
    assert str(exc.value) == f"PyPI request failed ({code}); retry later."


def test_transient_error_osv():
    with pytest.raises(ToolError) as exc:
        unwrap(err("network_error", "Error querying OSV API"))
    assert str(exc.value) == "OSV request failed (network_error); retry later."


@pytest.mark.parametrize("code", ["file_error", "permission_error"])
def test_file_errors(code):
    with pytest.raises(ToolError) as exc:
        unwrap(err(code, "no such file"))
    assert str(exc.value) == "Cannot read file: no such file"


def test_unexpected_error_logs_full_message(caplog):
    with caplog.at_level("WARNING"), pytest.raises(ToolError) as exc:
        unwrap(err("parse_error", "secret detail /x"))
    assert str(exc.value) == "Unexpected error (parse_error)"
    assert "secret detail /x" in caplog.text


async def test_checked_suggests_on_not_found(fake_client):
    fake_client.suggest_names.return_value = ["beautifulsoup4"]
    with pytest.raises(ToolError, match="Did you mean 'beautifulsoup4'"):
        await checked(err("not_found"), client=fake_client, package="beautifulsoup")
    fake_client.suggest_names.assert_awaited_once_with("beautifulsoup")


async def test_checked_only_suggests_on_not_found(fake_client):
    with pytest.raises(ToolError):
        await checked(err("network_error"), client=fake_client, package="requests")
    fake_client.suggest_names.assert_not_awaited()


async def test_checked_survives_suggest_failure(fake_client):
    fake_client.suggest_names.side_effect = RuntimeError("index down")
    with pytest.raises(ToolError, match="not found on PyPI"):
        await checked(err("not_found"), client=fake_client, package="x")


async def test_checked_passes_success_through(fake_client):
    result = {"ok": 1}
    assert await checked(result, client=fake_client, package="x") is result


def test_item_error_returns_message_or_none():
    assert item_error({"name": "x"}) is None
    msg = item_error(err("not_found"))
    assert msg is not None
    with pytest.raises(ToolError) as exc:
        unwrap(err("not_found"))
    assert msg == str(exc.value)
