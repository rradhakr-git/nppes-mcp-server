"""
Unit tests for RAG embedder.

Tests the sentence-transformers wrapper for embeddings.
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from app.rag.embedder import Embedder


# =============================================================================
# Test: embed_returns_list_of_floats
# =============================================================================
def test_embed_returns_list_of_floats():
    """Test that embed returns a list of floats with correct dimension."""
    embedder = Embedder()

    # Mock the model
    mock_model = MagicMock()
    mock_embedding = MagicMock()
    mock_embedding.tolist.return_value = [0.1] * 384
    mock_model.encode.return_value = mock_embedding

    embedder._model = mock_model

    result = embedder.embed("test text")

    assert isinstance(result, list)
    assert len(result) == 384
    assert all(isinstance(x, float) for x in result)


# =============================================================================
# Test: embed_batch_returns_multiple_embeddings
# =============================================================================
def test_embed_batch_returns_multiple_embeddings():
    """Test that embed_batch returns list of embeddings for multiple texts."""
    embedder = Embedder()

    mock_model = MagicMock()
    mock_embeddings = np.array([[0.1] * 384, [0.2] * 384])
    mock_model.encode.return_value = mock_embeddings

    embedder._model = mock_model

    result = embedder.embed_batch(["text1", "text2"])

    assert len(result) == 2
    assert all(len(emb) == 384 for emb in result)


# =============================================================================
# Test: dimension_property_returns_384
# =============================================================================
def test_dimension_property_returns_384():
    """Test that dimension property returns 384."""
    embedder = Embedder()

    assert embedder.dimension == 384


# =============================================================================
# Test: embed_handles_empty_model_gracefully
# =============================================================================
def test_embed_handles_empty_model_gracefully():
    """Test that embed works when model is pre-set."""
    embedder = Embedder()

    mock_model = MagicMock()
    mock_embedding = np.array([0.1] * 384)
    mock_model.encode.return_value = mock_embedding

    embedder._model = mock_model

    result = embedder.embed("test")

    assert len(result) == 384


# =============================================================================
# Test: uses_custom_model_name
# =============================================================================
def test_uses_custom_model_name():
    """Test that embedder accepts custom model name."""
    embedder = Embedder(model_name="custom-model")

    assert embedder.model_name == "custom-model"


# =============================================================================
# Test: uses_specified_device
# =============================================================================
def test_uses_specified_device():
    """Test that embedder uses specified device."""
    embedder = Embedder(device="cuda")

    assert embedder.device == "cuda"

    embedder_cpu = Embedder(device="cpu")
    assert embedder_cpu.device == "cpu"