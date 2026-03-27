"""
Integration tests for MCP endpoint.

Tests the FastAPI /mcp endpoint with MCP protocol dispatch.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


# =============================================================================
# Test: valid MCP request dispatches to search_providers
# =============================================================================
def test_mcp_tool_call_dispatches_to_search_providers():
    """When I POST a valid MCP tools/call request for the search_providers tool
    to /mcp, the request is dispatched to the correct tool function and the
    JSON response includes a structured MCP-style envelope and the provider
    list from that tool."""
    from app.main import app, TOOL_REGISTRY

    # Mock the search_providers function
    mock_providers = [
        {
            "npi": "1234567890",
            "basic": {"first_name": "John", "last_name": "Smith"},
            "addresses": [{"city": "Hartford", "state": "CT"}]
        }
    ]

    async def mock_search_fn(**kwargs):
        return mock_providers

    # Patch the tool registry directly
    original_tool = TOOL_REGISTRY["search_providers"]
    TOOL_REGISTRY["search_providers"] = mock_search_fn

    try:
        client = TestClient(app)
        response = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search_providers",
                "arguments": {
                    "state": "CT",
                    "limit": 10
                }
            }
        })

        assert response.status_code == 200
        data = response.json()

        # Check MCP envelope structure
        assert "jsonrpc" in data
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "result" in data

        # Check result contains tool response
        result = data["result"]
        assert "content" in result
        assert isinstance(result["content"], list)
    finally:
        # Restore original tool
        TOOL_REGISTRY["search_providers"] = original_tool


# =============================================================================
# Test: unknown tool returns error envelope
# =============================================================================
def test_mcp_unknown_tool_returns_error_envelope():
    """When I call /mcp with an unknown tool name, I get a clear error
    envelope describing UNKNOWN_TOOL."""
    from app.main import app

    client = TestClient(app)
    response = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "nonexistent_tool",
            "arguments": {}
        }
    })

    assert response.status_code == 200
    data = response.json()

    # Check error envelope
    assert "error" in data
    error = data["error"]
    assert error["code"] == -32601  # MCP error code for unknown method
    assert "UNKNOWN_TOOL" in error["message"]


# =============================================================================
# Test: malformed request returns HTTP 400
# =============================================================================
def test_mcp_malformed_request_returns_400():
    """When I call /mcp with a malformed request body (missing required
    fields), I get an HTTP 400 status."""
    from app.main import app

    client = TestClient(app)

    # Missing jsonrpc field
    response = client.post("/mcp", json={
        "id": 1,
        "method": "tools/call"
    })

    assert response.status_code == 400

    # Missing method field
    response = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1
    })

    assert response.status_code == 400


# =============================================================================
# Test: missing required arguments returns validation error
# =============================================================================
def test_mcp_missing_required_param_returns_validation_error():
    """When I call /mcp with missing required tool arguments, I get a
    validation error (400 or 422) describing which parameter is missing."""
    from app.main import app

    client = TestClient(app)

    # Missing 'arguments' object entirely
    response = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "search_providers"
            # Missing arguments
        }
    })

    # Should return validation error
    assert response.status_code == 400
    data = response.json()

    # Should describe the validation issue
    assert "error" in data or "detail" in data


# =============================================================================
# Test: ping method returns valid response
# =============================================================================
def test_mcp_ping_returns_pong():
    """When I call /mcp with method='ping', I get a valid JSON-RPC response
    with result (standard MCP ping/pong)."""
    from app.main import app

    client = TestClient(app)
    response = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "ping"
    })

    assert response.status_code == 200
    data = response.json()

    # Check valid JSON-RPC response
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 1
    assert "result" in data


# =============================================================================
# Test: initialize method returns protocol info
# =============================================================================
def test_mcp_initialize_returns_protocol_info():
    """When I call /mcp with method='initialize', I get protocol capabilities
    and server info."""
    from app.main import app

    client = TestClient(app)
    response = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0.0"}
        }
    })

    assert response.status_code == 200
    data = response.json()

    # Check valid JSON-RPC response
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 1
    assert "result" in data

    # Check server info in result
    result = data["result"]
    assert "protocolVersion" in result
    assert "capabilities" in result
    assert "serverInfo" in result


# =============================================================================
# Test: tools/list method returns available tools
# =============================================================================
def test_mcp_tools_list_returns_tool_definitions():
    """When I call /mcp with method='tools/list', I get a list of available
    MCP tools."""
    from app.main import app

    client = TestClient(app)
    response = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    })

    assert response.status_code == 200
    data = response.json()

    assert data["jsonrpc"] == "2.0"
    assert "result" in data

    result = data["result"]
    assert "tools" in result
    assert isinstance(result["tools"], list)

    # Should have our registered tools
    tool_names = [t["name"] for t in result["tools"]]
    assert "search_providers" in tool_names
    assert "get_provider_by_npi" in tool_names
    assert "validate_npi" in tool_names
    assert "get_npi_for_provider" in tool_names


# =============================================================================
# Test: get_provider_by_npi dispatches correctly
# =============================================================================
def test_mcp_dispatches_get_provider_by_npi():
    """When I call /mcp with get_provider_by_npi tool, it dispatches correctly."""
    from app.main import app, TOOL_REGISTRY

    mock_result = {"found": True, "npi": "1234567893", "data": {}}

    async def mock_fn(**kwargs):
        return mock_result

    original_tool = TOOL_REGISTRY["get_provider_by_npi"]
    TOOL_REGISTRY["get_provider_by_npi"] = mock_fn

    try:
        client = TestClient(app)
        response = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "get_provider_by_npi",
                "arguments": {"npi": "1234567893"}
            }
        })

        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["content"][0]["found"] is True
    finally:
        TOOL_REGISTRY["get_provider_by_npi"] = original_tool


# =============================================================================
# Test: validate_npi dispatches correctly
# =============================================================================
def test_mcp_dispatches_validate_npi():
    """When I call /mcp with validate_npi tool, it dispatches correctly."""
    from app.main import app, TOOL_REGISTRY

    mock_result = {"valid": True, "npi": "1000000023"}

    async def mock_fn(**kwargs):
        return mock_result

    original_tool = TOOL_REGISTRY["validate_npi"]
    TOOL_REGISTRY["validate_npi"] = mock_fn

    try:
        client = TestClient(app)
        response = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "validate_npi",
                "arguments": {"npi": "1000000023"}
            }
        })

        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["content"][0]["valid"] is True
    finally:
        TOOL_REGISTRY["validate_npi"] = original_tool


# =============================================================================
# Test: get_npi_for_provider dispatches correctly
# =============================================================================
def test_mcp_dispatches_get_npi_for_provider():
    """When I call /mcp with get_npi_for_provider tool, it dispatches correctly."""
    from app.main import app, TOOL_REGISTRY

    mock_result = {"found": True, "npi": "1234567893"}

    async def mock_fn(**kwargs):
        return mock_result

    original_tool = TOOL_REGISTRY["get_npi_for_provider"]
    TOOL_REGISTRY["get_npi_for_provider"] = mock_fn

    try:
        client = TestClient(app)
        response = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "get_npi_for_provider",
                "arguments": {"first_name": "John", "last_name": "Smith"}
            }
        })

        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["content"][0]["found"] is True
    finally:
        TOOL_REGISTRY["get_npi_for_provider"] = original_tool


# =============================================================================
# Test: health_check_endpoint
# =============================================================================
def test_health_check_returns_healthy():
    """Health endpoint returns healthy status."""
    from app.main import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


# =============================================================================
# Test: root_endpoint_returns_info
# =============================================================================
def test_root_endpoint_returns_info():
    """Root endpoint returns server info."""
    from app.main import app

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "NPPES MCP Server"
    assert "/mcp" in data["mcp_endpoint"]


# =============================================================================
# Test: tools/list includes parameter descriptions
# =============================================================================
def test_mcp_tools_list_includes_param_descriptions():
    """When I call /mcp with method='tools/list', each tool parameter
    includes a helpful description."""
    from app.main import app

    client = TestClient(app)
    response = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    })

    assert response.status_code == 200
    data = response.json()

    result = data["result"]
    tools = {t["name"]: t for t in result["tools"]}

    # Check search_providers has descriptions
    search_tool = tools["search_providers"]
    props = search_tool["inputSchema"]["properties"]

    # Each parameter should have a description
    if "state" in props:
        assert "description" in props["state"]
        assert "Two-letter" in props["state"]["description"] or "state code" in props["state"]["description"]

    if "name" in props:
        assert "description" in props["name"]


# =============================================================================
# Test: tools/list includes validation patterns for key parameters
# =============================================================================
def test_mcp_tools_list_includes_validation_patterns():
    """When I call /mcp with method='tools/list', NPI and state parameters
    include regex patterns for validation."""
    from app.main import app

    client = TestClient(app)
    response = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    })

    assert response.status_code == 200
    data = response.json()

    result = data["result"]
    tools = {t["name"]: t for t in result["tools"]}

    # Check validate_npi has NPI pattern
    validate_tool = tools["validate_npi"]
    npi_props = validate_tool["inputSchema"]["properties"]["npi"]
    assert "pattern" in npi_props
    assert npi_props["pattern"] == "^[0-9]{10}$"
    assert "description" in npi_props
    assert "10 digits" in npi_props["description"]

    # Check search_providers has state pattern
    search_tool = tools["search_providers"]
    props = search_tool["inputSchema"]["properties"]
    if "state" in props:
        assert "pattern" in props["state"]
        assert props["state"]["pattern"] == "^[A-Z]{2}$"


# =============================================================================
# Test: tools/list correctly identifies required vs optional parameters
# =============================================================================
def test_mcp_tools_list_marks_required_params():
    """When I call /mcp with method='tools/list', required parameters
    are listed separately and optional params have 'optional: true'."""
    from app.main import app

    client = TestClient(app)
    response = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    })

    assert response.status_code == 200
    data = response.json()

    result = data["result"]
    tools = {t["name"]: t for t in result["tools"]}

    # validate_npi should have 'npi' as required
    validate_tool = tools["validate_npi"]
    assert validate_tool["inputSchema"]["required"] == ["npi"]
    props = validate_tool["inputSchema"]["properties"]
    assert "optional" not in props["npi"] or props["npi"]["optional"] is False

    # search_providers should have no required params (all optional with defaults)
    search_tool = tools["search_providers"]
    props = search_tool["inputSchema"]["properties"]
    if search_tool["inputSchema"]["required"] is not None:
        # If there are required params, check they don't have defaults
        for param_name in search_tool["inputSchema"]["required"]:
            if param_name in props:
                assert "default" not in props[param_name]


# =============================================================================
# Test: Invalid JSON body returns 400
# =============================================================================
def test_mcp_invalid_json_returns_400():
    """When I send a request with invalid JSON to /mcp, it returns 400."""
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/mcp",
        content=b"not valid json",
        headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 400
    assert "Invalid JSON" in response.json()["detail"]


# =============================================================================
# Test: Missing jsonrpc field returns 400
# =============================================================================
def test_mcp_missing_jsonrpc_field_returns_400():
    """When I call /mcp without the jsonrpc field, it returns 400."""
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post("/mcp", json={
        "id": 1,
        "method": "ping",
        "params": {}
    })

    assert response.status_code == 400
    assert "jsonrpc" in response.json()["detail"]


# =============================================================================
# Test: Invalid jsonrpc version returns 400
# =============================================================================
def test_mcp_invalid_jsonrpc_version_returns_400():
    """When I call /mcp with wrong jsonrpc version, it returns 400."""
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post("/mcp", json={
        "jsonrpc": "1.0",
        "id": 1,
        "method": "ping",
        "params": {}
    })

    assert response.status_code == 400
    assert "Invalid jsonrpc version" in response.json()["detail"]


# =============================================================================
# Test: Missing method field returns 400
# =============================================================================
def test_mcp_missing_method_returns_400():
    """When I call /mcp without a method field, it returns 400."""
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1
    })

    assert response.status_code == 400
    assert "Missing method" in response.json()["detail"]


# =============================================================================
# Test: tools/call missing params returns 400
# =============================================================================
def test_mcp_tools_call_missing_params_returns_400():
    """When I call /mcp with method='tools/call' but no params, it returns 400."""
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call"
    })

    assert response.status_code == 400
    assert "Missing params" in response.json()["detail"]


# =============================================================================
# Test: tools/call with non-dict params returns 400
# =============================================================================
def test_mcp_tools_call_params_not_object_returns_400():
    """When I call /mcp with method='tools/call' and params as array, it returns 400."""
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": ["invalid"]
    })

    assert response.status_code == 400
    assert "Params must be an object" in response.json()["detail"]


# =============================================================================
# Test: tools/call missing tool name returns 400
# =============================================================================
def test_mcp_tools_call_missing_tool_name_returns_400():
    """When I call /mcp with method='tools/call' but no tool name, it returns 400."""
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"arguments": {}}
    })

    assert response.status_code == 400
    assert "Missing tool name" in response.json()["detail"]


# =============================================================================
# Test: tools/call missing arguments returns 400
# =============================================================================
def test_mcp_tools_call_missing_arguments_returns_400():
    """When I call /mcp with method='tools/call' but no arguments, it returns 400."""
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "search_providers"}
    })

    assert response.status_code == 400
    assert "arguments" in response.json()["detail"]


# =============================================================================
# Test: Unknown tool returns error envelope (not HTTP error)
# =============================================================================
def test_mcp_unknown_tool_returns_error_envelope():
    """When I call /mcp with a non-existent tool, it returns JSON-RPC error, not 400."""
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 42,
        "method": "tools/call",
        "params": {
            "name": "nonexistent_tool",
            "arguments": {}
        }
    })

    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert data["id"] == 42
    assert data["error"]["code"] == -32601
    assert "UNKNOWN_TOOL" in data["error"]["message"]


# =============================================================================
# Test: parse_docstring_params handles function without Args section
# =============================================================================
def test_parse_docstring_params_no_args_section():
    """When a function has no Args section, parse_docstring_params returns empty dict."""
    from app.main import parse_docstring_params

    def func_no_args():
        """Simple function with no Args."""
        pass

    result = parse_docstring_params(func_no_args)
    assert result == {}


# =============================================================================
# Test: parse_docstring_params handles function with Args section
# =============================================================================
def test_parse_docstring_params_with_args():
    """When a function has Args section, parse_docstring_params extracts params."""
    from app.main import parse_docstring_params

    def func_with_args():
        """Function with Args.

        Args:
            name: Provider name
            city: City filter
        """
        pass

    result = parse_docstring_params(func_with_args)
    assert "name" in result
    assert "Provider name" in result["name"]
    assert "city" in result
    assert "City filter" in result["city"]


# =============================================================================
# Test: parse_docstring_params with type annotations
# =============================================================================
def test_parse_docstring_params_with_type_annotations():
    """When Args section has type annotations, they are stripped."""
    from app.main import parse_docstring_params

    def func_with_types():
        """Function with typed Args.

        Args:
            name: str - Provider name
            npi: int - NPI number
        """
        pass

    result = parse_docstring_params(func_with_types)
    assert "name" in result
    assert "str - " not in result["name"]
    assert "Provider name" in result["name"]


# =============================================================================
# Test: tools/list includes type annotations for parameters
# =============================================================================
def test_mcp_tools_list_includes_type_annotations():
    """When I call /mcp with method='tools/list', parameters include type info."""
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    })

    assert response.status_code == 200
    data = response.json()

    result = data["result"]
    tools = {t["name"]: t for t in result["tools"]}

    # Check validate_npi has type annotation for npi
    validate_tool = tools["validate_npi"]
    props = validate_tool["inputSchema"]["properties"]
    assert "npi" in props
    assert "type" in props["npi"]


# =============================================================================
# Test: Unknown method returns error envelope (not HTTP error)
# =============================================================================
def test_mcp_unknown_method_returns_error_envelope():
    """When I call /mcp with an unknown method, it returns JSON-RPC error envelope."""
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 99,
        "method": "unknown_method",
        "params": {}
    })

    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert data["id"] == 99
    assert data["error"]["code"] == -32601
    assert "Unknown method" in data["error"]["message"]
