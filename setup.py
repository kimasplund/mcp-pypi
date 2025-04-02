#!/usr/bin/env python3
from setuptools import setup, find_packages

# Read long description from README
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="mcp-pypi",
    version="2.0.0",
    author="Kim Asplund",
    author_email="kim.asplund@gmail.com",
    description="A modern PyPI client library and CLI tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kimasplund/mcp-pypi",
    project_urls={
        "Bug Tracker": "https://github.com/kimasplund/mcp-pypi/issues",
        "Documentation": "https://github.com/kimasplund/mcp-pypi#readme",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Software Distribution",
    ],
    package_dir={"": "."},
    packages=find_packages(where="."),
    python_requires=">=3.10",
    install_requires=[
        "aiohttp>=3.8.0",
        "packaging>=23.0",
        "typer>=0.9.0",
        "rich>=13.0.0",
        "mcp>=1.6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "mypy>=1.0.0",
        ],
        "viz": [
            "plotly>=5.13.0",
            "kaleido>=0.2.1",
        ],
        "search": [
            "beautifulsoup4>=4.12.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "pypi-mcp=mcp_pypi.cli.main:app",
        ],
    },
) 