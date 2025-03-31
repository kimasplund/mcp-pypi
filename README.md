# PyPI MCP Server

An MCP (Model Controlled Program) server that provides tools for interacting with the Python Package Index (PyPI). This tool integrates with Claude, Gordon, Cursor, or any other AI assistant that supports the MCP protocol.

## Features

The PyPI MCP server provides the following capabilities:

### Core Features

- **Package Information**: Get detailed information about Python packages
- **Version Management**: Retrieve and compare package versions
- **Download URL Generation**: Generate predictable download URLs
- **Search**: Search for packages on PyPI
- **Dependencies**: Get package dependencies and their details

### Enhanced Features

- **Package Statistics**: Get download statistics for packages
- **Dependency Visualization**: Generate and visualize dependency trees
- **Documentation Discovery**: Find documentation URLs for packages
- **Requirements Analysis**: Check requirements files for outdated packages
- **Caching**: Local response caching with ETag support
- **User-Agent Configuration**: Proper user-agent with contact information

## MCP Compliance

This tool is fully compliant with [Anthropic's Model Context Protocol](https://modelcontextprotocol.io) standards:

- **Standardized Prompt Templates**: Includes templates for common PyPI workflows
- **Consistent Error Handling**: All errors follow the MCP standard format with clear error codes
- **Well-Documented Responses**: All tool responses have documented schemas
- **Secure File Operations**: Path validation and proper permissions handling
- **Version Information**: Explicit versioning for better compatibility

## Installation

### Build Docker Image

```bash
docker build -t pypi-mcp .
```

### Set Up MCP Server

To run the PyPI MCP server and register it with the MCP Docker server:

```bash
docker run --rm -i --pull always -q --init \
  --name pypi-mcp-server \
  -v /var/run/docker.sock:/var/run/docker.sock \
  --mount type=volume,source=docker-prompts,target=/prompts \
  -v $(pwd)/pypi.md:/pypi.md \
  -p 8812:8812 \
  mcp/docker:latest serve --mcp --port 8812 --register file:///pypi.md
```

### Run Directly (Without Docker)

You can also run the PyPI tools directly from your local directory:

```bash
# Install dependencies
pip install requests beautifulsoup4 packaging exceptiongroup plotly

# Run a specific command
python pypi_tools.py get_package_info requests
python pypi_tools.py get_documentation_url package_name=flask
python pypi_tools.py get_dependency_tree package_name=django depth=2
```

### Configure Cursor

The MCP configuration is stored in `~/.cursor/mcp.json`. Make sure it includes:

```json
{
  "mcpServers": {
    "PYPI_MCP": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "alpine/socat", "STDIO", "TCP:host.docker.internal:8812"]
    }
  }
}
```

## Available Tools

### Package Information

- **get_package_info**: Get detailed package information
- **get_latest_version**: Get the latest version of a package
- **get_package_releases**: Get all releases of a package
- **get_release_urls**: Get download URLs for a release
- **check_package_exists**: Check if a package exists
- **get_package_metadata**: Get detailed package metadata

### Download URLs

- **get_source_url**: Generate source package URL
- **get_wheel_url**: Generate wheel package URL

### RSS Feeds

- **get_newest_packages**: Get newest packages feed
- **get_latest_updates**: Get latest updates feed
- **get_project_releases**: Get releases feed for a specific project

### Search and Comparison

- **search_packages**: Search for packages
- **compare_versions**: Compare two versions

### Dependencies

- **get_dependencies**: Get package dependencies
- **get_dependency_tree**: Get dependency tree with visualization

### Documentation and Statistics

- **get_documentation_url**: Get documentation URL and summary
- **get_package_stats**: Get package download statistics

### Requirements Analysis

- **check_requirements_file**: Check requirements file for outdated packages

## Error Handling

All tools use standardized error responses with the following error codes:

- `not_found`: Package or resource not found
- `invalid_input`: Invalid parameter value provided
- `network_error`: Error communicating with PyPI
- `parse_error`: Error parsing response from PyPI
- `file_error`: Error accessing or reading a file
- `permission_error`: Insufficient permissions

## Examples

### Get Package Information
```
get_package_info package_name=requests
```

### Get Package Statistics
```
get_package_stats package_name=django
```

### Get Dependency Tree
```
get_dependency_tree package_name=flask depth=2
```

### Check Requirements File
```
check_requirements_file file_path=/path/to/requirements.txt
```

## License

MIT

## Author

Kim Asplund (kim.asplund@gmail.com) 