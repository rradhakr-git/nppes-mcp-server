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
