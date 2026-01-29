"""Custom middleware for the API."""

import time
import uuid
from collections.abc import Awaitable, Callable
from typing import cast

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Type alias for call_next function
CallNext = Callable[[Request], Awaitable[Response]]

logger = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add unique request ID to each request for tracing."""

    async def dispatch(self, request: Request, call_next: CallNext) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Bind request ID to structlog context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Add to request state for access in handlers
        request.state.request_id = request_id

        response = cast(Response, await call_next(request))

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log request/response details."""

    async def dispatch(self, request: Request, call_next: CallNext) -> Response:
        start_time = time.perf_counter()

        # Log request
        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            query=str(request.query_params) if request.query_params else None,
        )

        response = cast(Response, await call_next(request))

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log response
        logger.info(
            "Request completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        return response
