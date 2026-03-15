"""
Embedding model wrapper using sentence-transformers.

Uses all-MiniLM-L6-v2 for efficient CPU-based embeddings.
"""

from typing import Optional
import numpy as np


DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384


class Embedder:
    """
    Wrapper for sentence-transformers embedding model.

    Produces 384-dimensional vectors for text queries.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: Optional[str] = None
    ):
        self.model_name = model_name
        self.device = device or "cpu"
        self._model = None

    def _load_model(self):
        """Lazy load the transformer model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name, device=self.device)

    def embed(self, text: str) -> list[float]:
        """
        Embed a single text string.

        Args:
            text: Input text to embed

        Returns:
            List of 384-dimensional embedding vector
        """
        self._load_model()
        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple text strings.

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors
        """
        self._load_model()
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return [emb.tolist() for emb in embeddings]

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        return EMBEDDING_DIMENSION
