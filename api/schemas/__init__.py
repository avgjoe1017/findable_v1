"""Pydantic schemas package."""

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Standard error detail."""

    code: str
    message: str
    field: str | None = None


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    error: ErrorDetail


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str
