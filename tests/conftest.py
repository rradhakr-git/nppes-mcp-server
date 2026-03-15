"""
Pytest configuration and shared fixtures.
"""

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def nppes_client():
    """Provide an NPPESClient instance for tests."""
    from app.clients.nppes import NPPESClient
    client = NPPESClient()
    yield client
    await client.close()


# Import stubs for easy access in tests
from tests.stubs.nppes_responses import (
    VALID_STATE_SEARCH_RESPONSE,
    EMPTY_SEARCH_RESPONSE,
    SERVER_ERROR_RESPONSE,
    INVALID_REQUEST_RESPONSE,
)