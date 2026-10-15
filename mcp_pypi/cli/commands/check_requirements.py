"""The `check-requirements` command: a CLI view of the `audit_project` tool."""

import asyncio

import typer
from fastmcp.exceptions import ToolError
from rich.console import Console
from rich.table import Table

from mcp_pypi.cli.utils import get_config
from mcp_pypi.core import PyPIClient
from mcp_pypi.server.schemas import ProjectAudit
from mcp_pypi.server.tools.project import run_audit

console = Console()
stderr_console = Console(stderr=True)


def render_audit(audit: ProjectAudit) -> None:
    """Print an audit as one table per file with something to report."""
    totals = audit.totals
    for file in audit.files:
        if file.error:
            stderr_console.print(f"[red]{file.path}: {file.error}[/red]")
            continue
        if not file.dependencies:
            continue
        table = Table(
            "Package",
            "Specifier",
            "Checked",
            "Latest",
            "Status",
            title=f"{file.path} ({file.kind})",
            title_style="bold magenta",
            header_style="bold blue",
        )
        for dep in file.dependencies:
            if dep.error:
                status = f"[yellow]unchecked: {dep.error}[/yellow]"
            elif dep.vulnerable:
                status = f"[bold red]{len(dep.vulnerabilities)} vulnerabilities[/bold red]"
            elif dep.outdated:
                status = "[yellow]outdated[/yellow]"
            else:
                status = "[green]ok[/green]"
            table.add_row(
                dep.name,
                dep.specifier,
                dep.checked_version or "-",
                dep.latest_version or "-",
                status,
            )
        console.print(table)
    for warning in audit.consistency_warnings:
        console.print(f"[yellow]Inconsistent constraints for {warning.package}:[/yellow]")
        for path, spec in warning.specifiers.items():
            console.print(f"  {path}: {spec}")
    for rec in audit.recommendations:
        console.print(f"* {rec}")
    colour = "red" if totals.vulnerable else "green"
    console.print(
        f"\n[{colour}]{totals.files} files, {totals.dependencies} dependencies: "
        f"{totals.vulnerable} vulnerable, {totals.outdated} outdated, "
        f"{totals.unchecked} unchecked[/{colour}]"
    )


def check_requirements(
    path: str = typer.Argument(
        ..., help="Dependency file or project directory (requirements, pyproject, setup, ...)"
    ),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table or json"),
    full: bool = typer.Option(False, "--full", help="List clean dependencies too"),
) -> None:
    """Audit a project's dependency files for vulnerabilities and outdated pins.

    Exits 1 when any dependency has a known vulnerability, 2 on an error.
    """
    if format not in ("table", "json"):
        raise typer.BadParameter("use 'table' or 'json'", param_hint="--format")

    async def run() -> ProjectAudit:
        client = PyPIClient(get_config())
        try:
            return await run_audit(client, path, "full" if full else "summary")
        finally:
            await client.close()

    try:
        audit = asyncio.run(run())
    except ToolError as exc:
        stderr_console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(2) from exc

    if format == "json":
        print(audit.model_dump_json(indent=2))
    else:
        render_audit(audit)
    raise typer.Exit(1 if audit.totals.vulnerable else 0)
