"""
get_npi_for_provider MCP tool.

Searches for NPI by provider name and optional filters.
"""

from typing import Optional

from app.clients.nppes import NPPESClient
from app.clients.cache import CacheClient


async def get_npi_for_provider(
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    organization_name: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    zip_code: Optional[str] = None,
    specialty: Optional[str] = None,
    nppes_client: Optional[NPPESClient] = None,
    cache: Optional[CacheClient] = None
):
    """
    Search for a provider's NPI by name and location.

    Args:
        first_name: Provider first name
        last_name: Provider last name
        organization_name: Organization name (for facilities)
        city: City filter
        state: State filter
        zip_code: ZIP code filter
        specialty: Taxonomy code filter (e.g., "207Q00000X")
        nppes_client: NPPESClient instance (optional, for testing)
        cache: CacheClient instance (optional, for testing)

    Returns:
        Dict with NPI or not found status
    """
    # Require at least one name parameter
    if not any([first_name, last_name, organization_name]):
        return {
            "error": "At least one of first_name, last_name, or organization_name is required",
            "found": False
        }

    # Initialize clients if not provided
    if nppes_client is None:
        nppes_client = NPPESClient()

    if cache is None:
        cache = CacheClient()

    # Build cache key
    cache_key = cache.build_search_key(
        name=first_name or last_name,
        city=city,
        state=state,
        specialty=specialty
    )

    async def search_providers() -> list[dict]:
        """Search for providers."""
        return await nppes_client.search_by_name_and_fields(
            first_name=first_name,
            last_name=last_name,
            organization_name=organization_name,
            city=city,
            state=state,
            zip_code=zip_code,
            specialty=specialty,
            limit=10
        )

    # Get from cache or fetch
    providers = await cache.get_or_fetch(cache_key, search_providers)

    # Return not found if no results
    if not providers:
        return {
            "found": False,
            "error": "No provider found matching the given criteria"
        }

    # Return first match
    first_provider = providers[0]
    npi = first_provider.get("number") or first_provider.get("npi")

    return {
        "found": True,
        "npi": npi,
        "data": first_provider
    }