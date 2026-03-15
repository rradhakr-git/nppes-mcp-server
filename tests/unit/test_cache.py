"""
Unit tests for Redis cache wrapper.

Tests the caching layer that wraps the NPPES client.
"""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.clients.cache import CacheClient


# =============================================================================
# Test: cache_miss_calls_through_to_nppes
# =============================================================================
@pytest.mark.asyncio
async def test_cache_miss_calls_through_to_nppes():
    """When redis.get(key) returns None, fetch_fn is called exactly once,
    redis.set/setex is called once with the same key and TTL, and the
    returned value equals the fetch result."""
    # Track calls
    fetch_call_count = 0
    set_call_count = 0

    async def mock_get(key: str):
        return None  # Cache miss

    async def mock_set(key: str, value: str, ex: int = None):
        nonlocal set_call_count
        set_call_count +=1

    async def fetch_fn():
        nonlocal fetch_call_count
        fetch_call_count +=1
        return [{"npi": "1234567890", "basic": {"first_name": "John"}}]

    # Create mock client
    mock_client = MagicMock()
    mock_client.get = mock_get
    mock_client.set = mock_set

    # Inject mock client via constructor
    cache = CacheClient(client=mock_client)

    result = await cache.get_or_fetch("nppes:search:state=CT", fetch_fn)

    assert fetch_call_count == 1, "fetch_fn should be called exactly once on cache miss"
    assert set_call_count == 1, "redis.set should be called once on cache miss"
    assert result == [{"npi": "1234567890", "basic": {"first_name": "John"}}]


# =============================================================================
# Test: cache_hit_returns_without_calling_nppes
# =============================================================================
@pytest.mark.asyncio
async def test_cache_hit_returns_without_calling_nppes():
    """When redis.get(key) returns a cached list, fetch_fn is never called,
    no new set/setex is issued, and the cached value is returned."""
    cached_data = json.dumps([{"npi": "1234567890", "basic": {"first_name": "John"}}])
    fetch_call_count = 0
    set_call_count = 0

    async def mock_get(key: str):
        return cached_data  # Cache hit

    async def mock_set(key: str, value: str, ex: int = None):
        nonlocal set_call_count
        set_call_count +=1

    async def fetch_fn():
        nonlocal fetch_call_count
        fetch_call_count +=1
        return [{"npi": "9999999999"}]  # Should not be called

    mock_client = MagicMock()
    mock_client.get = mock_get
    mock_client.set = mock_set

    cache = CacheClient(client=mock_client)

    result = await cache.get_or_fetch("nppes:search:state=CT", fetch_fn)

    assert fetch_call_count == 0, "fetch_fn should NOT be called on cache hit"
    assert set_call_count == 0, "redis.set should NOT be called on cache hit"
    assert result == [{"npi": "1234567890", "basic": {"first_name": "John"}}]


# =============================================================================
# Test: cache_key_includes_all_search_params
# =============================================================================
@pytest.mark.asyncio
async def test_cache_key_includes_all_search_params():
    """A helper like build_search_key must produce different keys when any
    search parameter differs, and the same key when all parameters are equal."""
    cache = CacheClient()

    # Different params should produce different keys
    key1 = cache.build_search_key(state="CT")
    key2 = cache.build_search_key(state="CT", city="Hartford")
    key3 = cache.build_search_key(state="CT", city="Hartford", name="John")
    key4 = cache.build_search_key(state="NY")

    assert key1 != key2, "key with state only should differ from state+city"
    assert key2 != key3, "key with state+city should differ from state+city+name"
    assert key1 != key4, "key with CT should differ from NY"
    assert key3 != key4, "key with CT+city+name should differ from NY"

    # Same params should produce same key
    key1_again = cache.build_search_key(state="CT")
    key2_again = cache.build_search_key(state="CT", city="Hartford")

    assert key1 == key1_again, "same params should produce same key"
    assert key2 == key2_again, "same params should produce same key"


# =============================================================================
# Test: expired_entry_triggers_refresh
# =============================================================================
@pytest.mark.asyncio
async def test_expired_entry_triggers_refresh():
    """After an initial cache fill, simulating expiry causes a second call
    to invoke fetch_fn again and overwrite the cached value with the new result."""
    fetch_results = ["FIRST_RESULT", "SECOND_RESULT"]
    call_index = 0

    class MockRedis:
        def __init__(self):
            self.calls = []

        async def get(self, key: str):
            self.calls.append(("get", key))
            # Return None to simulate expired entry
            return None

        async def set(self, key: str, value: str, ex: int = None):
            self.calls.append(("set", key))

        async def aclose(self):
            pass

    mock_client = MockRedis()

    async def fetch_fn():
        nonlocal call_index
        result = fetch_results[call_index]
        call_index += 1
        return [{"npi": result}]

    cache = CacheClient(client=mock_client)

    # First call - should fetch
    result1 = await cache.get_or_fetch("nppes:search:state=CT", fetch_fn)
    assert result1 == [{"npi": "FIRST_RESULT"}]

    # Second call - cache is expired (get returns None), should fetch again
    result2 = await cache.get_or_fetch("nppes:search:state=CT", fetch_fn)
    assert result2 == [{"npi": "SECOND_RESULT"}], "Expired entries should trigger fetch_fn call"