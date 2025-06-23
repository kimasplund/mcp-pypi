# Protocol Version Negotiation

This document describes the protocol version negotiation system implemented in the MCP-PyPI project, explaining the concepts, implementation details, and usage patterns.

## Overview

The Model Context Protocol (MCP) uses semantic versioning with a date-based format (`YYYY-MM-DD`) to indicate protocol compatibility. Different protocol versions may support different capabilities, and proper negotiation is essential for ensuring compatibility between clients and servers.

The protocol version negotiation module (`utils/protocol.py`) provides utilities for:

1. Defining protocol versions and their capabilities
2. Checking compatibility between versions
3. Negotiating the protocol version between client and server
4. Extracting version information from error messages
5. Determining the minimum version required for specific capabilities

## Protocol Versions and Capabilities

### Version Definition

Each protocol version is defined with a set of capabilities it supports:

```python
PROTOCOL_VERSIONS = {
    "2023-12-01": ProtocolVersion(
        "2023-12-01",
        {
            ProtocolCapability.INITIALIZE,
            ProtocolCapability.LIST_TOOLS,
            # ... other capabilities ...
        },
        is_deprecated=True,
        successor="2024-11-05"
    ),
    # ... other versions ...
}
```

### Capabilities

Capabilities are defined as an Enum, categorizing different functionalities:

```python
class ProtocolCapability(Enum):
    # Core capabilities
    INITIALIZE = auto()
    LIST_TOOLS = auto()
    INVOKE_TOOL = auto()
    
    # Resource handling
    LIST_RESOURCES = auto()
    GET_RESOURCE = auto()
    # ... other capabilities ...
}
```

## Negotiation Process

The protocol negotiation process follows these steps:

1. **Client Initialization**: Client sends an `initialize` request with its preferred protocol version
2. **Server Validation**: Server checks if it supports the requested version
3. **Negotiation Response**:
   - If the version is supported, the server accepts it
   - If not supported but has a compatible alternative, the server suggests it
   - If incompatible, the server returns an error with supported versions

## Implementation

### Server-Side

During initialization, the server uses `negotiate_version()` to check compatibility:

```python
def handle_initialize(client_version):
    result = negotiate_version(client_version, SUPPORTED_VERSIONS)
    
    if result["success"]:
        # Use negotiated version
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": result["version"],
                # ... other info ...
            }
        }
    else:
        # Return error
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "error": result["error"]
        }
```

### Client-Side

Clients handle version negotiation errors and adapt accordingly:

```python
async def initialize(self, protocol_version):
    response = await self.send_initialize(protocol_version)
    
    if "error" in response:
        required_version = extract_required_version_from_error(response["error"])
        if required_version:
            # Retry with required version
            return await self.initialize(required_version)
    
    # Use negotiated version
    self.protocol_version = response["result"]["protocolVersion"]
    return True
```

## Usage

### Checking Version Compatibility

```python
# Check if version supports required capabilities
compatibility = check_version_compatibility(
    requested_version="2023-12-01",
    required_capabilities={
        ProtocolCapability.SSE_SUPPORT,
        ProtocolCapability.BINARY_DATA
    }
)

if not compatibility["compatible"]:
    # Use suggested version
    suggested_version = compatibility["suggested_version"]
```

### Finding Minimum Version

```python
# Find minimum version supporting specific capabilities
min_version = get_minimum_version_for_capabilities({
    ProtocolCapability.STREAMING_RESULTS,
    ProtocolCapability.SSE_SUPPORT
})
```

### Error Formatting

```python
# Format standard error for version mismatch
error = format_version_error(
    client_version="2023-01-01",
    server_versions=["2024-11-05", "2025-03-26"]
)
```

## Best Practices

1. **Always negotiate versions during initialization**
2. **Use capabilities to determine functional compatibility**
3. **Handle version errors gracefully with automatic retry**
4. **Document version requirements for clients**
5. **Provide clear error messages for version mismatch**

## Testing

The module includes comprehensive tests in `tests/test_protocol.py` covering:
- Protocol version definitions
- Version compatibility checking
- Version negotiation
- Extracting versions from error messages
- Finding minimum versions for capabilities
- Error formatting

## Future Extensions

The protocol version negotiation system is designed to be extended as new protocol versions are released:

1. Add new versions to `PROTOCOL_VERSIONS`
2. Define new capabilities in `ProtocolCapability`
3. Update deprecated versions with successors
4. Extend tests for new versions

## Conclusion

Protocol version negotiation is a critical component of MCP communication, ensuring that clients and servers can work together despite differences in implementation details and supported features. The centralized approach simplifies management and reduces errors across different transport implementations. 