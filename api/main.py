"""FastAPI application factory and main entrypoint."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from api.config import get_settings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup/shutdown events."""
    settings = get_settings()
    logger.info("Starting Findable API", env=settings.env, debug=settings.debug)
    yield
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
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    from api.routers import health, v1

    app.include_router(health.router)
    app.include_router(v1.router, prefix="/v1")

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> ORJSONResponse:
        logger.error("Unhandled exception", exc_info=exc, path=request.url.path)
        return ORJSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred",
                }
            },
        )

    return app


app = create_app()
