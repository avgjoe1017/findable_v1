"""Tests for health check endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """Test health endpoint returns healthy status."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient) -> None:
    """Test root endpoint returns API info."""
    response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Findable Score Analyzer API"
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_v1_root(client: AsyncClient) -> None:
    """Test v1 API root endpoint."""
    response = await client.get("/v1/")

    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "1"
    assert data["status"] == "active"
