# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Findable Score Analyzer** measures whether AI answer engines can retrieve and use a website as a source. It produces a single **Findable Score (0-100)** with transparent scoring breakdown, competitive benchmarks, and actionable fixes.

The system has two modes:
- **Simulated Findability**: Deterministic sourceability engine (crawl → extract → chunk → retrieve → grade)
- **Observed Findability**: Reality snapshots from actual AI model outputs

## Tech Stack

- **Backend**: Python 3.11+, FastAPI (async)
- **Database**: PostgreSQL + pgvector (hybrid retrieval)
- **Queue**: Redis + RQ
- **Crawling**: httpx (static) + Playwright (headless when render delta triggers)
- **Extraction**: trafilatura + BeautifulSoup fallback
- **Embeddings**: sentence-transformers (bge-small-en-v1.5)
- **Hosting**: Railway (api + worker services)
- **Storage**: Cloudflare R2 or S3-compatible bucket

## Repository Structure

```
/api         # FastAPI application (routers, models, schemas, services)
/worker      # Background job processing (crawler, extraction, chunking, scoring)
/migrations  # Alembic database migrations
/web         # Jinja2 templates for MVP UI
/tests       # Pytest test suite (unit + integration)
/scripts     # Startup and utility scripts
```

## Key Commands

```bash
# Linting and formatting
ruff check .
black .
mypy api worker

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"

# Run API server (dev)
uvicorn api.main:app --reload

# Run worker (separate terminal)
python -m worker.main

# Run scheduler (for monitoring snapshots)
python -m worker.scheduler

# Run tests
pytest
pytest tests/unit/test_auth.py -v      # Single file
pytest -k "test_create"                 # Pattern match
pytest --cov=api --cov=worker          # With coverage
```

## Local Development Setup

```bash
# Start PostgreSQL + Redis
docker-compose up -d

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate     # Linux/Mac

# Install dependencies
pip install -e ".[dev]"

# Run migrations
alembic upgrade head
```

## Core Architecture

### Pipeline Flow
1. `crawl_site` → bounded BFS crawl (max_pages, max_depth)
2. `extract_pages` → trafilatura with render delta rule
3. `chunk_pages` → semantic chunking (preserve tables/lists/steps)
4. `embed_chunks` → pgvector embeddings
5. `generate_questions` → 15 universal + 5 site-derived + custom
6. `simulate_run` → retrieve top-k per question, grade per band
7. `observe_run` → hit provider layer, parse mentions/citations
8. `assemble_report` → JSON contract (Section 19 of spec)

### Worker Module Structure

```
/worker
├── tasks/           # Job entry points (audit.py, monitoring.py)
├── crawler/         # BFS crawler, fetcher, Playwright renderer
├── extraction/      # Content extraction (trafilatura + BeautifulSoup)
├── chunking/        # Semantic text chunking
├── embeddings/      # sentence-transformers wrapper
├── questions/       # Question generation (universal, derived, custom)
├── retrieval/       # Hybrid search (BM25 + vector, RRF fusion)
├── simulation/      # Simulate AI retrieval per question
├── observation/     # Real LLM provider calls + parsing
├── scoring/         # Score calculation (coverage, extractability, etc.)
├── fixes/           # Fix recommendations + impact estimation
└── reports/         # Final report assembly
```

### Retrieval System
- **Lexical**: Postgres FTS (BM25-style)
- **Vector**: pgvector cosine similarity
- **Hybrid**: RRF fusion with diversity constraints and deduplication

### Robustness Bands
Scores computed at three context budgets:
- Conservative: 3,000 tokens
- Typical: 6,000 tokens
- Generous: 12,000 tokens

### Question Suite (15 + 5 + 5)
- **Universal (15)**: Stable across all business types
- **Site-derived (5)**: Deterministic rules from FAQ/nav/claims/policies
- **Custom (up to 5)**: User-supplied "money questions"

## API Structure

All endpoints under `/v1`. Key routes:
- `/v1/auth/*` - JWT authentication (register, login, logout)
- `/v1/sites` - Site CRUD + competitor management
- `/v1/sites/{id}/questions/generate` - Question suite generation
- `/v1/sites/{id}/runs` - Start audit runs
- `/v1/runs/{id}` - Run status polling
- `/v1/reports/{id}` - Full report JSON
- `/v1/jobs/{id}` - Background job status
- `/v1/monitoring/*` - Snapshots and alerts

### Key Patterns
- **Dependency Injection**: `DbSession`, `CurrentUser`, `Pagination` in deps.py
- **Response Envelope**: All endpoints return `SuccessResponse[T]`
- **Exception Hierarchy**: `FindableError` subclasses with HTTP status codes

## Database Schema (Key Tables)

- `users`, `sites`, `competitors`
- `pages`, `chunks` (with vector column)
- `question_sets`, `runs`, `sim_results`
- `fixes`, `fix_impact`
- `obs_runs`, `obs_results`
- `snapshots`, `alerts`

Required extensions:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

## Scoring System

Score components:
- **Coverage**: questions answered / total
- **Extractability**: retrieval quality penalties
- **Citability**: quotable + attributable penalties
- **Trust**: entity legitimacy penalties
- **Conflicts**: contradicting values penalty
- **Redundancy**: boilerplate crowding penalty

## Fix Impact Estimator

- **Tier C**: Pre-computed pattern ranges (default, fast)
- **Tier B**: Synthetic patch + re-score affected questions only
- **Tier A**: Full re-score (post-implementation verification)

## Key Design Principles

1. **Render Delta Rule**: Only use headless rendering when static extraction < threshold
2. **Determinism**: Same site content → same derived questions → stable scores
3. **Observation as truth**: When simulation and observation diverge, observation is headline
4. **Affected-question targeting**: Fix impact only re-scores plausibly impacted questions
5. **Plan caps**: Enforce competitor/question limits by tier (Starter/Professional/Agency)

## Environment Variables

```
DATABASE_URL          # PostgreSQL connection (asyncpg)
REDIS_URL             # Redis for job queue
JWT_SECRET            # JWT signing key
OPENROUTER_API_KEY    # LLM aggregator (primary)
OPENAI_API_KEY        # Direct LLM (fallback)
STORAGE_BUCKET_NAME   # S3/R2 bucket for artifacts
ENV=prod|dev
```

## Reference Documents

- `findable-score-analyzer-project.md` - Complete system specification
- `findable-score-analyzer-day-to-day.md` - 30-day build plan
- `findable-day31-wireframe-spec.md` - UI wireframes and API bindings
