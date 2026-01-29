# syntax=docker/dockerfile:1

FROM python:3.11-slim as base

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy application code
COPY . .

# --- API image ---
FROM base as api

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# --- Worker image ---
FROM base as worker

# Install Playwright for headless rendering
RUN pip install playwright && playwright install chromium --with-deps

CMD ["python", "-m", "worker.main"]
