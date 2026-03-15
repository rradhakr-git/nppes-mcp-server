"""
Build FAISS taxonomy index.

Run this before Docker build to generate the index files.
"""

import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.embedder import Embedder
from app.rag.index import TaxonomyIndex


def build_index():
    """Build and save the FAISS index."""
    print("Building FAISS taxonomy index...")

    # Initialize embedder
    embedder = Embedder()

    # Build index (this will load model, build index, save to disk)
    index = TaxonomyIndex(
        embedder=embedder,
        index_path="app/rag/taxonomy_index",
        skip_build=False
    )

    print(f"Index built successfully!")
    print(f"  - Taxonomy count: {len(index._taxonomies)}")
    print(f"  - Index dimension: {index.dimension}")
    print(f"  - Saved to: app/rag/taxonomy_index.bin")


if __name__ == "__main__":
    build_index()
