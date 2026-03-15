"""
E2E tests for MCP server.

This file contains two types of tests:

1. Live server E2E tests (test_live_server_search_providers)
   - Requires a running MCP server
   - Set MCP_SERVER_URL environment variable:
     * CI: MCP_SERVER_URL=https://your-render-app.onrender.com
     * Local: MCP_SERVER_URL=http://127.0.0.1:8000 (with uvicorn running)
   - Skipped automatically if MCP_SERVER_URL is not set
   - Run locally:
     $ uvicorn app.main:app --host 127.0.0.1 --port 8000 &
     $ MCP_SERVER_URL=http://127.0.0.1:8000 pytest tests/e2e/test_mcp_client.py::test_live_server_search_providers -v

2. Integration tests (test_mcp_search_providers_full_flow, etc.)
   - Uses FastAPI TestClient, no external dependencies
   - Always runs in CI and local development
"""

import os
import pytest
import requests


# =============================================================================
# E2E: Live server test (requires MCP_SERVER_URL env var)
# =============================================================================


@pytest.mark.skipif(
    not os.getenv("MCP_SERVER_URL"),
    reason="MCP_SERVER_URL not set - run against live server"
)
def test_live_server_search_providers():
    """
    E2E test: sends real tools/call request to live MCP server.
    Asserts success JSON-RPC envelope with provider data.
    """
    base_url = os.getenv("MCP_SERVER_URL")
    if not base_url:
        pytest.skip("MCP_SERVER_URL not set")

    # Build full URL
    mcp_url = f"{base_url.rstrip('/')}/mcp"

    # Send real MCP request
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "search_providers",
            "arguments": {
                "state": "CT",
                "city": "Hartford",
                "limit": 3
            }
        }
    }

    response = requests.post(mcp_url, json=payload, timeout=30)

    # Assert HTTP success
    assert response.status_code == 200, f"Got status {response.status_code}: {response.text}"

    data = response.json()

    # Assert JSON-RPC envelope (no error)
    assert "error" not in data, f"Got error: {data.get('error')}"
    assert data.get("jsonrpc") == "2.0"

    # Assert result structure
    assert "result" in data, f"No result in response: {data}"
    assert "content" in data["result"], f"No content in result: {data['result']}"

    # Assert providers list with required fields
    providers = data["result"]["content"]
    assert isinstance(providers, list), f"Content should be list, got {type(providers)}"
    assert len(providers) > 0, "Expected at least one provider"

    # Check first provider has required fields (NPPES returns "number" for NPI)
    first = providers[0]
    assert "number" in first or "NPI" in first, f"Missing NPI number: {first.keys()}"
    assert "basic" in first, f"Missing basic info: {first.keys()}"

    print(f"✓ E2E test passed: got {len(providers)} providers from {base_url}")


# =============================================================================
# Integration-style tests using FastAPI TestClient
# (These run without MCP_SERVER_URL)
# =============================================================================

from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


# =============================================================================
# Test: full MCP flow for search_providers
# =============================================================================
def test_mcp_search_providers_full_flow():
    """
    End-to-end test: MCP request -> tool dispatch -> response envelope.
    This proves the /mcp endpoint correctly processes requests and returns
    proper JSON-RPC envelopes with provider data.
    """
    from app.main import app
    from app.clients.cache import CacheClient
    from app.clients.nppes import NPPESClient

    # Mock providers that would come from NPPES
    mock_providers = [
        {
            "number": "1234567890",
            "basic": {
                "first_name": "JOHN",
                "last_name": "SMITH",
                "status": "A"
            },
            "addresses": [
                {
                    "city": "HARTFORD",
                    "state": "CT",
                    "address_1": "123 MAIN ST"
                }
            ],
            "taxonomies": [
                {"code": "207Q00000X", "desc": "Family Medicine", "primary": True}
            ]
        }
    ]

    # Create mock clients that return test data
    mock_cache = MagicMock(spec=CacheClient)
    mock_cache.get_or_fetch = AsyncMock(return_value=mock_providers)
    mock_cache.build_search_key = MagicMock(return_value="test:key:ct")

    mock_nppes = MagicMock(spec=NPPESClient)
    mock_nppes.search = AsyncMock(return_value=mock_providers)

    # Patch the tool in the registry
    from app.main import TOOL_REGISTRY

    async def mock_search(**kwargs):
        return mock_providers

    original_tool = TOOL_REGISTRY["search_providers"]
    TOOL_REGISTRY["search_providers"] = mock_search

    try:
        client = TestClient(app)

        # Full MCP request
        response = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/call",
            "params": {
                "name": "search_providers",
                "arguments": {
                    "state": "CT",
                    "city": "Hartford",
                    "limit": 10
                }
            }
        })

        # Verify HTTP success
        assert response.status_code == 200

        # Verify JSON-RPC envelope
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 42

        # Verify result structure
        assert "result" in data
        assert "content" in data["result"]

        # Verify provider data
        providers = data["result"]["content"]
        assert len(providers) == 1
        assert providers[0]["number"] == "1234567890"
        assert providers[0]["basic"]["first_name"] == "JOHN"

    finally:
        # Restore original tool
        TOOL_REGISTRY["search_providers"] = original_tool


# =============================================================================
# Test: unknown tool error through full stack
# =============================================================================
def test_mcp_unknown_tool_error_flow():
    """Test that unknown tool requests produce proper error envelope."""
    from app.main import app

    client = TestClient(app)

    response = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "fake_tool",
            "arguments": {}
        }
    })

    assert response.status_code == 200
    data = response.json()

    # Verify error envelope
    assert "error" in data
    assert data["error"]["code"] == -32601
    assert "fake_tool" in data["error"]["message"]


# =============================================================================
# Test: malformed request through full stack
# =============================================================================
def test_mcp_malformed_request_error_flow():
    """Test that malformed requests return HTTP 400."""
    from app.main import app

    client = TestClient(app)

    # Missing required jsonrpc field
    response = client.post("/mcp", json={
        "id": 1,
        "method": "tools/call"
    })

    assert response.status_code == 400
    assert "detail" in response.json()
