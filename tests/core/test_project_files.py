from pathlib import Path

import pytest

from mcp_pypi.core.project_files import (
    DeclaredDependency,
    DependencyFileError,
    discover_dependency_files,
    file_kind,
    floor_version,
    parse_dependency_file,
)

FIX = Path(__file__).parent.parent / "fixtures" / "projects"


def pairs(deps):
    return [(d.name, d.specifier) for d in deps]


def test_requirements_txt_real_world_lines(tmp_path):
    f = tmp_path / "requirements.txt"
    f.write_text(
        "requests[socks]==2.31.0\n"
        'Django>=4.2 ; python_version>"3.8"\n'
        "-e .\n-r other.txt\n--hash=sha256:abc\n"
        "git+https://github.com/x/y.git\n# comment\n\nnumpy\n"
    )
    assert pairs(parse_dependency_file(f)) == [
        ("requests", "==2.31.0"),
        ("Django", ">=4.2"),
        ("numpy", ""),
    ]


def test_pinned_and_floor_versions():
    assert DeclaredDependency("a", "==2.31.0", "x").pinned_version == "2.31.0"
    assert DeclaredDependency("a", "==2.*", "x").pinned_version is None
    assert DeclaredDependency("a", ">=1,<2", "x").pinned_version is None
    assert DeclaredDependency("A_b", "", "x").normalized_name == "a-b"
    assert floor_version(">=1.2,<2") == "1.2"
    assert floor_version("~=3.1") == "3.1"
    assert floor_version("<2") is None


def test_pyproject_project_and_optional_and_poetry_groups():
    deps = parse_dependency_file(FIX / "pyproject.toml")
    got = {(d.name, d.specifier, d.group) for d in deps}
    assert got == {
        ("requests", ">=2.31", None),
        ("Flask", "==3.0.0", None),
        ("pytest", ">=8", "optional:dev"),
        ("httpx", ">=0.27", None),
        ("rich", ">=13.7", None),
        ("anyio", "", None),
        ("hypothesis", "==6.100.0", "poetry:test"),
    }


def test_setup_cfg_install_requires():
    deps = parse_dependency_file(FIX / "setup.cfg")
    assert pairs(deps) == [("requests", ">=2.31"), ("click", "==8.1.7")]


def test_setup_py_is_not_executed():
    deps = parse_dependency_file(FIX / "setup.py")
    assert pairs(deps) == [("requests", ">=2.31"), ("numpy", "==1.26.4")]


def test_pipfile_and_lock():
    deps = parse_dependency_file(FIX / "Pipfile")
    assert {(d.name, d.specifier, d.group) for d in deps} == {
        ("requests", "", None),
        ("flask", "==3.0.0", None),
        ("pytest", ">=8", "dev"),
    }
    lock = parse_dependency_file(FIX / "Pipfile.lock")
    assert pairs(lock) == [("requests", "==2.31.0"), ("pytest", "==8.0.0")]


def test_poetry_lock():
    deps = parse_dependency_file(FIX / "poetry.lock")
    assert pairs(deps) == [("requests", "==2.31.0"), ("Flask", "==3.0.0")]


def test_conda_pip_section_only():
    deps = parse_dependency_file(FIX / "environment.yml")
    assert pairs(deps) == [("requests", "==2.31.0"), ("flask", ">=3.0")]


def test_invalid_toml_raises_dependency_file_error(tmp_path):
    f = tmp_path / "pyproject.toml"
    f.write_text("[project\nbroken")
    with pytest.raises(DependencyFileError) as exc:
        parse_dependency_file(f)
    assert exc.value.path == f


def test_file_kind():
    assert file_kind(Path("constraints-dev.txt")) == "requirements"
    assert file_kind(Path("sub/Pipfile.lock")) == "pipfile.lock"
    assert file_kind(Path("environment.yaml")) == "conda"


def test_discovery_skips_vendor_dirs_and_caps(tmp_path):
    for rel in (
        "requirements.txt",
        "sub/pyproject.toml",
        ".venv/requirements.txt",
        "node_modules/x/requirements.txt",
        "build/setup.py",
        "a/b/c/d/e/requirements.txt",
    ):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("")
    assert discover_dependency_files(tmp_path) == [
        tmp_path / "requirements.txt",
        tmp_path / "sub" / "pyproject.toml",
    ]
    assert len(discover_dependency_files(tmp_path, max_files=1)) == 1
