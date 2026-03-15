"""
Redis stub for testing - uses fakeredis to simulate Upstash Redis.
"""

import fakeredis.aioredis
from typing import Optional, Any


class RedisStub:
    """Fake Redis client for testing cache behavior."""

    def __init__(self):
        self._client = fakeredis.aioredis.FakeRedis()
        self._store: dict[str, tuple[Any, float]] = {}  # key -> (value, expiry_timestamp)

    async def get(self, key: str) -> Optional[str]:
        """Get a value by key."""
        import time
        if key in self._store:
            value, expiry = self._store[key]
            if expiry == 0 or expiry > time.time():
                return value
            else:
                del self._store[key]
        return None

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set a key-value pair with optional expiry in seconds."""
        import time
        expiry = time.time() + ex if ex else 0
        self._store[key] = (value, expiry)
        return True

    async def close(self):
        """Close the connection."""
        self._store.clear()
