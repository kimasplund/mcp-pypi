#!/usr/bin/env python3
import sys
import json
import subprocess
from pathlib import Path

# Path to the pypi_tools.py script
PYPI_TOOLS = Path(__file__).parent / "pypi_tools.py"

def main():
    # Standard MCP protocol requires reading JSON requests from stdin
    print("MCP server started. Waiting for requests...", file=sys.stderr)
    
    while True:
        try:
            # Read a line from stdin (blocking)
            line = sys.stdin.readline()
            
            if not line:
                # End of input stream, exit
                print("Input stream closed. Exiting.", file=sys.stderr)
                break
                
            # Parse the JSON request
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                print(f"Error: Invalid JSON: {line}", file=sys.stderr)
                continue
                
            # Check if this is a tool call
            if "method" in request and request["method"] == "execute":
                params = request.get("params", {})
                tool_name = params.get("name", "")
                tool_args = params.get("arguments", {})
                
                # Convert the tool call to command-line arguments for pypi_tools.py
                cmd_args = [sys.executable, str(PYPI_TOOLS)]
                
                # Map the tool name to the corresponding command
                if tool_name == "get_package_info":
                    cmd_args.append("get_package_info")
                    if "package_name" in tool_args:
                        cmd_args.append(tool_args["package_name"])
                elif tool_name == "get_latest_version":
                    cmd_args.append("get_latest_version")
                    if "package_name" in tool_args:
                        cmd_args.append(tool_args["package_name"])
                elif tool_name == "get_dependency_tree":
                    cmd_args.append("get_dependency_tree")
                    if "package_name" in tool_args:
                        cmd_args.append(tool_args["package_name"])
                    if "depth" in tool_args:
                        cmd_args.extend(["--depth", str(tool_args["depth"])])
                elif tool_name == "get_documentation_url":
                    cmd_args.append("get_documentation_url")
                    if "package_name" in tool_args:
                        cmd_args.append(tool_args["package_name"])
                elif tool_name == "check_requirements_file":
                    cmd_args.append("check_requirements_file")
                    if "file_path" in tool_args:
                        cmd_args.append(tool_args["file_path"])
                else:
                    # Handle unknown tool
                    response = {
                        "id": request.get("id"),
                        "error": {
                            "code": -32601,
                            "message": f"Unknown tool: {tool_name}"
                        }
                    }
                    print(json.dumps(response))
                    continue
                
                # Execute pypi_tools.py with the appropriate arguments
                result = subprocess.run(
                    cmd_args, 
                    capture_output=True, 
                    text=True
                )
                
                # Parse the result as JSON if possible
                try:
                    result_data = json.loads(result.stdout)
                    response = {
                        "id": request.get("id"),
                        "result": result_data
                    }
                except json.JSONDecodeError:
                    response = {
                        "id": request.get("id"),
                        "result": result.stdout.strip()
                    }
                
                # Send the response
                print(json.dumps(response))
            else:
                # Handle unknown method or ping
                if request.get("method") == "ping":
                    response = {
                        "id": request.get("id"),
                        "result": "pong"
                    }
                else:
                    response = {
                        "id": request.get("id"),
                        "error": {
                            "code": -32601,
                            "message": f"Unknown method: {request.get('method')}"
                        }
                    }
                print(json.dumps(response))
                
        except KeyboardInterrupt:
            print("Received interrupt. Exiting.", file=sys.stderr)
            break
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            # Send error response if we have a request ID
            if 'request' in locals() and hasattr(request, 'get'):
                response = {
                    "id": request.get("id"),
                    "error": {
                        "code": -32603,
                        "message": str(e)
                    }
                }
                print(json.dumps(response))

if __name__ == "__main__":
    main() 