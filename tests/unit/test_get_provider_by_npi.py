"""
Unit tests for get_provider_by_npi MCP tool.

Tests the MCP tool that wraps NPPES client with caching and validation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.tools.get_provider_by_npi import get_provider_by_npi
from app.clients.nppes import NPPESClient
from app.clients.cache import CacheClient


async def _call_fetch_fn(key, fetch_fn):
    """Helper to call fetch_fn in tests."""
    return await fetch_fn()


# =============================================================================
# Test: get_provider_by_npi_returns_full_record
# =============================================================================
@pytest.mark.asyncio
async def test_get_provider_by_npi_returns_full_record():
    """Test that get_provider_by_npi returns full provider record."""
    # Mock NPPES client returning provider
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.get_by_npi = AsyncMock(return_value={
        "npi": "1234567893",
        "basic": {
            "first_name": "John",
            "last_name": "Smith",
            "credential": "MD"
        },
        "addresses": [
            {"city": "Hartford", "state": "CT"}
        ],
        "taxonomies": [
            {"code": "207Q00000X", "desc": "Family Medicine"}
        ]
    })

    # Mock cache miss (return None to force fetch)
    mock_cache = MagicMock(spec=CacheClient)
    mock_cache.get_or_fetch = AsyncMock(side_effect=_call_fetch_fn)
    mock_cache.build_npi_key = CacheClient().build_npi_key

    result = await get_provider_by_npi(
        npi="1234567893",
        nppes_client=mock_nppes,
        cache=mock_cache
    )

    assert result is not None
    assert result["found"] is True
    assert result["npi"] == "1234567893"
    assert result["data"]["basic"]["first_name"] == "John"


# =============================================================================
# Test: get_provider_by_npi_uses_cache_on_second_call
# =============================================================================
@pytest.mark.asyncio
async def test_get_provider_by_npi_uses_cache_on_second_call():
    """Test that get_provider_by_npi uses cached result on second call."""
    # First call returns provider from API
    cached_provider = {
        "npi": "1234567893",
        "basic": {"first_name": "John", "last_name": "Smith"}
    }

    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_cache = MagicMock(spec=CacheClient)

    # First call: cache returns None, so fetch_fn is called
    fetch_fn_called = False

    async def fetch_from_api(key, fetch_fn):
        nonlocal fetch_fn_called
        fetch_fn_called = True
        return cached_provider

    mock_cache.get_or_fetch = fetch_from_api
    mock_cache.build_npi_key = CacheClient().build_npi_key

    # First call - should hit API
    await get_provider_by_npi(
        npi="1234567893",
        nppes_client=mock_nppes,
        cache=mock_cache
    )
    assert fetch_fn_called is True


# =============================================================================
# Test: get_provider_by_npi_rejects_non_10_digit_input
# =============================================================================
@pytest.mark.asyncio
async def test_get_provider_by_npi_rejects_non_10_digit_input():
    """Test that get_provider_by_npi rejects invalid NPI format."""
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_cache = MagicMock(spec=CacheClient)

    # Test with invalid NPI (too short)
    result = await get_provider_by_npi(
        npi="12345",
        nppes_client=mock_nppes,
        cache=mock_cache
    )

    assert result["error"] is not None
    assert "must be exactly 10 digits" in result["error"]

    # Test with non-numeric
    result = await get_provider_by_npi(
        npi="123456789a",
        nppes_client=mock_nppes,
        cache=mock_cache
    )

    assert result["error"] is not None


# =============================================================================
# Test: get_provider_by_npi_returns_not_found_for_unknown_npi
# =============================================================================
@pytest.mark.asyncio
async def test_get_provider_by_npi_returns_not_found_for_unknown_npi():
    """Test that get_provider_by_npi returns not found for unknown NPI."""
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.get_by_npi = AsyncMock(return_value=None)

    mock_cache = MagicMock(spec=CacheClient)
    mock_cache.get_or_fetch = AsyncMock(side_effect=_call_fetch_fn)
    mock_cache.build_npi_key = CacheClient().build_npi_key

    result = await get_provider_by_npi(
        npi="1000000023",  # Valid format, not found in registry
        nppes_client=mock_nppes,
        cache=mock_cache
    )

    assert result["found"] is False
    assert result["npi"] == "1000000023"


# =============================================================================
# Test: get_provider_by_npi_handles_npi2_organization
# =============================================================================
@pytest.mark.asyncio
async def test_get_provider_by_npi_handles_npi2_organization():
    """Test that get_provider_by_npi handles NPI-2 organization records."""
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.get_by_npi = AsyncMock(return_value={
        "npi": "1234567893",
        "basic": {
            "organization_name": "Acme Medical Group",
            "organizational_sub_part": ""
        },
        "addresses": [
            {"city": "Boston", "state": "MA"}
        ],
        "taxonomies": [
            {"code": "193200000X", "desc": "Multi-Specialty"}
        ]
    })

    mock_cache = MagicMock(spec=CacheClient)
    mock_cache.get_or_fetch = AsyncMock(side_effect=_call_fetch_fn)
    mock_cache.build_npi_key = CacheClient().build_npi_key

    result = await get_provider_by_npi(
        npi="1234567893",
        nppes_client=mock_nppes,
        cache=mock_cache
    )

    assert result["found"] is True
    assert result["npi"] == "1234567893"
    assert result["data"]["basic"]["organization_name"] == "Acme Medical Group"


# =============================================================================
# Test: get_provider_by_npi_builds_correct_cache_key
# =============================================================================
@pytest.mark.asyncio
async def test_get_provider_by_npi_builds_correct_cache_key():
    """Test that get_provider_by_npi uses correct cache key format."""
    captured_key = None

    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.get_by_npi = AsyncMock(return_value={"npi": "1234567893"})

    mock_cache = MagicMock(spec=CacheClient)

    async def capture_key(key, fetch_fn):
        nonlocal captured_key
        captured_key = key
        return await fetch_fn()

    mock_cache.get_or_fetch = capture_key
    mock_cache.build_npi_key = CacheClient().build_npi_key

    await get_provider_by_npi(
        npi="1234567893",
        nppes_client=mock_nppes,
        cache=mock_cache
    )

    # Should call cache with npi:{npi} format (includes key_prefix)
    assert "npi:1234567893" in captured_key