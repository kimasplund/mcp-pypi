"""Tool registration modules for the MCP-PyPI server."""

# Shared MCP tool annotations: every tool is a read-only PyPI/OSV lookup.
TOOL_ANNOTATIONS: dict[str, bool] = {
    "readOnlyHint": True,
    "idempotentHint": True,
    "openWorldHint": True,
}

__all__ = ["TOOL_ANNOTATIONS"]
