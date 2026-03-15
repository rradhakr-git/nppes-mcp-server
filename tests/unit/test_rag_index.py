"""
Unit tests for RAG pipeline - taxonomy embedding and FAISS index.

Tests the semantic search capability using sentence-transformers and FAISS.
"""

import pytest
import os
import tempfile
import json
from unittest.mock import patch, MagicMock

from app.rag.index import TaxonomyIndex


# =============================================================================
# Test: embed_query_returns_fixed_dimension_vector
# =============================================================================
@pytest.mark.asyncio
async def test_embed_query_returns_fixed_dimension_vector():
    """Test that embedding a query returns a vector of fixed dimension."""
    # Mock the embedder to return a fixed-size vector
    mock_embedder = MagicMock()
    mock_embedder.embed = MagicMock(return_value=[0.1] * 384)  # all-MiniLM-L6-v2 returns 384-dim

    index = TaxonomyIndex(embedder=mock_embedder, skip_build=True)

    result = await index.embed_query("heart doctor")

    assert isinstance(result, list)
    assert len(result) == 384  # all-MiniLM-L6-v2 dimension
    assert all(isinstance(x, float) for x in result)


# =============================================================================
# Test: faiss_top3_returns_relevant_taxonomy_codes
# =============================================================================
@pytest.mark.asyncio
async def test_faiss_top3_returns_relevant_taxonomy_codes():
    """Test that FAISS search returns top-k relevant taxonomy codes."""
    # Create index with mock embedder and FAISS
    mock_embedder = MagicMock()

    # Sample embeddings - query is similar to cardiology-related entries
    mock_embedder.embed = MagicMock(side_effect=[
        [0.1, 0.2, 0.3] + [0.0] * 381,  # query embedding
    ])

    # Pre-populate index with known taxonomies (skip auto-build)
    index = TaxonomyIndex(embedder=mock_embedder, dimension=384, skip_build=True)

    # Manually add some taxonomy entries to the index
    # Simulate index already built with embeddings
    index._taxonomies = [
        {"code": "207RC0000X", "classification": "Cardiovascular Disease"},
        {"code": "207RE0000X", "classification": "Endocrinology"},
        {"code": "207Q00000X", "classification": "Family Medicine"},
        {"code": "207N00000X", "classification": "Dermatology"},
        {"code": "208600000X", "classification": "Pediatrics"},
    ]

    # Mock FAISS index
    class MockFaissIndex:
        def __init__(self):
            self.dimension = 384

        def add(self, vectors):
            pass

        def search(self, query_vec, k):
            # Return top 3 - indices 0, 1, 2 (cardiology first)
            return ([1.0, 0.8, 0.6], [[0, 1, 2]])

        def reset(self):
            pass

    index._faiss = MockFaissIndex()

    # Search should return top 3 matching taxonomy codes
    results = await index.search("heart disease", top_k=3)

    assert len(results) == 3
    assert results[0]["code"] == "207RC0000X"  # Cardiovascular Disease first


# =============================================================================
# Test: index_rebuilds_on_missing_file
# =============================================================================
@pytest.mark.asyncio
async def test_index_rebuilds_on_missing_file():
    """Test that the index rebuilds when the index file is missing."""
    # Create temp directory for index
    with tempfile.TemporaryDirectory() as tmpdir:
        index_path = os.path.join(tmpdir, "taxonomy_index")

        # Mock embedder
        mock_embedder = MagicMock()
        mock_embedder.embed = MagicMock(return_value=[[0.1] * 384])
        mock_embedder.embed_batch = MagicMock(return_value=[[0.1] * 384] * 3)

        # Create index - should rebuild since no file exists
        index = TaxonomyIndex(
            embedder=mock_embedder,
            index_path=index_path,
            dimension=384
        )

        # The build method should be called when index doesn't exist
        # Verify the taxonomies were loaded (stub data)
        assert len(index._taxonomies) > 0

        # Check that FAISS index was created
        assert index._faiss is not None


# =============================================================================
# Test: low_similarity_score_filtered_out
# =============================================================================
@pytest.mark.asyncio
async def test_low_similarity_score_filtered_out():
    """Test that results with low similarity scores are filtered out."""
    mock_embedder = MagicMock()
    mock_embedder.embed = MagicMock(return_value=[0.1] * 384)

    index = TaxonomyIndex(embedder=mock_embedder, dimension=384, skip_build=True)

    # Pre-populate with taxonomies
    index._taxonomies = [
        {"code": "HIGH_SIM", "classification": "Cardiology"},
        {"code": "LOW_SIM", "classification": "Unrelated"},
    ]

    # Mock FAISS to return L2 distances (lower = better)
    # 0.1 = high similarity (close), 1.7 = low similarity (far)
    class MockFaissIndex:
        def __init__(self):
            self.dimension = 384

        def search(self, query_vec, k):
            # First result close (high similarity), second far (low similarity)
            return ([0.1, 1.7], [[0, 1]])

    index._faiss = MockFaissIndex()

    # Search with threshold - should only return high similarity result
    results = await index.search("heart specialist", top_k=2, min_score=0.5)

    assert len(results) == 1
    assert results[0]["code"] == "HIGH_SIM"
