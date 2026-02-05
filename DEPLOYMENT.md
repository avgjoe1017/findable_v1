# Findable Score Analyzer - Deployment Guide

This guide covers deploying Findable Score Analyzer to Railway and other platforms.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Railway Deployment](#railway-deployment)
3. [Docker Deployment](#docker-deployment)
4. [Environment Variables](#environment-variables)
5. [Database Setup](#database-setup)
6. [Post-Deployment](#post-deployment)
7. [Monitoring](#monitoring)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- **Python 3.11+** (for local development)
- **Docker** (for containerized deployment)
- **PostgreSQL 16** with pgvector extension
- **Redis 7+**
- **Railway Account** (recommended) or other PaaS

### Required API Keys

- **OpenRouter** or **OpenAI** API key (for LLM observations)
- **Stripe** keys (for billing, optional)
- **Sentry DSN** (for error tracking, optional)

---

## Railway Deployment

Railway is the recommended deployment platform for Findable.

### Step 1: Create Railway Project

1. Sign up at [railway.app](https://railway.app)
2. Click "New Project" → "Deploy from GitHub repo"
3. Connect your GitHub repository

### Step 2: Add Services

Add the following services to your Railway project:

1. **PostgreSQL**
   - Click "New" → "Database" → "PostgreSQL"
   - Railway auto-provisions with pgvector support
   - Note: You may need to run `CREATE EXTENSION vector;` manually

2. **Redis**
   - Click "New" → "Database" → "Redis"
   - Railway auto-configures the URL

3. **API Service** (from your repo)
   - Set root directory: `/`
   - Set Dockerfile target: `api`

4. **Worker Service** (optional, for background jobs)
   - Set root directory: `/`
   - Set Dockerfile target: `worker`
   - Or use Procfile: set process type to `worker`

### Step 3: Configure Environment Variables

In Railway dashboard, add these variables to your API service:

```bash
# Required
JWT_SECRET=<generate-32-byte-hex>
ENV=production
LOG_LEVEL=INFO

# Railway auto-provides these
# DATABASE_URL - auto-linked from Postgres
# REDIS_URL - auto-linked from Redis

# LLM Provider (at least one required)
OPENROUTER_API_KEY=sk-or-v1-xxx
# or
OPENAI_API_KEY=sk-xxx

# Optional
SENTRY_DSN=https://xxx@sentry.io/xxx
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
```

### Step 4: Deploy

Railway automatically deploys on push to your main branch.

Manual deploy:
```bash
railway up
```

### Step 5: Run Migrations

Migrations run automatically on startup. To run manually:

```bash
railway run alembic upgrade head
```

### Step 6: Initialize pgvector

Connect to your database and run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

---

## Docker Deployment

### Build Images

```bash
# Build API image
docker build --target api -t findable-api .

# Build Worker image
docker build --target worker -t findable-worker .

# Build Scheduler image
docker build --target scheduler -t findable-scheduler .
```

### Run with Docker Compose

For production, create a `docker-compose.prod.yml`:

```yaml
version: "3.8"

services:
  api:
    build:
      context: .
      target: api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/findable
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET=${JWT_SECRET}
      - ENV=production
    depends_on:
      - postgres
      - redis

  worker:
    build:
      context: .
      target: worker
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/findable
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis

  postgres:
    image: pgvector/pgvector:pg16
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=findable

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

Run:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL` | Redis connection string | `redis://host:6379/0` |
| `JWT_SECRET` | Secret key for JWT tokens | 64-char hex string |

### LLM Providers (at least one required)

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | OpenRouter API key (recommended) |
| `OPENAI_API_KEY` | OpenAI API key (fallback) |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENV` | `development` | Environment: development, production, test |
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Logging level |
| `API_WORKERS` | `1` | Number of uvicorn workers |
| `SENTRY_DSN` | - | Sentry error tracking DSN |
| `STRIPE_SECRET_KEY` | - | Stripe secret key for billing |

See `.env.example` for complete list.

---

## Database Setup

### Create Extensions

After connecting to your PostgreSQL database:

```sql
-- Required for vector embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Required for text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Required for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### Run Migrations

```bash
# Using alembic directly
alembic upgrade head

# Or using Railway CLI
railway run alembic upgrade head

# Or using Docker
docker-compose exec api alembic upgrade head
```

### Create Initial Admin User

After deployment, register your first user via the API:

```bash
curl -X POST https://your-app.railway.app/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "secure-password"}'
```

---

## Post-Deployment

### Health Checks

Verify deployment:

```bash
# Health check
curl https://your-app.railway.app/api/health

# Ready check (includes DB/Redis)
curl https://your-app.railway.app/api/ready
```

### Stripe Webhook Setup

1. Go to Stripe Dashboard → Webhooks
2. Add endpoint: `https://your-app.railway.app/v1/billing/webhooks/stripe`
3. Select events:
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.paid`
   - `invoice.payment_failed`
4. Copy webhook secret to `STRIPE_WEBHOOK_SECRET`

### Create Stripe Products

1. Go to Stripe Dashboard → Products
2. Create products for each plan tier:
   - Starter ($X/month, $Y/year)
   - Professional ($X/month, $Y/year)
   - Agency ($X/month, $Y/year)
3. Copy price IDs to environment variables

---

## Monitoring

### Prometheus Metrics

Metrics are exposed at `/metrics`:

```bash
curl https://your-app.railway.app/metrics
```

Key metrics:
- `findable_http_requests_total` - Request count
- `findable_http_request_duration_seconds` - Request latency
- `findable_runs_total` - Audit runs
- `findable_errors_total` - Error count

### Sentry Integration

1. Create project at [sentry.io](https://sentry.io)
2. Set `SENTRY_DSN` environment variable
3. Errors automatically reported with context

### Railway Logs

View logs in Railway dashboard or CLI:

```bash
railway logs
```

---

## Troubleshooting

### Settings validation errors (database_url, redis_url, jwt_secret required)

If the container fails on startup with:

```
pydantic_core._pydantic_core.ValidationError: 3 validation errors for Settings
database_url - Field required
redis_url - Field required
jwt_secret - Field required
```

the API service is running **without the required environment variables**. Fix it as follows:

1. **Link PostgreSQL and Redis to the API service**
   - In the Railway project, open your **API service** (the one built from the repo).
   - In the service’s **Variables** tab, use “Add variable” → “Add reference” (or “Connect” to the Postgres and Redis services).
   - That injects `DATABASE_URL` and `REDIS_URL` into the API service. If you created Postgres/Redis in the same project, linking them is required for those vars to appear.

2. **Set `JWT_SECRET` manually**
   - In the API service Variables tab, add: `JWT_SECRET` = a long random string (e.g. 32+ hex chars: `openssl rand -hex 32`).

3. **Redeploy** after saving variables so the new container gets them.

### Database Connection Issues

```bash
# Test connection
railway run python -c "from api.database import engine; print('Connected!')"
```

If using pgvector, ensure extension is installed:
```sql
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### Migration Failures

```bash
# Check migration status
railway run alembic current

# Generate new migration
railway run alembic revision --autogenerate -m "description"

# Rollback
railway run alembic downgrade -1
```

### Worker Not Processing Jobs

Check Redis connection:
```bash
railway run python -c "from worker.redis import get_redis_connection; r = get_redis_connection(); print(r.ping())"
```

Check queue:
```bash
railway run rq info
```

### Memory Issues

For Railway, adjust resource limits in dashboard or railway.toml:
```toml
[deploy]
memory = "1Gi"
```

### Playwright Issues (Worker)

Ensure worker container has Playwright installed:
```bash
docker exec -it findable-worker playwright install chromium --with-deps
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Railway                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │   API    │────│  Worker  │────│Scheduler │              │
│  │ (uvicorn)│    │   (rq)   │    │(rq-sched)│              │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘              │
│       │               │               │                     │
│       └───────────────┼───────────────┘                     │
│                       │                                     │
│              ┌────────┴────────┐                           │
│              │                 │                            │
│        ┌─────┴─────┐    ┌─────┴─────┐                      │
│        │ PostgreSQL│    │   Redis   │                      │
│        │ (pgvector)│    │           │                      │
│        └───────────┘    └───────────┘                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Support

- GitHub Issues: [findable/issues](https://github.com/avgjoe1017/findable_v1/issues)
- Documentation: See CLAUDE.md for development guide
