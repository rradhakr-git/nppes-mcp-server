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


# =============================================================================
# Phase A: RAG Lifespan Fix Tests (TDD - Red)
# =============================================================================

@pytest.mark.asyncio
async def test_taxonomy_index_build_is_idempotent():
    """
    Test that TaxonomyIndex.build() (via _load_or_build) is safe to call multiple times.

    This ensures that even if build() is called twice (e.g., edge case in lifespan),
    the index remains consistent.
    """
    mock_embedder = MagicMock()
    mock_embedder.embed = MagicMock(return_value=[0.1] * 384)
    mock_embedder.embed_batch = MagicMock(return_value=[[0.1] * 384] * 3)

    index = TaxonomyIndex(embedder=mock_embedder, dimension=384, skip_build=True)

    # Manually set up index data
    index._taxonomies = [
        {"code": "207RC0000X", "classification": "Cardiology", "specialization": "", "description": ""}
    ]

    # Mock FAISS index
    class MockFaissIndex:
        def __init__(self):
            self.dimension = 384
            self._vectors = []

        def add(self, vectors):
            self._vectors.extend(vectors)

        def search(self, query_vec, k):
            return ([0.5], [[0]])

    # Build twice - should not cause issues
    index._faiss = MockFaissIndex()

    # First call to internal build
    index._load_or_build()

    # Store reference to first FAISS index
    first_faiss = index._faiss
    first_taxonomies = list(index._taxonomies)

    # Second call - should be safe (idempotent)
    index._load_or_build()

    # Should be the same objects (not recreated)
    assert index._faiss is first_faiss
    assert index._taxonomies == first_taxonomies


# =============================================================================
# Test: keyword_search_finds_matches
# =============================================================================
@pytest.mark.asyncio
async def test_keyword_search_finds_matches():
    """Test keyword search fallback finds matches in taxonomy."""
    mock_embedder = MagicMock()
    mock_embedder.embed = MagicMock(return_value=[0.1] * 384)

    index = TaxonomyIndex(embedder=None, dimension=384, skip_build=True)

    # Pre-populate with taxonomies (no embedder = keyword search mode)
    index._taxonomies = [
        {"code": "207RC0000X", "classification": "Cardiovascular Disease", "specialization": "Interventional", "description": "Heart procedures"},
        {"code": "207Q00000X", "classification": "Family Medicine", "specialization": "", "description": ""}
    ]
    index._faiss = None  # Force keyword search

    results = await index.search("heart doctor", top_k=5)

    # Should find at least one result (cardiovascular has "heart" in description)
    assert len(results) >= 1
    codes = [r["code"] for r in results]
    assert "207RC0000X" in codes


# =============================================================================
# Test: keyword_search_returns_results_for_partial_match
# =============================================================================
@pytest.mark.asyncio
async def test_keyword_search_returns_results_for_partial_match():
    """Test keyword search returns results for partial matches."""
    index = TaxonomyIndex(embedder=None, skip_build=True)

    index._taxonomies = [
        {"code": "207Q00000X", "classification": "Family Medicine", "specialization": "", "description": ""}
    ]
    index._faiss = None

    # "family" matches "Family Medicine"
    results = await index.search("family", top_k=5)

    assert len(results) >= 1
    assert results[0]["code"] == "207Q00000X"


# =============================================================================
# Test: search_respects_min_score_threshold
# =============================================================================
@pytest.mark.asyncio
async def test_search_respects_min_score_threshold():
    """Test that search filters results by min_score."""
    mock_embedder = MagicMock()
    mock_embedder.embed = MagicMock(return_value=[0.1] * 384)

    index = TaxonomyIndex(embedder=mock_embedder, dimension=384, skip_build=True)

    index._taxonomies = [
        {"code": "HIGH_SIM", "classification": "Cardiology"},
        {"code": "LOW_SIM", "classification": "Unrelated"}
    ]

    # Mock FAISS returning both with different distances
    class MockFaissIndex:
        def search(self, query_vec, k):
            # High sim (0.1), Low sim (1.5)
            return ([0.1, 1.5], [[0, 1]])

    index._faiss = MockFaissIndex()

    results = await index.search("heart", top_k=2, min_score=0.5)

    # Should only return high similarity result
    assert len(results) == 1
    assert results[0]["code"] == "HIGH_SIM"


# =============================================================================
# Test: search_returns_empty_when_no_taxonomies
# =============================================================================
@pytest.mark.asyncio
async def test_search_returns_empty_when_no_taxonomies():
    """Test search returns empty list when no taxonomies loaded."""
    index = TaxonomyIndex(skip_build=True)

    index._taxonomies = []

    results = await index.search("test query")

    assert results == []


# =============================================================================
# Test: loads_taxonomies_from_csv
# =============================================================================
def test_loads_taxonomies_from_csv():
    """Test that TaxonomyIndex loads from CSV when available."""
    import tempfile
    import csv

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.DictWriter(f, fieldnames=["Code", "Classification", "Specialization", "Description"])
        writer.writeheader()
        writer.writerow({
            "Code": "207Q00000X",
            "Classification": "Family Medicine",
            "Specialization": "",
            "Description": "Primary care"
        })
        csv_path = f.name

    try:
        # Create index without skip_build but with no embedder (will use keyword mode)
        index = TaxonomyIndex(
            embedder=None,
            taxonomy_csv=csv_path,
            skip_build=False
        )

        # Should have loaded taxonomies
        assert len(index._taxonomies) >= 1
        codes = [t["code"] for t in index._taxonomies]
        assert "207Q00000X" in codes
    finally:
        import os
        os.unlink(csv_path)
