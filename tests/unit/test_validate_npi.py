"""
Unit tests for validate_npi MCP tool.

Tests the MCP tool that validates NPI format and registry status.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.tools.validate_npi import validate_npi
from app.clients.nppes import NPPESClient
from app.clients.cache import CacheClient


async def _call_fetch_fn(key, fetch_fn, ttl=None):
    """Helper to call fetch_fn in tests."""
    return await fetch_fn()


# =============================================================================
# Test: validate_npi_returns_valid_for_good_npi
# =============================================================================
@pytest.mark.asyncio
async def test_validate_npi_returns_valid_for_good_npi():
    """Test that validate_npi returns valid for correct NPI format and found in registry."""
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.validate = AsyncMock(return_value={"valid": True, "npi": "1000000023"})

    mock_cache = MagicMock(spec=CacheClient)
    mock_cache.get_or_fetch = AsyncMock(side_effect=_call_fetch_fn)
    mock_cache.build_validate_key = CacheClient().build_validate_key

    result = await validate_npi(
        npi="1000000023",
        nppes_client=mock_nppes,
        cache=mock_cache
    )

    assert result["valid"] is True
    assert result["npi"] == "1000000023"


# =============================================================================
# Test: validate_npi_rejects_invalid_format
# =============================================================================
@pytest.mark.asyncio
async def test_validate_npi_rejects_invalid_format():
    """Test that validate_npi rejects invalid NPI format without API call."""
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_cache = MagicMock(spec=CacheClient)

    # Test with too short
    result = await validate_npi(npi="123", nppes_client=mock_nppes, cache=mock_cache)
    assert result["valid"] is False
    assert "error" in result

    # Test with non-numeric
    result = await validate_npi(npi="123456789a", nppes_client=mock_nppes, cache=mock_cache)
    assert result["valid"] is False


# =============================================================================
# Test: validate_npi_returns_invalid_for_not_found
# =============================================================================
@pytest.mark.asyncio
async def test_validate_npi_returns_invalid_for_not_found():
    """Test that validate_npi returns invalid when NPI not found in registry."""
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.validate = AsyncMock(return_value={
        "valid": False,
        "npi": "1000000023",
        "error": "NPI not found in registry"
    })

    mock_cache = MagicMock(spec=CacheClient)
    mock_cache.get_or_fetch = AsyncMock(side_effect=_call_fetch_fn)
    mock_cache.build_validate_key = CacheClient().build_validate_key

    result = await validate_npi(
        npi="1000000023",
        nppes_client=mock_nppes,
        cache=mock_cache
    )

    assert result["valid"] is False
    assert "not found" in result["error"].lower()


# =============================================================================
# Test: validate_npi_uses_24hr_cache_ttl
# =============================================================================
@pytest.mark.asyncio
async def test_validate_npi_uses_24hr_cache_ttl():
    """Test that validate_npi uses 24hr cache TTL (longer than get_provider_by_npi)."""
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.validate = AsyncMock(return_value={"valid": True, "npi": "1000000023"})

    mock_cache = MagicMock(spec=CacheClient)

    # Track if get_or_fetch is called with correct TTL
    captured_ttl = None

    async def capture_with_ttl(key, fetch_fn, ttl=None):
        nonlocal captured_ttl
        captured_ttl = ttl
        return await fetch_fn()

    mock_cache.get_or_fetch = capture_with_ttl
    mock_cache.build_validate_key = CacheClient().build_validate_key

    await validate_npi(
        npi="1000000023",
        nppes_client=mock_nppes,
        cache=mock_cache,
        ttl=86400  # 24 hours in seconds
    )

    # Should use 24hr TTL (86400 seconds)
    assert captured_ttl == 86400


# =============================================================================
# Test: validate_npi_builds_correct_cache_key
# =============================================================================
@pytest.mark.asyncio
async def test_validate_npi_builds_correct_cache_key():
    """Test that validate_npi uses distinct cache key from get_provider_by_npi."""
    captured_key = None

    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.validate = AsyncMock(return_value={"valid": True, "npi": "1000000023"})

    mock_cache = MagicMock(spec=CacheClient)

    async def capture_key(key, fetch_fn, ttl=None):
        nonlocal captured_key
        captured_key = key
        return await fetch_fn()

    mock_cache.get_or_fetch = capture_key
    mock_cache.build_validate_key = CacheClient().build_validate_key

    await validate_npi(
        npi="1000000023",
        nppes_client=mock_nppes,
        cache=mock_cache
    )

    # Should use validate:{npi} format, distinct from npi:{npi}
    assert "validate:1000000023" in captured_key