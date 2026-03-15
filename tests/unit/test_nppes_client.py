"""
Unit tests for NPPES client.

Tests the async httpx client that interfaces with api.cms.gov.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.clients.nppes import NPPESClient


# =============================================================================
# Test: search_returns_providers_for_valid_state
# =============================================================================
@pytest.mark.asyncio
async def test_search_returns_providers_for_valid_state():
    """Test that search returns provider list for valid state query."""
    client = NPPESClient()

    # Mock httpx response with valid provider data
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result_count": 1,
        "results": [
            {
                "npi": "1234567890",
                "basic": {
                    "first_name": "John",
                    "last_name": "Smith",
                },
                "addresses": [
                    {
                        "city": "Hartford",
                        "state": "CT",
                    }
                ],
                "taxonomies": [
                    {
                        "code": "207Q00000X",
                        "desc": "Family Medicine",
                    }
                ],
            }
        ]
    }

    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await client.search(state="CT")

    assert len(result) == 1
    assert result[0]["npi"] == "1234567890"
    assert result[0]["basic"]["first_name"] == "John"
    await client.close()


# =============================================================================
# Test: retries_on_503
# =============================================================================
@pytest.mark.asyncio
async def test_retries_on_503():
    """Test that client retries on 503 server error."""
    client = NPPESClient()

    # First two responses are 503, third succeeds
    error_response = MagicMock()
    error_response.status_code = 503

    success_response = MagicMock()
    success_response.status_code = 200
    success_response.json.return_value = {"result_count": 0, "results": []}

    # Mock returns 503 twice, then 200
    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [error_response, error_response, success_response]

        # Should retry and eventually succeed
        result = await client.search(state="CT")

    # Should have made 3 attempts
    assert mock_get.call_count == 3
    assert result == []
    await client.close()


# =============================================================================
# Test: raises_on_timeout
# =============================================================================
@pytest.mark.asyncio
async def test_raises_on_timeout():
    """Test that client raises TimeoutError on timeout."""
    client = NPPESClient()

    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Request timed out")

        with pytest.raises(httpx.TimeoutException):
            await client.search(state="CT")

    await client.close()


# =============================================================================
# Test: returns_empty_list_on_404
# =============================================================================
@pytest.mark.asyncio
async def test_returns_empty_list_on_404():
    """Test that client returns empty list on 404 not found."""
    client = NPPESClient()

    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await client.search(state="XX")  # Invalid state code

    assert result == []
    await client.close()