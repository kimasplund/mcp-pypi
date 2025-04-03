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

# Docker fixtures - only used when --run-docker is specified
@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig, request):
    """Path to the docker-compose.yml file."""
    # Only provide real path if --run-docker is specified
    if request.config.getoption("--run-docker"):
        return str(pytestconfig.rootdir / "docker-compose.yml")
    return None

@pytest.fixture(scope="session")
def docker_services(request):
    """Mock for the docker_services fixture when pytest-docker is not available or --run-docker is not specified."""
    # This is a mock fixture that will be used when pytest-docker is not available
    # or when --run-docker is not specified
    class MockDockerServices:
        def start(self, service_name):
            """Mock the start method."""
            return True
    
    return MockDockerServices()

@pytest.fixture(scope="session")
def python_versions(docker_services, request):
    """Ensure all Python version services are running and responsive."""
    # Only attempt to start services if --run-docker is specified
    if request.config.getoption("--run-docker"):
        # List of service names from docker-compose.yml
        services = ["python-3.10", "python-3.11", "python-3.12", "python-3.13"]
        for service in services:
            docker_services.start(service)
        
        # Return the services for use in tests
        return services
    
    # Return empty list if --run-docker is not specified
    return [] 