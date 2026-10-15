"""Pytest configuration for MCP-PyPI tests."""

import pytest


def pytest_addoption(parser):
    """Add command line options to pytest."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests",
    )


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: mark test as an integration test")


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless --run-integration or `-m integration` is given."""
    # Handle integration tests
    selected = "integration" in (config.getoption("markexpr") or "").replace("not integration", "")
    if not (config.getoption("--run-integration") or selected):
        skip_integration = pytest.mark.skip(reason="Needs --run-integration option to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)
