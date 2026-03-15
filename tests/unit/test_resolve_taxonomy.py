"""
Unit tests for resolve_taxonomy MCP tool.

Tests taxonomy code resolution and natural language query handling.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.tools.resolve_taxonomy import resolve_taxonomy
from app.rag.index import TaxonomyIndex


# =============================================================================
# Test: resolve_taxonomy_by_code
# =============================================================================
@pytest.mark.asyncio
async def test_resolve_taxonomy_by_code():
    """Test that resolve_taxonomy returns taxonomy details when code is provided."""
    # Mock taxonomy index that returns direct lookup
    taxonomy_data = {
        "code": "207Q00000X",
        "classification": "Family Medicine",
        "specialization": "General Practice",
        "description": "Family Medicine is the medical specialty..."
    }

    # Create mock index with taxonomies loaded
    mock_index = MagicMock(spec=TaxonomyIndex)
    mock_index._taxonomies = [taxonomy_data]
    mock_index.search = AsyncMock(return_value=[])

    # Call with code - should do direct lookup, not RAG search
    result = await resolve_taxonomy(code="207Q00000X", taxonomy_index=mock_index)

    assert isinstance(result, dict)
    assert result["code"] == "207Q00000X"
    assert result["classification"] == "Family Medicine"


# =============================================================================
# Test: resolve_taxonomy_by_natural_language_query
# =============================================================================
@pytest.mark.asyncio
async def test_resolve_taxonomy_by_natural_language_query():
    """Test that resolve_taxonomy uses RAG when query is provided."""
    # Mock taxonomy index for semantic search
    mock_index = MagicMock(spec=TaxonomyIndex)
    mock_index._taxonomies = []
    mock_index.search = AsyncMock(return_value=[
        {
            "code": "207RC0000X",
            "classification": "Cardiovascular Disease",
            "score": 0.95
        }
    ])

    # Call with natural language query - should use RAG search
    result = await resolve_taxonomy(query="heart doctor", taxonomy_index=mock_index)

    # Should have called search on the index
    mock_index.search.assert_called_once()

    assert isinstance(result, dict)
    assert result["code"] == "207RC0000X"


# =============================================================================
# Test: resolve_taxonomy_returns_empty_on_no_match
# =============================================================================
@pytest.mark.asyncio
async def test_resolve_taxonomy_returns_empty_on_no_match():
    """Test that resolve_taxonomy returns empty dict when no match found."""
    # Mock taxonomy index with no results
    mock_index = MagicMock(spec=TaxonomyIndex)
    mock_index._taxonomies = []
    mock_index.search = AsyncMock(return_value=[])

    # Call with query that returns no results
    result = await resolve_taxonomy(query="xyznonexistent", taxonomy_index=mock_index)

    assert result == {}


# =============================================================================
# Test: resolve_taxonomy_prefers_code_over_query
# =============================================================================
@pytest.mark.asyncio
async def test_resolve_taxonomy_prefers_code_over_query():
    """Test that code parameter takes precedence over query."""
    # Mock taxonomy index
    mock_index = MagicMock(spec=TaxonomyIndex)
    mock_index._taxonomies = [
        {"code": "207Q00000X", "classification": "Family Medicine"}
    ]
    mock_index.search = AsyncMock(return_value=[])  # Should not be called

    # Call with both code and query - code should win
    result = await resolve_taxonomy(
        code="207Q00000X",
        query="heart doctor",
        taxonomy_index=mock_index
    )

    # search should NOT have been called (code takes precedence)
    mock_index.search.assert_not_called()

    assert result["code"] == "207Q00000X"