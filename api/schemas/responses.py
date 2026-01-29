"""Standard API response schemas."""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Error detail in response."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    field: str | None = Field(None, description="Field that caused the error")
    details: dict[str, Any] | None = Field(None, description="Additional error details")


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    error: ErrorDetail


class SuccessResponse(BaseModel, Generic[T]):
    """Standard success response envelope."""

    data: T
    meta: dict[str, Any] | None = None


class PaginatedMeta(BaseModel):
    """Pagination metadata."""

    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number (1-indexed)")
    per_page: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response envelope."""

    data: list[T]
    meta: PaginatedMeta


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str


class StatusResponse(BaseModel):
    """Status response with optional details."""

    status: str
    message: str | None = None
    details: dict[str, Any] | None = None


class JobResponse(BaseModel):
    """Background job response."""

    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status: queued, running, complete, failed")
    created_at: datetime
    updated_at: datetime | None = None
    progress: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


def paginated_meta(total: int, page: int, per_page: int) -> PaginatedMeta:
    """Create pagination metadata."""
    total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0
    return PaginatedMeta(
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )
