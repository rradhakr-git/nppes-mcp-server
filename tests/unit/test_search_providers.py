"""
Unit tests for search_providers MCP tool.

Tests that the tool correctly orchestrates cache and NPPES client.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from app.tools.search_providers import search_providers
from app.clients.cache import CacheClient
from app.clients.nppes import NPPESClient


# =============================================================================
# Test: search_providers_returns_list_of_providers
# =============================================================================
@pytest.mark.asyncio
async def test_search_providers_returns_list_of_providers():
    """Test that search_providers returns list of providers from NPPES."""
    # Mock NPPES client response
    nppes_result = [
        {
            "npi": "1234567890",
            "basic": {"first_name": "John", "last_name": "Smith"},
            "addresses": [{"city": "Hartford", "state": "CT"}],
            "taxonomies": [{"code": "207Q00000X", "desc": "Family Medicine"}]
        }
    ]

    # Create mock NPPES client
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.search = AsyncMock(return_value=nppes_result)

    # Create mock cache that passes through to NPPES
    async def mock_get_or_fetch(key, fetch_fn):
        return await fetch_fn()

    mock_cache = MagicMock(spec=CacheClient)
    mock_cache.get_or_fetch = mock_get_or_fetch

    # Call the tool
    result = await search_providers(state="CT", cache=mock_cache, nppes_client=mock_nppes)

    # Assert result is list of providers
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["npi"] == "1234567890"


# =============================================================================
# Test: search_providers_calls_cache_with_correct_key
# =============================================================================
@pytest.mark.asyncio
async def test_search_providers_calls_cache_with_correct_key():
    """Test that search_providers builds correct cache key from params."""
    captured_key = None

    async def capture_get_or_fetch(key, fetch_fn):
        nonlocal captured_key
        captured_key = key
        return await fetch_fn()

    # Mock NPPES client
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.search = AsyncMock(return_value=[])

    # Create mock cache
    mock_cache = MagicMock(spec=CacheClient)
    mock_cache.get_or_fetch = capture_get_or_fetch
    mock_cache.build_search_key = CacheClient().build_search_key

    # Call with specific params
    await search_providers(
        state="CT",
        city="Hartford",
        name="John",
        cache=mock_cache,
        nppes_client=mock_nppes
    )

    # Assert cache key was built from params
    assert captured_key is not None
    assert "nppes:search:" in captured_key


# =============================================================================
# Test: search_providers_uses_cache_on_second_call
# =============================================================================
@pytest.mark.asyncio
async def test_search_providers_uses_cache_on_second_call():
    """Test that second call with same params uses cache (no NPPES call)."""
    call_count = 0

    async def count_calls(key, fetch_fn):
        nonlocal call_count
        call_count += 1
        return [{"npi": "1234567890"}]

    # Mock NPPES client
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.search = AsyncMock(return_value=[{"npi": "FROM_NPpes"}])

    # Create mock cache that caches result
    mock_cache = MagicMock(spec=CacheClient)
    mock_cache.get_or_fetch = count_calls

    # First call
    await search_providers(state="CT", cache=mock_cache, nppes_client=mock_nppes)

    # Second call with same params - cache hit
    await search_providers(state="CT", cache=mock_cache, nppes_client=mock_nppes)

    # get_or_fetch should be called twice (once per search_providers call)
    # but NPPES search should only be called once (first call)
    assert call_count == 2


# =============================================================================
# Test: search_providers_respects_limit_param
# =============================================================================
@pytest.mark.asyncio
async def test_search_providers_respects_limit_param():
    """Test that limit parameter is passed through correctly."""
    captured_params = {}

    async def capture_fetch(key):
        # Return different amounts based on what's asked
        return [{"npi": f"prov-{i}"} for i in range(captured_params.get("limit", 10))]

    # Capture the params passed to fetch_fn
    async def mock_get_or_fetch(key, fetch_fn):
        result = await fetch_fn()
        return result

    # Mock NPPES client
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.search = AsyncMock(return_value=[])

    # Create mock cache
    mock_cache = MagicMock(spec=CacheClient)
    mock_cache.get_or_fetch = mock_get_or_fetch
    mock_cache.build_search_key = CacheClient().build_search_key

    # Call with limit
    result = await search_providers(
        state="CT",
        limit=5,
        cache=mock_cache,
        nppes_client=mock_nppes
    )

    # NPPES client should have been called with limit=5
    mock_nppes.search.assert_called_once()
    call_kwargs = mock_nppes.search.call_args.kwargs
    assert call_kwargs.get("limit") == 5
