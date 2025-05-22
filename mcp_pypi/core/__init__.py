"""
Core PyPI client functionality.

This module provides the main PyPIClient class and supporting components
for interacting with the Python Package Index (PyPI).
"""

from .client import PyPIClient
from .models import (
    PyPIClientConfig, 
    PackageInfo, 
    VersionInfo, 
    ReleasesInfo,
    SearchResult, 
    DependenciesResult,
    ErrorCode
)

__all__ = [
    "PyPIClient",
    "PyPIClientConfig", 
    "PackageInfo",
    "VersionInfo",
    "ReleasesInfo", 
    "SearchResult",
    "DependenciesResult",
    "ErrorCode"
]