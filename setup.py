#!/usr/bin/env python
from setuptools import setup, find_packages

# Read long description from README
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="mcp-pypi",
    version="2.0.2",
    author="Kim Asplund",
    author_email="kim.asplund@gmail.com",
    description="Model Context Protocol (MCP) server for PyPI package information",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kimasplund/mcp-pypi",
    project_urls={
        "Bug Tracker": "https://github.com/kimasplund/mcp-pypi/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: Commercial",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    package_dir={"": "."},
    packages=find_packages(where="."),
    python_requires=">=3.10",
    install_requires=[
        "mcp>=1.6.0",
        "fastmcp>=2.1.0",
        "aiohttp>=3.8.0",
        "typer>=0.9.0",
        "rich>=13.3.0",
        "pydantic>=2.0.0",
        "anyio>=3.6.0",
        "uvicorn>=0.21.0",
        "packaging>=23.0",
        "websockets>=12.0",
        "httpx>=0.24.0",
    ],
    entry_points={
        "console_scripts": [
            "mcp-pypi=mcp_pypi.cli.main:app",
            "mcp-pypi-server=mcp_pypi.cli.mcp_server:app",
            "mcp-pypi-rpc=mcp_pypi.cli.server:start_server",
            "mcp-pypi-run=run_mcp_server:main",
        ],
    },
)
