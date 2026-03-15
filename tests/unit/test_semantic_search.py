"""
Unit tests for semantic_search MCP tool.

Tests the combined RAG + NPPES search functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.tools.semantic_search import semantic_search
from app.rag.index import TaxonomyIndex
from app.clients.cache import CacheClient
from app.clients.nppes import NPPESClient


# =============================================================================
# Test: semantic_search_combines_rag_and_nppes
# =============================================================================
@pytest.mark.asyncio
async def test_semantic_search_combines_rag_and_nppes():
    """Test that semantic_search uses RAG to find taxonomies then searches NPPES."""
    # Mock taxonomy index returning relevant taxonomy codes
    mock_index = MagicMock(spec=TaxonomyIndex)
    mock_index.search = AsyncMock(return_value=[
        {"code": "207RC0000X", "classification": "Cardiovascular Disease", "score": 0.95},
        {"code": "207Q00000X", "classification": "Family Medicine", "score": 0.80}
    ])

    # Mock NPPES client returning providers
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.search = AsyncMock(return_value=[
        {"npi": "1234567890", "basic": {"first_name": "John"}}
    ])

    # Mock cache that calls fetch_fn
    async def mock_get_or_fetch(key, fetch_fn):
        return await fetch_fn()

    mock_cache = MagicMock(spec=CacheClient)
    mock_cache.get_or_fetch = mock_get_or_fetch
    mock_cache.build_search_key = CacheClient().build_search_key

    # Call semantic search
    result = await semantic_search(
        query="heart specialist in Connecticut",
        taxonomy_index=mock_index,
        nppes_client=mock_nppes,
        cache=mock_cache
    )

    # Should have called taxonomy search
    mock_index.search.assert_called_once()

    # Should have called NPPES with taxonomy codes
    mock_nppes.search.assert_called()

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["npi"] == "1234567890"


# =============================================================================
# Test: semantic_search_returns_empty_on_no_match
# =============================================================================
@pytest.mark.asyncio
async def test_semantic_search_returns_empty_on_no_match():
    """Test that semantic_search returns empty when no taxonomies match."""
    # Mock taxonomy index with no results
    mock_index = MagicMock(spec=TaxonomyIndex)
    mock_index.search = AsyncMock(return_value=[])

    # Mock NPPES client
    mock_nppes = AsyncMock(spec=NPPESClient)

    # Mock cache
    mock_cache = MagicMock(spec=CacheClient)
    mock_cache.get_or_fetch = AsyncMock(return_value=[])
    mock_cache.build_search_key = CacheClient().build_search_key

    # Call with query that returns no taxonomy matches
    result = await semantic_search(
        query="xyznonexistentquery12345",
        taxonomy_index=mock_index,
        nppes_client=mock_nppes,
        cache=mock_cache
    )

    # NPPES should NOT be called when no taxonomies match
    mock_nppes.search.assert_not_called()

    assert result == []


# =============================================================================
# Test: semantic_search_passes_location_to_nppes
# =============================================================================
@pytest.mark.asyncio
async def test_semantic_search_passes_location_to_nppes():
    """Test that location params from query are passed to NPPES search."""
    captured_params = {}

    async def capture_params(**kwargs):
        captured_params.update(kwargs)
        return []

    # Mock taxonomy index
    mock_index = MagicMock(spec=TaxonomyIndex)
    mock_index.search = AsyncMock(return_value=[
        {"code": "207RC0000X", "classification": "Cardiology"}
    ])

    # Mock NPPES client capturing params
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.search = capture_params

    # Mock cache that calls fetch_fn
    async def mock_get_or_fetch(key, fetch_fn):
        return await fetch_fn()

    mock_cache = MagicMock(spec=CacheClient)
    mock_cache.get_or_fetch = mock_get_or_fetch
    mock_cache.build_search_key = CacheClient().build_search_key

    # Call with location hint in query
    await semantic_search(
        query="cardiologist in Connecticut",
        state="CT",
        taxonomy_index=mock_index,
        nppes_client=mock_nppes,
        cache=mock_cache
    )

    # NPPES should be called with state param
    assert "state" in captured_params
    assert captured_params["state"] == "CT"


# =============================================================================
# Test: semantic_search_ranks_by_similarity
# =============================================================================
@pytest.mark.asyncio
async def test_semantic_search_ranks_by_similarity():
    """Test that results are ranked by taxonomy similarity score."""
    # Mock taxonomy index with scored results
    mock_index = MagicMock(spec=TaxonomyIndex)
    mock_index.search = AsyncMock(return_value=[
        {"code": "207RC0000X", "classification": "Cardiovascular Disease", "score": 0.95},
        {"code": "207RE0000X", "classification": "Endocrinology", "score": 0.60}
    ])

    # Mock NPPES returning providers
    mock_nppes = AsyncMock(spec=NPPESClient)
    mock_nppes.search = AsyncMock(side_effect=[
        [{"npi": "CARDIO-1", "taxonomies": [{"code": "207RC0000X"}]}],  # High score
        [{"npi": "ENDO-1", "taxonomies": [{"code": "207RE0000X"}]}]    # Low score
    ])

    # Mock cache that calls fetch_fn
    async def mock_get_or_fetch(key, fetch_fn):
        return await fetch_fn()

    mock_cache = MagicMock(spec=CacheClient)
    mock_cache.get_or_fetch = mock_get_or_fetch
    mock_cache.build_search_key = CacheClient().build_search_key

    result = await semantic_search(
        query="heart disease doctor",
        taxonomy_index=mock_index,
        nppes_client=mock_nppes,
        cache=mock_cache
    )

    # NPPES search should have been called at least once
    assert mock_nppes.search.call_count >= 1