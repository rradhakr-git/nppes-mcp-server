"""
search_providers MCP tool.

Searches the NPPES registry for healthcare providers with caching.
"""

from typing import Optional

from app.clients.cache import CacheClient
from app.clients.nppes import NPPESClient, Provider


# Default cache TTL in seconds (1 hour)
DEFAULT_TTL = 3600


async def search_providers(
    name: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    organization_name: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    specialty: Optional[str] = None,
    limit: int = 10,
    cache: Optional[CacheClient] = None,
    nppes_client: Optional[NPPESClient] = None,
    ttl_seconds: int = DEFAULT_TTL
) -> list[Provider]:
    """
    Search for healthcare providers in the NPPES registry.

    Uses cache to avoid redundant NPPES API calls.

    Args:
        name: Provider first name (deprecated, use first_name instead)
        first_name: Provider first name
        last_name: Provider last name
        organization_name: Organization/facility name
        city: City filter
        state: Two-letter state code
        specialty: Taxonomy/specialty filter
        limit: Maximum results to return
        cache: CacheClient instance (optional, creates default if not provided)
        nppes_client: NPPESClient instance (optional, creates default if not provided)
        ttl_seconds: Cache TTL in seconds

    Returns:
        List of provider dictionaries
    """
    # Use provided clients or create defaults
    if cache is None:
        cache = CacheClient()
    if nppes_client is None:
        nppes_client = NPPESClient()

    # Build cache key from search parameters
    cache_key = cache.build_search_key(
        name=name or first_name or last_name,
        city=city,
        state=state,
        specialty=specialty,
        limit=limit
    )

    # Define fetch function that calls NPPES API
    async def fetch_providers() -> list[Provider]:
        return await nppes_client.search(
            name=name,
            first_name=first_name,
            last_name=last_name,
            organization_name=organization_name,
            city=city,
            state=state,
            specialty=specialty,
            limit=limit
        )

    # Get from cache or fetch from NPPES
    result = await cache.get_or_fetch(cache_key, fetch_providers)

    return result
