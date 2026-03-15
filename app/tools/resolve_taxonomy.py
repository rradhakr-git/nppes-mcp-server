"""
resolve_taxonomy MCP tool.

Resolves taxonomy codes or performs semantic search over taxonomy descriptions.
"""

from typing import Optional

from app.rag.index import TaxonomyIndex


async def resolve_taxonomy(
    code: Optional[str] = None,
    query: Optional[str] = None,
    taxonomy_index: Optional[TaxonomyIndex] = None,
    top_k: int = 5,
    min_score: float = 0.0
) -> dict:
    """
    Resolve a taxonomy code or search by natural language query.

    Args:
        code: Specific taxonomy code (e.g., "207Q00000X")
        query: Natural language query (e.g., "heart doctor")
        taxonomy_index: TaxonomyIndex instance
        top_k: Number of results for semantic search
        min_score: Minimum similarity score for semantic search

    Returns:
        Taxonomy dict with code, classification, specialization, description
        Returns empty dict if no match found
    """
    if taxonomy_index is None:
        from app.rag.embedder import Embedder
        embedder = Embedder()
        taxonomy_index = TaxonomyIndex(embedder=embedder)

    # If code is provided, do direct lookup
    if code:
        # Search taxonomies for matching code
        for taxonomy in taxonomy_index._taxonomies:
            if taxonomy.get("code") == code:
                return taxonomy
        return {}

    # If query is provided, use RAG semantic search
    if query:
        results = await taxonomy_index.search(
            query=query,
            top_k=top_k,
            min_score=min_score
        )
        if results:
            # Return first (highest scoring) result
            return results[0]

    # No code or query provided
    return {}
