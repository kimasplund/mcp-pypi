import json
import logging
import asyncio
import os
import sys
from typing import Any, Dict, List, Optional, Union, Tuple

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("MCP_DEBUG") else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)


class MCPClient:
    """Client for MCP (Modular Capabilities Protocol) servers"""

    def __init__(self, protocol_version: str = "2023-12-01"):
        self.protocol_version = protocol_version
        self.tools = {}
        self.resources = {}
        self.resource_templates = {}
        self.server_info = None
        self.initialized = False
        self.client_info = {"name": "mcp-pypi-client", "version": "0.1.0"}
        self.writer: Any = None
        self.reader: Any = None

    async def connect_subprocess(
        self, command: List[str], env: Optional[Dict[str, str]] = None
    ) -> None:
        """Connect to an MCP server via subprocess"""
        if env is None:
            env = os.environ.copy()

        # Make sure we log environment variables if debugging
        if os.environ.get("MCP_DEBUG"):
            logger.debug(f"Subprocess environment: {env}")

        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        self.reader = process.stdout
        self.writer = process.stdin

        # Start a task to monitor stderr from the subprocess
        async def log_stderr():
            stderr = process.stderr
            if stderr is not None:
                while True:
                    line = await stderr.readline()
                    if not line:
                        break
                    logger.info(f"Server stderr: {line.decode().strip()}")

        asyncio.create_task(log_stderr())

        logger.info(f"Connected to subprocess: {command}")

        # Now initialize the connection
        await self.initialize()

    async def connect_stdio(
        self, command: Optional[List[str]] = None, env: Optional[Dict[str, str]] = None
    ) -> None:
        """Connect to an MCP server via stdio"""
        if command is not None:
            await self.connect_subprocess(command, env)
            return

        loop = asyncio.get_event_loop()
        
        # Set up stdin reader
        self.reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(self.reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        # Set up stdout writer
        transport, protocol = await loop.connect_write_pipe(
            lambda: asyncio.Protocol(), sys.stdout
        )
        self.writer = asyncio.StreamWriter(transport, protocol, self.reader, loop)
        logger.info("Connected to stdio")

        await self.initialize()

    async def initialize(self) -> None:
        """Initialize the MCP connection"""
        logger.info(f"Initializing with protocol version {self.protocol_version}")

        request = {
            "jsonrpc": "2.0",
            "id": "init1",
            "method": "initialize",
            "params": {
                "protocolVersion": self.protocol_version,
                "clientInfo": self.client_info,
            },
        }

        response = await self._send_request(request)
        if "error" in response:
            raise Exception(f"Initialization failed: {response['error']['message']}")

        result = response.get("result", {})
        self.server_info = result.get("serverInfo", {})
        self.protocol_version = result.get("protocolVersion", self.protocol_version)

        logger.info(
            f"Initialized with server {self.server_info.get('name')} v{self.server_info.get('version')}"
        )
        logger.info(f"Using protocol version: {self.protocol_version}")

        # Fetch available tools
        await self._fetch_tools()

        # Fetch available resources
        await self._fetch_resources()

        # Fetch available resource templates
        await self._fetch_resource_templates()

        self.initialized = True

    async def close(self) -> None:
        """Close the connection to the MCP server"""
        if self.writer:
            self.writer.close()
            if hasattr(self.writer, "wait_closed"):
                await self.writer.wait_closed()
        logger.info("Connection closed")

    async def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to the MCP server and return the response"""
        if not self.writer:
            raise Exception("Not connected to an MCP server")

        # Log the request if debug is enabled
        if os.environ.get("MCP_DEBUG"):
            logger.debug(f"Sending request: {json.dumps(request, indent=2)}")

        # Send the request
        if not self.writer:
            raise Exception("Writer not initialized")
        self.writer.write((json.dumps(request) + "\n").encode())
        await self.writer.drain()

        # Read the response
        if not self.reader:
            raise Exception("Reader not initialized")
        response_line = await self.reader.readline()
        if not response_line:
            raise Exception("Server closed connection")

        response_text = response_line.decode().strip()

        # Log the response if debug is enabled
        if os.environ.get("MCP_DEBUG"):
            try:
                response_json = json.loads(response_text)
                logger.debug(
                    f"Received response: {json.dumps(response_json, indent=2)}"
                )
            except json.JSONDecodeError:
                logger.debug(f"Received non-JSON response: {response_text}")

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {response_text}")
            raise Exception(f"Invalid JSON response: {e}")

    async def _fetch_tools(self) -> None:
        """Fetch available tools from the server"""
        request = {"jsonrpc": "2.0", "id": "tools1", "method": "listTools"}

        response = await self._send_request(request)
        if "error" in response:
            logger.warning(f"Failed to fetch tools: {response['error']['message']}")
            return

        result = response.get("result", {})
        tools = result.get("tools", [])

        for tool in tools:
            name = tool.get("name")
            if name:
                self.tools[name] = tool

        logger.info(f"Fetched {len(self.tools)} tools")

    async def _fetch_resources(self) -> None:
        """Fetch available resources from the server"""
        request = {"jsonrpc": "2.0", "id": "resources1", "method": "listResources"}

        response = await self._send_request(request)
        if "error" in response:
            logger.warning(f"Failed to fetch resources: {response['error']['message']}")
            return

        result = response.get("result", {})
        resources = result.get("resources", [])

        for resource in resources:
            id = resource.get("resourceId")
            if id:
                self.resources[id] = resource

        logger.info(f"Fetched {len(self.resources)} resources")

    async def _fetch_resource_templates(self) -> None:
        """Fetch available resource templates from the server"""
        request = {
            "jsonrpc": "2.0",
            "id": "templates1",
            "method": "listResourceTemplates",
        }

        response = await self._send_request(request)
        if "error" in response:
            logger.warning(
                f"Failed to fetch resource templates: {response['error']['message']}"
            )
            return

        result = response.get("result", {})
        templates = result.get("resourceTemplates", [])

        for template in templates:
            id = template.get("resourceId")
            if id:
                self.resource_templates[id] = template

        logger.info(f"Fetched {len(self.resource_templates)} resource templates")

    async def invoke_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke a tool on the MCP server"""
        if not self.initialized:
            raise Exception("Client not initialized")

        if name not in self.tools:
            raise Exception(f"Tool {name} not available")

        request = {
            "jsonrpc": "2.0",
            "id": f"invoke_{name}",
            "method": "invoke",
            "params": {"name": name, "arguments": arguments},
        }

        response = await self._send_request(request)
        if "error" in response:
            raise Exception(f"Tool invocation failed: {response['error']['message']}")

        return response.get("result", {})

    async def get_resource(self, resource_id: str) -> str:
        """Get a resource from the MCP server"""
        if not self.initialized:
            raise Exception("Client not initialized")

        if resource_id not in self.resources:
            logger.warning(f"Resource {resource_id} not listed, but trying anyway")

        request = {
            "jsonrpc": "2.0",
            "id": f"get_resource_{resource_id}",
            "method": "getResource",
            "params": {"resourceId": resource_id},
        }

        response = await self._send_request(request)
        if "error" in response:
            raise Exception(f"Resource request failed: {response['error']['message']}")

        result = response.get("result", {})
        resource = result.get("resource", {})

        return resource.get("content", "")

    async def create_resource_from_template(
        self, template_id: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a resource from a template"""
        if not self.initialized:
            raise Exception("Client not initialized")

        if template_id not in self.resource_templates:
            raise Exception(f"Template {template_id} not available")

        request = {
            "jsonrpc": "2.0",
            "id": f"create_resource_{template_id}",
            "method": "createResourceFromTemplate",
            "params": {"resourceId": template_id, "arguments": arguments},
        }

        response = await self._send_request(request)
        if "error" in response:
            raise Exception(f"Resource creation failed: {response['error']['message']}")

        result = response.get("result", {})
        return result.get("resource", {})


async def main():
    """Example usage of the MCPClient"""
    # Create a client
    client = MCPClient()

    try:
        # Connect to the server
        await client.connect_stdio()

        # Example tool invocation
        if "search" in client.tools:
            search_results = await client.invoke_tool("search", {"query": "requests"})
            print(f"Search results: {search_results}")
        else:
            print("Search tool not available")

        # Example resource retrieval
        if "popular_packages" in client.resources:
            content = await client.get_resource("popular_packages")
            print(f"Resource content: {content}")
        else:
            print("Popular packages resource not available")

        # Example resource creation from template
        if "package_template" in client.resource_templates:
            resource = await client.create_resource_from_template(
                "package_template",
                {"package_name": "my_package", "author": "MCP Client"},
            )
            print(f"Created resource: {resource}")
        else:
            print("Package template not available")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
