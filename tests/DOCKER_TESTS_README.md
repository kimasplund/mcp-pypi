# Docker Tests

## Overview

This directory contains tests that verify compatibility across multiple Python versions (3.10, 3.11, 3.12, 3.13) using Docker containers. These tests are **for local development only** and are deliberately excluded from CI/CD pipelines.

## Why These Tests are Development-Only

1. **CI Performance**: Docker tests are slow and resource-intensive, making them impractical for CI/CD environments.
2. **Docker Dependencies**: CI environments may not have Docker available or properly configured.
3. **Local Verification**: These tests are meant for developers to verify cross-version compatibility before pushing code.

## Running Docker Tests

### Prerequisites

- Docker and Docker Compose installed and running
- Python development environment

### Installation

Install the Docker testing dependencies:

```bash
# Install the package with Docker testing dependencies
pip install -e ".[docker-test]"
```

### Running Tests

To run all Docker tests:

```bash
# Run all Docker tests
pytest tests/test_docker.py --run-docker
```

To run a specific Docker test:

```bash
# Run a specific test
pytest tests/test_docker.py::test_package_import --run-docker
```

## Test Coverage

The Docker tests verify:

1. **Basic Import**: The package can be imported in all supported Python versions
2. **CLI Functionality**: The command-line interface works properly
3. **PyPI Client**: The core client functionality works correctly
4. **MCP Server**: The server can be initialized and responds correctly
5. **Requirements Checking**: The requirements file checking functionality works for both `requirements.txt` and `pyproject.toml` formats

## Troubleshooting

If Docker tests are failing:

1. Make sure Docker and Docker Compose are running
2. Check that you have added the `--run-docker` flag
3. Verify that the Docker daemon has enough resources allocated
4. Try running one test at a time to isolate issues

## Notes for CI/CD

These tests are deliberately excluded from CI/CD pipelines to ensure fast and reliable builds. The `.github/workflows/pypi-publish.yml` file explicitly excludes these tests to prevent issues with Docker availability in CI environments. 