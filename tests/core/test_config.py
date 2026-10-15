"""Configuration defaults."""

import platformdirs

from mcp_pypi.core.models import PyPIClientConfig


def test_default_cache_dir_is_per_user(monkeypatch):
    monkeypatch.delenv("PYPI_CACHE_DIR", raising=False)
    expected = platformdirs.user_cache_dir("mcp-pypi", appauthor=False)
    assert PyPIClientConfig().cache_dir == expected
    assert "pypi_mcp_cache" not in expected


def test_cache_dir_env_and_argument_override(monkeypatch, tmp_path):
    monkeypatch.setenv("PYPI_CACHE_DIR", str(tmp_path / "env"))
    assert PyPIClientConfig().cache_dir == str(tmp_path / "env")
    assert PyPIClientConfig(cache_dir=str(tmp_path / "arg")).cache_dir == str(tmp_path / "arg")
