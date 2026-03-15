"""
semantic_search MCP tool.

Combines RAG-based taxonomy search with NPPES provider search.
"""

from typing import Optional

from app.rag.index import TaxonomyIndex
from app.clients.cache import CacheClient
from app.clients.nppes import NPPESClient, Provider


async def semantic_search(
    query: str,
    state: Optional[str] = None,
    city: Optional[str] = None,
    taxonomy_index: Optional[TaxonomyIndex] = None,
    nppes_client: Optional[NPPESClient] = None,
    cache: Optional[CacheClient] = None,
    top_k: int = 5,
    min_score: float = 0.0
) -> list[Provider]:
    """
    Search for providers using natural language query.

    Combines RAG taxonomy search with NPPES provider search.

    Args:
        query: Natural language query (e.g., "cardiologist in Connecticut")
        state: Optional state filter
        city: Optional city filter
        taxonomy_index: TaxonomyIndex instance
        nppes_client: NPPESClient instance
        cache: CacheClient instance
        top_k: Number of taxonomy codes to search
        min_score: Minimum similarity score for taxonomy match

    Returns:
        List of provider dictionaries
    """
    # Initialize defaults
    if taxonomy_index is None:
        from app.rag.embedder import Embedder
        embedder = Embedder()
        taxonomy_index = TaxonomyIndex(embedder=embedder)

    if nppes_client is None:
        nppes_client = NPPESClient()

    if cache is None:
        cache = CacheClient()

    # Step 1: Use RAG to find matching taxonomy codes
    taxonomy_results = await taxonomy_index.search(
        query=query,
        top_k=top_k,
        min_score=min_score
    )

    # If no taxonomies match, return empty
    if not taxonomy_results:
        return []

    # Step 2: Extract taxonomy codes
    taxonomy_codes = [t["code"] for t in taxonomy_results]

    # Step 3: Build cache key
    cache_key = cache.build_search_key(
        specialty=",".join(taxonomy_codes),
        state=state,
        city=city
    )

    # Step 4: Search NPPES with taxonomy codes
    async def fetch_providers() -> list[Provider]:
        # Search with each taxonomy code and combine results
        all_providers = []
        seen_npis = set()

        for code in taxonomy_codes:
            providers = await nppes_client.search(
                specialty=code,
                state=state,
                city=city,
                limit=10
            )

            # Deduplicate by NPI
            for provider in providers:
                npi = provider.get("npi")
                if npi and npi not in seen_npis:
                    seen_npis.add(npi)
                    all_providers.append(provider)

        return all_providers

    # Get from cache or fetch
    results = await cache.get_or_fetch(cache_key, fetch_providers)

    return results
