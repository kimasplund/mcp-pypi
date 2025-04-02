"""
Server implementation for MCP-PyPI.
Handles JSON-RPC 2.0 requests and responses.
"""

import asyncio
import json
import logging
import sys
from typing import Dict, Any, Optional, List
import socket

from mcp_pypi.core import PyPIClient
from mcp_pypi.core.models import PyPIClientConfig

logger = logging.getLogger("mcp-pypi.server")

class RPCServer:
    """JSON-RPC 2.0 server for MCP-PyPI."""
    
    def __init__(self, client: Optional[PyPIClient] = None):
        """Initialize the RPC server."""
        self.client = client or PyPIClient()
        
    async def handle_request(self, request_data: str) -> str:
        """Handle a JSON-RPC request."""
        try:
            # Parse the request
            request = json.loads(request_data)
            
            # Validate request format
            if "jsonrpc" not in request or request["jsonrpc"] != "2.0":
                return self._format_error(-32600, "Invalid Request", "Not a valid JSON-RPC 2.0 request", request.get("id"))
            
            if "method" not in request:
                return self._format_error(-32600, "Invalid Request", "Method field is required", request.get("id"))
            
            method = request["method"]
            params = request.get("params", {})
            request_id = request.get("id")
            
            # Process the request
            try:
                result = await self._dispatch_method(method, params)
                
                # Check if result contains an error and format it properly
                if isinstance(result, dict) and "error" in result:
                    error = result["error"]
                    return self._format_error(
                        self._map_error_code(error.get("code", "unknown_error")), 
                        error.get("message", "Unknown error"),
                        None,
                        request_id
                    )
                
                # Format success response
                return json.dumps({
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": request_id
                })
                
            except Exception as e:
                logger.exception(f"Error processing method {method}: {e}")
                return self._format_error(-32603, "Internal error", str(e), request_id)
                
        except json.JSONDecodeError:
            return self._format_error(-32700, "Parse error", "Invalid JSON", None)
        except Exception as e:
            logger.exception(f"Unexpected error handling request: {e}")
            return self._format_error(-32603, "Internal error", str(e), None)
    
    def _format_error(self, code: int, message: str, data: Optional[Any] = None, request_id: Optional[Any] = None) -> str:
        """Format a JSON-RPC 2.0 error response."""
        error_obj = {
            "code": code,
            "message": message
        }
        
        if data:
            error_obj["data"] = data
            
        response = {
            "jsonrpc": "2.0",
            "error": error_obj,
            "id": request_id
        }
        
        return json.dumps(response)
    
    def _map_error_code(self, code_str: str) -> int:
        """Map internal error codes to JSON-RPC error codes."""
        code_map = {
            "parse_error": -32700,
            "invalid_input": -32602,
            "not_found": -32001,
            "network_error": -32002,
            "unknown_error": -32603,
            "permission_error": -32003,
            "file_error": -32004
        }
        
        return code_map.get(code_str, -32000)  # Default to -32000 for application errors
    
    async def _dispatch_method(self, method: str, params: Dict[str, Any]) -> Any:
        """Dispatch method calls to the appropriate client method."""
        # Special handling for method discovery and ping
        if method == "describe":
            from mcp_pypi.cli.main import get_mcp_schema
            return get_mcp_schema()
        
        if method == "ping":
            return "pong"
            
        method_map = {
            "search_packages": self.client.search_packages,
            "get_dependencies": self.client.get_dependencies,
            "check_package_exists": self.client.check_package_exists,
            "get_package_metadata": self.client.get_package_metadata,
            "get_package_stats": self.client.get_package_stats,
            "get_dependency_tree": self.client.get_dependency_tree,
            "get_package_info": self.client.get_package_info,
            "get_latest_version": self.client.get_latest_version,
            "get_package_releases": self.client.get_package_releases,
            "get_release_urls": self.client.get_release_urls,
            "get_newest_packages": self.client.get_newest_packages,
            "get_latest_updates": self.client.get_latest_updates,
            "get_project_releases": self.client.get_project_releases,
            "get_documentation_url": self.client.get_documentation_url,
            "check_requirements_file": self.client.check_requirements_file,
            "compare_versions": self.client.compare_versions
        }
        
        if method not in method_map:
            raise ValueError(f"Unknown method: {method}")
        
        method_func = method_map[method]
        
        # Convert params to args and kwargs based on method signature
        if isinstance(params, dict):
            return await method_func(**params)
        elif isinstance(params, list):
            return await method_func(*params)
        else:
            return await method_func()

async def process_mcp_stdin(verbose: bool = False):
    """Process MCP protocol lines from stdin and handle requests."""
    # Create a new client instance that persists for the entire session
    config = PyPIClientConfig()
    client = PyPIClient(config)
    
    # Configure logging
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Create RPC server with our persistent client
    server = RPCServer(client)
    
    logger.info("Starting MCP stdin processing...")
    
    try:
        while True:
            # Read a line from stdin
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            
            if not line:
                # End of input
                break
                
            line = line.strip()
            if not line:
                continue
                
            # Process the input
            logger.debug(f"Received input: {line[:50]}...")
            
            try:
                # Parse the JSON request
                response_data = await server.handle_request(line)
                print(response_data, flush=True)
            except Exception as e:
                logger.exception(f"Error processing request: {e}")
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": str(e)
                    },
                    "id": None
                }
                print(json.dumps(error_response), flush=True)
    finally:
        # Only close the client when we're completely done with STDIN processing
        logger.info("MCP processing completed")
        await client.close()

async def start_server(host: str = "127.0.0.1", port: int = 8000):
    """Start the JSON-RPC server."""
    from aiohttp import web
    import sys
    
    # Create client
    client = PyPIClient()
    server = RPCServer(client)
    
    # Create web app
    app = web.Application()
    
    async def handle_rpc(request):
        """Handle RPC requests."""
        try:
            request_data = await request.text()
            response_data = await server.handle_request(request_data)
            return web.Response(text=response_data, content_type="application/json")
        except Exception as e:
            logger.exception(f"Error handling RPC request: {e}")
            error_response = server._format_error(-32603, "Internal error", str(e), None)
            return web.Response(text=error_response, content_type="application/json")
    
    # Setup routes
    app.router.add_post("/", handle_rpc)
    app.router.add_post("/rpc", handle_rpc)
    
    # Setup shutdown handler
    async def on_shutdown(app):
        await client.close()
    
    app.on_shutdown.append(on_shutdown)
    
    # Handle port already in use by scanning for an available port
    max_port_scan = 10
    original_port = port
    
    # Check if the specified port is available
    def is_port_in_use(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex((host, port)) == 0
    
    # If the specified port is in use, try to find an available port
    for offset in range(max_port_scan):
        if offset > 0:
            port = original_port + offset
            logger.info(f"Port {original_port} is in use, trying port {port}...")
        
        if not is_port_in_use(port):
            break
    else:
        # If we couldn't find an available port in the range
        logger.error(f"Could not find an available port in range {original_port}-{original_port + max_port_scan - 1}")
        raise OSError(f"All ports in range {original_port}-{original_port + max_port_scan - 1} are in use")
    
    # Start server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    
    logger.info(f"Starting JSON-RPC server at http://{host}:{port}")
    await site.start()
    
    # Keep the server running
    try:
        while True:
            await asyncio.sleep(3600)  # Just keep it running
    finally:
        logger.info("Shutting down server")
        await runner.cleanup() 