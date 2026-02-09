# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Findable Score Analyzer** measures whether AI answer engines can retrieve and use a website as a source. It produces a single **Findable Score (0-100)** with transparent scoring breakdown, competitive benchmarks, and actionable fixes.

Two modes:
- **Simulated Findability**: Deterministic sourceability engine (crawl → extract → chunk → retrieve → grade)
- **Observed Findability**: Reality snapshots from actual AI model outputs

## Tech Stack

- **Backend**: Python 3.11+, FastAPI (async), SQLAlchemy 2.0 (async sessions)
- **Database**: PostgreSQL + pgvector (hybrid retrieval), Alembic migrations
- **Queue**: Redis + RQ
- **Crawling**: httpx (static) + Playwright (headless when render delta triggers)
- **Extraction**: trafilatura + BeautifulSoup fallback
- **Embeddings**: sentence-transformers (bge-small-en-v1.5)
- **Hosting**: Railway (api + worker services)

## Key Commands

```bash
# Linting and formatting
ruff check .
black .
mypy api worker --ignore-missing-imports

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
pytest                                  # All tests
pytest tests/unit/test_auth.py -v       # Single file
pytest -k "test_create"                 # Pattern match
pytest --cov=api --cov=worker           # With coverage

# Calibration optimizer
powershell -Command "set PYTHONIOENCODING=utf-8 && python scripts/run_optimizer.py --save"
```

## Windows Development Notes

- Always use `PYTHONIOENCODING=utf-8` when running Python scripts (structlog emoji breaks cp1252)
- Use `powershell -Command` not `cmd /c` for running scripts (cmd eats stdout)
- Virtual env activation: `.\venv\Scripts\Activate.ps1`

## Core Architecture

### Audit Pipeline (worker/tasks/audit.py)

Linear async pipeline with ~15 steps. Failures in optional sections (observation, calibration) don't stop the audit—they mark sections as `evaluated=False`.

1. Technical checks (robots.txt, TTFB, llms.txt, JS detection)
2. Crawl (with optional caching via `get_cached_or_crawl()`)
3. Extract content (trafilatura + BeautifulSoup fallback)
4. Chunk semantically (preserves tables, lists, code blocks)
5. Embed & store in pgvector
6. Generate questions (15 universal + 5 site-derived + custom)
7. Simulate retrieval (hybrid BM25 + vector, RRF fusion)
8. Score simulation (v1 calculator)
9. Run v2 pillar checks (technical, structure, schema, authority, entity recognition)
10. Calculate v2 score with calibration weights
11. Generate fixes
12. Assemble report (contract-driven)
13. Save to DB

Progress tracking uses optimistic locking (`version_id_col`) to prevent race conditions.

### Dual Scoring System

**Two calculators coexist—v2 wraps v1, doesn't replace it:**

- **`worker/scoring/calculator.py`** (v1): 4-criterion system (content_relevance, signal_coverage, answer_confidence, source_quality) with category weighting. Used for simulation scoring.
- **`worker/scoring/calculator_v2.py`** (v2): 7-pillar system with dynamic weights from `CalibrationConfig`. The `retrieval` and `coverage` pillars are populated directly from v1's `ScoreBreakdown`.

**7 Pillars** (defaults: technical=12%, structure=18%, schema=13%, authority=12%, entity_recognition=13%, retrieval=22%, coverage=10%):
- Weights loaded from DB at startup via `load_active_calibration_weights()`
- Cached in module-level `_cached_weights` variable
- Falls back to defaults if no active config exists

### Calibration System

**Grid search, not ML.** All in `worker/calibration/optimizer.py`.

- Generates weight combos where each pillar is 5-35% (step=5), sum=100 (~4500 combos)
- Numpy vectorized `_batch_evaluate` for speed (490K+ evals/sec)
- Two-phase: coarse (step=5) then fine (step=2) around best
- **Domain-stratified holdout** (whole domains in train OR holdout, never split)
- Bias-adjusted accuracy: `accuracy - 0.5 * |over_rate - under_rate|`
- A/B experiment framework in `worker/calibration/experiment.py` (chi-squared significance)

**CRITICAL**: Calibrate against `obs_cited` (URL explicitly cited, 68% positive), NOT `obs_mentioned` (brand name appears, 99.8% positive—useless).

### The Citation Paradox

Low-citation sites (news, SaaS marketing) have **higher pillar scores** than high-citation sites (documentation). Content type is the real predictor:
- documentation=100%, reference=90%+, SaaS marketing=0-60%, news=0-20%

This drove creation of the two-layer model:
- **Findable Score** (sourceability): Can AI find and use your content?
- **Citation Context** (`worker/scoring/citation_context.py`): Will AI actually cite you?

Supporting modules:
- `worker/extraction/site_type.py`: 9 site types with empirical citation baselines
- `worker/extraction/source_primacy.py`: PRIMARY/AUTHORITATIVE/DERIVATIVE classification

### Observation System

Two-stage pipeline:
1. **Runner**: Calls LLM providers, collects raw responses
2. **Parser** (`worker/observation/parser.py`): Extracts mentions, citations, sentiment, confidence, hallucination risk via regex patterns

**Citation depth scale (0-5)**: 0=not mentioned, 1=brand mentioned, 2=listed as option, 3=cited with URL (citable threshold), 4=recommended, 5=authoritative source

**Benchmarking** (`worker/observation/benchmark.py`): Head-to-head comparison vs competitors per question.

### Report Assembly

Contract-driven: `worker/reports/contract.py` defines immutable dataclasses for every section. `worker/reports/assembler.py` builds via `._build_X_section()` methods. Reports have version field (current: `"1.1"`). New features added as optional sections—never break the schema.

Key sections: headline (2-axis), top causes, action center (quick wins vs high-impact), divergence (sim vs obs), fix plan.

### Fix Generation

Three tiers:
- **Tier C**: Pre-computed pattern ranges (default, fast)
- **Tier B**: Synthetic patch + re-score affected questions only
- **Tier A**: Full re-score (post-implementation verification)

`worker/fixes/reason_codes.py` has structured enum of fix types. `worker/fixes/generator_v2.py` builds action center with path-to-next-milestone sorting.

## API Patterns

- All endpoints under `/v1`
- **Dependency injection**: `DbSession` (async session + commit), `CurrentUser` (JWT → User or 401), `Pagination` (query params)
- **Response envelope**: All endpoints return `SuccessResponse[T]`
- **Exception hierarchy**: `FindableError` subclasses with `.code` and `.message`
- **Middleware order** (first added = last executed): RequestID → Logging → RateLimit → Metrics → SecurityHeaders → CORS (outermost)

## Test Patterns

- `ENV=test` must be set **before** importing `api.config.get_settings`
- Session-scoped DB setup (tables created once per test run)
- `ASGITransport` for calling FastAPI directly (no HTTP server)
- HTTP recorder cassettes for deterministic external API tests
- `asyncio_mode = "auto"` in pytest config

## Repository Structure

```
/api         # FastAPI app (routers, models, schemas, services, deps.py)
/worker      # Background jobs (see audit pipeline above)
/migrations  # Alembic migrations
/web         # Jinja2 templates for MVP UI
/tests       # Pytest (unit + integration)
/scripts     # Utilities (optimizer, corpus collection, experiment management)
```

## Environment Variables

```
DATABASE_URL          # PostgreSQL (asyncpg)
REDIS_URL             # Redis for job queue
JWT_SECRET            # JWT signing key
OPENROUTER_API_KEY    # LLM aggregator (primary)
OPENAI_API_KEY        # Direct LLM (fallback)
STORAGE_BUCKET_NAME   # S3/R2 bucket
ENV=prod|dev|test
```

## Reference Documents

- `findable-score-analyzer-project.md` - Complete system specification
- `findable-score-analyzer-day-to-day.md` - 30-day build plan
- `findable-day31-wireframe-spec.md` - UI wireframes and API bindings
