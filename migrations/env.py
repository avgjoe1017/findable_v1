"""Alembic environment configuration."""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from api.database import Base

# Import all models to register them with Base.metadata
from api.models.alert import Alert, AlertConfig  # noqa: F401
from api.models.billing import (  # noqa: F401
    BillingEvent,
    Subscription,
    UsageRecord,
    UsageSummary,
)
from api.models.embedding import Embedding  # noqa: F401
from api.models.run import Report, Run  # noqa: F401
from api.models.site import Competitor, Site  # noqa: F401
from api.models.snapshot import MonitoringSchedule, Snapshot  # noqa: F401
from api.models.user import User  # noqa: F401

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _normalize_async_url(url: str) -> str:
    """Use asyncpg so we don't require psycopg2 in the image."""
    if url.startswith("postgresql://") and "asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


# Prefer DATABASE_URL from environment so migrations can run when only Postgres is linked
# (no need for REDIS_URL or JWT_SECRET in the migration subprocess)
_raw_url = os.getenv("DATABASE_URL")
if _raw_url:
    config.set_main_option("sqlalchemy.url", _normalize_async_url(_raw_url))
else:
    from api.config import get_settings

    settings = get_settings()
    config.set_main_option("sqlalchemy.url", _normalize_async_url(str(settings.database_url)))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL only; uses same url as online)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    # Pass url explicitly; get_section() only returns [alembic] from ini, not sqlalchemy.url
    configuration = config.get_section(config.config_ini_section, {})
    configuration["url"] = config.get_main_option("sqlalchemy.url")
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
