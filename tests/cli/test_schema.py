#!/usr/bin/env python3
"""Test script to verify the MCP schema format."""

import json
import sys
from mcp_pypi.cli.main import get_mcp_schema


def main():
    # Get the schema
    schema = get_mcp_schema()

    # Print it formatted for inspection
    print(json.dumps(schema, indent=2))

    # Validate required fields
    required_fields = ["name", "version", "description", "tools"]
    for field in required_fields:
        if field not in schema:
            print(f"ERROR: Missing required field '{field}' in schema")
            return 1

    # Check tools array
    if not isinstance(schema["tools"], list) or len(schema["tools"]) == 0:
        print("ERROR: 'tools' must be a non-empty array")
        return 1

    # Validate each tool
    for i, tool in enumerate(schema["tools"]):
        # Check required tool fields
        tool_fields = ["name", "description", "parameters"]
        for field in tool_fields:
            if field not in tool:
                print(f"ERROR: Tool {i} missing required field '{field}'")
                return 1

        # Check parameters format (JSON Schema)
        params = tool["parameters"]
        if not isinstance(params, dict):
            print(f"ERROR: Tool {tool['name']} parameters must be a JSON Schema object")
            return 1

        # Verify parameters has type and properties
        if "type" not in params or params["type"] != "object":
            print(f"ERROR: Tool {tool['name']} parameters must have type 'object'")
            return 1

        if "properties" not in params or not isinstance(params["properties"], dict):
            print(
                f"ERROR: Tool {tool['name']} parameters must have 'properties' object"
            )
            return 1

    print("\nSchema validation PASSED. The schema follows the MCP specification.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
