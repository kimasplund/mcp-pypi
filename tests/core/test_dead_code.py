"""Removed code must stay removed."""

import mcp_pypi.utils.validation as validation
from mcp_pypi.core import PyPIClient
from mcp_pypi.core.models import DependencyTreeResult


def test_no_plotly_visualization():
    assert not hasattr(PyPIClient, "_check_import")
    assert "_has_plotly" not in PyPIClient.__annotations__
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
