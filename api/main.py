"""FastAPI application factory and main entrypoint."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from api.config import get_settings
from api.exceptions import FindableError
from api.logging import setup_logging

# Initialize logging
setup_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup/shutdown events."""
    settings = get_settings()
    logger.info(
        "Starting Findable API",
        env=settings.env,
        debug=settings.debug,
        version="0.1.0",
    )

    # Startup tasks
    # - Database connection pool is created lazily
    # - Redis connection is created per-request

    yield

    # Shutdown tasks
    logger.info("Shutting down Findable API")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Findable Score Analyzer",
        description="Measure AI sourceability for websites",
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    # Middleware (order matters - first added = last executed)
    # CORS must be last (first to process)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging and tracing
    from api.middleware import LoggingMiddleware, RequestIDMiddleware

    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # Register exception handlers
    register_exception_handlers(app)

    # Register routers
    from api.routers import health, v1

    app.include_router(health.router)
    app.include_router(v1.router, prefix="/v1")

    return app


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers."""

    @app.exception_handler(FindableError)
    async def findable_error_handler(request: Request, exc: FindableError) -> ORJSONResponse:
        """Handle custom Findable exceptions."""
        logger.warning(
            "Application error",
            error_code=exc.code,
            message=exc.message,
            path=request.url.path,
        )
        return ORJSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    **({"details": exc.details} if exc.details else {}),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> ORJSONResponse:
        """Handle Pydantic validation errors."""
        errors = exc.errors()
        first_error = errors[0] if errors else {"msg": "Validation error"}

        # Extract field path
        field = ".".join(str(loc) for loc in first_error.get("loc", [])[1:])

        logger.warning(
            "Validation error",
            path=request.url.path,
            errors=errors,
        )
        return ORJSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "validation_error",
                    "message": first_error.get("msg", "Validation error"),
                    "field": field if field else None,
                    "details": {"errors": errors},
                }
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> ORJSONResponse:
        """Handle unhandled exceptions."""
        logger.error(
            "Unhandled exception",
            exc_info=exc,
            path=request.url.path,
            method=request.method,
        )
        return ORJSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred",
                }
            },
        )


app = create_app()
