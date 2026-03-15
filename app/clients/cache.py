"""
Redis cache wrapper for NPPES API responses.
"""

import json
import hashlib
import os
from typing import Optional, Callable, Any, Awaitable

import redis.asyncio as redis


# Environment-based defaults
DEFAULT_TTL = 3600  # 1 hour in seconds
DEFAULT_REDIS_URL = "redis://localhost:6379"
DEFAULT_KEY_PREFIX = "nppes"


def _get_env_int(name: str, default: int) -> int:
    """Get integer from environment, with fallback."""
    return int(os.getenv(name, default))


def _get_env_str(name: str, default: str) -> str:
    """Get string from environment, with fallback."""
    return os.getenv(name, default)


class CacheClient:
    """
    Async Redis cache client with TTL support.

    Wraps NPPES API responses with caching to reduce API calls.

    Environment variables:
        REDIS_URL: Redis connection URL (default: redis://localhost:6379)
        CACHE_TTL_SECONDS: Cache TTL in seconds (default: 3600)
        CACHE_KEY_PREFIX: Prefix for cache keys (default: nppes)
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        ttl: Optional[int] = None,
        key_prefix: Optional[str] = None,
        client: Optional[redis.Redis] = None
    ):
        self.redis_url = redis_url or _get_env_str("REDIS_URL", DEFAULT_REDIS_URL)
        self.ttl = ttl or _get_env_int("CACHE_TTL_SECONDS", DEFAULT_TTL)
        self.key_prefix = key_prefix or _get_env_str("CACHE_KEY_PREFIX", DEFAULT_KEY_PREFIX)
        self._client = client

    async def _get_client(self) -> redis.Redis:
        """Get or create the Redis client."""
        if self._client is None:
            self._client = redis.from_url(self.redis_url, decode_responses=True)
        return self._client

    async def get_or_fetch(
        self,
        key: str,
        fetch_fn: Callable[[], Awaitable[list[dict]]]
    ) -> list[dict]:
        """
        Get value from cache, or fetch from source if missing/expired.

        Gracefully degrades to passthrough if Redis is unavailable.

        Args:
            key: Cache key
            fetch_fn: Async function to call if cache miss

        Returns:
            List of provider dicts
        """
        try:
            client = await self._get_client()

            # Try to get from cache
            cached = await client.get(key)
            if cached is not None:
                return json.loads(cached)

            # Cache miss - call fetch_fn
            result = await fetch_fn()

            # Store in cache with TTL
            await client.set(key, json.dumps(result), ex=self.ttl)

            return result
        except Exception:
            # Graceful degradation: if cache fails, just call fetch_fn directly
            return await fetch_fn()

    async def get(self, key: str) -> Optional[str]:
        """Get a raw string value from cache."""
        client = await self._get_client()
        return await client.get(key)

    async def set(self, key: str, value: str, ex: int = None) -> bool:
        """Set a string value in cache with optional TTL."""
        client = await self._get_client()
        ex = ex or self.ttl
        return await client.set(key, value, ex=ex)

    def build_search_key(
        self,
        name: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        specialty: Optional[str] = None,
        limit: int = 10
    ) -> str:
        """
        Build a consistent cache key from search parameters.

        Args:
            name: Provider name filter
            city: City filter
            state: State filter
            specialty: Specialty/taxonomy filter
            limit: Result limit

        Returns:
            Cache key string
        """
        # Build sorted tuple of params for consistent hashing
        params = []
        if name:
            params.append(f"name={name}")
        if city:
            params.append(f"city={city}")
        if state:
            params.append(f"state={state}")
        if specialty:
            params.append(f"specialty={specialty}")
        if limit != 10:
            params.append(f"limit={limit}")

        # Join params into a string
        param_str = "&".join(sorted(params)) if params else "empty"

        # Use hash for potentially long keys
        key_hash = hashlib.md5(param_str.encode()).hexdigest()[:12]

        return f"{self.key_prefix}:search:{key_hash}"

    async def close(self):
        """Close the Redis connection."""
        if self._client:
            await self._client.close()