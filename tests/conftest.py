"""Pytest configuration and fixtures."""

import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Set test environment before any app code runs (CI must use same credentials)
os.environ["ENV"] = "test"
os.environ["JWT_SECRET"] = "test-secret-key"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/findable_test"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"


@pytest.fixture(scope="session")
async def setup_database() -> AsyncGenerator[None, None]:
    """Set up test database with all tables."""
    from api.config import get_settings

    get_settings.cache_clear()  # Use test env/DB, not stale or .env values
    from api.database import Base
    from api.models.alert import Alert, AlertConfig  # noqa: F401
    from api.models.billing import (  # noqa: F401
        BillingEvent,
        Subscription,
        UsageRecord,
        UsageSummary,
    )
    from api.models.run import Report, Run  # noqa: F401
    from api.models.site import Competitor, Site  # noqa: F401
    from api.models.snapshot import MonitoringSchedule, Snapshot  # noqa: F401

    # Import all models to register them with Base.metadata
    from api.models.user import User  # noqa: F401

    settings = get_settings()

    # Create async engine for test database
    engine = create_async_engine(str(settings.database_url), echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Clean up: drop all tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(setup_database) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for tests."""
    from api.config import get_settings

    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), echo=False)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def client(setup_database) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client."""
    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
