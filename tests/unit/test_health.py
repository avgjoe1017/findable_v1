"""Tests for health check endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """Test health endpoint returns healthy status."""
    response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_root_endpoint_returns_dashboard(client: AsyncClient) -> None:
    """Test root endpoint returns the web dashboard."""
    response = await client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert b"Findable" in response.content


@pytest.mark.asyncio
async def test_api_root_returns_info(client: AsyncClient) -> None:
    """Test API root endpoint returns API info."""
    response = await client.get("/api/")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Findable Score Analyzer API"
    assert data["version"] == "0.1.0"
    assert "env" in data


@pytest.mark.asyncio
async def test_v1_root(client: AsyncClient) -> None:
    """Test v1 API root endpoint."""
    response = await client.get("/v1/")

    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "1"
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_ready_endpoint_structure(client: AsyncClient) -> None:
    """Test ready endpoint returns expected structure."""
    response = await client.get("/api/ready")

    # May be unhealthy if DB/Redis not running, but structure should be correct
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "timestamp" in data
    assert "version" in data
    assert "checks" in data
    assert "database" in data["checks"]
    assert "redis" in data["checks"]
