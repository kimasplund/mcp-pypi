#!/usr/bin/env python3
"""
Test script to simulate multiple JSON-RPC requests to the STDIN server
This helps diagnose if the client is being closed between requests.
"""

import subprocess
import json
import time
import sys

# Start the server process
server_process = subprocess.Popen(
    ["pypi-mcp", "serve", "--stdin"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1  # Line buffering
)

# Define the requests to send
requests = [
    {"jsonrpc": "2.0", "method": "describe", "id": 1},
    {"jsonrpc": "2.0", "method": "search_packages", "params": {"query": "requests"}, "id": 2},
    {"jsonrpc": "2.0", "method": "get_latest_version", "params": {"package_name": "requests"}, "id": 3},
    {"jsonrpc": "2.0", "method": "get_package_info", "params": {"package_name": "requests"}, "id": 4},
    {"jsonrpc": "2.0", "method": "search_packages", "params": {"query": "flask"}, "id": 5}
]

# Send each request and get the response
try:
    print("Sending multiple requests to test client lifecycle...")
    
    for i, request in enumerate(requests):
        # Convert request to JSON and send
        request_json = json.dumps(request)
        print(f"\nRequest {i+1}: {request_json}")
        
        # Write request to server's stdin
        server_process.stdin.write(request_json + "\n")
        server_process.stdin.flush()
        
        # Read response from stdout
        response = server_process.stdout.readline().strip()
        
        # Parse the response
        try:
            response_obj = json.loads(response)
            # Print a shortened version of the response for readability
            if "result" in response_obj:
                if isinstance(response_obj["result"], dict) and "tools" in response_obj["result"]:
                    response_obj["result"]["tools"] = f"[{len(response_obj['result']['tools'])} tools]"
                elif isinstance(response_obj["result"], dict) and "results" in response_obj["result"]:
                    response_obj["result"]["results"] = f"[{len(response_obj['result']['results'])} results]"
            print(f"Response {i+1}: {json.dumps(response_obj)[:200]}...")
        except json.JSONDecodeError:
            print(f"Response {i+1} (raw): {response[:200]}...")
        
        # Small delay between requests
        time.sleep(0.5)
        
    print("\nAll requests completed successfully!")
        
except KeyboardInterrupt:
    print("Test interrupted by user")
finally:
    # Close the server process
    print("Closing server process...")
    server_process.stdin.close()
    server_process.terminate()
    server_process.wait()
    
    # Print any stderr output
    stderr_output = server_process.stderr.read()
    if stderr_output:
        print("\nServer stderr output:")
        print(stderr_output) 