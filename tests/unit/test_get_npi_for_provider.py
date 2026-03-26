"""
Unit tests for get_npi_for_provider MCP tool.

Tests the MCP tool that searches for NPI by provider name/location.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.tools.get_npi_for_provider import get_npi_for_provider
from app.clients.nppes import NPPESClient
from app.clients.cache import CacheClient


async def _call_fetch_fn(key, fetch_fn, ttl=None):
    """Helper to call fetch_fn in tests."""
    return await fetch_fn()


# =============================================================================
# Test: get_npi_for_provider_returns_npi_for_exact_match
# =============================================================================
@pytest.mark.asyncio
async def test_get_npi_for_provider_returns_npi_for_exact_match():
    """Test that get_npi_for_provider returns NPI when exact name match found."""
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.search_by_name_and_fields = AsyncMock(return_value=[
        {"number": "1234567893", "basic": {"first_name": "John", "last_name": "Smith"}}
    ])

    mock_cache = MagicMock(spec=CacheClient)
    mock_cache.get_or_fetch = AsyncMock(side_effect=_call_fetch_fn)
    mock_cache.build_search_key = CacheClient().build_search_key

    result = await get_npi_for_provider(
        first_name="John",
        last_name="Smith",
        state="CT",
        nppes_client=mock_nppes,
        cache=mock_cache
    )

    assert result["found"] is True
    assert result["npi"] == "1234567893"


# =============================================================================
# Test: get_npi_for_provider_returns_not_found
# =============================================================================
@pytest.mark.asyncio
async def test_get_npi_for_provider_returns_not_found():
    """Test that get_npi_for_provider returns not found when no match."""
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.search_by_name_and_fields = AsyncMock(return_value=[])

    mock_cache = MagicMock(spec=CacheClient)
    mock_cache.get_or_fetch = AsyncMock(side_effect=_call_fetch_fn)
    mock_cache.build_search_key = CacheClient().build_search_key

    result = await get_npi_for_provider(
        first_name="Nonexistent",
        last_name="Doctor",
        state="XX",
        nppes_client=mock_nppes,
        cache=mock_cache
    )

    assert result["found"] is False


# =============================================================================
# Test: get_npi_for_provider_requires_name
# =============================================================================
@pytest.mark.asyncio
async def test_get_npi_for_provider_requires_name():
    """Test that get_npi_for_provider requires at least name or organization."""
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_cache = MagicMock(spec=CacheClient)

    # No name parameters
    result = await get_npi_for_provider(
        state="CT",
        nppes_client=mock_nppes,
        cache=mock_cache
    )

    assert result["error"] is not None
    assert "name" in result["error"].lower()


# =============================================================================
# Test: get_npi_for_provider_returns_first_when_multiple
# =============================================================================
@pytest.mark.asyncio
async def test_get_npi_for_provider_returns_first_when_multiple():
    """Test that get_npi_for_provider returns first NPI when multiple matches."""
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.search_by_name_and_fields = AsyncMock(return_value=[
        {"number": "1111111111", "basic": {"first_name": "John", "last_name": "Smith"}},
        {"number": "2222222222", "basic": {"first_name": "John", "last_name": "Smith"}}
    ])

    mock_cache = MagicMock(spec=CacheClient)
    mock_cache.get_or_fetch = AsyncMock(side_effect=_call_fetch_fn)
    mock_cache.build_search_key = CacheClient().build_search_key

    result = await get_npi_for_provider(
        first_name="John",
        last_name="Smith",
        nppes_client=mock_nppes,
        cache=mock_cache
    )

    assert result["found"] is True
    # Returns first match
    assert result["npi"] == "1111111111"


# =============================================================================
# Test: get_npi_for_provider_handles_organization
# =============================================================================
@pytest.mark.asyncio
async def test_get_npi_for_provider_handles_organization():
    """Test that get_npi_for_provider works with organization_name."""
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.search_by_name_and_fields = AsyncMock(return_value=[
        {"number": "3333333333", "basic": {"organization_name": "Acme Health"}}
    ])

    mock_cache = MagicMock(spec=CacheClient)
    mock_cache.get_or_fetch = AsyncMock(side_effect=_call_fetch_fn)
    mock_cache.build_search_key = CacheClient().build_search_key

    result = await get_npi_for_provider(
        organization_name="Acme Health",
        nppes_client=mock_nppes,
        cache=mock_cache
    )

    assert result["found"] is True
    assert result["npi"] == "3333333333"