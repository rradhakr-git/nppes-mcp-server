"""
get_provider_by_npi MCP tool.

Returns full provider record by NPI with caching.
"""

from typing import Optional

from app.clients.nppes import NPPESClient
from app.clients.cache import CacheClient


# Default TTL for NPI lookups (1 hour)
DEFAULT_TTL = 3600


async def get_provider_by_npi(
    npi: str,
    nppes_client: Optional[NPPESClient] = None,
    cache: Optional[CacheClient] = None,
    ttl: int = DEFAULT_TTL
) -> dict:
    """
    Get a provider by NPI number.

    Args:
        npi: 10-digit National Provider Identifier
        nppes_client: NPPESClient instance (optional, for testing)
        cache: CacheClient instance (optional, for testing)
        ttl: Cache TTL in seconds (default: 3600)

    Returns:
        Dict with provider data or error/not_found status
    """
    # Validate NPI format
    if not npi or not npi.isdigit() or len(npi) != 10:
        return {
            "error": "NPI must be exactly 10 digits",
            "npi": npi
        }

    # Initialize clients if not provided
    if nppes_client is None:
        nppes_client = NPPESClient()

    if cache is None:
        cache = CacheClient()

    # Build cache key
    cache_key = cache.build_npi_key(npi)

    async def fetch_provider() -> Optional[dict]:
        """Fetch provider from NPPES API."""
        result = await nppes_client.get_by_npi(npi)
        return result

    # Get from cache or fetch
    provider = await cache.get_or_fetch(cache_key, fetch_provider)

    # Handle not found
    if provider is None:
        return {
            "found": False,
            "npi": npi
        }

    # Return found provider with metadata
    return {
        "found": True,
        "npi": provider.get("number") or provider.get("npi"),
        "data": provider
    }