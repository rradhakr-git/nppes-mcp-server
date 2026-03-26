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
