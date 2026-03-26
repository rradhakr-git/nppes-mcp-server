"""
validate_npi MCP tool.

Validates NPI format and checks registry status with longer TTL.
"""

from typing import Optional

from app.clients.nppes import NPPESClient
from app.clients.cache import CacheClient


# Default TTL for validation (24 hours - longer than provider lookup)
VALIDATE_TTL = 86400


async def validate_npi(
    npi: str,
    nppes_client: Optional[NPPESClient] = None,
    cache: Optional[CacheClient] = None,
    ttl: int = VALIDATE_TTL
) -> dict:
    """
    Validate an NPI number.

    Checks format validity and registry existence. Uses longer TTL than
    provider lookup for better cache efficiency on repeated validations.

    Args:
        npi: 10-digit National Provider Identifier
        nppes_client: NPPESClient instance (optional, for testing)
        cache: CacheClient instance (optional, for testing)
        ttl: Cache TTL in seconds (default: 86400 = 24 hours)

    Returns:
        Dict with validation result
    """
    # Initialize clients if not provided
    if nppes_client is None:
        nppes_client = NPPESClient()

    if cache is None:
        cache = CacheClient()

    # Validate format first (fail fast without API call)
    if not npi or not npi.isdigit() or len(npi) != 10:
        return {
            "valid": False,
            "npi": npi,
            "error": "NPI must be exactly 10 digits"
        }

    # Build cache key
    cache_key = cache.build_validate_key(npi)

    async def fetch_validation() -> dict:
        """Fetch validation result from NPPES client."""
        return await nppes_client.validate(npi)

    # Get from cache or fetch
    result = await cache.get_or_fetch(cache_key, fetch_validation, ttl=ttl)

    return result