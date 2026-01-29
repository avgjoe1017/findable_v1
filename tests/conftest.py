"""Pytest configuration and fixtures."""

import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

# Set test environment before importing app
os.environ["ENV"] = "test"
os.environ["JWT_SECRET"] = "test-secret-key"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/findable_test"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create async test client."""
    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
