#!/usr/bin/env python
"""
Tests for the protocol version negotiation module.
"""

import sys
import unittest
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.protocol import (LATEST_VERSION, PROTOCOL_VERSIONS,
                            SUPPORTED_VERSIONS, ProtocolCapability,
                            check_version_compatibility,
                            extract_required_version_from_error,
                            format_version_error,
                            get_minimum_version_for_capabilities,
                            get_version_from_env, negotiate_version)


class TestProtocolVersionNegotiation(unittest.TestCase):
    """Test cases for protocol version negotiation utilities."""

    def test_protocol_version_definitions(self):
        """Test that protocol versions are defined correctly."""
        # At least one version should be defined
        self.assertTrue(PROTOCOL_VERSIONS, "No protocol versions defined")

        # Latest version should be derived correctly
        expected_latest = sorted(PROTOCOL_VERSIONS.keys())[-1]
        self.assertEqual(LATEST_VERSION, expected_latest)

        # Supported versions should be defined
        self.assertTrue(SUPPORTED_VERSIONS, "No supported versions defined")

        # Supported versions should only include non-deprecated ones
        for version in SUPPORTED_VERSIONS:
            self.assertFalse(
                PROTOCOL_VERSIONS[version].is_deprecated,
                f"Deprecated version {version} included in SUPPORTED_VERSIONS",
            )

    def test_version_compatibility_check(self):
        """Test version compatibility checking."""
        # Unknown version should be incompatible
        unknown_result = check_version_compatibility("1999-01-01")
        self.assertFalse(unknown_result["compatible"])
        self.assertEqual(unknown_result["suggested_version"], LATEST_VERSION)

        # Deprecated version should be incompatible
        deprecated_versions = [
            v for v, pv in PROTOCOL_VERSIONS.items() if pv.is_deprecated
        ]
        if deprecated_versions:
            deprecated_result = check_version_compatibility(deprecated_versions[0])
            self.assertFalse(deprecated_result["compatible"])
            self.assertTrue(deprecated_result["is_deprecated"])
            self.assertIsNotNone(deprecated_result["suggested_version"])

        # Latest version should be compatible
        latest_result = check_version_compatibility(LATEST_VERSION)
        self.assertTrue(latest_result["compatible"])
        self.assertFalse(latest_result["is_deprecated"])

        # Check with capabilities requirement
        capabilities = {ProtocolCapability.SSE_SUPPORT, ProtocolCapability.BINARY_DATA}

        # Capability compatibility for latest version
        latest_with_capabilities = check_version_compatibility(
            LATEST_VERSION, capabilities
        )
        self.assertTrue(latest_with_capabilities["compatible"])

        # Verify that older versions missing required capabilities are detected
        if len(PROTOCOL_VERSIONS) > 1:
            oldest_version = sorted(PROTOCOL_VERSIONS.keys())[0]
            oldest_with_capabilities = check_version_compatibility(
                oldest_version, capabilities
            )

            # If the oldest version doesn't support all capabilities,
            # it should be marked incompatible
            if not PROTOCOL_VERSIONS[oldest_version].capabilities.issuperset(
                capabilities
            ):
                self.assertFalse(oldest_with_capabilities["compatible"])
                self.assertTrue(oldest_with_capabilities["missing_capabilities"])

    def test_version_negotiation(self):
        """Test version negotiation between client and server."""
        # Direct match should succeed
        if SUPPORTED_VERSIONS:
            supported_version = SUPPORTED_VERSIONS[0]
            direct_match = negotiate_version(supported_version, SUPPORTED_VERSIONS)
            self.assertTrue(direct_match["success"])
            self.assertEqual(direct_match["version"], supported_version)
            self.assertIsNone(direct_match["error"])

        # Unsupported version should fail with error
        unsupported = negotiate_version("1999-01-01", SUPPORTED_VERSIONS)
        self.assertFalse(unsupported["success"])
        self.assertIsNone(unsupported["version"])
        self.assertIsNotNone(unsupported["error"])
        self.assertEqual(unsupported["error"]["code"], -32001)
        self.assertIn("supportedVersions", unsupported["error"]["data"])
        self.assertIn("requiredVersion", unsupported["error"]["data"])

        # Deprecated version should suggest successor
        deprecated_versions = [
            v
            for v, pv in PROTOCOL_VERSIONS.items()
            if pv.is_deprecated and pv.successor
        ]
        if deprecated_versions:
            deprecated_version = deprecated_versions[0]
            successor = PROTOCOL_VERSIONS[deprecated_version].successor

            # Only test if successor is in supported versions
            if successor in SUPPORTED_VERSIONS:
                deprecated_negotiation = negotiate_version(
                    deprecated_version, SUPPORTED_VERSIONS
                )
                self.assertTrue(deprecated_negotiation["success"])
                self.assertEqual(deprecated_negotiation["version"], successor)

    def test_extract_required_version(self):
        """Test extracting required version from error message."""
        # Test with data field
        error_with_data = {
            "code": -32001,
            "message": "Unsupported protocol version",
            "data": {"requiredVersion": "2025-03-26"},
        }
        self.assertEqual(
            extract_required_version_from_error(error_with_data), "2025-03-26"
        )

        # Test with supportedVersions field
        error_with_supported = {
            "code": -32001,
            "message": "Unsupported protocol version",
            "data": {"supportedVersions": ["2025-03-26", "2024-11-05"]},
        }
        self.assertEqual(
            extract_required_version_from_error(error_with_supported), "2025-03-26"
        )

        # Test with direct requiredVersion field
        error_with_direct = {
            "code": -32001,
            "message": "Unsupported protocol version",
            "requiredVersion": "2025-03-26",
        }
        self.assertEqual(
            extract_required_version_from_error(error_with_direct), "2025-03-26"
        )

        # Test extraction from message
        error_with_message = {
            "code": -32001,
            "message": "Unsupported protocol version. Server requires version 2025-03-26",
        }
        self.assertEqual(
            extract_required_version_from_error(error_with_message), "2025-03-26"
        )

        # Test with no version information
        error_without_version = {"code": -32001, "message": "Unknown error"}
        self.assertIsNone(extract_required_version_from_error(error_without_version))

    def test_minimum_version_for_capabilities(self):
        """Test finding minimum version for capabilities."""
        # Test with core capabilities that all versions should support
        core_capabilities = {
            ProtocolCapability.INITIALIZE,
            ProtocolCapability.LIST_TOOLS,
            ProtocolCapability.INVOKE_TOOL,
        }
        min_version_core = get_minimum_version_for_capabilities(core_capabilities)
        self.assertIsNotNone(min_version_core)
        self.assertEqual(min_version_core, sorted(PROTOCOL_VERSIONS.keys())[0])

        # Test with advanced capabilities only in latest version
        advanced_capabilities = {
            ProtocolCapability.STREAMING_RESULTS,
            ProtocolCapability.SSE_SUPPORT,
            ProtocolCapability.STDIO_SUPPORT,
        }
        min_version_advanced = get_minimum_version_for_capabilities(
            advanced_capabilities
        )
        self.assertIsNotNone(min_version_advanced)

        # The minimum version for these advanced capabilities should be the latest one
        for version in PROTOCOL_VERSIONS:
            if PROTOCOL_VERSIONS[version].capabilities.issuperset(
                advanced_capabilities
            ):
                expected_min = version
                break
        else:
            expected_min = LATEST_VERSION

        self.assertEqual(min_version_advanced, expected_min)

    def test_format_version_error(self):
        """Test error formatting for version mismatch."""
        client_version = "1999-01-01"
        server_versions = ["2024-11-05", "2025-03-26"]

        error = format_version_error(client_version, server_versions)

        self.assertEqual(error["code"], -32001)
        self.assertIn(client_version, error["message"])
        self.assertIn(server_versions[0], error["message"])
        self.assertEqual(error["data"]["supportedVersions"], server_versions)
        self.assertEqual(error["data"]["requiredVersion"], server_versions[0])


if __name__ == "__main__":
    unittest.main()
