import pytest
import tempfile
import os
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_check_requirements_file_pyproject(pypi_mcp_server):
    """Test the check_requirements_file method with pyproject.toml file."""
    # Create a temporary pyproject.toml file
    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.toml') as tmp:
        pyproject_path = tmp.name
        tmp.write("""
[project]
name = "test-project"
version = "0.1.0"
dependencies = [
    "requests>=2.26.0",
    "flask==2.0.0"
]

[tool.poetry.dependencies]
python = ">=3.8"
aiohttp = ">=3.8.0"
        """)
    
    try:
        # Mock client.check_requirements_file in the PyPIClient class
        expected_result = {
            "outdated": [
                {"package": "flask", "current_version": "2.0.0", "latest_version": "2.3.0", "constraint": "==2.0.0"}
            ],
            "up_to_date": [
                {"package": "requests", "current_version": ">=2.26.0", "latest_version": "2.28.1", "constraint": ">=2.26.0"},
                {"package": "aiohttp", "current_version": ">=3.8.0", "latest_version": "3.8.5", "constraint": ">=3.8.0"}
            ]
        }
        
        pypi_mcp_server.client.check_requirements_file = AsyncMock(return_value=expected_result)
        
        # Call the method through server
        result = await pypi_mcp_server.check_requirements_file(pyproject_path)
        
        # Verify result
        assert result == expected_result
        
        # Verify the client method was called correctly
        pypi_mcp_server.client.check_requirements_file.assert_called_once_with(pyproject_path)
    
    finally:
        # Clean up
        if os.path.exists(pyproject_path):
            os.unlink(pyproject_path)


@pytest.mark.asyncio
async def test_check_requirements_file_format_option(pypi_mcp_server):
    """Test the check_requirements_file method with format option."""
    # Create a temporary requirements file
    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt') as tmp:
        requirements_path = tmp.name
        tmp.write("package1==1.0.0\npackage2>=2.0.0")
    
    try:
        # Mock client.check_requirements_file in the PyPIClient class
        expected_result = {
            "outdated": [
                {"package": "package1", "current_version": "1.0.0", "latest_version": "1.5.0", "constraint": "==1.0.0"}
            ],
            "up_to_date": [
                {"package": "package2", "current_version": ">=2.0.0", "latest_version": "2.1.0", "constraint": ">=2.0.0"}
            ]
        }
        
        pypi_mcp_server.client.check_requirements_file = AsyncMock(return_value=expected_result)
        
        # Call the method through server with format option
        result = await pypi_mcp_server.check_requirements_file(requirements_path, format="json")
        
        # Verify result
        assert result == expected_result
        
        # Verify the client method was called correctly
        pypi_mcp_server.client.check_requirements_file.assert_called_once_with(requirements_path)
    
    finally:
        # Clean up
        if os.path.exists(requirements_path):
            os.unlink(requirements_path) 