"""Map core error dicts to agent-friendly ToolError messages."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any, cast

from fastmcp.exceptions import ToolError

from mcp_pypi.core import PyPIClient

logger = logging.getLogger("mcp-pypi.server")

_TRANSIENT = {"network_error", "timeout_error", "rate_limit_error"}
_FILE = {"file_error", "permission_error"}


def _message(error: dict, package: str | None, suggestions: Sequence[str]) -> str:
    code = str(error.get("code", "unknown_error"))
    message = str(error.get("message", ""))
    if code == "not_found":
        text = f"Package '{package}' not found on PyPI."
        if suggestions:
            text += f" Did you mean '{suggestions[0]}'?"
        return text + " Use search_packages to find the exact name."
    if code == "invalid_input":
        return f"Invalid input: {message}"
    if code in _TRANSIENT:
        service = "OSV" if "osv" in message.lower() else "PyPI"
        return f"{service} request failed ({code}); retry later."
    if code in _FILE:
        return f"Cannot read file: {message}"
    logger.warning("Unexpected core error (%s): %s", code, message)
    return f"Unexpected error ({code})"


def unwrap(
    result: Mapping[str, Any], *, package: str | None = None, suggestions: Sequence[str] = ()
) -> dict[str, Any]:
    """Return `result` unchanged, or raise ToolError if it is a core error."""
    error = result.get("error")
    if not error:
        return cast(dict[str, Any], result)
    raise ToolError(_message(error, package, suggestions))


async def checked(
    result: Mapping[str, Any], *, client: PyPIClient, package: str | None = None
) -> dict[str, Any]:
    """Like `unwrap`, adding "did you mean" suggestions for unknown packages."""
    error = result.get("error")
    suggestions: list[str] = []
    if error and error.get("code") == "not_found" and package:
        try:
            suggestions = list(await client.suggest_names(package))
        except Exception:  # suggestions are best-effort
            logger.debug("suggest_names failed", exc_info=True)
    return unwrap(result, package=package, suggestions=suggestions)


async def checked_release(
    result: Mapping[str, Any], *, client: PyPIClient, package: str, version: str | None
) -> dict[str, Any]:
    """Like `checked` for a version-specific lookup: a missing release of an existing
    package is reported as a missing version, not as a missing package."""
    error = result.get("error")
    if version and error and error.get("code") == "not_found":
        try:
            base = await client.get_package_info(package)
        except Exception:  # fall back to the package-not-found message
            logger.debug("package lookup for version error failed", exc_info=True)
            base = None
        if isinstance(base, dict) and not base.get("error"):
            info = base.get("info") or {}
            name = info.get("name") or package
            raise ToolError(
                f"Version '{version}' of '{name}' not found on PyPI "
                f"(latest is {info.get('version') or 'unknown'}). "
                "Use get_package_versions to list versions."
            )
    return await checked(result, client=client, package=package)


def item_error(result: dict) -> str | None:
    """Message for a failed batch item, or None if the item succeeded."""
    error = result.get("error")
    if not error:
        return None
    return _message(error, None, ())
