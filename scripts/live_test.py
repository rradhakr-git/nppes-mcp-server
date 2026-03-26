#!/usr/bin/env python3
"""
Live testing script for NPPES MCP server.
Tests the deployed server via HTTP POST to /mcp endpoint.
"""

import requests
import json
import sys

BASE_URL = "https://nppes-mcp-server.onrender.com"


def mcp_request(method: str, params: dict = None, tool_name: str = None):
    """Send a JSON-RPC request to the MCP endpoint."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
    }

    if params:
        payload["params"] = params
    elif tool_name:
        payload["params"] = {"name": tool_name, "arguments": params or {}}

    response = requests.post(f"{BASE_URL}/mcp", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def test_ping():
    """Test ping method."""
    print("Testing ping...")
    result = mcp_request("ping")
    assert result["result"] == {}, "ping should return empty result"
    print("  ✓ ping OK")


def test_initialize():
    """Test initialize method."""
    print("Testing initialize...")
    result = mcp_request("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "live_test", "version": "1.0.0"}
    })
    assert "protocolVersion" in result["result"]
    assert "capabilities" in result["result"]
    print("  ✓ initialize OK")


def test_tools_list():
    """Test tools/list method."""
    print("Testing tools/list...")
    result = mcp_request("tools/list", {})
    tools = result["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "search_providers" in tool_names
    assert "get_provider_by_npi" in tool_names
    assert "validate_npi" in tool_names
    assert "get_npi_for_provider" in tool_names
    print(f"  ✓ tools/list OK ({len(tools)} tools)")


def test_search_providers():
    """Test search_providers tool."""
    print("Testing search_providers...")
    result = mcp_request("tools/call", {
        "name": "search_providers",
        "arguments": {"state": "CT", "limit": 5}
    })
    content = result["result"]["content"]
    assert len(content) > 0, "Should return providers"
    print(f"  ✓ search_providers OK ({len(content)} providers)")


def test_get_provider_by_npi():
    """Test get_provider_by_npi tool."""
    print("Testing get_provider_by_npi...")
    result = mcp_request("tools/call", {
        "name": "get_provider_by_npi",
        "arguments": {"npi": "1000000023"}
    })
    content = result["result"]["content"][0]
    assert content["found"] is True
    assert content["npi"] == "1000000023"
    print(f"  ✓ get_provider_by_npi OK")


def test_validate_npi_valid():
    """Test validate_npi with valid NPI."""
    print("Testing validate_npi (valid)...")
    result = mcp_request("tools/call", {
        "name": "validate_npi",
        "arguments": {"npi": "1000000023"}
    })
    content = result["result"]["content"][0]
    assert content["valid"] is True
    print("  ✓ validate_npi (valid) OK")


def test_validate_npi_invalid():
    """Test validate_npi with invalid NPI."""
    print("Testing validate_npi (invalid)...")
    result = mcp_request("tools/call", {
        "name": "validate_npi",
        "arguments": {"npi": "1234567890"}  # Invalid checksum
    })
    content = result["result"]["content"][0]
    assert content["valid"] is False
    print("  ✓ validate_npi (invalid) OK")


def test_get_npi_for_provider():
    """Test get_npi_for_provider tool."""
    print("Testing get_npi_for_provider...")
    result = mcp_request("tools/call", {
        "name": "get_npi_for_provider",
        "arguments": {"first_name": "John", "last_name": "Smith", "state": "CT"}
    })
    content = result["result"]["content"][0]
    assert content["found"] is True
    assert "npi" in content
    print(f"  ✓ get_npi_for_provider OK (found: {content['npi']})")


def main():
    print(f"Testing live server: {BASE_URL}\n")

    try:
        test_ping()
        test_initialize()
        test_tools_list()
        test_search_providers()
        test_get_provider_by_npi()
        test_validate_npi_valid()
        test_validate_npi_invalid()
        test_get_npi_for_provider()

        print("\n✓ All tests passed!")
        return 0
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())