"""Database connection and session management."""

from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


@lru_cache
def get_engine() -> AsyncEngine:
    """
    Get the async database engine (lazy initialization).

    The engine is created on first call and cached for subsequent calls.
    This avoids creating the engine at module import time.
    """
    from api.config import get_settings

    settings = get_settings()
    return create_async_engine(
        str(settings.database_url),
        echo=settings.debug,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


@lru_cache
def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """
    Get the async session maker (lazy initialization).

    Creates the session factory on first call and caches it.
    """
    engine = get_engine()
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


# Alias for backwards compatibility - lazily evaluated
def _get_async_session_maker() -> async_sessionmaker[AsyncSession]:
    """Get session maker (for backwards compatibility)."""
    return get_session_maker()


class _SessionMakerProxy:
    """Proxy object that lazily initializes the session maker."""

    def __call__(self) -> AsyncSession:
        return get_session_maker()()

    def __getattr__(self, name: str):
        return getattr(get_session_maker(), name)


# Backwards compatible session maker - lazily initialized
async_session_maker = _SessionMakerProxy()


class _EngineProxy:
    """Proxy object that lazily initializes the engine."""

    def __getattr__(self, name: str):
        return getattr(get_engine(), name)


# Backwards compatible engine - lazily initialized
engine = _EngineProxy()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Type alias for dependency injection
DbSession = Annotated[AsyncSession, Depends(get_db)]


def reset_engine() -> None:
    """
    Reset the cached engine and session maker.

    Useful for tests that need to reconfigure the database connection.
    """
    get_engine.cache_clear()
    get_session_maker.cache_clear()
