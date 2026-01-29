"""Tests for Pydantic schemas."""

from api.schemas import (
    ErrorDetail,
    ErrorResponse,
    MessageResponse,
    paginated_meta,
)


def test_error_detail() -> None:
    """Test ErrorDetail schema."""
    error = ErrorDetail(code="not_found", message="Resource not found")
    assert error.code == "not_found"
    assert error.message == "Resource not found"
    assert error.field is None


def test_error_response() -> None:
    """Test ErrorResponse schema."""
    response = ErrorResponse(
        error=ErrorDetail(code="validation_error", message="Invalid input", field="email")
    )
    assert response.error.code == "validation_error"
    assert response.error.field == "email"


def test_message_response() -> None:
    """Test MessageResponse schema."""
    response = MessageResponse(message="Operation successful")
    assert response.message == "Operation successful"


def test_paginated_meta() -> None:
    """Test paginated_meta helper."""
    meta = paginated_meta(total=100, page=2, per_page=20)
    assert meta.total == 100
    assert meta.page == 2
    assert meta.per_page == 20
    assert meta.total_pages == 5
    assert meta.has_next is True
    assert meta.has_prev is True


def test_paginated_meta_first_page() -> None:
    """Test paginated_meta for first page."""
    meta = paginated_meta(total=50, page=1, per_page=20)
    assert meta.has_prev is False
    assert meta.has_next is True


def test_paginated_meta_last_page() -> None:
    """Test paginated_meta for last page."""
    meta = paginated_meta(total=50, page=3, per_page=20)
    assert meta.has_prev is True
    assert meta.has_next is False


def test_paginated_meta_empty() -> None:
    """Test paginated_meta for empty results."""
    meta = paginated_meta(total=0, page=1, per_page=20)
    assert meta.total_pages == 0
    assert meta.has_prev is False
    assert meta.has_next is False
