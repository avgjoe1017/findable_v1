# syntax=docker/dockerfile:1

# =============================================================================
# Findable Score Analyzer - Production Dockerfile
# =============================================================================
# Multi-stage build for optimized production images
# Supports: API server, Worker, and Scheduler services
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Base image with system dependencies
# -----------------------------------------------------------------------------
FROM python:3.11-slim as base

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Stage 2: Dependencies installation
# -----------------------------------------------------------------------------
FROM base as deps

# Copy only dependency files first (for better caching)
COPY pyproject.toml ./
COPY README.md ./

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# -----------------------------------------------------------------------------
# Stage 3: Production API image
# -----------------------------------------------------------------------------
FROM deps as api

# Copy application code
COPY api/ ./api/
COPY migrations/ ./migrations/
COPY web/ ./web/
COPY scripts/ ./scripts/
COPY alembic.ini ./

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Start command
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# -----------------------------------------------------------------------------
# Stage 4: Worker image (with Playwright for rendering)
# -----------------------------------------------------------------------------
FROM deps as worker

# Install Playwright and its dependencies
RUN pip install playwright && \
    playwright install chromium --with-deps

# Copy application code
COPY api/ ./api/
COPY worker/ ./worker/
COPY scripts/ ./scripts/

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Start command
CMD ["python", "-m", "worker.main"]

# -----------------------------------------------------------------------------
# Stage 5: Scheduler image (for rq-scheduler)
# -----------------------------------------------------------------------------
FROM deps as scheduler

# Copy application code
COPY api/ ./api/
COPY worker/ ./worker/
COPY scripts/ ./scripts/

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Start command
CMD ["python", "-m", "worker.scheduler"]

# -----------------------------------------------------------------------------
# Stage 6: Migration image (for database migrations)
# -----------------------------------------------------------------------------
FROM deps as migrate

# Copy migration files
COPY api/ ./api/
COPY migrations/ ./migrations/
COPY alembic.ini ./

# Run migrations
CMD ["alembic", "upgrade", "head"]
