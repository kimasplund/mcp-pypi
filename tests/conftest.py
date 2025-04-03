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

# Docker fixtures
@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig):
    """Path to the docker-compose.yml file."""
    return str(pytestconfig.rootdir / "docker-compose.yml")

@pytest.fixture(scope="session")
def docker_services():
    """Mock for the docker_services fixture when pytest-docker is not available."""
    # This is a mock fixture that will be used when pytest-docker is not available
    # It's a no-op that simply returns a dictionary-like object
    class MockDockerServices:
        def start(self, service_name):
            """Mock the start method."""
            return True
    
    return MockDockerServices()

@pytest.fixture(scope="session")
def python_versions(docker_services):
    """Ensure all Python version services are running and responsive."""
    # List of service names from docker-compose.yml
    services = ["python-3.10", "python-3.11", "python-3.12", "python-3.13"]
    for service in services:
        docker_services.start(service)
    
    # Return the services for use in tests
    return services 