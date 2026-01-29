"""FastAPI dependencies for dependency injection."""

from typing import Annotated

from fastapi import Depends, Query
from redis import Redis

from api.config import Settings, get_settings
from api.database import DbSession

# Re-export DbSession for convenience
__all__ = ["DbSession", "SettingsDep", "RedisDep", "PaginationParams"]


# Settings dependency
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_redis() -> Redis:
    """Get Redis connection."""
    settings = get_settings()
    return Redis.from_url(str(settings.redis_url), decode_responses=True)


RedisDep = Annotated[Redis, Depends(get_redis)]


class PaginationParams:
    """Pagination query parameters."""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    ):
        self.page = page
        self.per_page = per_page
        self.offset = (page - 1) * per_page
        self.limit = per_page


PaginationDep = Annotated[PaginationParams, Depends()]
