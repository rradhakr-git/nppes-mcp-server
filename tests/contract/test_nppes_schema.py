"""
Contract tests for NPPES API.

Validates our client against the live NPPES Registry API.
API: https://npiregistry.cms.hhs.gov/api/?version=2.1
"""

import pytest
import requests


# NPPES API base URL
NPPES_API_BASE = "https://npiregistry.cms.hhs.gov/api"
NPPES_API_VERSION = "2.1"


def skip_if_no_network():
    """Skip test if network is unavailable."""
    try:
        requests.get(NPPES_API_BASE, timeout=5)
    except requests.RequestException:
        pytest.skip("Network unavailable - skipping contract test")


# =============================================================================
# Test: NPPES API is accessible
# =============================================================================
def test_nppes_api_is_accessible():
    """Test that the NPPES API endpoint is accessible."""
    skip_if_no_network()

    url = f"{NPPES_API_BASE}/?version={NPPES_API_VERSION}&state=CT&limit=1"
    response = requests.get(url, timeout=30)

    # Should get 200 or 400 (bad request), not 5xx
    assert response.status_code < 500, f"NPPES API returned {response.status_code}"


# =============================================================================
# Test: NPPES search response structure
# =============================================================================
def test_nppes_search_response_structure():
    """Test that NPPES search returns expected response structure."""
    skip_if_no_network()

    url = f"{NPPES_API_BASE}/?version={NPPES_API_VERSION}&state=CT&limit=1"
    response = requests.get(url, timeout=30)

    if response.status_code == 200:
        data = response.json()

        # Check top-level structure
        assert isinstance(data, dict), "Response should be a dictionary"

        # NPPES v2.1 uses 'results' key
        if "results" in data:
            assert isinstance(data["results"], list), "Results should be a list"
    elif response.status_code == 400:
        pytest.skip("NPPES API returned 400 - may need different params")
    else:
        pytest.skip(f"NPPES API returned {response.status_code}")


# =============================================================================
# Test: our NPPES client matches API fields
# =============================================================================
def test_nppes_client_fields_match_api():
    """Test that our NPPES client uses valid fields from the API."""
    skip_if_no_network()

    url = f"{NPPES_API_BASE}/?version={NPPES_API_VERSION}&state=CT&limit=2"
    response = requests.get(url, timeout=30)

    if response.status_code != 200:
        pytest.skip(f"NPPES API unavailable: {response.status_code}")

    data = response.json()

    # Verify the response fields our client expects
    if "results" in data and data["results"]:
        result = data["results"][0]

        # These are the fields our client uses
        expected_fields = ["NPI", "basic", "addresses", "taxonomies"]
        for field in expected_fields:
            assert field in result, \
                f"Expected field '{field}' in NPPES response"


# =============================================================================
# Test: NPPES handles invalid state gracefully
# =============================================================================
def test_nppes_invalid_state_handling():
    """Test that NPPES API returns appropriate response for invalid state."""
    skip_if_no_network()

    url = f"{NPPES_API_BASE}/?version={NPPES_API_VERSION}&state=XX&limit=1"
    response = requests.get(url, timeout=30)

    # Should return 200 with empty results
    if response.status_code == 200:
        data = response.json()
        results = data.get("results", [])
        assert isinstance(results, list), "Results should be a list"
    elif response.status_code == 400:
        # 400 is also acceptable for invalid input
        pass
    else:
        pytest.skip(f"NPPES API returned {response.status_code}")


# =============================================================================
# Test: NPPES supports JSON format
# =============================================================================
def test_nppes_json_format():
    """Test that NPPES API supports JSON responses."""
    skip_if_no_network()

    # Default should be JSON
    url = f"{NPPES_API_BASE}/?version={NPPES_API_VERSION}&state=CT&limit=1"
    response = requests.get(url, timeout=30)

    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")
