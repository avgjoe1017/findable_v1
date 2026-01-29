# Findable Score Analyzer - Progress Tracker

Last Updated: 2026-01-28 (Session #14)

**Current Status:** Day 20 complete, ready for Day 21 (Observation Parsing)

## Overall Status

| Phase | Status | Progress |
|-------|--------|----------|
| **Week 1: Foundation** | Complete | 7/7 days |
| **Week 2: Crawl & Extract** | Complete | 7/7 days |
| Week 3: Scoring Engine | In Progress | 6/7 days |
| Week 4: Observation & Report | Not Started | 0/9 days |

---

## Day-by-Day Progress

### Week 1: Foundation

#### Day 1: Repo + CI Foundation ✅ COMPLETE
**Date:** 2026-01-28
**Commit:** `eb88d96`

**Deliverables:**
- [x] Monorepo layout (`/api`, `/worker`, `/migrations`, `/web`, `/tests`)
- [x] Dependency manager (pyproject.toml with all dependencies)
- [x] Lint/format/test tooling (ruff, black, mypy)
- [x] GitHub Actions CI pipeline (lint + test jobs)
- [x] Pre-commit hooks configured
- [x] Docker Compose for local Postgres + Redis
- [x] FastAPI skeleton with health endpoint
- [x] Basic test suite

**Files Created:**
- `api/main.py` - FastAPI app factory
- `api/config.py` - Settings management
- `api/routers/health.py` - Health endpoints
- `api/routers/v1.py` - V1 API router
- `worker/main.py` - RQ worker entrypoint
- `migrations/env.py` - Alembic config
- `tests/unit/test_health.py` - Health endpoint tests
- `pyproject.toml` - Dependencies + tool config
- `.github/workflows/ci.yml` - CI pipeline
- `docker-compose.yml` - Local services
- `Dockerfile` - Container build
- `railway.toml` - Deployment config

---

#### Day 2: FastAPI Skeleton + API Conventions ✅ COMPLETE
**Date:** 2026-01-28
**Commit:** `e463012`

**Deliverables:**
- [x] Database connection (async SQLAlchemy + pgvector)
- [x] Custom exception hierarchy
- [x] Standard response schemas (Success, Paginated, Error)
- [x] Structured logging with structlog
- [x] Request ID + logging middleware
- [x] Dependency injection (DbSession, PaginationParams)
- [x] Enhanced /ready endpoint with dependency checks
- [x] Test suite for exceptions and schemas

**Files Created:**
- `api/database.py` - Async SQLAlchemy setup
- `api/exceptions.py` - Custom exception classes
- `api/schemas/responses.py` - Response envelopes
- `api/logging.py` - Structured logging config
- `api/middleware.py` - Request ID + logging middleware
- `api/deps.py` - Dependency injection
- `tests/unit/test_exceptions.py` - Exception tests
- `tests/unit/test_schemas.py` - Schema tests

---

#### Day 3: Auth (JWT) ✅ COMPLETE
**Date:** 2026-01-28
**Commit:** `6f36444`

**Deliverables:**
- [x] User model with FastAPI-Users integration
- [x] Plan tiers (starter, professional, agency)
- [x] JWT authentication backend
- [x] Register, login, logout, me endpoints
- [x] Password reset and verification endpoints
- [x] Plan info endpoint with tier limits
- [x] Base model mixins (UUID, timestamps)
- [x] Auth and user schema tests

**Files Created:**
- `api/auth.py` - FastAPI-Users configuration
- `api/models/base.py` - Base model mixins
- `api/models/user.py` - User model
- `api/routers/auth.py` - Auth endpoints
- `api/schemas/user.py` - User schemas
- `tests/unit/test_auth.py` - Auth tests
- `tests/unit/test_user_schemas.py` - User schema tests

**Endpoints Added:**
- `POST /v1/auth/register` - Create account
- `POST /v1/auth/login` - Get JWT token
- `POST /v1/auth/logout` - Logout
- `GET /v1/auth/users/me` - Get current user
- `PATCH /v1/auth/users/me` - Update current user
- `GET /v1/auth/me/plan` - Get plan limits

---

#### Day 4: Core DB Models v1 ✅ COMPLETE
**Date:** 2026-01-28
**Commit:** `824676a`

**Deliverables:**
- [x] Site model with business model classification
- [x] Competitor model with site relationship
- [x] Run model with status tracking and progress
- [x] Report model with quick access fields
- [x] RunStatus and RunType enums
- [x] BusinessModel enum
- [x] SiteService with plan limit enforcement
- [x] RunService with status updates
- [x] Generic CRUDBase class
- [x] Site, Run, and Report schemas
- [x] Domain normalization validators
- [x] Test suites for models and services

**Files Created:**
- `api/models/site.py` - Site and Competitor models
- `api/models/run.py` - Run and Report models
- `api/models/__init__.py` - Model exports
- `api/services/crud.py` - Generic CRUD base class
- `api/services/site_service.py` - Site operations
- `api/services/run_service.py` - Run operations
- `api/services/__init__.py` - Service exports
- `api/schemas/site.py` - Site/Competitor schemas
- `api/schemas/run.py` - Run/Report schemas
- `tests/unit/test_site_schemas.py` - Site schema tests
- `tests/unit/test_run_schemas.py` - Run schema tests

**Model Relationships:**
- User → Sites (1:N)
- Site → Competitors (1:N, cascade delete)
- Site → Runs (1:N, cascade delete)
- Run → Report (1:1)

---

#### Day 5: RQ + Redis Job Plumbing ✅ COMPLETE
**Date:** 2026-01-28
**Commit:** `29e5633`

**Deliverables:**
- [x] Redis connection utilities with connection pooling
- [x] RQ worker with multi-queue support (high/default/low)
- [x] JobQueue service for enqueueing and managing jobs
- [x] JobInfo dataclass with status tracking
- [x] JobService for API-level job management
- [x] Audit task skeleton with status updates
- [x] Job status polling endpoints
- [x] Queue statistics endpoint
- [x] Test suite for job components

**Files Created:**
- `worker/redis.py` - Redis connection utilities
- `worker/queue.py` - JobQueue service
- `worker/tasks/audit.py` - Audit run background task
- `api/services/job_service.py` - Job service for API
- `api/routers/jobs.py` - Job status endpoints
- `api/schemas/job.py` - Job schemas
- `tests/unit/test_jobs.py` - Job tests

**Endpoints Added:**
- `GET /v1/jobs/{job_id}` - Get job status
- `DELETE /v1/jobs/{job_id}` - Cancel job
- `GET /v1/jobs/` - Get queue statistics

**Queue Names:**
- `findable-high` - High priority jobs
- `findable-default` - Default priority
- `findable-low` - Low priority jobs

---

#### Day 6: Site + Competitor Endpoints ✅ COMPLETE
**Date:** 2026-01-28
**Commit:** `7148e54`

**Deliverables:**
- [x] Sites router with full CRUD operations
- [x] POST /sites - Create site with competitors
- [x] GET /sites - List sites with pagination
- [x] GET /sites/{id} - Get site details
- [x] PATCH /sites/{id} - Update site settings
- [x] DELETE /sites/{id} - Delete site and all data
- [x] PUT /sites/{id}/competitors - Update competitor list
- [x] Runs router for audit management
- [x] POST /sites/{id}/runs - Start audit run
- [x] GET /sites/{id}/runs - List runs
- [x] GET /sites/{id}/runs/{run_id} - Get run details
- [x] DELETE /sites/{id}/runs/{run_id} - Cancel run
- [x] GET /reports/{id} - Get full report
- [x] PaginatedResponse.create() helper method
- [x] RunWithReport schema
- [x] get_active_run service method
- [x] Plan limit enforcement on competitors
- [x] Test suite for endpoint schemas

**Files Created:**
- `api/routers/sites.py` - Site CRUD endpoints
- `api/routers/runs.py` - Run management + reports endpoints
- `tests/unit/test_site_endpoints.py` - Endpoint tests

**Endpoints Added:**
- `POST /v1/sites` - Create site
- `GET /v1/sites` - List sites (paginated)
- `GET /v1/sites/{id}` - Get site details
- `PATCH /v1/sites/{id}` - Update site
- `DELETE /v1/sites/{id}` - Delete site
- `PUT /v1/sites/{id}/competitors` - Update competitors
- `POST /v1/sites/{id}/runs` - Start audit
- `GET /v1/sites/{id}/runs` - List runs (paginated)
- `GET /v1/sites/{id}/runs/{run_id}` - Get run
- `DELETE /v1/sites/{id}/runs/{run_id}` - Cancel run
- `GET /v1/reports/{id}` - Get full report

---

#### Day 7: Crawler v1 (Static) ✅ COMPLETE
**Date:** 2026-01-28
**Commit:** `688df4b`

**Deliverables:**
- [x] URL normalization utilities
- [x] Tracking parameter stripping (UTM, fbclid, etc.)
- [x] Skip extensions (images, PDFs, etc.)
- [x] robots.txt parser with wildcard support
- [x] RobotsChecker with caching
- [x] HTTP fetcher with retries and rate limiting
- [x] BFS crawler with configurable limits
- [x] Progress callbacks for status updates
- [x] File-based crawl storage with manifests
- [x] Test suites for URL and robots.txt

**Files Created:**
- `worker/crawler/__init__.py` - Package exports
- `worker/crawler/url.py` - URL normalization
- `worker/crawler/robots.py` - robots.txt parser
- `worker/crawler/fetcher.py` - HTTP fetcher
- `worker/crawler/crawler.py` - BFS crawler
- `worker/crawler/storage.py` - Crawl storage
- `tests/unit/test_crawler_url.py` - URL tests (21 tests)
- `tests/unit/test_crawler_robots.py` - Robots tests (16 tests)

**Crawler Features:**
- Configurable max_pages (default 250)
- Configurable max_depth (default 3)
- Respects robots.txt crawl-delay
- Per-domain rate limiting
- Automatic link extraction
- Internal-only link following
- Concurrent fetching with semaphore

---

### Week 2: Crawl & Extract Pipeline

#### Day 8: Extraction v1 ✅ COMPLETE
**Date:** 2026-01-28
**Commit:** `5b29340`

**Deliverables:**
- [x] HTML cleaning and boilerplate removal
- [x] Script, style, and comment stripping
- [x] Boilerplate pattern detection (nav, footer, sidebar, etc.)
- [x] Main content identification (article, main tags)
- [x] Text density analysis for content detection
- [x] Whitespace normalization
- [x] Metadata extraction (title, description, keywords)
- [x] Open Graph tag extraction
- [x] Twitter Card extraction
- [x] Schema.org type extraction (JSON-LD + microdata)
- [x] Heading extraction (h1-h6)
- [x] Link counting (internal vs external)
- [x] ContentExtractor class for crawl integration
- [x] Test suite (31 tests passing)

**Files Created:**
- `worker/extraction/__init__.py` - Package exports (lazy imports)
- `worker/extraction/cleaner.py` - HTML cleaning and boilerplate removal
- `worker/extraction/metadata.py` - Metadata extraction
- `worker/extraction/extractor.py` - ContentExtractor class
- `tests/unit/test_extraction_cleaner.py` - Cleaner tests (14 tests)
- `tests/unit/test_extraction_metadata.py` - Metadata tests (17 tests)

**Extraction Features:**
- Removes script, style, noscript, iframe, etc.
- Identifies boilerplate by tag name (nav, header, footer, aside)
- Identifies boilerplate by class/id patterns (social, comment, widget)
- Preserves main content containers (article, main)
- Extracts structured metadata (OG, Twitter, Schema.org)
- Counts words, links, and images
- Configurable min/max content length

---

#### Day 9: Render Delta Rule ✅ COMPLETE
**Date:** 2026-01-28
**Commit:** `ba7db96`

**Deliverables:**
- [x] RenderMode enum (static, rendered, auto)
- [x] RendererConfig with configurable thresholds
- [x] Jaccard similarity calculation for content comparison
- [x] RenderDelta dataclass with metrics
- [x] PageRenderer class with Playwright integration
- [x] RenderDeltaDetector for single-page analysis
- [x] Site-level render mode detection (majority voting)
- [x] Graceful handling when Playwright not installed
- [x] Test suite (17 tests passing)

**Files Created:**
- `worker/crawler/render.py` - Render delta detection module
- `tests/unit/test_render_delta.py` - Render delta tests (17 tests)

**Detection Logic:**
- Compares static (httpx) vs rendered (Playwright) content
- Calculates word count delta and ratio
- Measures content similarity via Jaccard index
- Triggers rendering if:
  - Word delta >= 50 AND delta ratio >= 20%
  - OR content similarity < 70%
- Samples multiple pages for site-wide decision
- Uses majority voting to determine site mode

**Thresholds (configurable):**
- `min_word_delta`: 50 words
- `min_delta_ratio`: 0.2 (20%)
- `similarity_threshold`: 0.7 (70%)
- `sample_count`: 3 pages

---

#### Day 10: Semantic Chunker v1 ✅ COMPLETE
**Date:** 2026-01-28
**Commit:** `55f2c94`

**Deliverables:**
- [x] TextSplitter with hierarchical splitting (section → paragraph → sentence → word)
- [x] Token estimation for chunk size control
- [x] Sentence splitting with abbreviation handling
- [x] List and table content detection
- [x] SemanticChunker with chunk type detection
- [x] ChunkType enum (text, heading, list, table, code, quote)
- [x] Heading hierarchy extraction for context
- [x] Content deduplication via hash
- [x] Position tracking for chunks
- [x] Configurable chunk sizes and overlap
- [x] Test suite (59 tests passing)

**Files Created:**
- `worker/chunking/__init__.py` - Package exports (lazy imports)
- `worker/chunking/splitter.py` - Low-level text splitting
- `worker/chunking/chunker.py` - Semantic chunker with metadata
- `tests/unit/test_chunking_splitter.py` - Splitter tests (27 tests)
- `tests/unit/test_chunking_chunker.py` - Chunker tests (32 tests)

**Chunker Features:**
- Hierarchical splitting: sections → paragraphs → sentences → words
- Preserves structure (lists, tables, code blocks)
- Token-based size control (~4 chars/token heuristic)
- Overlap between chunks for context continuity
- Merges small chunks to meet minimum size
- Heading context attached to each chunk
- Position ratio for document location
- Content hash for deduplication

**Default Configuration:**
- `max_chunk_size`: 512 tokens
- `min_chunk_size`: 100 tokens
- `overlap_size`: 50 tokens

---

#### Day 11: Embeddings v1 (pgvector) ✅ COMPLETE
**Date:** 2026-01-28
**Commit:** `bc9e891`

**Deliverables:**
- [x] Embedding model registry with multiple options
- [x] SentenceTransformerModel wrapper with prefix handling
- [x] MockEmbeddingModel for testing (deterministic)
- [x] Embedder class with batch processing and caching
- [x] EmbeddingResult and EmbeddedPage dataclasses
- [x] EmbeddingStore for pgvector storage
- [x] SearchResult dataclass for similarity search
- [x] SQL for creating pgvector table and indexes
- [x] Test suite (51 tests passing)

**Files Created:**
- `worker/embeddings/__init__.py` - Package exports (lazy imports)
- `worker/embeddings/models.py` - Embedding model definitions
- `worker/embeddings/embedder.py` - Embedder class
- `worker/embeddings/storage.py` - pgvector storage
- `tests/unit/test_embeddings_models.py` - Model tests (20 tests)
- `tests/unit/test_embeddings_embedder.py` - Embedder tests (19 tests)
- `tests/unit/test_embeddings_storage.py` - Storage tests (12 tests)

**Supported Models:**
- `bge-small` - BAAI/bge-small-en-v1.5 (384 dims, default)
- `bge-base` - BAAI/bge-base-en-v1.5 (768 dims)
- `minilm` - all-MiniLM-L6-v2 (384 dims)
- `e5-small` - intfloat/e5-small-v2 (384 dims)
- `mock` - Mock model for testing

**Features:**
- Model prefixes for BGE/E5 (query vs document)
- Batch embedding with configurable size
- Embedding cache by content hash
- Normalized embeddings
- pgvector cosine similarity search
- IVFFlat and HNSW index support

---

#### Day 12: Retrieval v1 (Hybrid) ✅ COMPLETE
**Date:** 2026-01-28
**Commit:** `0e3c9ee`

**Deliverables:**
- [x] BM25 lexical search implementation
- [x] Tokenization with configurable settings
- [x] Inverted index for efficient term lookup
- [x] IDF and term frequency scoring
- [x] HybridRetriever combining vector + BM25
- [x] Reciprocal Rank Fusion (RRF) algorithm
- [x] Page diversity enforcement
- [x] Configurable search weights
- [x] Test suite (54 tests passing)

**Files Created:**
- `worker/retrieval/__init__.py` - Package exports (lazy imports)
- `worker/retrieval/bm25.py` - BM25 lexical search
- `worker/retrieval/retriever.py` - Hybrid retriever with RRF
- `tests/unit/test_retrieval_bm25.py` - BM25 tests (28 tests)
- `tests/unit/test_retrieval_retriever.py` - Retriever tests (26 tests)

**BM25 Features:**
- Configurable k1 (term saturation) and b (length normalization)
- Minimum token length filtering
- Lowercase normalization
- Document add/remove/update
- Search with limit and min_score

**Hybrid Retrieval Features:**
- Vector similarity search (embeddings)
- BM25 lexical search
- RRF fusion with configurable k constant
- Weighted combination (default 50/50)
- Page diversity: max N chunks per page
- Results include both individual and combined scores

**Default Configuration:**
- RRF k: 60 (from original paper)
- Vector weight: 0.5
- BM25 weight: 0.5
- Max per page: 2

---

#### Day 13: Universal Questions (15) ✅ COMPLETE
**Date:** 2026-01-28
**Commit:** `2cd954c`

**Deliverables:**
- [x] QuestionCategory enum (identity, offerings, contact, trust, differentiation)
- [x] QuestionDifficulty enum (easy, medium, hard)
- [x] UniversalQuestion dataclass with weights and expected signals
- [x] 15 universal questions across 5 categories
- [x] Question distribution (3+4+2+3+3 by category)
- [x] Helper functions (get_by_category, get_by_difficulty, format_question)
- [x] Category weights calculation
- [x] QuestionGenerator for site-specific questions
- [x] Schema-based question templates (8 schema types)
- [x] Heading-based question patterns (10 patterns)
- [x] GeneratedQuestion with source tracking
- [x] Question deduplication
- [x] Test suite (56 tests passing)

**Files Created:**
- `worker/questions/__init__.py` - Package exports
- `worker/questions/universal.py` - 15 universal questions
- `worker/questions/generator.py` - Site-specific question generator
- `tests/unit/test_questions_universal.py` - Universal question tests (29 tests)
- `tests/unit/test_questions_generator.py` - Generator tests (27 tests)

**Universal Questions by Category:**
- IDENTITY (3): What does X do? Founders? Location?
- OFFERINGS (4): Products? Pricing? Target customers? Problems solved?
- CONTACT (2): How to contact? How to get started?
- TRUST (3): Notable clients? Awards? Track record?
- DIFFERENTIATION (3): Competitors? Why choose? Mission/values?

**Schema-Based Templates:**
- Product, LocalBusiness, Organization, SoftwareApplication
- Service, Article, FAQPage, HowTo

---

#### Day 14: Site-Derived Questions (5) ✅ COMPLETE
**Date:** 2026-01-28
**Commit:** `5b9dbf0`

**Deliverables:**
- [x] ContentAnalyzer for extracting entities and patterns
- [x] Content type detection (pricing, blog, careers, API, integrations)
- [x] Entity extraction (products, features, locations)
- [x] Keyword extraction with frequency filtering
- [x] Industry detection from headings
- [x] DerivedQuestionGenerator for site-specific questions
- [x] Up to 5 derived questions from content analysis
- [x] Question generation from detected content types
- [x] Question generation from metadata (enterprise, AI/ML)
- [x] Question generation from significant keywords
- [x] QuestionService combining universal + derived
- [x] QuestionSet dataclass with totals
- [x] API endpoints for question generation
- [x] Test suite (52 new tests: 36 derived + 16 service)

**Files Created:**
- `worker/questions/derived.py` - Site-derived question generator
- `api/services/question_service.py` - Question service layer
- `api/routers/questions.py` - Question API endpoints
- `tests/unit/test_questions_derived.py` - Derived question tests (36 tests)
- `tests/unit/test_question_service.py` - Service tests (16 tests)

**API Endpoints Added:**
- `GET /v1/questions/universal` - List all 15 universal questions
- `GET /v1/questions/universal/{id}` - Get specific question
- `GET /v1/questions/stats` - Get question statistics
- `POST /v1/questions/generate` - Generate full question set
- `GET /v1/questions/categories` - List categories
- `GET /v1/questions/difficulties` - List difficulty levels

**Content Analysis Features:**
- Detects API, integrations, blog, careers content
- Extracts products, features, locations from text
- Identifies industries from headings
- Generates targeted questions based on findings

---

---

### Week 3: Scoring Engine

#### Day 15: Simulation Runner v1 ✅ COMPLETE
**Date:** 2026-01-28
**Commit:** `3c58241`

**Deliverables:**
- [x] Answerability enum (fully_answerable, partially_answerable, not_answerable, contradictory)
- [x] ConfidenceLevel enum (high, medium, low)
- [x] RetrievedContext dataclass with chunk aggregation
- [x] SignalMatch for tracking expected signal matches
- [x] QuestionResult with full evaluation details
- [x] SimulationResult with aggregate metrics
- [x] SimulationRunner for running question evaluations
- [x] Signal matching (exact and fuzzy)
- [x] Configurable thresholds for answerability
- [x] Category and difficulty score aggregation
- [x] Coverage and confidence score calculation
- [x] SimulationSummary for reporting
- [x] CategoryAnalysis, SignalAnalysis, GapAnalysis
- [x] Recommendation generator for content gaps
- [x] Simulation comparison for monitoring
- [x] Test suite (48 tests passing)

**Files Created:**
- `worker/simulation/__init__.py` - Package exports
- `worker/simulation/runner.py` - SimulationRunner and core classes
- `worker/simulation/results.py` - Result analysis and utilities
- `tests/unit/test_simulation_runner.py` - Runner tests (24 tests)
- `tests/unit/test_simulation_results.py` - Results tests (24 tests)

**Scoring Features:**
- Retrieves top N chunks per question
- Matches expected signals in retrieved content
- Fuzzy matching for partial signal detection
- Weighted scoring (relevance + signals + confidence)
- Category/difficulty breakdown
- Letter grades (A-F) from scores
- Gap analysis with recommendations

---

#### Day 16: Scoring Rubric + Show the Math ✅ COMPLETE
**Date:** 2026-01-28
**Commit:** `25decbf`

**Deliverables:**
- [x] ScoreLevel enum (excellent, good, fair, needs_work, poor)
- [x] RubricCriterion for individual scoring criteria
- [x] CategoryWeight for question category weights
- [x] DifficultyMultiplier for difficulty adjustments
- [x] ScoringRubric with default criteria (4) and weights (5)
- [x] Letter grade thresholds (A+ to F)
- [x] Grade descriptions for user feedback
- [x] CriterionScore for detailed criterion breakdown
- [x] QuestionScore with calculation steps
- [x] CategoryBreakdown with per-category metrics
- [x] ScoreBreakdown with full transparency
- [x] ScoreCalculator for score calculations
- [x] `show_the_math()` method for human-readable breakdown
- [x] Scoring formula: 70% criterion + 30% category weighted
- [x] Test suite (51 tests passing)

**Files Created:**
- `worker/scoring/__init__.py` - Package exports
- `worker/scoring/rubric.py` - Scoring rubric definitions
- `worker/scoring/calculator.py` - Score calculator with transparency
- `tests/unit/test_scoring_rubric.py` - Rubric tests (25 tests)
- `tests/unit/test_scoring_calculator.py` - Calculator tests (26 tests)

**Scoring Criteria:**
- Content Relevance (35%): How well retrieved content matches questions
- Signal Coverage (35%): Presence of expected information signals
- Answer Confidence (20%): Confidence in answer completeness
- Source Quality (10%): Quality and diversity of source pages

**Category Weights:**
- Identity (25%): Who you are and what you do
- Offerings (30%): Products, services, and capabilities
- Contact (15%): How to reach and engage with you
- Trust (15%): Credibility and social proof
- Differentiation (15%): What makes you unique

**Difficulty Multipliers:**
- Easy: 1.0x
- Medium: 1.2x
- Hard: 1.5x

---

#### Day 17: Fix Generator v1 (Clarity Scaffolds) ✅ COMPLETE
**Date:** 2026-01-28
**Commit:** `7f37241`

**Deliverables:**
- [x] ReasonCode enum (19 reason codes across 5 categories)
- [x] ReasonCodeInfo dataclass with severity and impact
- [x] FixTemplate dataclass with scaffold templates
- [x] 19 fix templates mapping to reason codes
- [x] ExtractedContent for pulling site language
- [x] Fix dataclass with scaffold and metadata
- [x] FixPlan with prioritized fixes
- [x] FixGenerator analyzing simulation results
- [x] Problem identification (not answerable, partial, low score)
- [x] Reason code diagnosis based on signals and content
- [x] Scaffold generation with company name and examples
- [x] Estimated impact calculation
- [x] Target URL suggestions
- [x] Test suite (70 tests passing)

**Files Created:**
- `worker/fixes/__init__.py` - Package exports
- `worker/fixes/reason_codes.py` - 19 reason codes with metadata
- `worker/fixes/templates.py` - Fix templates with scaffolds
- `worker/fixes/generator.py` - FixGenerator and dataclasses
- `tests/unit/test_fixes_reason_codes.py` - Reason code tests (22 tests)
- `tests/unit/test_fixes_templates.py` - Template tests (24 tests)
- `tests/unit/test_fixes_generator.py` - Generator tests (24 tests)

**Reason Code Categories:**
- Content: missing_definition, missing_pricing, missing_contact, missing_location, missing_features, missing_social_proof
- Structure: buried_answer, fragmented_info, no_dedicated_page, poor_headings
- Quality: not_citable, vague_language, outdated_info, inconsistent
- Trust: trust_gap, no_authority, unverified_claims
- Technical: render_required, blocked_by_robots

**Fix Generation Features:**
- Maps failed questions to reason codes
- Groups fixes by reason code to avoid duplicates
- Generates content scaffolds with [PLACEHOLDERS]
- Extracts relevant content from site for reference
- Prioritizes fixes by severity and impact
- Suggests target URLs for fixes

---

#### Day 18: Fix Impact Estimator Tier C ✅ COMPLETE
**Date:** 2026-01-28
**Commit:** `998658f`

**Deliverables:**
- [x] ImpactTier enum (tier_c, tier_b, tier_a)
- [x] ConfidenceLevel enum (high, medium, low)
- [x] ImpactRange dataclass with min/max/expected points
- [x] FixImpactEstimate with breakdown and explanation
- [x] FixPlanImpact with aggregated estimates
- [x] Precomputed lookup tables for all 19 reason codes
- [x] Question count multipliers (diminishing returns)
- [x] Category weight factors
- [x] TierCEstimator class for impact calculations
- [x] Overlap adjustment for multiple fixes
- [x] Human-readable explanations and assumptions
- [x] Top fix identification and sorting
- [x] Plan-level notes and recommendations
- [x] Test suite (35 tests passing)

**Files Created:**
- `worker/fixes/impact.py` - Tier C impact estimator
- `tests/unit/test_fixes_impact.py` - Impact estimator tests (35 tests)

**Lookup Tables:**
- REASON_CODE_BASE_IMPACT: (min, expected, max) points per reason code
- QUESTION_COUNT_MULTIPLIERS: 1→1.0, 2→1.5, 3→1.8, 4→2.0, 5→2.2
- CATEGORY_WEIGHT_FACTORS: Offerings=1.2, Contact=1.1, others=1.0

**Key Features:**
- Fast, precomputed estimates without re-simulation
- Conservative ranges with confidence levels
- Diminishing returns for multiple fixes (80% efficiency per additional fix)
- Max total impact cap (default 30 points) to prevent unrealistic estimates
- Notes about technical fixes and Tier B recommendations

---

#### Day 19: Fix Impact Estimator Tier B ✅ COMPLETE
**Date:** 2026-01-28
**Commit:** `de0ce0d`

**Deliverables:**
- [x] SyntheticChunk dataclass for patched content
- [x] PatchedQuestionResult with score delta tracking
- [x] TierBEstimate with Tier C comparison
- [x] TierBConfig for tunable parameters
- [x] TierBEstimator class for synthetic patching
- [x] Signal extraction from fix scaffolds
- [x] Question re-scoring with relevance boost
- [x] Confidence calculation from improvement metrics
- [x] Answerability transition detection
- [x] Plan-level Tier B estimation (top N fixes)
- [x] Computation time tracking
- [x] Human-readable explanations
- [x] Convenience functions (estimate_fix_tier_b, estimate_plan_tier_b)
- [x] Test suite (29 tests passing)

**Files Created:**
- `worker/fixes/synthetic.py` - Tier B synthetic patching estimator
- `tests/unit/test_fixes_synthetic.py` - Tier B estimator tests (29 tests)

**Files Modified:**
- `worker/fixes/__init__.py` - Added Tier B exports

**Key Features:**
- Patches fix scaffolds into content in-memory
- Re-scores only affected questions (no full re-crawl)
- More accurate than Tier C (tighter bounds)
- Compares Tier B vs Tier C estimates
- Signal matching based on scaffold content
- Configurable scoring weights and thresholds

**Tier B vs Tier C:**
- Tier C: Fast lookup tables, conservative estimates
- Tier B: Synthetic patching, more accurate but higher cost
- Both return ImpactRange with min/max/expected points

---

#### Day 20: Observation Provider Layer ✅ COMPLETE
**Date:** 2026-01-28
**Commit:** `9fba82a`

**Deliverables:**
- [x] ProviderType enum (openrouter, openai, anthropic, mock)
- [x] ObservationStatus enum (pending, in_progress, completed, failed, partial)
- [x] UsageStats dataclass with token tracking and cost estimation
- [x] ProviderError dataclass with retryability flag
- [x] ObservationRequest with prompt generation
- [x] ObservationResponse with usage and latency tracking
- [x] ObservationResult with mention/citation parsing
- [x] ObservationRun with aggregate metrics
- [x] Abstract ObservationProvider base class
- [x] OpenRouterProvider (primary aggregator)
- [x] OpenAIProvider (fallback)
- [x] MockProvider for testing
- [x] get_provider factory function
- [x] RunConfig with provider settings
- [x] ObservationRunner with retries and failover
- [x] Progress callback support
- [x] Concurrent request handling with semaphore
- [x] Cost estimation for popular models
- [x] Test suite (44 tests passing)

**Files Created:**
- `worker/observation/__init__.py` - Package exports
- `worker/observation/models.py` - Data models
- `worker/observation/providers.py` - Provider implementations
- `worker/observation/runner.py` - Observation runner with retry logic
- `tests/unit/test_observation_providers.py` - Provider tests (29 tests)
- `tests/unit/test_observation_runner.py` - Runner tests (15 tests)

**Provider Features:**
- OpenRouter: Primary aggregator with model switching
- OpenAI: Direct fallback provider
- Mock: Deterministic testing with configurable responses/failures
- Automatic failover between providers
- Exponential backoff retries

**Runner Features:**
- Concurrent execution with rate limiting
- Progress callbacks for UI updates
- Total timeout protection
- Mention and URL extraction from responses
- Aggregate mention rate calculations

---
#### Day 21: Observation Parsing ⏳ PENDING

---

### Week 4: Observation & Report

#### Day 22: Competitor Benchmark ⏳ PENDING
#### Day 23: Report Assembler v1 ⏳ PENDING
#### Day 24: Minimal UI (Jinja2) ⏳ PENDING (templates created in Day 20)
#### Day 25: Monitoring Scheduler ⏳ PENDING
#### Day 26: Alerts v1 ⏳ PENDING
#### Day 27: Plan Caps + Billing Hooks ⏳ PENDING
#### Day 28: Hardening + Observability ⏳ PENDING
#### Day 29: Determinism + Replay Tests ⏳ PENDING
#### Day 30: Deployment (Railway) ⏳ PENDING

---

## Repository

**GitHub:** https://github.com/avgjoe1017/findable_v1

---

## Session Log

| Date | Session | Work Completed |
|------|---------|----------------|
| 2026-01-28 | #1 | Created CLAUDE.md, IMPLEMENTATION_ROADMAP.md |
| 2026-01-28 | #2 | Day 1 complete: repo skeleton, CI, FastAPI setup |
| 2026-01-28 | #3 | Created PROGRESS.md, pushed to GitHub |
| 2026-01-28 | #4 | Day 2 complete: database, exceptions, middleware, response schemas |
| 2026-01-28 | #5 | Lint fixes, Day 3 complete: JWT auth with FastAPI-Users |
| 2026-01-28 | #6 | Day 4 complete: Site, Competitor, Run, Report models + services |
| 2026-01-28 | #7 | Day 5 complete: RQ + Redis job infrastructure |
| 2026-01-28 | #8 | Day 6 complete: Site, Run, Report REST endpoints |
| 2026-01-28 | #9 | Day 7 complete: BFS crawler with robots.txt support |
| 2026-01-28 | #10 | Day 8 complete: Content extraction with metadata |
| 2026-01-28 | #10 | Day 9 complete: Render delta rule for JS detection |
| 2026-01-28 | #10 | Day 10 complete: Semantic chunker with structure preservation |
| 2026-01-28 | #10 | Day 11 complete: Embeddings with pgvector storage |
| 2026-01-28 | #10 | Day 12 complete: Hybrid retrieval with RRF |
| 2026-01-28 | #11 | Day 13 complete: Universal questions (15) + generator |
| 2026-01-28 | #11 | Day 14 complete: Site-derived questions (5) + API endpoints |
| 2026-01-28 | #11 | Day 15 complete: Simulation runner v1 + results analysis |
| 2026-01-28 | #12 | Codebase debug: mypy fixes, Fetcher user_agent, PROGRESS notes |
| 2026-01-28 | #13 | Day 16 complete: Scoring rubric + "Show the Math" transparency |
| 2026-01-28 | #13 | Day 17 complete: Fix generator v1 with reason codes and scaffolds |
| 2026-01-28 | #13 | Day 18 complete: Fix impact estimator Tier C with lookup tables |
| 2026-01-28 | #14 | Day 19 complete: Fix impact estimator Tier B with synthetic patching |
| 2026-01-28 | #14 | Day 20 complete: Observation provider layer with retry/failover |
| 2026-01-28 | #14 | Bonus: UI templates (dashboard + score report) using frontend-design skill |

---

## Next Session: Day 21 - Observation Parsing

### What to Build
Day 21 turns raw AI model outputs into measurable signals. The observation provider (Day 20) returns raw text responses - now we need structured parsing.

**Deliverables from spec:**
- Extract mentions (brand/domain) - *basic version done in runner, needs enhancement*
- Extract links/URLs - *basic version done in runner, needs enhancement*
- Extract citation-like patterns where present
- Persist `obs_results`
- Observed mention rate computed
- Per-question observed outcomes stored

### Key Files to Know

**Observation Layer (Day 20):**
- `worker/observation/models.py` - `ObservationResult` has basic fields: `mentions_company`, `mentions_domain`, `mentions_url`, `cited_urls`, `confidence_expressed`
- `worker/observation/runner.py:230-260` - `_parse_response_to_result()` does basic parsing (regex URL extraction, substring matching)

**What Day 21 Should Add:**
1. **Enhanced parsing module** (`worker/observation/parser.py`):
   - Fuzzy company name matching (handles "Acme", "Acme Corp", "Acme Corporation")
   - Citation pattern detection ("according to X", "X reports that", "source: X")
   - Sentiment/tone analysis (positive mention vs neutral vs negative)
   - Confidence extraction from hedging language

2. **Persistence layer** - Store observation results to database (may need new model)

3. **Comparison with simulation** - `ObservationResult` has `simulation_predicted` and `observation_actual` fields ready

### Architecture Context

**Scoring Pipeline Flow:**
```
Crawl → Extract → Chunk → Embed → Retrieve → Simulate → Score → Fix Generate → Impact Estimate
                                                                         ↓
                                              Observe (Day 20) → Parse (Day 21) → Compare
```

**Impact Estimation Tiers:**
- Tier C: Precomputed lookup tables (fast, conservative) - `worker/fixes/impact.py`
- Tier B: Synthetic patching (more accurate) - `worker/fixes/synthetic.py`
- Tier A: Full re-simulation (most accurate, expensive) - not yet implemented

**Question Categories (5):**
- Identity (25%): Who you are, what you do
- Offerings (30%): Products, services, pricing
- Contact (15%): How to reach/engage
- Trust (15%): Credibility, social proof
- Differentiation (15%): What makes you unique

### UI Templates (Bonus - Added Ahead of Schedule)

Created using `/frontend-design` skill with "Signal Observatory" design system:
- `web/templates/reports/score_report.html` - Full report page with animated score gauge, category breakdown, fix cards
- `web/templates/sites/dashboard.html` - Sites listing with stats, table, actions
- `web/templates/base.html` - Updated base template

Day 24 (Minimal UI) can now focus on Jinja2 integration with FastAPI rather than design.

### Test Count Summary
- Day 16 (Scoring): 51 tests
- Day 17 (Fix Generator): 70 tests
- Day 18 (Tier C Impact): 35 tests
- Day 19 (Tier B Synthetic): 29 tests
- Day 20 (Observation): 44 tests
- **Total project tests: 400+**

---

## Debug Pass (2026-01-28)

**Scope:** Lint/type-check and test discovery across `api`, `worker`, `tests`.

**Findings and fixes:**

1. **Mypy (10 errors → 0)**  
   - **worker/extraction/metadata.py**: `_get_meta_content` returned `tag["content"]` (Any). Fixed by branching on `isinstance(content, str)` and returning a string explicitly.  
   - **worker/questions/generator.py**: `generate_for_site(**kwargs)` had untyped `**kwargs`; unpacking into `SiteContext` caused arg-type errors. Fixed by extracting optional fields (`title`, `description`, `keywords`, `metadata`) from kwargs and passing them explicitly with type-safe defaults.  
   - **worker/crawler/render.py**: `__aexit__` lacked type annotations; `RenderDeltaDetector.detect_delta` called `Fetcher()` without required `user_agent`. Fixed by adding `exc_type`, `exc_val`, `exc_tb` types (`types.TracebackType`) and default `Fetcher(user_agent="FindableBot/1.0")`.  
   - **worker/embeddings/storage.py**: `delete_site_embeddings` and `delete_page_embeddings` returned `result.rowcount` (Any). Replaced with `int(result.rowcount) if result.rowcount is not None else 0`.  
   - **worker/embeddings/models.py**: `get_model()` assigned both `SentenceTransformerModel` and `MockEmbeddingModel` to the same variable; declared `model: EmbeddingModelProtocol`. `MockEmbeddingModel.embed_query` returns `self.embed([query])[0]` (indexing yields Any); added `# type: ignore[no-any-return]` on that return.

2. **Ruff / Black**  
   - `ruff check api worker tests` and `black --check` both pass (no changes).

3. **Pytest**  
   - Seven test modules failed at **collection** with `ModuleNotFoundError` (e.g. `bs4`, `rq`, `sqlalchemy`, `structlog`, `fastapi_users`). Cause: tests were run without project dependencies installed.  
   - **Requirement:** Run `pip install -e ".[dev]"` (or use a venv with the project installed) before `pytest`. Quick Commands already list this; no code change.

**Decision:** All fixes preserve behavior; type ignores are limited to one numpy indexing case where stubs infer Any.

---

## Blockers & Notes

- **Tests:** Pytest requires project dependencies. Run `pip install -e ".[dev]"` (or equivalent) before `pytest -v`. Otherwise collection will fail with missing modules (`bs4`, `rq`, `sqlalchemy`, etc.).

---

## Quick Commands

```bash
# Start local services
docker-compose up -d

# Install dependencies
pip install -e ".[dev]"

# Run API
uvicorn api.main:app --reload

# Run tests
pytest -v

# Run linting
ruff check . && black --check . && mypy api worker
```
