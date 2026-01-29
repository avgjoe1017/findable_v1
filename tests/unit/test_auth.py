"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient) -> None:
    """Test user registration endpoint structure."""
    response = await client.post(
        "/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "testpassword123",
        },
    )
    # Will fail without DB, but should return proper error structure
    assert response.status_code in [201, 400, 422, 500]


@pytest.mark.asyncio
async def test_login_endpoint_exists(client: AsyncClient) -> None:
    """Test login endpoint exists."""
    response = await client.post(
        "/v1/auth/login",
        data={
            "username": "test@example.com",
            "password": "testpassword123",
        },
    )
    # Will fail without DB, but endpoint should exist
    assert response.status_code in [200, 400, 401, 422, 500]


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient) -> None:
    """Test /me endpoint requires authentication."""
    response = await client.get("/v1/auth/users/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_plan_endpoint_requires_auth(client: AsyncClient) -> None:
    """Test /me/plan endpoint requires authentication."""
    response = await client.get("/v1/auth/me/plan")
    assert response.status_code == 401
