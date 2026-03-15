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

    Can use pre-built index (no ML model needed at runtime) or build on-the-fly.
    """

    def __init__(
        self,
        embedder=None,
        index_path: Optional[str] = None,
        dimension: int = 384,
        taxonomy_csv: Optional[str] = None,
        skip_build: bool = False,
        use_prebuilt: bool = True
    ):
        self.embedder = embedder
        self.index_path = index_path
        self.dimension = dimension
        # Use env var, then param, then bundled CSV path
        default_csv = os.getenv("TAXONOMY_CSV_PATH", str(DEFAULT_TAXONOMY_CSV_PATH))
        self.taxonomy_csv_path = taxonomy_csv or default_csv

        self._faiss = None
        self._taxonomies: list[dict] = []

        if skip_build:
            return

        # Check for pre-built index first (no ML model needed!)
        if use_prebuilt and index_path:
            import faiss
            import os as os_module
            bin_path = f"{index_path}.bin"
            json_path = f"{index_path}.json"
            if os_module.path.exists(bin_path) and os_module.path.exists(json_path):
                self._load_prebuilt_index()
                return

        # Fall back to build or load
        if not skip_build:
            self._load_or_build()

    def _load_or_build(self):
        """Load existing index or build a new one."""
        # If no embedder, just load taxonomies from CSV (keyword search mode)
        if self.embedder is None:
            self._taxonomies = self._load_taxonomies_from_csv()
            self._faiss = None  # No vector search
            return

        # Otherwise try to load or build index
        if self.index_path and os.path.exists(f"{self.index_path}.bin"):
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

    def _load_prebuilt_index(self):
        """Load pre-built FAISS index (no embedder needed at runtime)."""
        import faiss

        print(f"Loading pre-built index from {self.index_path}")
        # Load FAISS index
        self._faiss = faiss.read_index(f"{self.index_path}.bin")

        # Load taxonomy metadata
        with open(f"{self.index_path}.json", 'r') as f:
            self._taxonomies = json.load(f)

        print(f"Loaded {len(self._taxonomies)} taxonomies from pre-built index")

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

        Uses semantic search if embedder available, otherwise falls back to keyword matching.

        Args:
            query: Natural language query
            top_k: Number of results to return
            min_score: Minimum similarity score (0-1, higher is more similar)

        Returns:
            List of taxonomy dicts with similarity scores
        """
        if not self._taxonomies:
            return []

        # If no FAISS index but we have taxonomies, use keyword fallback
        if not self._faiss:
            return self._keyword_search(query, top_k)

        # Check if embedder is available
        if self.embedder is None:
            return self._keyword_search(query, top_k)

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

    def _keyword_search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Fallback keyword-based search when ML model unavailable.

        Matches query terms against taxonomy classification, specialization, and description.
        """
        query_lower = query.lower()
        query_terms = query_lower.split()

        results = []
        for taxonomy in self._taxonomies:
            score = 0.0

            # Check classification
            classification = taxonomy.get("classification", "") or ""
            if classification.lower() in query_lower:
                score += 1.0
            for term in query_terms:
                if term in classification.lower():
                    score += 0.3

            # Check specialization
            specialization = taxonomy.get("specialization", "") or ""
            if specialization.lower() in query_lower:
                score += 0.8
            for term in query_terms:
                if term in specialization.lower():
                    score += 0.2

            # Check description
            description = taxonomy.get("description", "") or ""
            if description.lower() in query_lower:
                score += 0.5
            for term in query_terms:
                if term in description.lower():
                    score += 0.1

            if score > 0:
                result = dict(taxonomy)
                result["score"] = min(score / 3.0, 1.0)  # Normalize to 0-1
                results.append(result)

        # Sort by score and return top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
