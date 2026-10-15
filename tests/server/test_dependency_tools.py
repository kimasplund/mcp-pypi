"""Tests for get_dependencies and check_packages."""

from typing import Any

NOT_FOUND = {"error": {"code": "not_found", "message": "gone"}}
NETWORK_ERROR = {"error": {"code": "network_error", "message": "PyPI unreachable"}}


def doc(version: str = "1.0", summary: str = "A package") -> dict[str, Any]:
    return {"info": {"version": version, "summary": summary}}


def dep(name: str, spec: str = "", extras=None, marker=None) -> dict[str, Any]:
    return {"name": name, "version_spec": spec, "extras": extras or [], "marker": marker}


TREE = {
    "tree": {
        "name": "flask",
        "version": "3.0",
        "dependencies": [
            {
                "name": "werkzeug",
                "version": "3.0.1",
                "dependencies": [
                    {"name": "flask", "version": "3.0", "cycle": True, "dependencies": []}
                ],
            }
        ],
    },
    "flat_list": ["flask (3.0)", "werkzeug (3.0.1)"],
}


async def test_get_dependencies_direct(fake_client, mcp_client):
    fake_client.get_dependencies.return_value = {
        "dependencies": [dep("werkzeug", ">=3.0", marker='extra == "async"'), dep("click", ">=8")]
    }
    res = await mcp_client.call_tool("get_dependencies", {"package_name": "flask"})
    d = res.structured_content
    assert d["depth"] == 1
    assert d["tree"] is None
    assert d["dependencies"][0] == {
        "name": "werkzeug",
        "specifier": ">=3.0",
        "extras": [],
        "marker": 'extra == "async"',
    }
    fake_client.get_dependency_tree.assert_not_called()


async def test_get_dependencies_tree_when_depth_gt_1(fake_client, mcp_client):
    fake_client.get_dependencies.return_value = {"dependencies": [dep("werkzeug")]}
    fake_client.get_dependency_tree.return_value = TREE
    res = await mcp_client.call_tool("get_dependencies", {"package_name": "flask", "depth": 3})
    d = res.structured_content
    assert d["depth"] == 3
    assert d["version"] == "3.0"
    werkzeug = d["tree"]["dependencies"][0]
    assert werkzeug["name"] == "werkzeug"
    assert werkzeug["dependencies"][0]["cycle"] is True
    fake_client.get_dependency_tree.assert_awaited_once_with("flask", None, 3)


async def test_depth_clamped_to_5(fake_client, mcp_client):
    fake_client.get_dependencies.return_value = {"dependencies": []}
    fake_client.get_dependency_tree.return_value = TREE
    res = await mcp_client.call_tool("get_dependencies", {"package_name": "flask", "depth": 99})
    assert res.structured_content["depth"] == 5
    fake_client.get_dependency_tree.assert_awaited_once_with("flask", None, 5)
    res = await mcp_client.call_tool("get_dependencies", {"package_name": "flask", "depth": -4})
    assert res.structured_content["depth"] == 1


async def test_get_dependencies_not_found(fake_client, mcp_client):
    fake_client.get_dependencies.return_value = NOT_FOUND
    res = await mcp_client.call_tool(
        "get_dependencies", {"package_name": "nope"}, raise_on_error=False
    )
    assert res.is_error
    assert "not found" in res.content[0].text


async def test_dependency_node_output_schema_is_recursive(mcp_client):
    tool = next(t for t in await mcp_client.list_tools() if t.name == "get_dependencies")
    assert "DependencyNode" in str(tool.output_schema)


async def test_check_packages_normalizes_and_dedupes(fake_client, mcp_client):
    async def info(name, version=None):
        return NOT_FOUND if name == "nope-xyz" else doc()

    fake_client.get_package_info.side_effect = info
    names = ["Django", "django", "typing_extensions", "nope-xyz"]
    res = await mcp_client.call_tool("check_packages", {"names": names})
    d = res.structured_content
    assert d["total"] == 3
    assert [r["name"] for r in d["results"]] == ["Django", "typing_extensions", "nope-xyz"]
    assert d["missing"] == ["nope-xyz"]
    assert d["results"][1]["normalized_name"] == "typing-extensions"
    assert d["results"][2]["exists"] is False
    assert d["results"][2]["error"] is None
    assert d["results"][0]["latest_version"] == "1.0"


async def test_check_packages_partial_failure_is_per_item(fake_client, mcp_client):
    async def info(name, version=None):
        return NETWORK_ERROR if name == "flaky" else doc()

    fake_client.get_package_info.side_effect = info
    res = await mcp_client.call_tool(
        "check_packages", {"names": ["a", "flaky", "b"]}, raise_on_error=False
    )
    assert not res.is_error
    d = res.structured_content
    flaky = d["results"][1]
    assert flaky["exists"] is False
    assert "retry later" in flaky["error"]
    assert d["missing"] == []
    assert d["results"][0]["exists"] and d["results"][2]["exists"]


async def test_check_packages_rejects_over_100(mcp_client):
    res = await mcp_client.call_tool(
        "check_packages", {"names": [f"p{i}" for i in range(101)]}, raise_on_error=False
    )
    assert res.is_error
    assert "Invalid input: at most 100 names per call" in res.content[0].text


async def test_progress_reported(fake_client, mcp_client):
    fake_client.get_package_info.return_value = doc()
    calls: list[tuple[float, float | None]] = []

    async def handler(progress, total, message):
        calls.append((progress, total))

    await mcp_client.call_tool(
        "check_packages", {"names": ["a", "b", "c"]}, progress_handler=handler
    )
    assert calls
    assert calls[-1] == (3, 3)


async def test_get_dependencies_unknown_version_names_the_version(fake_client, mcp_client):
    fake_client.get_dependencies.return_value = NOT_FOUND
    fake_client.get_package_info.return_value = {"info": {"name": "requests", "version": "2.32.3"}}
    res = await mcp_client.call_tool(
        "get_dependencies",
        {"package_name": "requests", "version": "99.0.0", "depth": 2},
        raise_on_error=False,
    )
    assert res.is_error
    assert res.content[0].text == (
        "Version '99.0.0' of 'requests' not found on PyPI (latest is 2.32.3). "
        "Use get_package_versions to list versions."
    )
    fake_client.get_dependency_tree.assert_not_called()


async def test_get_dependencies_unknown_package_with_version_keeps_package_message(
    fake_client, mcp_client
):
    fake_client.get_dependencies.return_value = NOT_FOUND
    fake_client.get_package_info.return_value = NOT_FOUND
    res = await mcp_client.call_tool(
        "get_dependencies", {"package_name": "nope", "version": "1.0"}, raise_on_error=False
    )
    assert res.is_error
    assert res.content[0].text.startswith("Package 'nope' not found on PyPI.")


async def test_get_dependency_tree_unknown_version_names_the_version(fake_client, mcp_client):
    fake_client.get_dependencies.return_value = {"dependencies": []}
    fake_client.get_dependency_tree.return_value = NOT_FOUND
    fake_client.get_package_info.return_value = {"info": {"name": "requests", "version": "2.32.3"}}
    res = await mcp_client.call_tool(
        "get_dependencies",
        {"package_name": "requests", "version": "99.0.0", "depth": 2},
        raise_on_error=False,
    )
    assert res.is_error
    assert res.content[0].text.startswith("Version '99.0.0' of 'requests' not found on PyPI")
