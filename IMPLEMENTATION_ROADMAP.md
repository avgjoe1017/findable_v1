# Findable Score Analyzer - Implementation Roadmap

## 1. Project Structure

```
findable/
├── api/                          # FastAPI backend
│   ├── __init__.py
│   ├── main.py                   # App factory, middleware
│   ├── config.py                 # Settings (pydantic-settings)
│   ├── deps.py                   # Dependency injection
│   ├── routers/
│   │   ├── auth.py               # JWT auth endpoints
│   │   ├── sites.py              # Site CRUD + competitors
│   │   ├── questions.py          # Question generation
│   │   ├── runs.py               # Audit runs
│   │   ├── reports.py            # Report retrieval
│   │   ├── fixes.py              # Fix impact estimation
│   │   └── monitoring.py         # Snapshots, alerts
│   ├── models/                   # SQLAlchemy models
│   │   ├── user.py
│   │   ├── site.py
│   │   ├── page.py
│   │   ├── chunk.py
│   │   ├── question.py
│   │   ├── run.py
│   │   └── report.py
│   ├── schemas/                  # Pydantic schemas
│   ├── services/                 # Business logic
│   │   ├── crawler.py
│   │   ├── extractor.py
│   │   ├── chunker.py
│   │   ├── embedder.py
│   │   ├── retriever.py
│   │   ├── question_generator.py
│   │   ├── simulator.py
│   │   ├── observer.py
│   │   ├── scorer.py
│   │   ├── fix_generator.py
│   │   └── report_builder.py
│   └── providers/                # Observation provider layer
│       ├── base.py               # Abstract interface
│       ├── openrouter.py         # Aggregator router
│       └── openai_direct.py      # Direct OpenAI fallback
│
├── worker/                       # Background job processing
│   ├── __init__.py
│   ├── main.py                   # RQ worker entrypoint
│   ├── tasks/
│   │   ├── crawl.py
│   │   ├── extract.py
│   │   ├── chunk.py
│   │   ├── embed.py
│   │   ├── simulate.py
│   │   ├── observe.py
│   │   └── report.py
│   └── scheduler.py              # Cron-style monitoring scheduler
│
├── web/                          # Jinja2 templates (MVP UI)
│   ├── templates/
│   │   ├── base.html
│   │   ├── auth/
│   │   ├── sites/
│   │   ├── runs/
│   │   ├── reports/
│   │   └── components/
│   └── static/
│       ├── css/
│       └── js/
│
├── migrations/                   # Alembic
│   ├── versions/
│   ├── env.py
│   └── alembic.ini
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/                 # Golden test sites
│
├── scripts/                      # Dev utilities
│   ├── seed_db.py
│   └── run_local.sh
│
├── docs/                         # Specs (existing files)
│   ├── findable-score-analyzer-project.md
│   ├── findable-score-analyzer-day-to-day.md
│   └── findable-day31-wireframe-spec.md
│
├── pyproject.toml                # Poetry/uv dependencies
├── Dockerfile
├── docker-compose.yml            # Local dev (postgres, redis)
├── railway.toml                  # Railway deployment config
├── .env.example
├── CLAUDE.md
└── README.md
```

---

## 2. Open Source Tools & Libraries

### 2.1 Web Crawling

| Tool | GitHub | Use Case |
|------|--------|----------|
| **httpx** | [encode/httpx](https://github.com/encode/httpx) | Async HTTP client for static fetches |
| **Playwright** | [microsoft/playwright-python](https://github.com/microsoft/playwright-python) | Headless browser for JS-heavy sites |
| **Scrapy** | [scrapy/scrapy](https://github.com/scrapy/scrapy) | Alternative: full crawl framework |
| **url-normalize** | [niksite/url-normalize](https://github.com/niksite/url-normalize) | URL canonicalization |

### 2.2 Content Extraction

| Tool | GitHub | Use Case |
|------|--------|----------|
| **trafilatura** | [adbar/trafilatura](https://github.com/adbar/trafilatura) | Main content extraction (primary) |
| **readability-lxml** | [buriy/python-readability](https://github.com/buriy/python-readability) | Fallback extraction |
| **BeautifulSoup4** | [PyPI](https://pypi.org/project/beautifulsoup4/) | HTML parsing fallback |
| **jusText** | [miso-belica/jusText](https://github.com/miso-belica/jusText) | Boilerplate removal |
| **html2text** | [Alir3z4/html2text](https://github.com/Alir3z4/html2text) | HTML to markdown conversion |

### 2.3 Chunking & Text Processing

| Tool | GitHub | Use Case |
|------|--------|----------|
| **LangChain Text Splitters** | [langchain-ai/langchain](https://github.com/langchain-ai/langchain) | Semantic chunking utilities |
| **semantic-text-splitter** | [benbrandt/text-splitter](https://github.com/benbrandt/text-splitter) | Rust-based semantic chunking |
| **unstructured** | [Unstructured-IO/unstructured](https://github.com/Unstructured-IO/unstructured) | Document parsing + chunking |
| **tiktoken** | [openai/tiktoken](https://github.com/openai/tiktoken) | Token counting for budget caps |

### 2.4 Embeddings

| Model | Hugging Face | Notes |
|-------|--------------|-------|
| **all-MiniLM-L6-v2** | [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | Fast, 384 dims, good quality |
| **bge-small-en-v1.5** | [BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5) | SOTA small model |
| **bge-base-en-v1.5** | [BAAI/bge-base-en-v1.5](https://huggingface.co/BAAI/bge-base-en-v1.5) | Better quality, 768 dims |
| **e5-small-v2** | [intfloat/e5-small-v2](https://huggingface.co/intfloat/e5-small-v2) | Microsoft, excellent retrieval |
| **nomic-embed-text-v1.5** | [nomic-ai/nomic-embed-text-v1.5](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) | 8192 context, open weights |

| Library | GitHub | Use Case |
|---------|--------|----------|
| **sentence-transformers** | [UKPLab/sentence-transformers](https://github.com/UKPLab/sentence-transformers) | Load/run embedding models |
| **FlagEmbedding** | [FlagOpen/FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding) | BGE model family |
| **fastembed** | [qdrant/fastembed](https://github.com/qdrant/fastembed) | Fast CPU inference |

### 2.5 Vector Database & Retrieval

| Tool | GitHub | Use Case |
|------|--------|----------|
| **pgvector** | [pgvector/pgvector](https://github.com/pgvector/pgvector) | Vector search in Postgres (primary) |
| **rank_bm25** | [dorianbrown/rank_bm25](https://github.com/dorianbrown/rank_bm25) | BM25 implementation |
| **Postgres FTS** | Built-in | Lexical search via tsvector |

**Alternatives (if scaling beyond Postgres):**
| Tool | GitHub | Notes |
|------|--------|-------|
| **Qdrant** | [qdrant/qdrant](https://github.com/qdrant/qdrant) | Rust vector DB, hybrid search |
| **Weaviate** | [weaviate/weaviate](https://github.com/weaviate/weaviate) | GraphQL API, hybrid search |
| **Milvus** | [milvus-io/milvus](https://github.com/milvus-io/milvus) | Scalable vector DB |
| **ChromaDB** | [chroma-core/chroma](https://github.com/chroma-core/chroma) | Simple, embedded |

### 2.6 LLM Providers & Routers

| Service | Use Case |
|---------|----------|
| **OpenRouter** | [openrouter.ai](https://openrouter.ai) | Aggregator API, model switching |
| **OpenAI API** | Direct fallback provider |
| **Anthropic API** | Alternative observation provider |
| **Together AI** | Cheap inference for scaffolds |

| Library | GitHub | Use Case |
|---------|--------|----------|
| **litellm** | [BerriAI/litellm](https://github.com/BerriAI/litellm) | Unified LLM API interface |
| **openai-python** | [openai/openai-python](https://github.com/openai/openai-python) | OpenAI SDK |

### 2.7 Backend Framework

| Tool | GitHub | Use Case |
|------|--------|----------|
| **FastAPI** | [tiangolo/fastapi](https://github.com/tiangolo/fastapi) | API framework |
| **SQLAlchemy 2.0** | [sqlalchemy/sqlalchemy](https://github.com/sqlalchemy/sqlalchemy) | ORM |
| **Alembic** | [sqlalchemy/alembic](https://github.com/sqlalchemy/alembic) | Migrations |
| **Pydantic v2** | [pydantic/pydantic](https://github.com/pydantic/pydantic) | Validation |
| **fastapi-users** | [fastapi-users/fastapi-users](https://github.com/fastapi-users/fastapi-users) | Auth (JWT) |
| **RQ (Redis Queue)** | [rq/rq](https://github.com/rq/rq) | Background jobs |
| **rq-scheduler** | [rq/rq-scheduler](https://github.com/rq/rq-scheduler) | Scheduled jobs |

### 2.8 Frontend (MVP)

| Tool | GitHub | Use Case |
|------|--------|----------|
| **Jinja2** | Built into FastAPI | Server-side templates |
| **HTMX** | [bigskysoftware/htmx](https://github.com/bigskysoftware/htmx) | Dynamic UI without JS framework |
| **Alpine.js** | [alpinejs/alpine](https://github.com/alpinejs/alpine) | Lightweight interactivity |
| **Tailwind CSS** | [tailwindlabs/tailwindcss](https://github.com/tailwindlabs/tailwindcss) | Utility CSS |
| **DaisyUI** | [saadeghi/daisyui](https://github.com/saadeghi/daisyui) | Tailwind components |

### 2.9 Monitoring & Observability

| Tool | GitHub | Use Case |
|------|--------|----------|
| **Sentry** | [getsentry/sentry-python](https://github.com/getsentry/sentry-python) | Error tracking |
| **structlog** | [hynek/structlog](https://github.com/hynek/structlog) | Structured logging |
| **prometheus-fastapi-instrumentator** | [trallnag/prometheus-fastapi-instrumentator](https://github.com/trallnag/prometheus-fastapi-instrumentator) | Metrics |

### 2.10 Testing & Quality

| Tool | GitHub | Use Case |
|------|--------|----------|
| **pytest** | [pytest-dev/pytest](https://github.com/pytest-dev/pytest) | Testing framework |
| **pytest-asyncio** | [pytest-dev/pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio) | Async test support |
| **httpx** | Mock HTTP in tests |
| **ruff** | [astral-sh/ruff](https://github.com/astral-sh/ruff) | Fast linter |
| **black** | [psf/black](https://github.com/psf/black) | Formatter |
| **mypy** | [python/mypy](https://github.com/python/mypy) | Type checking |

---

## 3. Next Steps (Immediate Actions)

### Week 1: Foundation
- [ ] **Day 1-2**: Initialize repo, Poetry/uv, pre-commit hooks, CI pipeline
- [ ] **Day 3**: FastAPI skeleton with health endpoint, settings, error handling
- [ ] **Day 4**: Auth system (fastapi-users + JWT)
- [ ] **Day 5**: Database models v1 (users, sites, runs) + Alembic setup
- [ ] **Day 6-7**: RQ setup, site CRUD endpoints

### Week 2: Crawl & Extract Pipeline
- [ ] **Day 8**: Static crawler with httpx (bounded BFS)
- [ ] **Day 9**: Content extraction with trafilatura
- [ ] **Day 10**: Render delta rule with Playwright
- [ ] **Day 11**: Semantic chunker (preserve tables/lists)
- [ ] **Day 12-14**: Embeddings + pgvector + hybrid retrieval

### Week 3: Scoring Engine
- [ ] **Day 15**: Universal question set (15 questions)
- [ ] **Day 16**: Site-derived question generator (5 questions)
- [ ] **Day 17-18**: Simulation runner + grading rubric
- [ ] **Day 19-20**: Fix generator + Tier C impact estimator
- [ ] **Day 21**: Tier B synthetic patch impact

### Week 4: Observation & Report
- [ ] **Day 22**: Provider layer + OpenRouter integration
- [ ] **Day 23**: Observation parsing (mentions, citations)
- [ ] **Day 24**: Competitor benchmark
- [ ] **Day 25**: Report assembler (JSON contract)
- [ ] **Day 26-27**: Jinja2 UI (wizard + report page)
- [ ] **Day 28-29**: Monitoring scheduler + alerts
- [ ] **Day 30**: Railway deployment

---

## 4. Path Forward (Phased Roadmap)

### Phase 1: MVP (Days 1-30)
**Goal**: Working product that can audit one site + one competitor

Deliverables:
- Full audit pipeline (crawl → score → observe → report)
- Starter tier functionality
- Basic web UI
- Railway deployment

### Phase 2: Hardening (Days 31-45)
**Goal**: Production-ready reliability

Tasks:
- [ ] Rate limiting and abuse prevention
- [ ] Retry logic and circuit breakers
- [ ] Comprehensive error handling
- [ ] Golden test suite for determinism
- [ ] Load testing
- [ ] Security audit (auth, input validation)

### Phase 3: Professional Tier (Days 46-60)
**Goal**: Subscription-ready features

Tasks:
- [ ] Weekly monitoring automation
- [ ] Full alerts system
- [ ] Historical trend graphs
- [ ] Multiple competitors (2)
- [ ] Stripe billing integration
- [ ] Email notifications

### Phase 4: Scale & Polish (Days 61-90)
**Goal**: Growth-ready product

Tasks:
- [ ] Agency tier (multi-site, white-label)
- [ ] PDF export
- [ ] API access for integrations
- [ ] Performance optimization (caching, batch processing)
- [ ] Migrate to dedicated vector DB if needed
- [ ] SEO + content marketing infrastructure

### Phase 5: Differentiation (Days 91+)
**Goal**: Competitive moat

Tasks:
- [ ] Advanced contradiction detection
- [ ] Adaptive question suites per vertical
- [ ] Webhook integrations (Slack, Zapier)
- [ ] WordPress plugin
- [ ] Shopify app
- [ ] Chrome extension for quick audits

---

## 5. Key Technical Decisions

### 5.1 Embedding Model Selection
**Recommended**: `BAAI/bge-small-en-v1.5` or `sentence-transformers/all-MiniLM-L6-v2`
- Small enough for CPU inference
- Good retrieval quality
- 384/768 dimensions fits pgvector well

### 5.2 Hybrid Retrieval Strategy
```python
# RRF (Reciprocal Rank Fusion)
def hybrid_search(query, k=7):
    bm25_results = lexical_search(query, k=20)
    vector_results = vector_search(query, k=20)

    # Fuse with RRF
    fused = reciprocal_rank_fusion(bm25_results, vector_results, k=60)

    # Diversity constraint: max 2 chunks per page
    diversified = enforce_page_diversity(fused, max_per_page=2)

    return diversified[:k]
```

### 5.3 Provider Layer Interface
```python
class ObservationProvider(ABC):
    @abstractmethod
    async def run_observation(
        self,
        model: str,
        prompts: list[str],
        settings: dict
    ) -> ObservationRun:
        """Returns responses, usage, metadata, errors"""
        pass
```

### 5.4 Cost Control
- Cache embeddings by content hash (re-embed only on change)
- Use smaller models for scaffolds (Together AI, Groq)
- Batch observation calls where possible
- Enforce hard caps per plan tier

---

## 6. Recommended Development Order

```
1. Database + Auth (foundation)
   └── 2. Crawler + Extractor (data in)
       └── 3. Chunker + Embedder (indexed)
           └── 4. Retriever (searchable)
               └── 5. Question Generator
                   └── 6. Simulator + Scorer
                       └── 7. Fix Generator
                           └── 8. Observer + Benchmark
                               └── 9. Report Builder
                                   └── 10. Web UI
                                       └── 11. Monitoring
```

Each layer depends on the previous. Don't skip ahead.

---

## 7. Quick Start Commands

```bash
# Clone and setup
git clone <repo>
cd findable
cp .env.example .env

# Install dependencies
poetry install  # or: pip install -e .

# Start local services
docker-compose up -d  # postgres + redis

# Run migrations
alembic upgrade head

# Start API (dev)
uvicorn api.main:app --reload --port 8000

# Start worker (separate terminal)
rq worker findable-tasks

# Run tests
pytest -v
```

---

## 8. Environment Variables Template

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/findable

# Redis
REDIS_URL=redis://localhost:6379/0

# Auth
JWT_SECRET=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080

# Storage
STORAGE_BUCKET_URL=https://bucket.r2.cloudflarestorage.com
STORAGE_ACCESS_KEY=xxx
STORAGE_SECRET_KEY=xxx

# Observation Providers
OPENROUTER_API_KEY=sk-or-xxx
OPENAI_API_KEY=sk-xxx

# Embeddings (optional, for API-based)
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5

# Environment
ENV=development
DEBUG=true
```

---

## 9. References

### Documentation
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [pgvector Guide](https://github.com/pgvector/pgvector)
- [Sentence Transformers](https://www.sbert.net/)
- [trafilatura Docs](https://trafilatura.readthedocs.io/)
- [RQ Documentation](https://python-rq.org/)

### Tutorials
- [Building RAG with pgvector](https://www.timescale.com/blog/postgresql-as-a-vector-database-create-store-and-query-openai-embeddings-with-pgvector/)
- [Hybrid Search Explained](https://www.pinecone.io/learn/hybrid-search/)
- [FastAPI Production Setup](https://fastapi.tiangolo.com/deployment/)

### Similar Open Source Projects
- [llama-index](https://github.com/run-llama/llama_index) - RAG framework
- [haystack](https://github.com/deepset-ai/haystack) - NLP pipelines
- [embedchain](https://github.com/embedchain/embedchain) - RAG builder
