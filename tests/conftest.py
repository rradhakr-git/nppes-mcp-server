"""
Pytest configuration and shared fixtures.
"""

import sys
from pathlib import Path

# Add project root to path so tests can import app and tests modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

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
from stubs.nppes_responses import (
    VALID_STATE_SEARCH_RESPONSE,
    EMPTY_SEARCH_RESPONSE,
    SERVER_ERROR_RESPONSE,
    INVALID_REQUEST_RESPONSE,
)