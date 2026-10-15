"""Tests for the check-requirements command (a CLI view of audit_project)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp.exceptions import ToolError
from typer.testing import CliRunner

from mcp_pypi.cli.main import app
from mcp_pypi.server.schemas import (
    AuditedDependency,
    AuditedFile,
    AuditTotals,
    ProjectAudit,
    VulnerabilityItem,
)

runner = CliRunner()


def audit(vulnerable: bool) -> ProjectAudit:
    dep = AuditedDependency(
        name="jinja2",
        specifier="==2.4.1",
        checked_version="2.4.1",
        latest_version="3.1.4",
        outdated=True,
        vulnerable=vulnerable,
        vulnerabilities=[VulnerabilityItem(id="PYSEC-1")] if vulnerable else [],
    )
    return ProjectAudit(
        path="requirements.txt",
        files=[AuditedFile(path="requirements.txt", kind="requirements", dependencies=[dep])],
        totals=AuditTotals(
            files=1, dependencies=1, vulnerable=int(vulnerable), outdated=1, vulnerabilities=1
        ),
        summary="s",
    )


@pytest.fixture
def patched():
    client = MagicMock()
    client.close = AsyncMock()
    with patch("mcp_pypi.cli.commands.check_requirements.PyPIClient", return_value=client):
        yield client


def test_vulnerable_exits_1_and_renders_table(patched):
    with patch(
        "mcp_pypi.cli.commands.check_requirements.run_audit", AsyncMock(return_value=audit(True))
    ) as run:
        result = runner.invoke(app, ["check-requirements", "requirements.txt"])
    assert result.exit_code == 1
    assert "jinja2" in result.output
    assert "1 vulnerability" in result.output
    run.assert_awaited_once_with(patched, "requirements.txt", "summary")
    patched.close.assert_awaited_once()


def test_clean_exits_0(patched):
    with patch(
        "mcp_pypi.cli.commands.check_requirements.run_audit", AsyncMock(return_value=audit(False))
    ):
        result = runner.invoke(app, ["check-requirements", "requirements.txt"])
    assert result.exit_code == 0
    assert "outdated" in result.output


def test_json_format(patched):
    with patch(
        "mcp_pypi.cli.commands.check_requirements.run_audit", AsyncMock(return_value=audit(False))
    ):
        result = runner.invoke(app, ["check-requirements", "requirements.txt", "-f", "json"])
    assert result.exit_code == 0
    assert json.loads(result.output)["totals"]["dependencies"] == 1


def test_tool_error_exits_2(patched):
    with patch(
        "mcp_pypi.cli.commands.check_requirements.run_audit",
        AsyncMock(side_effect=ToolError("Invalid input: no dependency files found")),
    ):
        result = runner.invoke(app, ["check-requirements", "nowhere"])
    assert result.exit_code == 2
    assert "no dependency files found" in result.output
    patched.close.assert_awaited_once()


def test_markup_in_paths_and_errors_is_escaped(patched):
    dep = AuditedDependency(name="x", error="bad [/tool.poetry] table", checked_version=None)
    bracketed = "proj/[slug]/requirements.txt"
    audit_ = ProjectAudit(
        path=bracketed,
        files=[
            AuditedFile(path=bracketed, kind="requirements", dependencies=[dep]),
            AuditedFile(path="p/[/oops]/pyproject.toml", kind="pyproject", error="[/tool.poetry]"),
        ],
        totals=AuditTotals(files=2, dependencies=1, unchecked=1),
        summary="s",
    )
    with patch(
        "mcp_pypi.cli.commands.check_requirements.run_audit", AsyncMock(return_value=audit_)
    ):
        result = runner.invoke(app, ["check-requirements", bracketed])
    assert result.exit_code == 0, result.output
    assert "[slug]" in result.output
    assert "[/tool.poetry]" in result.output


def test_true_vulnerability_total_is_shown(patched):
    dep = AuditedDependency(
        name="jinja2",
        checked_version="2.4.1",
        vulnerable=True,
        total_vulnerabilities=120,
        vulnerabilities_truncated=True,
        vulnerabilities=[VulnerabilityItem(id=f"V-{i}") for i in range(20)],
    )
    audit_ = ProjectAudit(
        path="r.txt",
        files=[AuditedFile(path="r.txt", kind="requirements", dependencies=[dep])],
        totals=AuditTotals(files=1, dependencies=1, vulnerable=1, vulnerabilities=120),
        summary="s",
    )
    with patch(
        "mcp_pypi.cli.commands.check_requirements.run_audit", AsyncMock(return_value=audit_)
    ):
        result = runner.invoke(app, ["check-requirements", "r.txt"])
    assert result.exit_code == 1
    assert "120 vulnerabilities" in result.output
