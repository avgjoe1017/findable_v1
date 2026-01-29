"""Tests for custom exceptions and error handling."""

import pytest
from fastapi import status

from api.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    FindableError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)


def test_findable_error_base() -> None:
    """Test base FindableError."""
    error = FindableError(message="Test error", code="test_error")
    assert error.message == "Test error"
    assert error.code == "test_error"
    assert error.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert error.details == {}


def test_not_found_error() -> None:
    """Test NotFoundError."""
    error = NotFoundError("Site")
    assert error.message == "Site not found"
    assert error.code == "not_found"
    assert error.status_code == status.HTTP_404_NOT_FOUND

    error_with_id = NotFoundError("Site", "123")
    assert error_with_id.message == "Site with id '123' not found"


def test_validation_error() -> None:
    """Test ValidationError."""
    error = ValidationError("Invalid email", field="email")
    assert error.message == "Invalid email"
    assert error.code == "validation_error"
    assert error.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert error.details == {"field": "email"}


def test_authentication_error() -> None:
    """Test AuthenticationError."""
    error = AuthenticationError()
    assert error.message == "Authentication required"
    assert error.code == "authentication_error"
    assert error.status_code == status.HTTP_401_UNAUTHORIZED


def test_authorization_error() -> None:
    """Test AuthorizationError."""
    error = AuthorizationError()
    assert error.message == "Permission denied"
    assert error.code == "authorization_error"
    assert error.status_code == status.HTTP_403_FORBIDDEN


def test_conflict_error() -> None:
    """Test ConflictError."""
    error = ConflictError("Resource already exists")
    assert error.message == "Resource already exists"
    assert error.code == "conflict"
    assert error.status_code == status.HTTP_409_CONFLICT


def test_rate_limit_error() -> None:
    """Test RateLimitError."""
    error = RateLimitError()
    assert error.message == "Rate limit exceeded"
    assert error.code == "rate_limit_exceeded"
    assert error.status_code == status.HTTP_429_TOO_MANY_REQUESTS
