"""Contract tests for the public tool surface."""

import pytest

EXPECTED_TOOLS = {
    "search_packages",
    "get_package",
    "get_package_versions",
    "compare_versions",
    "get_package_changelog",
    "get_download_stats",
    "get_dependencies",
    "check_packages",
    "check_vulnerabilities",
    "scan_installed_packages",
    "audit_project",
}

SINGLE_PACKAGE_TOOLS = [
    "get_package",
    "get_package_versions",
    "compare_versions",
    "get_package_changelog",
    "get_download_stats",
    "get_dependencies",
]


@pytest.fixture
async def tools(mcp_client):
    return {t.name: t for t in await mcp_client.list_tools()}


async def test_exact_tool_set(tools):
    assert set(tools) == EXPECTED_TOOLS
    assert len(tools) == 11


async def test_every_tool_has_title_annotations_schema(tools):
    for name, tool in tools.items():
        assert tool.title, name
        assert tool.annotations is not None, name
        assert tool.annotations.read_only_hint is True, name
        assert tool.annotations.idempotent_hint is True, name
        assert tool.annotations.open_world_hint is True, name
        assert tool.output_schema is not None, name


@pytest.mark.parametrize("name", SINGLE_PACKAGE_TOOLS)
async def test_single_package_param_named_package_name(tools, name):
    schema = tools[name].input_schema
    assert "package_name" in schema["properties"]
    assert "package_name" in schema["required"]


async def test_descriptions_short_and_no_shouting(tools):
    for name, tool in tools.items():
        description = tool.description or ""
        assert len(description) <= 1200, name
        assert "IMPORTANT" not in description, name
        assert "MUST" not in description, name
