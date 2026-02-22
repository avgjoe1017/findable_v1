"""Redis connection utilities."""

from functools import lru_cache

from redis import ConnectionPool, Redis

from api.config import get_settings


@lru_cache
def get_redis_pool() -> ConnectionPool:
    """Get a cached Redis connection pool."""
    settings = get_settings()
    return ConnectionPool.from_url(
        str(settings.redis_url),
        decode_responses=True,
        max_connections=10,
    )


def get_redis_connection() -> Redis:
    """Get a Redis connection from the pool."""
    pool = get_redis_pool()
    return Redis(connection_pool=pool)


@lru_cache
def _get_redis_pool_bytes() -> ConnectionPool:
    """Get a cached Redis connection pool for byte-mode (RQ)."""
    settings = get_settings()
    return ConnectionPool.from_url(
        str(settings.redis_url),
        decode_responses=False,
        max_connections=10,
    )


def get_redis_connection_bytes() -> Redis:
    """Get a Redis connection without decode_responses for RQ."""
    pool = _get_redis_pool_bytes()
    return Redis(connection_pool=pool)


# Queue names
QUEUE_HIGH = "findable-high"
QUEUE_DEFAULT = "findable-default"
QUEUE_LOW = "findable-low"

# Job result TTL (7 days)
JOB_RESULT_TTL = 60 * 60 * 24 * 7
