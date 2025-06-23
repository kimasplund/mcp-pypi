#!/usr/bin/env python
"""Test module for the initialization sequence implementation."""

import unittest
import json
from unittest.mock import patch, MagicMock

import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.initialization import (
    ServerCapability,
    ClientCapability,
    InitializationHandler,
    create_default_client_capabilities,
    create_initialize_request,
    extract_server_capabilities,
)
from utils.protocol import ProtocolCapability, LATEST_VERSION, SUPPORTED_VERSIONS


class TestInitializationHandler(unittest.TestCase):
    """Test cases for the InitializationHandler class."""

    def setUp(self):
        """Set up test fixtures."""
        self.server_name = "TestMCPServer"
        self.server_version = "1.0.0"
        self.handler = InitializationHandler(
            server_name=self.server_name,
            server_version=self.server_version,
            description="Test server for MCP",
            vendor="Test, Inc.",
            url="https://example.com/mcp",
        )

    def test_initialization(self):
        """Test the initialization of the handler."""
        # Check that the handler was initialized correctly
        self.assertEqual(self.handler.server_name, self.server_name)
        self.assertEqual(self.handler.server_version, self.server_version)
        self.assertEqual(self.handler.description, "Test server for MCP")
        self.assertEqual(self.handler.vendor, "Test, Inc.")
        self.assertEqual(self.handler.url, "https://example.com/mcp")

        # Check that the default protocol version is set to the latest version
        self.assertEqual(self.handler.protocol_version, LATEST_VERSION)

        # Check that the capability map is correctly set up
        self.assertIn(ProtocolCapability.STREAMING_RESULTS, self.handler.capability_map)
        self.assertEqual(
            self.handler.capability_map[ProtocolCapability.STREAMING_RESULTS],
            ServerCapability.STREAMING,
        )

    def test_capabilities_to_dict(self):
        """Test the conversion of capabilities to a dictionary."""
        # Add some capabilities
        self.handler.capabilities = {
            ServerCapability.TOOL_EXECUTION,
            ServerCapability.RESOURCE_ACCESS,
            ServerCapability.STREAMING,
            ServerCapability.TOKEN_AUTH,
        }

        # Convert capabilities to a dictionary
        capabilities_dict = self.handler._capabilities_to_dict()

        # Check that the dictionary contains the correct values
        self.assertTrue(capabilities_dict["tools"]["execution"])
        self.assertTrue(capabilities_dict["resources"]["access"])
        self.assertTrue(capabilities_dict["protocol"]["streaming"])
        self.assertTrue(capabilities_dict["authentication"]["token"])

        # Check that other capabilities are not enabled
        self.assertFalse(capabilities_dict["protocol"]["cancellation"])
        self.assertFalse(capabilities_dict["authentication"]["oauth"])

    def test_parse_client_capabilities(self):
        """Test the parsing of client capabilities from a dictionary."""
        # Create a capabilities dictionary
        capabilities_dict = {
            "protocol": {
                "streaming": True,
                "cancellation": True,
                "progress": False,
            },
            "authentication": {
                "token": True,
                "oauth": False,
                "apiKey": True,
            },
            "tools": {
                "schemaValidation": True,
                "batchExecution": False,
            },
        }

        # Parse client capabilities
        client_capabilities = self.handler._parse_client_capabilities(capabilities_dict)

        # Check that the correct capabilities were parsed
        self.assertIn(ClientCapability.STREAMING, client_capabilities)
        self.assertIn(ClientCapability.CANCELLATION, client_capabilities)
        self.assertIn(ClientCapability.TOKEN_AUTH, client_capabilities)
        self.assertIn(ClientCapability.API_KEY, client_capabilities)
        self.assertIn(ClientCapability.SCHEMA_VALIDATION, client_capabilities)

        # Check that other capabilities are not included
        self.assertNotIn(ClientCapability.PROGRESS, client_capabilities)
        self.assertNotIn(ClientCapability.OAUTH, client_capabilities)
        self.assertNotIn(ClientCapability.BATCH_EXECUTION, client_capabilities)

    def test_handle_initialize_request_success(self):
        """Test handling an initialization request with a successful version negotiation."""
        # Create a request
        params = {
            "version": LATEST_VERSION,
            "client_id": "test-client",
            "client_name": "Test Client",
            "client_version": "1.0.0",
            "capabilities": create_default_client_capabilities(),
        }
        request_id = 42

        # Handle the request
        response = self.handler.handle_initialize_request(params, request_id)

        # Check the response
        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], request_id)
        self.assertIn("result", response)

        # Check the result
        result = response["result"]
        self.assertEqual(result["protocol_version"], LATEST_VERSION)
        self.assertIn("server_info", result)
        self.assertIn("capabilities", result)
        self.assertIn("session_id", result)

        # Check server info
        server_info = result["server_info"]
        self.assertEqual(server_info["name"], self.server_name)
        self.assertEqual(server_info["version"], self.server_version)
        self.assertEqual(server_info["protocol_version"], LATEST_VERSION)
        self.assertEqual(server_info["description"], "Test server for MCP")
        self.assertEqual(server_info["vendor"], "Test, Inc.")
        self.assertEqual(server_info["url"], "https://example.com/mcp")

    def test_handle_initialize_request_version_fallback(self):
        """Test handling an initialization request with a version fallback."""
        # Create a request with an old version
        params = {
            "version": "0.5",
            "client_id": "test-client",
            "client_name": "Test Client",
            "client_version": "1.0.0",
            "capabilities": create_default_client_capabilities(),
        }
        request_id = 42

        # Mock the negotiate_version function to simulate a fallback
        with patch("utils.protocol.negotiate_version") as mock_negotiate:
            mock_negotiate.return_value = {
                "success": True,
                "version": "1.0",
                "message": "Falling back to version 1.0",
            }

            # Handle the request
            response = self.handler.handle_initialize_request(params, request_id)

            # Check the response
            self.assertEqual(response["jsonrpc"], "2.0")
            self.assertEqual(response["id"], request_id)
            self.assertIn("result", response)

            # Check the result
            result = response["result"]
            self.assertEqual(result["protocol_version"], "1.0")

    def test_handle_initialize_request_version_failure(self):
        """Test handling an initialization request with a version negotiation failure."""
        # Create a request with an unsupported version
        params = {
            "version": "0.1",
            "client_id": "test-client",
            "client_name": "Test Client",
            "client_version": "1.0.0",
            "capabilities": create_default_client_capabilities(),
        }
        request_id = 42

        # Mock the negotiate_version function to simulate a failure
        with patch("utils.protocol.negotiate_version") as mock_negotiate:
            mock_negotiate.return_value = {
                "success": False,
                "error": {
                    "code": -32001,
                    "message": "Unsupported protocol version: 0.1",
                    "data": {
                        "supportedVersions": SUPPORTED_VERSIONS,
                        "requiredVersion": SUPPORTED_VERSIONS[0],
                    },
                },
            }

            # Handle the request
            response = self.handler.handle_initialize_request(params, request_id)

            # Check the response
            self.assertEqual(response["jsonrpc"], "2.0")
            self.assertEqual(response["id"], request_id)
            self.assertIn("error", response)

            # Check the error
            error = response["error"]
            self.assertEqual(error["code"], -32001)
            self.assertEqual(error["message"], "Unsupported protocol version: 0.1")
            self.assertIn("data", error)
            self.assertIn("supportedVersions", error["data"])
            self.assertIn("requiredVersion", error["data"])

    def test_create_initialization_error(self):
        """Test the creation of an initialization error."""
        # Create an error
        message = "Test error message"
        code = -32002
        data = {"foo": "bar"}
        request_id = 42

        # Create an error response
        response = self.handler.create_initialization_error(
            message=message,
            code=code,
            data=data,
            request_id=request_id,
        )

        # Check the response
        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], request_id)
        self.assertIn("error", response)

        # Check the error
        error = response["error"]
        self.assertEqual(error["code"], code)
        self.assertEqual(error["message"], message)
        self.assertIn("data", error)
        self.assertEqual(error["data"]["foo"], "bar")
        self.assertIn("supportedVersions", error["data"])
        self.assertIn("requiredVersion", error["data"])


class TestUtilityFunctions(unittest.TestCase):
    """Test cases for the utility functions."""

    def test_create_default_client_capabilities(self):
        """Test the creation of default client capabilities."""
        # Create default capabilities
        capabilities = create_default_client_capabilities()

        # Check that the dictionary contains the correct values
        self.assertTrue(capabilities["protocol"]["streaming"])
        self.assertTrue(capabilities["protocol"]["cancellation"])
        self.assertTrue(capabilities["protocol"]["progress"])
        self.assertTrue(capabilities["protocol"]["stateManagement"])
        self.assertTrue(capabilities["protocol"]["binaryTransfer"])
        self.assertFalse(capabilities["protocol"]["customMethods"])
        self.assertTrue(capabilities["protocol"]["eventNotifications"])

        self.assertTrue(capabilities["authentication"]["token"])
        self.assertFalse(capabilities["authentication"]["oauth"])
        self.assertTrue(capabilities["authentication"]["apiKey"])

        self.assertTrue(capabilities["tools"]["schemaValidation"])
        self.assertFalse(capabilities["tools"]["batchExecution"])
        self.assertTrue(capabilities["tools"]["asyncExecution"])

    def test_create_initialize_request(self):
        """Test the creation of an initialization request."""
        # Create a request
        client_id = "test-client"
        protocol_version = "1.2"
        client_name = "Test Client"
        client_version = "1.0.0"
        capabilities = create_default_client_capabilities()
        authentication = {"token": "test-token"}
        locale = "en-US"
        trace = "verbose"
        request_id = 42

        # Create a request
        request = create_initialize_request(
            client_id=client_id,
            protocol_version=protocol_version,
            client_name=client_name,
            client_version=client_version,
            capabilities=capabilities,
            authentication=authentication,
            locale=locale,
            trace=trace,
            request_id=request_id,
        )

        # Check the request
        self.assertEqual(request["jsonrpc"], "2.0")
        self.assertEqual(request["method"], "initialize")
        self.assertEqual(request["id"], request_id)
        self.assertIn("params", request)

        # Check params
        params = request["params"]
        self.assertEqual(params["version"], protocol_version)
        self.assertEqual(params["client_id"], client_id)
        self.assertEqual(params["client_name"], client_name)
        self.assertEqual(params["client_version"], client_version)
        self.assertEqual(params["capabilities"], capabilities)
        self.assertEqual(params["authentication"], authentication)
        self.assertEqual(params["locale"], locale)
        self.assertEqual(params["trace"], trace)

    def test_extract_server_capabilities(self):
        """Test the extraction of server capabilities from an initialization result."""
        # Create a result dictionary
        result = {
            "capabilities": {
                "tools": {
                    "execution": True,
                    "discovery": True,
                    "schemaValidation": True,
                    "batchExecution": False,
                    "asyncExecution": True,
                },
                "resources": {
                    "access": True,
                    "discovery": False,
                    "templates": True,
                    "streaming": False,
                },
                "protocol": {
                    "streaming": True,
                    "cancellation": True,
                    "progress": False,
                    "clientState": True,
                    "binaryTransfer": False,
                    "customMethods": True,
                    "eventNotifications": False,
                },
                "authentication": {
                    "token": True,
                    "oauth": False,
                    "apiKey": True,
                },
                "prompts": {
                    "generation": True,
                },
            }
        }

        # Extract capabilities
        capabilities = extract_server_capabilities(result)

        # Check that the correct capabilities were extracted
        self.assertIn(ServerCapability.TOOL_EXECUTION, capabilities)
        self.assertIn(ServerCapability.TOOL_DISCOVERY, capabilities)
        self.assertIn(ServerCapability.SCHEMA_VALIDATION, capabilities)
        self.assertIn(ServerCapability.ASYNC_EXECUTION, capabilities)
        self.assertIn(ServerCapability.RESOURCE_ACCESS, capabilities)
        self.assertIn(ServerCapability.RESOURCE_TEMPLATES, capabilities)
        self.assertIn(ServerCapability.STREAMING, capabilities)
        self.assertIn(ServerCapability.CANCELLATION, capabilities)
        self.assertIn(ServerCapability.CLIENT_STATE, capabilities)
        self.assertIn(ServerCapability.CUSTOM_METHODS, capabilities)
        self.assertIn(ServerCapability.TOKEN_AUTH, capabilities)
        self.assertIn(ServerCapability.API_KEY, capabilities)
        self.assertIn(ServerCapability.PROMPT_GENERATION, capabilities)

        # Check that other capabilities are not included
        self.assertNotIn(ServerCapability.BATCH_EXECUTION, capabilities)
        self.assertNotIn(ServerCapability.RESOURCE_DISCOVERY, capabilities)
        self.assertNotIn(ServerCapability.RESOURCE_STREAMING, capabilities)
        self.assertNotIn(ServerCapability.PROGRESS, capabilities)
        self.assertNotIn(ServerCapability.BINARY_TRANSFER, capabilities)
        self.assertNotIn(ServerCapability.EVENT_NOTIFICATIONS, capabilities)
        self.assertNotIn(ServerCapability.OAUTH, capabilities)


if __name__ == "__main__":
    unittest.main()
