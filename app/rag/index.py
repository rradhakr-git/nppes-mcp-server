"""
Taxonomy index using FAISS for semantic search over NUCC taxonomy codes.

Provides fast similarity search over embedded taxonomy descriptions.
"""

import os
import json
import csv
import tempfile
from typing import Optional
from pathlib import Path

import numpy as np


# Default NUCC taxonomy CSV URL (fallback for manual refresh)
DEFAULT_TAXONOMY_URL = "https://www.nucc.org/images/stories/CSV/nucc_taxonomy_251.csv"

# Directory containing taxonomy CSV (bundle in Docker image)
TAXONOMY_DIR = Path(__file__).parent
DEFAULT_TAXONOMY_CSV_PATH = TAXONOMY_DIR / "taxonomy.csv"


def _get_env_str(name: str, default: str) -> str:
    """Get string from environment, with fallback."""
    return os.getenv(name, default)


class TaxonomyIndex:
    """
    FAISS-based index for NUCC taxonomy semantic search.

    Embeds taxonomy descriptions and provides fast similarity search.
    """

    def __init__(
        self,
        embedder,
        index_path: Optional[str] = None,
        dimension: int = 384,
        taxonomy_csv: Optional[str] = None,
        skip_build: bool = False
    ):
        self.embedder = embedder
        self.index_path = index_path
        self.dimension = dimension
        # Use env var, then param, then bundled CSV path
        default_csv = os.getenv("TAXONOMY_CSV_PATH", str(DEFAULT_TAXONOMY_CSV_PATH))
        self.taxonomy_csv_path = taxonomy_csv or default_csv

        self._faiss = None
        self._taxonomies: list[dict] = []

        if not skip_build:
            # Try to load existing index, otherwise build new one
            self._load_or_build()

    def _load_or_build(self):
        """Load existing index or build a new one."""
        if self.index_path and os.path.exists(self.index_path):
            self._load_index()
        else:
            self._build_index()

    def _load_taxonomies_from_csv(self) -> list[dict]:
        """Load taxonomy data from CSV file."""
        taxonomies = []

        if not os.path.exists(self.taxonomy_csv_path):
            # Use bundled stub data if CSV doesn't exist
            from tests.stubs.taxonomy_rows import TAXONOMY_ROWS
            return TAXONOMY_ROWS

        with open(self.taxonomy_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Extract relevant fields from NUCC CSV format
                taxonomy = {
                    "code": row.get("Code", row.get("code", "")),
                    "classification": row.get("Classification", row.get("classification", "")),
                    "specialization": row.get("Specialization", row.get("specialization", "")),
                    "description": row.get("Description", row.get("description", ""))
                }
                if taxonomy["code"]:
                    taxonomies.append(taxonomy)

        return taxonomies

    def _build_index(self):
        """Build FAISS index from taxonomy data."""
        # Load taxonomies
        self._taxonomies = self._load_taxonomies_from_csv()

        if not self._taxonomies:
            return

        # Create text for embedding
        texts = []
        for t in self._taxonomies:
            parts = [t["classification"] or ""]
            if t["specialization"]:
                parts.append(t["specialization"])
            if t["description"]:
                parts.append(t["description"])
            texts.append(" - ".join(parts))

        # Embed all texts
        embeddings = self.embedder.embed_batch(texts)

        # Convert to numpy array
        embeddings_matrix = np.array(embeddings, dtype=np.float32)

        # Create FAISS index
        import faiss
        self._faiss = faiss.IndexFlatL2(self.dimension)
        self._faiss.add(embeddings_matrix)

        # Save index if path provided
        if self.index_path:
            self._save_index()

    def _save_index(self):
        """Save FAISS index and taxonomy data to disk."""
        if not self.index_path or not self._faiss:
            return

        # Save FAISS index
        import faiss
        faiss.write_index(self._faiss, f"{self.index_path}.bin")

        # Save taxonomy metadata
        with open(f"{self.index_path}.json", 'w') as f:
            json.dump(self._taxonomies, f)

    def _load_index(self):
        """Load FAISS index and taxonomy data from disk."""
        import faiss

        # Load FAISS index
        self._faiss = faiss.read_index(f"{self.index_path}.bin")

        # Load taxonomy metadata
        with open(f"{self.index_path}.json", 'r') as f:
            self._taxonomies = json.load(f)

    async def embed_query(self, text: str) -> list[float]:
        """
        Embed a query text.

        Args:
            text: Query text

        Returns:
            384-dimensional embedding vector
        """
        return self.embedder.embed(text)

    async def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0
    ) -> list[dict]:
        """
        Search for similar taxonomy codes.

        Args:
            query: Natural language query
            top_k: Number of results to return
            min_score: Minimum similarity score (0-1, higher is more similar)

        Returns:
            List of taxonomy dicts with similarity scores
        """
        if not self._faiss or not self._taxonomies:
            return []

        # Embed query
        query_embedding = np.array([await self.embed_query(query)], dtype=np.float32)

        # Search FAISS
        distances, indices = self._faiss.search(query_embedding, min(top_k * 2, len(self._taxonomies)))

        # Handle both numpy arrays and mock returns
        # Real FAISS returns 2D arrays, mocks may return different structures
        distances = np.array(distances)
        indices = np.array(indices)

        if distances.ndim > 1:
            distances = distances.flatten()
        if indices.ndim > 1:
            indices = indices.flatten()

        # Convert L2 distance to similarity score (lower distance = higher similarity)
        # Normalize: distance 0 -> score 1, distance 2 -> score 0
        results = []
        for dist, idx in zip(distances, indices):
            if idx < 0:
                continue

            # Convert distance to similarity (0-1 range, L2 typically 0-2)
            score = max(0.0, 1.0 - (dist / 2.0))

            if score >= min_score:
                result = dict(self._taxonomies[idx])
                result["score"] = score
                results.append(result)

            if len(results) >= top_k:
                break

        return results
