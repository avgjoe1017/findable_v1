#!/bin/bash

# Local development helper script

set -e

echo "Starting Findable local development..."

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Start services
echo "Starting Postgres and Redis..."
docker-compose up -d

# Wait for services
echo "Waiting for services to be ready..."
sleep 3

# Check postgres
until docker-compose exec -T postgres pg_isready -U findable > /dev/null 2>&1; do
    echo "Waiting for Postgres..."
    sleep 1
done

# Check redis
until docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; do
    echo "Waiting for Redis..."
    sleep 1
done

echo "Services are ready!"

# Run migrations
echo "Running migrations..."
alembic upgrade head

echo ""
echo "==================================="
echo "Local development ready!"
echo ""
echo "Start API:    uvicorn api.main:app --reload"
echo "Start Worker: python -m worker.main"
echo "==================================="
