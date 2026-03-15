"""
NPPES API client for querying the National Provider Identifier registry.
"""

import os
import httpx
from typing import Optional, Any


# NPPES API v2.1 base URL
BASE_URL = "https://npiregistry.cms.hhs.gov/api"
API_VERSION = "2.1"

NPI_ENDPOINT = "/"
DEFAULT_TIMEOUT = 30.0
DEFAULT_CONNECT_TIMEOUT = 10.0
HTTP_NOT_FOUND = 404
HTTP_SERVICE_UNAVAILABLE = 503

# Type alias for a provider record from NPPES
Provider = dict[str, Any]


def _get_env_float(name: str, default: float) -> float:
    """Get float from environment, with fallback."""
    return float(os.getenv(name, default))


class NPPESClient:
    """
    Async client for the NPPES Registry API (npiregistry.cms.hhs.gov).

    Environment variables:
        NPPES_API_URL: Override the API base URL
        REQUEST_TIMEOUT_SECONDS: Request timeout (default: 30.0)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        max_retries: int = 3,
        timeout: Optional[float] = None,
        client: Optional[httpx.AsyncClient] = None
    ):
        self.base_url = base_url or os.getenv("NPPES_API_URL", BASE_URL)
        self.max_retries = max_retries
        timeout_val = timeout or _get_env_float("REQUEST_TIMEOUT_SECONDS", DEFAULT_TIMEOUT)
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout_val, connect=DEFAULT_CONNECT_TIMEOUT)
        )

    async def search(
        self,
        name: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        specialty: Optional[str] = None,
        limit: int = 10
    ) -> list[dict]:
        """
        Search for healthcare providers in the NPPES registry.

        Args:
            name: Provider first or last name
            city: City filter
            state: Two-letter state code
            specialty: Taxonomy code filter (e.g., "207Q00000X")
            limit: Maximum results to return

        Returns:
            List of provider dictionaries
        """
        # NPPES API requires version parameter
        params = {"version": API_VERSION, "limit": limit}

        if name:
            params["first_name"] = name
        if city:
            params["city"] = city
        if state:
            params["state"] = state
        if specialty:
            params["taxonomy"] = specialty

        last_exception = None

        for attempt in range(self.max_retries):
            response = await self._client.get(NPI_ENDPOINT, params=params)

            # Check for API error responses
            data = response.json() if response.content else {}
            if "Errors" in data and data["Errors"]:
                # Return empty list on validation errors
                return []

            if response.status_code == HTTP_NOT_FOUND:
                return []

            if response.status_code == HTTP_SERVICE_UNAVAILABLE:
                last_exception = httpx.HTTPStatusError(
                    "Service unavailable",
                    request=response.request,
                    response=response
                )
                if attempt < self.max_retries - 1:
                    continue
                raise last_exception

            response.raise_for_status()
            results = data.get("results") if data else None
            if isinstance(results, list):
                return results
            return []

        return []

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
