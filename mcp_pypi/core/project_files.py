"""Framework-free discovery and parsing of Python dependency files.

Everything here is pure: files are read as text and parsed, never executed.
"""

from __future__ import annotations

import configparser
import json
import os
import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet

from mcp_pypi.core.search_index import normalize

_SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        "site-packages",
        "build",
        "dist",
        ".tox",
        ".nox",
        ".mypy_cache",
    }
)

_FIXED_KINDS = {
    "pyproject.toml": "pyproject",
    "setup.py": "setup.py",
    "setup.cfg": "setup.cfg",
    "pipfile": "pipfile",
    "pipfile.lock": "pipfile.lock",
    "poetry.lock": "poetry.lock",
    "environment.yml": "conda",
    "environment.yaml": "conda",
}


@dataclass(frozen=True)
class DeclaredDependency:
    name: str
    specifier: str
    source: str
    group: str | None = None

    @property
    def normalized_name(self) -> str:
        return normalize(self.name)

    @property
    def pinned_version(self) -> str | None:
        """The version when the specifier is exactly one ==X / ===X clause."""
        try:
            specs = list(SpecifierSet(self.specifier))
        except InvalidSpecifier:
            return None
        if len(specs) != 1 or specs[0].operator not in ("==", "==="):
            return None
        version = specs[0].version
        return None if "*" in version else version


class _ShapeError(ValueError):
    """A document has an unexpected structure."""


def _dict_or_empty(value: Any, what: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise _ShapeError(f"expected {what} to be a table, got {type(value).__name__}")
    return value


class DependencyFileError(Exception):
    def __init__(self, path: Path, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path
        self.message = message


def floor_version(specifier: str) -> str | None:
    """Lowest version allowed by the first ==, ===, >=, ~= or > clause."""
    for clause in specifier.split(","):
        m = re.match(r"\s*(===|==|>=|~=|>)\s*([^\s,;]+)", clause)
        if m:
            return m.group(2).rstrip(".*") if m.group(1).startswith("==") else m.group(2)
    return None


def file_kind(path: Path) -> str:
    name = path.name.lower()
    if name in _FIXED_KINDS:
        return _FIXED_KINDS[name]
    if re.fullmatch(r"(requirements|constraints).*\.txt", name):
        return "requirements"
    raise ValueError(f"Not a recognised dependency file: {path}")


def discover_dependency_files(root: Path, max_files: int = 50, max_depth: int = 4) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        depth = len(current.relative_to(root).parts)
        dirnames[:] = sorted(
            d
            for d in dirnames
            if d not in _SKIP_DIRS
            and not d.startswith(".")
            and depth < max_depth
            and not (current / d).is_symlink()
        )
        for fname in sorted(filenames):
            try:
                file_kind(Path(fname))
            except ValueError:
                continue
            found.append(current / fname)
            if len(found) >= max_files:
                return sorted(found)
    return sorted(found)


# --- requirement strings -----------------------------------------------------


def _parse_requirement(
    line: str, source: str, group: str | None = None
) -> DeclaredDependency | None:
    line = line.strip()
    if not line or line.startswith(("#", "-")):
        return None
    line = re.split(r"\s+#|\s+--", line)[0].strip()
    if re.match(r"[^<>=!~]*://", line):
        return None
    try:
        req = Requirement(line)
    except InvalidRequirement:
        return None
    if req.url:
        return None
    return DeclaredDependency(req.name, str(req.specifier), source, group)


def _requirement_list(
    items: Any, source: str, group: str | None = None
) -> list[DeclaredDependency]:
    if not isinstance(items, list):
        return []
    deps = (_parse_requirement(i, source, group) for i in items if isinstance(i, str))
    return [d for d in deps if d]


def _parse_requirements(text: str, source: str) -> list[DeclaredDependency]:
    # Join pip-compile style backslash continuations (`pkg==1 \` + `--hash=...`).
    joined = re.sub(r"\\[ \t]*\r?\n", " ", text)
    return _requirement_list(joined.splitlines(), source)


# --- pyproject.toml ----------------------------------------------------------


def _poetry_specifier(value: str) -> str | None:
    value = value.strip()
    if value in ("", "*"):
        return ""
    if value[0] in "^~" and re.fullmatch(r"[\^~]\d+(\.\d+)*", value):
        return f">={value[1:]}"
    if re.fullmatch(r"\d+(\.\d+)*", value):
        return f"=={value}"
    try:
        return str(SpecifierSet(value))
    except InvalidSpecifier:
        return None


def _poetry_deps(table: Any, source: str, group: str | None) -> list[DeclaredDependency]:
    deps: list[DeclaredDependency] = []
    if not isinstance(table, dict):
        return deps
    for name, value in table.items():
        if name.lower() == "python":
            continue
        if isinstance(value, dict):
            if any(k in value for k in ("git", "path", "url")):
                continue
            value = value.get("version", "*")
        if not isinstance(value, str):
            deps.append(DeclaredDependency(name, "", source, group))
            continue
        spec = _poetry_specifier(value)
        deps.append(DeclaredDependency(name, spec or "", source, group))
    return deps


def _parse_pyproject(text: str, source: str) -> list[DeclaredDependency]:
    data = tomllib.loads(text)
    deps: list[DeclaredDependency] = []
    project = _dict_or_empty(data.get("project"), "[project]")
    deps += _requirement_list(project.get("dependencies"), source)
    optional = project.get("optional-dependencies", {})
    if isinstance(optional, dict):
        for extra, items in optional.items():
            deps += _requirement_list(items, source, f"optional:{extra}")
    tool = _dict_or_empty(data.get("tool"), "[tool]")
    poetry = _dict_or_empty(tool.get("poetry"), "[tool.poetry]")
    deps += _poetry_deps(poetry.get("dependencies"), source, None)
    groups = poetry.get("group", {})
    if isinstance(groups, dict):
        for gname, g in groups.items():
            if isinstance(g, dict):
                deps += _poetry_deps(g.get("dependencies"), source, f"poetry:{gname}")
    return deps


# --- setup.py / setup.cfg ----------------------------------------------------

_STRING_OR_SEP = re.compile(r"""\s*(?:\#[^\n]*|"((?:[^"\\\n]|\\.)*)"|'((?:[^'\\\n]|\\.)*)'|,)""")


def _parse_setup_py(text: str, source: str) -> list[DeclaredDependency]:
    m = re.search(r"install_requires\s*=\s*[\[(]", text)
    if not m:
        return []
    items: list[str] = []
    pos = m.end()
    while (tok := _STRING_OR_SEP.match(text, pos)) is not None:
        literal = tok.group(1) if tok.group(1) is not None else tok.group(2)
        if literal is not None:
            items.append(literal)
        pos = tok.end()
    return _requirement_list(items, source)


def _parse_setup_cfg(text: str, source: str) -> list[DeclaredDependency]:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(text)
    raw = parser.get("options", "install_requires", fallback="")
    return _requirement_list(raw.splitlines(), source)


# --- Pipfile / Pipfile.lock / poetry.lock ------------------------------------


def _parse_pipfile(text: str, source: str) -> list[DeclaredDependency]:
    data = _dict_or_empty(tomllib.loads(text), "Pipfile")
    deps: list[DeclaredDependency] = []
    for section, group in (("packages", None), ("dev-packages", "dev")):
        table = data.get(section, {})
        if not isinstance(table, dict):
            continue
        for name, value in table.items():
            if isinstance(value, dict):
                if any(k in value for k in ("git", "path", "file", "url")):
                    continue
                value = value.get("version", "*")
            if not isinstance(value, str):
                continue
            spec = "" if value.strip() == "*" else value.strip()
            deps.append(DeclaredDependency(name, spec, source, group))
    return deps


def _parse_pipfile_lock(text: str, source: str) -> list[DeclaredDependency]:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise _ShapeError("expected a JSON object at top level")
    deps: list[DeclaredDependency] = []
    for section, group in (("default", None), ("develop", "dev")):
        table = data.get(section, {})
        if not isinstance(table, dict):
            continue
        for name, value in table.items():
            version = value.get("version") if isinstance(value, dict) else None
            if isinstance(version, str) and version:
                deps.append(
                    DeclaredDependency(name, f"=={version.removeprefix('==')}", source, group)
                )
    return deps


def _parse_poetry_lock(text: str, source: str) -> list[DeclaredDependency]:
    data = tomllib.loads(text)
    return [
        DeclaredDependency(p["name"], f"=={p['version']}", source)
        for p in data.get("package", [])
        if isinstance(p, dict) and "name" in p and "version" in p
    ]


# --- conda -------------------------------------------------------------------


def _parse_conda(text: str, source: str) -> list[DeclaredDependency]:
    """Line-based scan of the `- pip:` block (no YAML dependency)."""
    items: list[str] = []
    dash_indent: int | None = None
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        if dash_indent is None:
            if re.fullmatch(r"-\s*pip\s*:", stripped):
                dash_indent = indent
            continue
        if indent <= dash_indent:
            dash_indent = indent if re.fullmatch(r"-\s*pip\s*:", stripped) else None
            continue
        if stripped.startswith("-"):
            items.append(stripped[1:].strip().strip("'\""))
    return _requirement_list(items, source)


# --- dispatch ----------------------------------------------------------------

_PARSERS: dict[str, Callable[[str, str], list[DeclaredDependency]]] = {
    "requirements": _parse_requirements,
    "pyproject": _parse_pyproject,
    "setup.py": _parse_setup_py,
    "setup.cfg": _parse_setup_cfg,
    "pipfile": _parse_pipfile,
    "pipfile.lock": _parse_pipfile_lock,
    "poetry.lock": _parse_poetry_lock,
    "conda": _parse_conda,
}


def parse_dependency_file(path: Path) -> list[DeclaredDependency]:
    try:
        kind = file_kind(path)
    except ValueError as exc:
        raise DependencyFileError(path, str(exc)) from exc
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise DependencyFileError(path, f"cannot read file: {exc}") from exc
    try:
        return _PARSERS[kind](text, str(path))
    except (
        tomllib.TOMLDecodeError,
        json.JSONDecodeError,
        configparser.Error,
        _ShapeError,
    ) as exc:
        raise DependencyFileError(path, f"invalid {kind} file: {exc}") from exc
