"""Tests for the fastmcp 4 server factory."""

from mcp_pypi.server.app import build_server
from mcp_pypi.server.instructions import INSTRUCTIONS


def test_server_metadata(fake_client):
    server = build_server(client=fake_client)
    assert server.name == "mcp-pypi"
    assert server.version == "4.0.0"


async def test_resources_listed(mcp_client):
    uris = {str(r.uri) for r in await mcp_client.list_resources()}
    assert uris == {
        "pypi://recent-releases",
        "pypi://new-packages",
        "pypi://updated-packages",
    }


async def test_prompts_have_required_args(mcp_client):
    prompts = {p.name: p for p in await mcp_client.list_prompts()}
    for name, arg in [("analyze_dependencies", "package_name"), ("compare_packages", "packages")]:
        args = {a.name: a for a in prompts[name].arguments}
        assert args[arg].required
        assert prompts[name].title


async def test_prompt_mentions_tools(mcp_client):
    result = await mcp_client.get_prompt("analyze_dependencies", {"package_name": "requests"})
    text = result.messages[0].content.text
    assert "check_vulnerabilities" in text
    assert "requests" in text


async def test_lifespan_closes_client(fake_client):
    from fastmcp import Client

    async with Client(build_server(client=fake_client)):
        pass
    fake_client.close.assert_awaited()


async def test_unexpected_exception_is_masked(fake_client):
    from fastmcp import Client

    server = build_server(client=fake_client)

    @server.tool
    async def boom() -> str:
        raise RuntimeError("/secret/path")

    async with Client(server) as c:
        result = await c.call_tool("boom", {}, raise_on_error=False)
    assert result.is_error
    assert "/secret/path" not in str(result.content)


def test_instructions_cover_file_authority():
    assert "pyproject.toml" in INSTRUCTIONS
    assert "requirements" in INSTRUCTIONS
    assert len(INSTRUCTIONS.splitlines()) <= 40
    for tool in ("search_packages", "check_packages", "audit_project", "scan_installed_packages"):
        assert tool in INSTRUCTIONS
