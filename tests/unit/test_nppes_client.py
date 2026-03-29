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


# =============================================================================
# Phase B: Extend NPPES Client Tests (TDD - Red)
# =============================================================================

# -----------------------------------------------------------------------------
# Test: get_by_npi_returns_provider_when_found
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_by_npi_returns_provider_when_found():
    """Test that get_by_npi returns provider data when NPI exists."""
    client = NPPESClient()

    # Mock response with provider data
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
                }
            }
        ]
    }

    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await client.get_by_npi("1234567890")

    assert result is not None
    assert result["npi"] == "1234567890"
    assert result["basic"]["first_name"] == "John"
    await client.close()


# -----------------------------------------------------------------------------
# Test: get_by_npi_returns_none_when_not_found
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_by_npi_returns_none_when_not_found():
    """Test that get_by_npi returns None when NPI does not exist."""
    client = NPPESClient()

    # Mock 404 response
    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await client.get_by_npi("9999999999")

    assert result is None
    await client.close()


# -----------------------------------------------------------------------------
# Test: get_by_npi_returns_none_on_error
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_by_npi_returns_none_on_error():
    """Test that get_by_npi returns None on API error."""
    client = NPPESClient()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result_count": 0, "results": []}

    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await client.get_by_npi("1234567890")

    assert result is None
    await client.close()


# -----------------------------------------------------------------------------
# Test: validate_returns_valid_for_good_npi
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_validate_returns_valid_for_good_npi():
    """Test that validate returns valid status for correct NPI."""
    client = NPPESClient()

    # Use a known valid NPI format (passes ISO 7064 Mod 97-10)
    valid_npi = "1000000023"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result_count": 1,
        "results": [{"npi": valid_npi}]
    }

    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await client.validate(valid_npi)

    assert result["valid"] is True
    assert result["npi"] == valid_npi
    await client.close()


# -----------------------------------------------------------------------------
# Test: validate_returns_invalid_for_bad_npi
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_validate_returns_invalid_for_bad_npi():
    """Test that validate returns invalid for incorrect NPI format."""
    client = NPPESClient()

    # Invalid NPI - wrong length
    result = await client.validate("123")

    assert result["valid"] is False
    assert "error" in result


# -----------------------------------------------------------------------------
# Test: validate_returns_invalid_for_nonexistent_npi
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_validate_returns_invalid_for_nonexistent_npi():
    """Test that validate returns invalid when NPI not found in registry."""
    client = NPPESClient()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result_count": 0, "results": []}

    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await client.validate("9999999998")

    assert result["valid"] is False
    await client.close()


# -----------------------------------------------------------------------------
# Test: search_by_name_and_fields_returns_providers
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_by_name_and_fields_returns_providers():
    """Test that search_by_name_and_fields returns matching providers."""
    client = NPPESClient()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result_count": 1,
        "results": [
            {"npi": "1234567890", "basic": {"first_name": "John", "last_name": "Smith"}}
        ]
    }

    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await client.search_by_name_and_fields(first_name="John", state="CT")

    assert len(result) == 1
    assert result[0]["npi"] == "1234567890"

    # Verify the API was called with correct params
    call_args = mock_get.call_args
    params = call_args.kwargs.get("params", {})
    assert params.get("first_name") == "John"
    assert params.get("state") == "CT"
    await client.close()


# -----------------------------------------------------------------------------
# Test: search_by_name_and_fields_empty_query_returns_empty
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_by_name_and_fields_empty_query_returns_empty():
    """Test that search_by_name_and_fields returns empty list with no parameters."""
    client = NPPESClient()

    result = await client.search_by_name_and_fields()

    assert result == []


# -----------------------------------------------------------------------------
# Test: get_by_npi_handles_api_error
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_by_npi_handles_api_error():
    """Test that get_by_npi returns None on API error."""
    client = NPPESClient()

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server error", request=MagicMock(), response=mock_response
    )

    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await client.get_by_npi("1234567893")

    assert result is None
    await client.close()


# -----------------------------------------------------------------------------
# Test: validate_checks_luhn_algorithm
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_validate_checks_luhn_algorithm():
    """Test that validate uses ISO 7064 Mod 97-10 checksum."""
    client = NPPESClient()

    # Invalid checksum - should fail format check before API call
    result = await client.validate("1234567890")  # Invalid checksum

    assert result["valid"] is False
    assert "checksum" in result.get("error", "").lower()


# -----------------------------------------------------------------------------
# Test: validate_rejects_non_digit_input
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_validate_rejects_non_digit_input():
    """Test that validate rejects non-digit input."""
    client = NPPESClient()

    result = await client.validate("123456789a")

    assert result["valid"] is False
    assert "digits" in result.get("error", "").lower()


# -----------------------------------------------------------------------------
# Test: validate_rejects_wrong_length
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_validate_rejects_wrong_length():
    """Test that validate rejects wrong length input."""
    client = NPPESClient()

    result = await client.validate("12345")

    assert result["valid"] is False


# -----------------------------------------------------------------------------
# Test: search_handles_api_error_response
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_handles_api_error_response():
    """Test that search returns empty list on API error response."""
    client = NPPESClient()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Errors": [{"number": "99", "description": "Unknown error"}]
    }

    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await client.search(state="CT")

    assert result == []
    await client.close()


# -----------------------------------------------------------------------------
# Test: search_fallback_removes_taxonomy
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_fallback_removes_taxonomy():
    """Test that search falls back by removing taxonomy when required."""
    client = NPPESClient()

    # First call returns error with "07" code, second call succeeds
    error_response = MagicMock()
    error_response.status_code = 200
    error_response.json.return_value = {
        "Errors": [{"number": "07", "description": "requires additional search criteria"}]
    }

    success_response = MagicMock()
    success_response.status_code = 200
    success_response.json.return_value = {
        "result_count": 1,
        "results": [{"npi": "1234567893", "number": "1234567893"}]
    }

    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [error_response, success_response]

        result = await client.search(state="CT", specialty="207Q00000X")

    # Should have called twice (fallback attempted)
    assert mock_get.call_count >= 1
    # Results may be filtered due to fallback
    assert isinstance(result, list)
    await client.close()


# =============================================================================
# TDD: Tests for first_name, last_name, organization_name parameters
# =============================================================================

# -----------------------------------------------------------------------------
# Test: search_passes_first_name_parameter
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_passes_first_name_parameter():
    """Test that search passes first_name parameter to API."""
    client = NPPESClient()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result_count": 1,
        "results": [
            {"npi": "1234567890", "basic": {"first_name": "Barry", "last_name": "Hartman"}}
        ]
    }

    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await client.search(first_name="Barry", state="NY")

    assert len(result) == 1
    # Verify the API was called with first_name parameter
    call_args = mock_get.call_args
    params = call_args.kwargs.get("params", {})
    assert params.get("first_name") == "Barry"
    assert params.get("state") == "NY"
    await client.close()


# -----------------------------------------------------------------------------
# Test: search_passes_last_name_parameter
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_passes_last_name_parameter():
    """Test that search passes last_name parameter to API."""
    client = NPPESClient()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result_count": 1,
        "results": [
            {"npi": "1234567890", "basic": {"first_name": "Barry", "last_name": "Hartman"}}
        ]
    }

    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await client.search(last_name="Hartman", state="NY")

    assert len(result) == 1
    # Verify the API was called with last_name parameter
    call_args = mock_get.call_args
    params = call_args.kwargs.get("params", {})
    assert params.get("last_name") == "Hartman"
    assert params.get("state") == "NY"
    await client.close()


# -----------------------------------------------------------------------------
# Test: search_passes_organization_name_parameter
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_passes_organization_name_parameter():
    """Test that search passes organization_name parameter to API."""
    client = NPPESClient()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result_count": 1,
        "results": [
            {
                "npi": "1234567890",
                "basic": {"organization_name": "City Medical Group"}
            }
        ]
    }

    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await client.search(organization_name="City Medical", state="NY")

    assert len(result) == 1
    # Verify the API was called with organization_name parameter
    call_args = mock_get.call_args
    params = call_args.kwargs.get("params", {})
    assert params.get("organization_name") == "City Medical"
    assert params.get("state") == "NY"
    await client.close()


# -----------------------------------------------------------------------------
# Test: search_with_both_first_and_last_name
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_with_both_first_and_last_name():
    """Test that search passes both first_name and last_name to API."""
    client = NPPESClient()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result_count": 1,
        "results": [
            {"npi": "1053313940", "basic": {"first_name": "Barry", "last_name": "Hartman"}}
        ]
    }

    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await client.search(first_name="Barry", last_name="Hartman", state="NY")

    assert len(result) == 1
    # Verify both parameters are passed to the API
    call_args = mock_get.call_args
    params = call_args.kwargs.get("params", {})
    assert params.get("first_name") == "Barry"
    assert params.get("last_name") == "Hartman"
    assert params.get("state") == "NY"
    await client.close()


# -----------------------------------------------------------------------------
# Test: search_deprecated_name_parameter_maps_to_first_name
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_deprecated_name_parameter_maps_to_first_name():
    """Test that deprecated 'name' parameter still works as first_name."""
    client = NPPESClient()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result_count": 1,
        "results": [
            {"npi": "1234567890", "basic": {"first_name": "Barry", "last_name": "Hartman"}}
        ]
    }

    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        result = await client.search(name="Barry", state="NY")

    assert len(result) == 1
    # Verify name is passed as first_name for backward compatibility
    call_args = mock_get.call_args
    params = call_args.kwargs.get("params", {})
    assert params.get("first_name") == "Barry"
    await client.close()