# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Findable Score Analyzer** measures whether AI answer engines can retrieve and use a website as a source. It produces a single **Findable Score (0-100)** with transparent scoring breakdown, competitive benchmarks, and actionable fixes.

The system has two modes:
- **Simulated Findability**: Deterministic sourceability engine (crawl → extract → chunk → retrieve → grade)
- **Observed Findability**: Reality snapshots from actual AI model outputs

## Tech Stack (MVP)

- **Backend**: Python 3.11+, FastAPI (async)
- **Database**: PostgreSQL + pgvector (hybrid retrieval)
- **Queue**: Redis + RQ
- **Crawling**: httpx (static) + Playwright (headless when render delta triggers)
- **Extraction**: trafilatura + BeautifulSoup fallback
- **Hosting**: Railway (api + worker services)
- **Storage**: Cloudflare R2 or S3-compatible bucket

## Repository Structure

```
/api         # FastAPI application
/worker      # RQ worker entrypoint
/migrations  # Alembic database migrations
/web         # Jinja2 templates for MVP UI
```

## Key Commands

```bash
# Linting and formatting
ruff check .
black .
mypy .

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"

# Run API server (dev)
uvicorn api.main:app --reload

# Run worker
rq worker --with-scheduler

# Run tests
pytest
pytest tests/test_specific.py -v
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

### Observation Provider Layer
Abstract interface supporting multiple providers with failover:
- Router provider (aggregator, default)
- Direct OpenAI (fallback)

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

## API Versioning

All endpoints under `/v1`. Key routes:
- `/v1/auth/*` - JWT authentication
- `/v1/sites` - Site CRUD + competitors
- `/v1/sites/{id}/questions/generate` - Question suite
- `/v1/sites/{id}/runs` - Start audit runs
- `/v1/runs/{id}` - Run status polling
- `/v1/reports/{id}` - Report JSON
- `/v1/fixes/{id}/impact/estimate` - Fix impact (Tier B/C)

## Scoring System ("Show the Math")

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
DATABASE_URL
REDIS_URL
JWT_SECRET
STORAGE_BUCKET_URL
PROVIDER_ROUTER_API_KEY
OPENAI_API_KEY
ENV=prod|dev
```

## Reference Documents

- `findable-score-analyzer-project.md` - Complete system specification
- `findable-score-analyzer-day-to-day.md` - 30-day build plan
- `findable-day31-wireframe-spec.md` - UI wireframes and API bindings
