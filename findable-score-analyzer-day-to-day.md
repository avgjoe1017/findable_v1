Below is the **Day-by-Day MVP 1 plan** (30 days) with **Goal → Steps → Deliverables**. This matches the spec (FastAPI + RQ + Postgres/pgvector + Redis + Railway + Jinja2).

---

## Day 1 — Repo + CI foundation

**Goal:** Project boots cleanly and stays clean.
**Steps:**

* Create monorepo layout (`/api`, `/worker`, `/migrations`, `/web`)
* Add dependency manager (Poetry/uv) + lockfile
* Add lint/format/test tooling (ruff/black/mypy baseline)
* Add GitHub Actions for lint + tests
  **Deliverables:**
* Repo skeleton committed
* CI pipeline green on main

---

## Day 2 — FastAPI skeleton + API conventions

**Goal:** Stable API base with consistent errors.
**Steps:**

* App factory, settings, env loading
* Add `/health`
* Add `/v1` router + response envelope conventions
  **Deliverables:**
* Running API server with versioned routing
* Standard error format documented

---

## Day 3 — Auth (JWT)

**Goal:** Users can create accounts and authenticate.
**Steps:**

* Implement FastAPI-Users (or equivalent)
* Add register/login/me endpoints
* Add User model + migration
  **Deliverables:**
* `POST /auth/register`, `POST /auth/login`, `GET /auth/me` working
* Users table migrated

---

## Day 4 — Core DB models v1

**Goal:** Data model exists for sites + runs.
**Steps:**

* Create models: `sites`, `runs`, `competitors`
* Alembic migrations
* Basic CRUD layer
  **Deliverables:**
* DB schema migrated
* CRUD functions passing tests

---

## Day 5 — RQ + Redis job plumbing

**Goal:** Background jobs run reliably.
**Steps:**

* Add Redis connection
* Add RQ worker entrypoint
* Add enqueue + job status polling
  **Deliverables:**
* “hello job” runs end-to-end
* API can enqueue and poll job status

---

## Day 6 — Site + competitor endpoints

**Goal:** Users can create a site and set competitors.
**Steps:**

* Implement `POST/GET/PATCH /sites`
* Implement `PUT /sites/{id}/competitors`
* Stub plan caps (enforced later)
  **Deliverables:**
* Sites CRUD endpoints complete
* Competitor list stored and retrievable

---

## Day 7 — Crawler v1 (static)

**Goal:** Bounded crawl collects pages deterministically.
**Steps:**

* URL normalization + de-dup
* BFS crawl with `max_pages` / `max_depth`
* Basic robots respect
* Persist raw HTML to storage (local first, bucket later)
  **Deliverables:**
* Crawl job that outputs `pages` records + raw HTML artifacts
* Crawl report (counts, errors, skipped URLs)

---

## Day 8 — Extraction v1

**Goal:** Turn raw HTML into clean main content.
**Steps:**

* Add trafilatura extraction
* BeautifulSoup fallback
* Store extracted text + metadata + content hash
  **Deliverables:**
* `pages.extracted_text` populated
* Dedup by content hash working

---

## Day 9 — Render Delta Rule (headless only when needed)

**Goal:** Headless rendering is used only when measured necessary.
**Steps:**

* Integrate Playwright
* Implement rule: static extract < threshold → headless render → compare delta
* Persist `render_mode` per page
  **Deliverables:**
* “render required” flagged only when delta is real
* Crawl+extract pipeline handles JS sites correctly

---

## Day 10 — Semantic chunker v1

**Goal:** Chunking preserves tables/lists/steps.
**Steps:**

* Chunk by heading path
* Table/list detection heuristics to keep intact
* Persist chunks with metadata (url, title, heading_path, chunk_index)
  **Deliverables:**
* `chunks` table populated from extracted pages
* Visual inspection script (dev-only) to spot bad splits

---

## Day 11 — Embeddings v1 (pgvector)

**Goal:** Vector search works in Postgres.
**Steps:**

* Enable pgvector extension
* Add vector column + indexes
* Batch embed chunks
* Store embed model/version
  **Deliverables:**
* Embeddings stored for chunks
* Vector query returns relevant chunks

---

## Day 12 — Retrieval v1 (hybrid)

**Goal:** Retrieval returns diverse, relevant evidence.
**Steps:**

* Postgres FTS for lexical scoring
* pgvector similarity for semantic scoring
* RRF fusion
* Dedup near-identical chunks + diversity constraints
  **Deliverables:**
* Retrieval function: `retrieve(question) -> top_k chunks`
* Unit tests for dedup + diversity caps

---

## Day 13 — Universal questions (15) + question set table

**Goal:** Stable baseline question suite exists.
**Steps:**

* Create `question_sets` table
* Implement 15 universal questions (final wording)
* Brand insertion + normalization
  **Deliverables:**
* `POST /questions/generate` returns universal list
* Question sets are versioned and stored

---

## Day 14 — Deterministic site-derived questions (5)

**Goal:** Site-derived questions are repeatable and defensible.
**Steps:**

* Implement rule engine: FAQ → verbatim, nav → templates, claims → extract+verify, policy → templates
* Add selection rule for top 5
* Add fast pre-retrieval check for claim-derived
  **Deliverables:**
* Site-derived 5 generated deterministically
* Re-running on unchanged site yields same 5

---

## Day 15 — Simulation runner v1 (per band)

**Goal:** Simulated engine produces pass/fail + evidence.
**Steps:**

* For each question: retrieve top-k, build context capped by band budget
* Deterministic “answer found” heuristics first
* Store `sim_results` with evidence chunk IDs
  **Deliverables:**
* `simulate_run(site, bands)` job works
* Sim results stored per band

---

## Day 16 — Scoring rubric + Show the Math

**Goal:** Single score becomes transparent and trustworthy.
**Steps:**

* Add reason codes + point mapping
* Implement aggregation into Show-the-Math buckets
* Compute robustness band score trio
  **Deliverables:**
* `score.bands` + `score.show_the_math` generated
* Per-question contributions available

---

## Day 17 — Fix generator v1 (Clarity Scaffolds)

**Goal:** Actionable fixes map to failed questions.
**Steps:**

* Reason code → fix template mapping
* Extract-first scaffolds from existing site language
* Draft placeholders `[YOU FILL IN]` where needed
  **Deliverables:**
* `fix_plan` list created and stored
* Each fix links to affected questions

---

## Day 18 — Fix Impact Estimator Tier C (precomputed ranges)

**Goal:** Counterfactual lift exists without compute blowup.
**Steps:**

* Implement Tier C lookup table (conservative ranges)
* Attach Tier C impact estimates to top fixes
  **Deliverables:**
* Impact ranges appear in report for top 3–5 fixes

---

## Day 19 — Fix Impact Estimator Tier B (synthetic patch)

**Goal:** Fast “what if” re-score for affected questions only.
**Steps:**

* In-memory patch scaffold into target chunk(s)
* Identify affected questions (URL + reason mapping)
* Re-run retrieval+grading only for affected subset
  **Deliverables:**
* `POST /fixes/{id}/impact/estimate` supports Tier B
* Demonstrated that Tier B avoids full re-run cost

---

## Day 20 — Observation Provider Layer

**Goal:** Automated observation is real and resilient.
**Steps:**

* Implement provider interface
* Add router provider (aggregator-first)
* Add direct OpenAI fallback provider
* Add retries + failover
  **Deliverables:**
* `observe_run(site)` works via provider layer
* Provider failover proven in dev

---

## Day 21 — Observation parsing

**Goal:** Turn model outputs into measurable signals.
**Steps:**

* Extract mentions (brand/domain)
* Extract links/URLs
* Extract citation-like patterns where present
* Persist `obs_results`
  **Deliverables:**
* Observed mention rate computed
* Per-question observed outcomes stored

---

## Day 22 — Competitor benchmark run

**Goal:** Competitive intelligence is core and automated.
**Steps:**

* Run observation for competitors
* Create win/loss table
* Compute deltas (simple heuristics)
  **Deliverables:**
* Benchmark section generated (you vs competitor)
* Per-question win/loss list

---

## Day 23 — Report assembler v1 (JSON contract)

**Goal:** Stable “product artifact” exists.
**Steps:**

* Implement report JSON contract
* Add versioning and limitations
* Add divergence trigger logic
  **Deliverables:**
* `GET /reports/{id}` returns full report JSON
* Golden test report fixture saved

---

## Day 24 — Minimal UI (Jinja2)

**Goal:** MVP is usable without Postman.
**Steps:**

* Site creation screen
* “Run audit” screen with job progress
* Report viewer (score bands, math, blockers, fixes, benchmark)
  **Deliverables:**
* Working UI paths for start → report
* Screenshotable “demo flow”

---

## Day 25 — Monitoring scheduler

**Goal:** Weekly snapshots run automatically.
**Steps:**

* Add scheduler job (cron/service)
* Weekly snapshot job enqueue
* Monthly free snapshot mode for Starter sites
  **Deliverables:**
* Snapshot run created on schedule
* Snapshot records saved

---

## Day 26 — Alerts v1

**Goal:** Monitoring produces action, not noise.
**Steps:**

* Implement alert rules: mention_rate_drop, competitor_overtake, high_conflict, crawl_blocked
* Store alerts + show in UI
  **Deliverables:**
* Alerts table populated
* Alerts page in UI

---

## Day 27 — Plan caps + billing hooks (stub)

**Goal:** Economics enforced even before Stripe.
**Steps:**

* Enforce caps: competitors, custom questions, run frequency
* Add plan field to account/site
* Admin override tooling
  **Deliverables:**
* Caps enforced in endpoints and workers
* Plan gates tested

---

## Day 28 — Hardening + observability

**Goal:** Production behaviors are predictable.
**Steps:**

* Structured logging
* Sentry
* Timeouts + retries for crawl/observe
* Rate limiting basics
  **Deliverables:**
* Errors show up in Sentry with context
* Slow/failing sites don’t stall queues

---

## Day 29 — Determinism + replay tests

**Goal:** Trust-critical stability is verified.
**Steps:**

* Re-run same site twice; assert same site-derived questions
* Assert scores stable within tolerance
* Add small set of fixture sites for regression
  **Deliverables:**
* Regression test suite for determinism
* “known-good” fixtures committed

---

## Day 30 — Deployment (Railway)

**Goal:** Live MVP running with workers and storage.
**Steps:**

* Deploy API + Worker services
* Add Postgres + Redis add-ons
* Enable pgvector
* Configure secrets and storage bucket
* Run migrations
  **Deliverables:**
* Publicly reachable MVP
* End-to-end demo run on a real site + competitor

---

If you want, I can also output this as a **one-page execution checklist** (Week 1–4 milestones) so you can track it like a sprint board.
