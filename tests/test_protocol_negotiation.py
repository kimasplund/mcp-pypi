#!/usr/bin/env python
"""
Test script for protocol version negotiation with STDIO transport.

This script tests protocol version negotiation between a client using the MCPMonitor and a server
using the PyPIMCPServer via STDIO transport.
"""

import asyncio
import json
import logging
import os
import signal
import sys
import tempfile
import traceback
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.mcp_monitor import MCPMonitor
from utils.protocol import LATEST_VERSION, SUPPORTED_VERSIONS

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("protocol_test")


async def test_protocol_negotiation():
    """Test protocol version negotiation with different versions."""
    # List of protocol versions to test
    versions_to_test = [
        "1999-01-01",  # Invalid version - should trigger error
        "2023-12-01",  # Old version - should work
        "2025-03-26",  # Latest version - should work
        LATEST_VERSION,  # Latest version from the protocol module
        "2099-01-01",  # Future version - should fall back to latest
    ]

    results = {}

    # Create a temporary file to log results
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as result_file:
        result_path = result_file.name

        for version in versions_to_test:
            logger.info(f"Testing protocol version: {version}")

            try:
                # Create monitor with STDIO transport
                monitor = MCPMonitor(
                    transport_type="stdio",
                    transport_config={
                        "subprocess_cmd": [
                            sys.executable,
                            "-m",
                            "mcp_pypi.server.cli",
                            "--debug",
                            "--stdio",
                        ],
                        "debug": True,
                    },
                    debug=True,
                    protocol_version=version,
                )

                # Connect to the server
                connected = await monitor.connect()
                if not connected:
                    logger.error(f"Failed to connect with version {version}")
                    results[version] = {"success": False, "error": "Connection failed"}
                    continue

                # Try to initialize with the specified version
                try:
                    # Initialize with auto-upgrade enabled
                    monitor.auto_upgrade = True
                    info = await monitor.initialize(version)

                    if info:
                        logger.info(
                            f"Successfully initialized with version: {monitor.protocol_version}"
                        )
                        results[version] = {
                            "success": True,
                            "negotiated_version": monitor.protocol_version,
                            "server_info": monitor.server_info,
                        }
                    else:
                        logger.error(f"Initialization failed with version {version}")
                        results[version] = {
                            "success": False,
                            "error": "Initialization failed",
                        }
                except Exception as e:
                    logger.error(
                        f"Error during initialization with version {version}: {str(e)}"
                    )
                    results[version] = {"success": False, "error": str(e)}

                # Disconnect
                await monitor.disconnect()

            except Exception as e:
                logger.error(f"Error testing version {version}: {str(e)}")
                logger.debug(traceback.format_exc())
                results[version] = {"success": False, "error": str(e)}

            # Add some separation between tests
            await asyncio.sleep(0.5)

        # Write results to the file
        result_file.write(json.dumps(results, indent=2))

    # Display results
    logger.info("\n\n=== Protocol Version Negotiation Test Results ===\n")

    for version, result in results.items():
        if result["success"]:
            logger.info(
                f"Version {version}: SUCCESS - Negotiated version: {result['negotiated_version']}"
            )
        else:
            logger.info(f"Version {version}: FAILED - Error: {result['error']}")

    logger.info(f"\nDetailed results saved to: {result_path}")

    # Summary
    success_count = sum(1 for r in results.values() if r["success"])
    logger.info(f"\nSummary: {success_count}/{len(versions_to_test)} tests passed")

    return results


async def test_version_fallback():
    """Test automatic fallback to supported versions."""
    logger.info("\nTesting automatic version fallback...")

    # Create monitor with auto-upgrade enabled
    monitor = MCPMonitor(
        transport_type="stdio",
        transport_config={
            "subprocess_cmd": [
                sys.executable,
                "-m",
                "mcp_pypi.server.cli",
                "--debug",
                "--stdio",
            ],
            "debug": True,
        },
        debug=True,
    )

    # Set auto-upgrade to True to enable fallback
    monitor.auto_upgrade = True

    try:
        # Connect and initialize with an unsupported version
        connected = await monitor.connect()
        if not connected:
            logger.error("Failed to connect for fallback test")
            return False

        # Try to initialize with an invalid version
        logger.info("Trying to initialize with invalid version '1.0'...")
        info = await monitor.initialize("1.0")

        if info:
            logger.info(
                f"Successfully fell back to version: {monitor.protocol_version}"
            )
            logger.info(f"Server info: {monitor.server_info}")
            result = True
        else:
            logger.error("Failed to fall back to a supported version")
            result = False

        # Disconnect
        await monitor.disconnect()
        return result

    except Exception as e:
        logger.error(f"Error in fallback test: {str(e)}")
        logger.debug(traceback.format_exc())
        return False


async def main():
    """Run all protocol version negotiation tests."""
    try:
        logger.info("Starting protocol version negotiation tests")

        # Run the main protocol negotiation tests
        await test_protocol_negotiation()

        # Test version fallback
        fallback_result = await test_version_fallback()
        logger.info(
            f"Version fallback test: {'SUCCESS' if fallback_result else 'FAILED'}"
        )

        logger.info("All tests completed")

    except Exception as e:
        logger.error(f"Error in test suite: {str(e)}")
        logger.debug(traceback.format_exc())
        return 1

    return 0


if __name__ == "__main__":
    # Handle keyboard interrupts gracefully
    def signal_handler(sig, frame):
        logger.info("Interrupted, shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Run the async main function
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Interrupted, shutting down...")
        sys.exit(0)
