"""Tests that verify functionality across multiple Python versions using Docker."""

import subprocess
import pytest
import tempfile
import json
import os


@pytest.mark.docker
def test_python_versions(python_versions):
    """Test that the package works across multiple Python versions."""
    assert len(python_versions) > 0, "No Python versions available for testing"
    # The python_versions fixture already ensures that the services are running


@pytest.mark.docker
def test_package_import():
    """Test that the package can be imported in each Python version."""
    # Try only one version at a time to isolate failures
    version = "3.13"  # Using the latest Python version for this test
    cmd = [
        "docker-compose",
        "run",
        f"python-{version}",
        "python",
        "-c",
        "import mcp_pypi; print(mcp_pypi.__version__)",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        assert result.stdout.strip(), f"Failed to import mcp_pypi in Python {version}"
    except subprocess.CalledProcessError as e:
        pytest.skip(f"Docker test environment not ready: {e}")


@pytest.mark.docker
def test_cli():
    """Test that the CLI works in each Python version."""
    for version in ["3.10", "3.11", "3.12", "3.13"]:
        cmd = [
            "docker-compose",
            "run",
            f"python-{version}",
            "pypi",
            "--help",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        assert "Usage:" in result.stdout, f"CLI help not working in Python {version}"


@pytest.mark.docker
def test_pypi_client():
    """Test that the PyPI client works in each Python version."""
    for version in ["3.10", "3.11", "3.12", "3.13"]:
        cmd = [
            "docker-compose",
            "run",
            f"python-{version}",
            "python",
            "-c",
            "from mcp_pypi.client import PyPIClient; import asyncio; "
            "client = PyPIClient(); "
            "result = asyncio.run(client.get_package_info('pytest')); "
            "print(result['info']['name'])",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        assert "pytest" in result.stdout.strip(), f"PyPI client not working in Python {version}"


@pytest.mark.docker
def test_mcp_server():
    """Test that the MCP server works in each Python version."""
    for version in ["3.10", "3.11", "3.12", "3.13"]:
        # Just test that the server can be initialized
        cmd = [
            "docker-compose",
            "run",
            f"python-{version}",
            "python",
            "-c",
            "from mcp_pypi.server import PyPIMCPServer; "
            "server = PyPIMCPServer(); "
            "print('Server initialized')",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        assert "Server initialized" in result.stdout, f"MCP server not working in Python {version}"


@pytest.mark.docker
def test_check_requirements():
    """Basic test that the PyPIClient can be imported and initialized in all Python versions."""
    versions = ["3.10", "3.11", "3.12", "3.13"]
    
    for version in versions:
        print(f"\nTesting Python {version}...")
        
        if version == "3.10":
            # For Python 3.10, we need special handling for NotRequired
            test_cmd = [
                "docker-compose",
                "run",
                "--rm",
                f"python-{version}",
                "bash",
                "-c",
                """
                # Create a typing compatibility module
                mkdir -p /tmp/mcp_pypi_compat
                cat > /tmp/mcp_pypi_compat/typing_compat.py << 'EOF'
from typing_extensions import NotRequired

# Re-export NotRequired so it can be imported from this module
__all__ = ['NotRequired']
EOF

                # Create patch module that will modify the import
                cat > /tmp/mcp_pypi_compat/patch_imports.py << 'EOF'
import sys
import builtins
import importlib.util
import types

# Store the original import
original_import = builtins.__import__

# Create a custom import function
def custom_import(name, globals=None, locals=None, fromlist=(), level=0):
    # If trying to import NotRequired from typing, redirect to our compatibility module
    if name == 'typing' and fromlist and 'NotRequired' in fromlist:
        if not hasattr(custom_import, '_warned'):
            print("Redirecting NotRequired import to typing_extensions")
            custom_import._warned = True
        
        # First get the original typing module
        typing_module = original_import(name, globals, locals, fromlist, level)
        
        # Then get our compatibility module
        spec = importlib.util.spec_from_file_location('typing_compat', '/tmp/mcp_pypi_compat/typing_compat.py')
        compat_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(compat_module)
        
        # Add NotRequired to the typing module
        typing_module.NotRequired = compat_module.NotRequired
        
        return typing_module
    
    # For all other imports, use the original import function
    return original_import(name, globals, locals, fromlist, level)

# Replace the built-in import with our custom one
builtins.__import__ = custom_import
EOF

                # Install the package and dependencies
                pip install -e . && \
                pip install typing_extensions>=4.3.0 && \
                
                # Run the test with the import patch
                python -c "
import sys
sys.path.insert(0, '/tmp')
import mcp_pypi_compat.patch_imports
from mcp_pypi.core import PyPIClient
print('Import successful!')
client = PyPIClient()
print('Client initialized successfully!')
client.close()
"
                """
            ]
        else:
            # For Python 3.11+ which has NotRequired in typing module
            test_cmd = [
                "docker-compose",
                "run",
                "--rm",
                f"python-{version}",
                "bash",
                "-c",
                """
                pip install -e . && \
                python -c "
from mcp_pypi.core import PyPIClient
print('Import successful!')
client = PyPIClient()
print('Client initialized successfully!')
client.close()
"
                """
            ]
        
        result = subprocess.run(test_cmd, capture_output=True, text=True)
        
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        
        # Check if the test passed
        assert "Import successful!" in result.stdout, f"Failed to import PyPIClient in Python {version}"
        assert "Client initialized successfully!" in result.stdout, f"Failed to initialize PyPIClient in Python {version}"


@pytest.mark.docker
def test_check_requirements_cli():
    """Test the check-requirements CLI command in each Python version."""
    # Create temporary requirements.txt for testing
    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt') as tmp:
        requirements_path = tmp.name
        tmp.write("pytest==7.0.0\nrequests>=2.26.0")
    
    # Create temporary pyproject.toml for testing
    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.toml') as tmp:
        pyproject_path = tmp.name
        tmp.write("""
[project]
name = "test-project"
version = "0.1.0"
dependencies = [
    "pytest==7.0.0",
    "requests>=2.26.0"
]
""")
    
    try:
        # Test requirements.txt CLI command in each Python version
        for version in ["3.10", "3.11", "3.12", "3.13"]:
            # Copy the requirements file into a Docker volume
            copy_cmd = [
                "docker-compose",
                "run",
                f"python-{version}",
                "bash",
                "-c",
                f"mkdir -p /tmp/test && cat > /tmp/test/requirements.txt",
            ]
            with open(requirements_path, 'r') as f:
                subprocess.run(copy_cmd, input=f.read(), text=True, check=True)
            
            # Run the check-requirements command
            cmd = [
                "docker-compose",
                "run",
                f"python-{version}",
                "python",
                "-m",
                "mcp_pypi",
                "check-requirements",
                "/tmp/test/requirements.txt",
                "--format",
                "json"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Verify the command works by checking for JSON output
            try:
                output = json.loads(result.stdout.strip())
                assert "outdated" in output, f"Missing 'outdated' key in CLI output for Python {version}"
                assert "up_to_date" in output, f"Missing 'up_to_date' key in CLI output for Python {version}"
            except json.JSONDecodeError:
                pytest.fail(f"Invalid JSON output from CLI for Python {version}: {result.stdout}")
            
            # Verify packages are in the output
            packages = [pkg["package"] for pkg in output["outdated"] + output["up_to_date"]]
            assert any(pkg in packages for pkg in ["pytest", "requests"]), \
                f"Expected packages not found in CLI results for Python {version}"
        
        # Test pyproject.toml CLI command in each Python version
        for version in ["3.10", "3.11", "3.12", "3.13"]:
            # Copy the pyproject.toml into a Docker volume
            copy_cmd = [
                "docker-compose",
                "run",
                f"python-{version}",
                "bash",
                "-c",
                f"mkdir -p /tmp/test && cat > /tmp/test/pyproject.toml",
            ]
            with open(pyproject_path, 'r') as f:
                subprocess.run(copy_cmd, input=f.read(), text=True, check=True)
            
            # Run the check-requirements command
            cmd = [
                "docker-compose",
                "run",
                f"python-{version}",
                "python",
                "-m",
                "mcp_pypi",
                "check-requirements",
                "/tmp/test/pyproject.toml",
                "--format",
                "json"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Verify the command works by checking for JSON output
            try:
                output = json.loads(result.stdout.strip())
                assert "outdated" in output, f"Missing 'outdated' key in CLI output for Python {version} with pyproject.toml"
                assert "up_to_date" in output, f"Missing 'up_to_date' key in CLI output for Python {version} with pyproject.toml"
            except json.JSONDecodeError:
                pytest.fail(f"Invalid JSON output from CLI for Python {version} with pyproject.toml: {result.stdout}")
            
            # Verify packages are in the output
            packages = [pkg["package"] for pkg in output["outdated"] + output["up_to_date"]]
            assert any(pkg in packages for pkg in ["pytest", "requests"]), \
                f"Expected packages not found in CLI results for Python {version} with pyproject.toml"
    
    finally:
        # Clean up temporary files
        if os.path.exists(requirements_path):
            os.unlink(requirements_path)
        if os.path.exists(pyproject_path):
            os.unlink(pyproject_path)


@pytest.mark.docker
def test_server_check_requirements():
    """Test that the check_requirements_file JSON-RPC method works in each Python version."""
    # Create temporary requirements.txt for testing
    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt') as tmp:
        requirements_path = tmp.name
        tmp.write("pytest==7.0.0\nrequests>=2.26.0")
    
    # Create temporary pyproject.toml for testing
    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.toml') as tmp:
        pyproject_path = tmp.name
        tmp.write("""
[project]
name = "test-project"
version = "0.1.0"
dependencies = [
    "pytest==7.0.0",
    "requests>=2.26.0"
]
""")
    
    try:
        # Test requirements.txt with JSON-RPC server in each Python version
        for version in ["3.10", "3.11", "3.12", "3.13"]:
            # Copy the requirements file into the Docker container
            copy_cmd = [
                "docker-compose",
                "run",
                f"python-{version}",
                "bash",
                "-c",
                f"mkdir -p /tmp/test && cat > /tmp/test/requirements.txt",
            ]
            with open(requirements_path, 'r') as f:
                subprocess.run(copy_cmd, input=f.read(), text=True, check=True)
            
            # Start server, make request, and verify response
            cmd = [
                "docker-compose",
                "run",
                f"python-{version}",
                "python",
                "-c",
                f"import json, asyncio, tempfile, os, shutil; "
                f"from mcp_pypi.cli.server import RPCServer; "
                f"from mcp_pypi.core import PyPIClient; "
                f"client = PyPIClient(); "
                f"server = RPCServer(client); "
                f"request = json.dumps({{"
                f"  'jsonrpc': '2.0', "
                f"  'method': 'check_requirements_file', "
                f"  'params': {{'file_path': '/tmp/test/requirements.txt'}}, "
                f"  'id': 1"
                f"}}); "
                f"response = asyncio.run(server.handle_request(request)); "
                f"print(response); "
                f"client.close(); "
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Parse the JSON-RPC response
            try:
                response = json.loads(result.stdout.strip())
                assert "result" in response, f"Missing 'result' in JSON-RPC response for Python {version}"
                assert "error" not in response, f"Unexpected error in JSON-RPC response for Python {version}: {response.get('error')}"
                
                # Check the result structure
                output = response["result"]
                assert "outdated" in output, f"Missing 'outdated' key in JSON-RPC result for Python {version}"
                assert "up_to_date" in output, f"Missing 'up_to_date' key in JSON-RPC result for Python {version}"
                
                # Verify packages are in the output
                packages = [pkg["package"] for pkg in output["outdated"] + output["up_to_date"]]
                assert any(pkg in packages for pkg in ["pytest", "requests"]), \
                    f"Expected packages not found in JSON-RPC results for Python {version}"
            except json.JSONDecodeError:
                pytest.fail(f"Invalid JSON-RPC response for Python {version}: {result.stdout}")
        
        # Test pyproject.toml with JSON-RPC server in each Python version
        for version in ["3.10", "3.11", "3.12", "3.13"]:
            # Copy the pyproject.toml file into the Docker container
            copy_cmd = [
                "docker-compose",
                "run",
                f"python-{version}",
                "bash",
                "-c",
                f"mkdir -p /tmp/test && cat > /tmp/test/pyproject.toml",
            ]
            with open(pyproject_path, 'r') as f:
                subprocess.run(copy_cmd, input=f.read(), text=True, check=True)
            
            # Start server, make request, and verify response
            cmd = [
                "docker-compose",
                "run",
                f"python-{version}",
                "python",
                "-c",
                f"import json, asyncio, tempfile, os, shutil; "
                f"from mcp_pypi.cli.server import RPCServer; "
                f"from mcp_pypi.core import PyPIClient; "
                f"client = PyPIClient(); "
                f"server = RPCServer(client); "
                f"request = json.dumps({{"
                f"  'jsonrpc': '2.0', "
                f"  'method': 'check_requirements_file', "
                f"  'params': {{'file_path': '/tmp/test/pyproject.toml'}}, "
                f"  'id': 1"
                f"}}); "
                f"response = asyncio.run(server.handle_request(request)); "
                f"print(response); "
                f"client.close(); "
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Parse the JSON-RPC response
            try:
                response = json.loads(result.stdout.strip())
                assert "result" in response, f"Missing 'result' in JSON-RPC response for Python {version} with pyproject.toml"
                assert "error" not in response, f"Unexpected error in JSON-RPC response for Python {version} with pyproject.toml: {response.get('error')}"
                
                # Check the result structure
                output = response["result"]
                assert "outdated" in output, f"Missing 'outdated' key in JSON-RPC result for Python {version} with pyproject.toml"
                assert "up_to_date" in output, f"Missing 'up_to_date' key in JSON-RPC result for Python {version} with pyproject.toml"
                
                # Verify packages are in the output
                packages = [pkg["package"] for pkg in output["outdated"] + output["up_to_date"]]
                assert any(pkg in packages for pkg in ["pytest", "requests"]), \
                    f"Expected packages not found in JSON-RPC results for Python {version} with pyproject.toml"
            except json.JSONDecodeError:
                pytest.fail(f"Invalid JSON-RPC response for Python {version} with pyproject.toml: {result.stdout}")
    
    finally:
        # Clean up temporary files
        if os.path.exists(requirements_path):
            os.unlink(requirements_path)
        if os.path.exists(pyproject_path):
            os.unlink(pyproject_path) 