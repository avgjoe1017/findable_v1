"""Custom exceptions and error handling."""

from typing import Any

from fastapi import HTTPException, status


class FindableError(Exception):
    """Base exception for Findable application."""

    def __init__(
        self,
        message: str,
        code: str = "error",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(FindableError):
    """Resource not found."""

    def __init__(self, resource: str, identifier: str | None = None):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} with id '{identifier}' not found"
        super().__init__(
            message=message,
            code="not_found",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ValidationError(FindableError):
    """Validation error."""

    def __init__(self, message: str, field: str | None = None):
        details = {"field": field} if field else {}
        super().__init__(
            message=message,
            code="validation_error",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class AuthenticationError(FindableError):
    """Authentication failed."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            code="authentication_error",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class AuthorizationError(FindableError):
    """Authorization failed."""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            code="authorization_error",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ConflictError(FindableError):
    """Resource conflict."""

    def __init__(self, message: str):
        super().__init__(
            message=message,
            code="conflict",
            status_code=status.HTTP_409_CONFLICT,
        )


class RateLimitError(FindableError):
    """Rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            code="rate_limit_exceeded",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


class ExternalServiceError(FindableError):
    """External service error."""

    def __init__(self, service: str, message: str):
        super().__init__(
            message=f"{service}: {message}",
            code="external_service_error",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={"service": service},
        )


def raise_not_found(resource: str, identifier: str | None = None) -> None:
    """Raise HTTP 404 Not Found."""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": {
                "code": "not_found",
                "message": (
                    f"{resource} not found"
                    if not identifier
                    else f"{resource} with id '{identifier}' not found"
                ),
            }
        },
    )


def raise_bad_request(message: str, code: str = "bad_request") -> None:
    """Raise HTTP 400 Bad Request."""
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"error": {"code": code, "message": message}},
    )
