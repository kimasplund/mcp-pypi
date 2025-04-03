"""Pytest configuration for MCP-PyPI tests."""

import os
import sys
import pytest

def pytest_addoption(parser):
    """Add command line options to pytest."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests",
    )
    parser.addoption(
        "--run-docker",
        action="store_true",
        default=False,
        help="Run tests in Docker containers with multiple Python versions",
    )

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "docker: mark test to run with Docker")

def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless --run-integration is specified.
    Skip docker tests unless --run-docker is specified."""
    # Handle integration tests
    if not config.getoption("--run-integration"):
        skip_integration = pytest.mark.skip(reason="Needs --run-integration option to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)
    
    # Handle docker tests
    if not config.getoption("--run-docker"):
        skip_docker = pytest.mark.skip(reason="Needs --run-docker option to run")
        for item in items:
            if "docker" in item.keywords:
                item.add_marker(skip_docker)

# Simplified Docker fixtures for CI
@pytest.fixture(scope="session")
def docker_compose_file():
    """Return None to disable Docker Compose usage."""
    return None

@pytest.fixture(scope="session")
def docker_services():
    """Mock Docker services fixture."""
    class MockDockerServices:
        def start(self, service_name):
            """Mock the start method."""
            return True
    return MockDockerServices()

@pytest.fixture(scope="session")
def python_versions():
    """Return empty list to disable Python version services."""
    return [] 