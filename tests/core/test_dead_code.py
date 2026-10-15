"""Removed code must stay removed."""

from unittest.mock import MagicMock

import mcp_pypi.utils.validation as validation
from mcp_pypi.core import PyPIClient
from mcp_pypi.core.dependency_ops import DependencyOpsMixin
from mcp_pypi.core.models import DependencyTreeResult, PyPIClientConfig


def test_no_plotly_visualization(tmp_path):
    client = PyPIClient(
        config=PyPIClientConfig(cache_dir=str(tmp_path)),
        http_client=MagicMock(),
        cache_manager=MagicMock(),
        stats_service=MagicMock(),
    )
    assert not hasattr(client, "_has_plotly")
    assert not hasattr(PyPIClient, "_check_import")
    assert "_has_plotly" not in DependencyOpsMixin.__annotations__
    assert "visualization_url" not in DependencyTreeResult.__annotations__


def test_validation_has_no_dead_or_non_normalizing_helpers():
    for name in (
        "validate_pagination",
        "validate_depth",
        "make_error_response",
        "sanitize_package_name",
        "sanitize_version",
    ):
        assert not hasattr(validation, name), name
