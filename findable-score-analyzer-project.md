# Findable Score Analyzer
*A wide-ranging, adaptive website analyzer that measures **sourceability**: whether AI answer engines can retrieve and use your site as a source under real constraints, with **one score**, transparent math, and implementation-ready fixes, backed by **observed reality snapshots**, competitive benchmarks, and monitoring.*

---

## 0) Project North Star

### The job
Answer engines don’t browse your website like a human. They retrieve a small set of fragments, synthesize an answer, and move on. Visibility increasingly depends on whether your site is **usable as a source** for the questions buyers ask.

This project builds a system that:

- **Tests sourceability under constraints** (bounded crawl, extraction, semantic chunking, retrieval, strict context limits)
- **Validates against observed reality** (model outputs over a fixed question set)
- **Benchmarks against competitors** (same questions, same method)
- **Closes the loop with monitoring** (weekly snapshots, alerts, trending)
- Outputs:
  - **Findable Score (0–100)** with **robustness bands**
  - **Show the Math** breakdown (no black box)
  - **Per-question evidence** and failure reasons
  - **Fix Impact Estimator** (counterfactual re-scoring)
  - **Clarity Scaffolds** (extract-first, collaborative modules, not generic copywriting)

### The simplest, strongest differentiator (credible and defensible)
> **We measure whether AI can retrieve and use your site as a source, then prove it with observed snapshots and competitor benchmarks.**  
> One score. Transparent math. Fixes you can ship. Proof it worked.

---

## 1) Product Promise

### One score that’s actually useful
**Findable Score (0–100)** measures:
- **Coverage**: do you answer the key questions?
- **Extractability**: can those answers be retrieved under constraints?
- **Citability**: are answers explicit, quotable, attributable?
- **Trust clarity**: is the entity legitimate and consistent enough to cite?

You get:
- A single headline number
- A transparent decomposition (Show the Math)
- A ranked fix plan with estimated impact

### The product loop (this is the business)
**Track how AI sees you → fix what’s broken → prove it worked → keep it stable over time.**

Audit without observation is guesswork. Observation without actionability is noise. The product is the loop.

---

## 2) Modes: Simulated vs Observed (and why both exist)

### 2.1 Simulated Findability (sourceability engine)
A deterministic, reproducible simulation that tests whether correct, citable answers can be assembled from your site under constraints.

**What it measures**
- Retrieval success under constraints
- Answer specificity and clarity
- Citation-readiness (quotable + attributable)
- Trust clarity
- Conflict and redundancy penalties

**What it produces**
- Findable Score (with robustness bands)
- Simulation Trace (retrieved excerpts + pass/fail reasons)
- Fix plan + Fix Impact Estimator

### 2.2 Observed Findability (reality snapshot)
A reality-based snapshot of how a real model responds to the same question set.

**What it measures**
- Mentions / citations / link presence (where available)
- Accuracy vs the site
- “What you’re known for” patterns
- Differences versus simulation

**Why it’s existential**
Observed results are the only defensible validation layer:
- They prove the audit matters
- They anchor ROI
- They create monitoring value

**MVP requirement**
- Ship with **automated observation** through a provider layer (Section 2.3). Manual capture is fallback only.

### 2.3 Observation Provider Layer (de-risk vendor dependency)
Do not hard-couple MVP to any single API provider.

Implement a thin provider interface:

- `run_observation(model, prompts[], settings) -> ObservationRun`
- `ObservationRun` returns:
  - `responses[]` (raw text)
  - `usage` (tokens; cost estimate when available)
  - `metadata` (model id, timestamp, provider id)
  - `errors[]`

Supported providers:
- **Provider A (default):** Aggregator router (OpenRouter-style) for rapid switching
- **Provider B:** Direct OpenAI
- **Provider C:** Additional systems later (Perplexity, Gemini, etc.)

**Fallback**
- Manual capture: paste outputs into a single field for parsing (not a weekly workflow)

**Resilience**
- Queue observation jobs
- Retries with backoff
- Per-run caps (questions, competitors, custom questions)
- Provider failover if a run fails

---

## 3) Competitive Benchmark (Core Feature)

### 3.1 What it is
Every observed snapshot includes competitor comparison.

User provides:
- Their site
- 1 competitor (Starter)
- 2 competitors (Professional)

The system runs:
- The **same question set**
- The **same observation method**
- The **same scoring + trace**

### 3.2 Why it matters
Competitive benchmarking:
- Removes doubt (“maybe no one gets cited in my space”)
- Creates urgency (“competitor dominates questions you fail”)
- Makes fixes obvious (competitor has a clear pricing/service area/policy block; you don’t)
- Justifies price (this is competitive intelligence, not a checklist)

### 3.3 Benchmark outputs
- Observed mention/citation rate: **You vs Competitor**
- Per-question win/loss table
- Side-by-side evidence (Simulation Trace + observed deltas)
- Top structural differences (missing pages, missing modules, weaker trust surfaces)

---

## 4) Constraints Model (Not Just Tokens)

Answer engines are constrained by multiple factors. The analyzer models:

1) **Context limit** (how much text can be used per question)
2) **Relevance ranking** (retrieval quality and query matching)
3) **Source diversity** (avoid one-page dominance)
4) **Recency preference** (for time-sensitive topics/claims)
5) **Trust gates** (entity identity, policies, legitimacy)
6) **Consistency** (avoid conflicting values)

Token/context limits are a major constraint, but not the only one. Modeling multiple constraints keeps the system defensible.

---

## 5) Robustness Bands (Turn uncertainty into a feature)

Instead of assuming a single budget, compute a **robustness band**:

- **Conservative** (tight context)
- **Typical** (mid context)
- **Generous** (wide context)

Report as:
- **Findable Score (Conservative / Typical / Generous): 61 / 72 / 81**
- **Budget sensitivity**: “Your pricing answers only become reliable after ~X tokens.”
- **Minimum viable budget** (optional): smallest budget where the answer becomes correct/citable

This makes the metric forward-compatible as systems change.

---

## 6) Site Understanding (Adaptive, but overridable)

### 6.1 “Vertical” is not one label
A site can be ecommerce + media, or local service + SaaS. Use multi-axis understanding:

- `business_model` (primary)
- `industry_tags[]` (secondary, optional, multi-label)
- `intent_mix` (critical)

### 6.2 Business model inference (assistive)
Values (extendable):
- Local Service
- Ecommerce
- SaaS / Software
- Publisher / Media
- Marketplace / Directory
- Professional Services / Agency
- Nonprofit / Education
- B2B Industrial / Manufacturing
- Healthcare / Regulated
- Events / Hospitality
- Unknown

**Signals**
- Schema types: `LocalBusiness`, `Product`, `Service`, `Article`, `FAQPage`, `SoftwareApplication`, etc.
- Navigation: Pricing, Plans, Book, Shop, Cart, Locations, Industries, Docs, Support
- CTAs: Buy, Add to cart, Book now, Request demo, Get quote, Subscribe, Donate
- Commerce artifacts: cart/checkout routes, SKU patterns, shipping/returns pages
- Location footprint: NAP blocks, maps embeds, service area pages
- Content footprint: blog density, author boxes, publication dates

**User override**
- Always available in one click
- Required when confidence < threshold (e.g., 0.75)
- Overrides are logged and can improve future suite selection

---

## 7) Retrieval & Ingest Pipeline (Simulated Engine)

### 7.1 Bounded crawl strategy
Configurable:
- `max_pages` (e.g., 150–300)
- `max_depth` (e.g., 3)
- Always include: home, about, pricing (or equivalent), contact, key product/service pages, FAQs, policies

Exclude:
- query-string explosions
- faceted nav loops
- infinite tag pages
- low-value duplicates

### 7.2 Rendering: Render Delta Rule (no guessing)
Many sites include JS but still render meaningful HTML. Don’t guess “JS-heavy.” Measure.

**Rule**
1) Try static fetch + extraction
2) If extracted main content is below threshold (e.g., <200–300 meaningful words), run headless render
3) Compare extraction outputs (“render delta”):
   - If headless yields materially more content, use headless and flag “render-required”
   - If not, proceed with static and do not warn

### 7.3 Main content extraction requirements
- remove nav/footers/boilerplate
- preserve heading hierarchy
- preserve lists and tables meaningfully
- retain author/date when present

### 7.4 Semantic-aware chunking (must-have)
Chunking must preserve meaning:
- Tables: keep headers + rows together; avoid splitting mid-table
- Lists: keep headers + items together
- “How it works” steps: keep sequences intact

Defaults:
- chunk size target: 600–1,000 tokens
- overlap: 50–150 tokens (adaptive)
- store metadata: url, title, heading path, chunk index, lastmod/date, schema types

### 7.5 Retrieval
Support:
- Lexical (BM25 via Postgres FTS)
- Vector (pgvector)
- Hybrid (RRF fusion)

Per query:
- retrieve top‑k chunks (k configurable, e.g., 5–7)
- deduplicate near-identical chunks
- enforce diversity constraints (avoid same-page dominance)
- enforce robustness band context caps

---

## 8) Three-Layer Question Suite (15 + 5 + 5) + Custom Questions

### 8.1 Why this design
You cannot pre-build perfect vertical taxonomies. Let the site and user steer relevance while keeping scope tight.

### 8.2 Layer 1: Universal Core (15)
Always runs. Stable across business types.

### 8.3 Layer 2: Site-derived (5)
Generated deterministically from the site’s own signals using rules below.

#### 8.3.1 Site-derived generation rules (deterministic)
**Rule 1: FAQ headings → verbatim questions**
- If an FAQ heading is already a question, use it verbatim.
- If it is a statement, convert to a question minimally (preserve terms).

**Rule 2: Nav labels → template mapping**
Map common nav labels (case-insensitive, normalized) to a canonical question:

- Pricing / Plans → “How much does [BRAND] cost?”
- Services / Solutions → “What services does [BRAND] provide?”
- Products / Shop → “What products does [BRAND] sell?”
- Locations / Service Areas → “Where does [BRAND] operate or serve?”
- About → “What is [BRAND]?” and “Why should I trust [BRAND]?”
- Contact → “How do I contact [BRAND]?”
- Industries / Use Cases → “Who is [BRAND] for?” / “What industries does [BRAND] serve?”
- Docs / Support → “What support does [BRAND] offer?”
- Integrations → “What does [BRAND] integrate with?”
- Security / Privacy → “How does [BRAND] handle data and security?”
- Shipping / Returns / Warranty → policy-specific questions

If the label is generic (“Solutions”), prefer the least-assumptive mapping and defer to homepage claim extraction (Rule 3).

**Rule 3: Homepage claims → extract + verify pattern**
From hero headline/subhead/bullets, extract patterns:
- “We help X do Y” → “How does [BRAND] help X do Y?”
- “Trusted by N+” → “Who uses [BRAND]?”
- “24/7 support” → “What support does [BRAND] offer?”
- “Same-day / emergency” → “Do they offer same-day or emergency service?”
Verification step: only keep claim-derived questions if the retriever finds at least one relevant chunk mentioning the claim keywords.

**Rule 4: Policy pages → specific concerns**
If a dedicated policy page exists, add the matching question:
- Shipping → “What is [BRAND]’s shipping policy?”
- Returns/Refunds/Cancellations → “What is [BRAND]’s refund/return/cancellation policy?”
- Privacy → “How does [BRAND] handle customer data?”

**Selection rule (choose 5)**
Prioritize in order:
1) FAQ questions
2) Policy questions
3) High-signal nav mappings (Pricing, Contact, Locations, Returns)
4) Verified homepage-claim questions
Tie-breaker: choose questions with the highest retrieval confidence after a fast pre-retrieval check.

### 8.4 Layer 3: Adaptive Add-on (5)
Only when:
- business model confidence is high, or
- universal results strongly indicate a category

If skipped, the report explains why and suggests user-supplied custom questions.

### 8.5 Custom questions (3–5)
User supplies money questions. These are retained for monitoring.

---

## 9) Scoring: Show the Math, Per-Question Contributions, Fix Impact Estimator

### 9.1 What users see
**Findable Score: 61/100 (Conservative)**

**Show the Math**
- Coverage: 18/25 answerable (72%)
- Extractability: -5 (weak internal linking to answer pages)
- Citability: -7 (no quotable definition blocks / attribution)
- Trust: -4 (thin about/contact/policy surfaces)
- Conflicts: -2 (two pages disagree on pricing)
- Redundancy: -1 (repeated boilerplate crowding retrieval)

Also show:
- Typical and Generous band scores
- Budget sensitivity notes

### 9.2 Per-question score contributions
For each question:
- Pass/fail
- Points gained/lost
- Reason codes
- Evidence snippets (retrieved excerpts)
- Suggested fix mapping

### 9.3 Fix Impact Estimator (counterfactual re-scoring) — compute-safe design
The Fix Impact Estimator must not multiply costs linearly with the number of fixes.

#### 9.3.1 Three-tier impact estimation strategy
**Tier C (default): Pre-computed pattern ranges**
- For common missing elements, show an estimated lift range derived from historical runs.

**Tier B (most fixes): Synthetic patch**
- Insert proposed scaffold text into the relevant existing chunk(s) in-memory.
- Re-run retrieval + grading for affected questions only.

**Tier A (rare / post-implementation): Full re-score**
- Reserved for “prove it worked” after the user makes changes.

#### 9.3.2 Affected-question targeting (mandatory)
Only re-score questions that are plausibly impacted by the fix target URL or reason mapping.

---

## 10) Evidence Output: Simulation Trace + Observed Reality Snapshot

### 10.1 Simulation Trace (default evidence)
For selected questions (especially failures):
- Question
- Retrieved excerpts
- Why it failed
- Fix recommendation and placement

### 10.2 Reality Snapshot (required in shipped product)
Automated observation through provider layer:
- Runs the same question set
- Captures outputs
- Extracts mention/citation/link presence when available
- Produces:
  - observed mention/citation rate
  - per-question observed outcome
  - delta analysis vs simulation

---

## 11) Divergence Protocol: When Simulation and Observation Disagree

### 11.1 Divergence definition
Example:
- Simulation Typical score ≥ 70
- Observed mention/citation rate ≤ 10% across the same questions

### 11.2 Diagnostic buckets
- Authority gap
- Recency gap
- Diversity suppression
- Query mismatch

### 11.3 Product behavior
**Short-term**
- Observation becomes headline truth
- Simulation becomes fix engine
- Suggest next experiments (custom questions aligned to observed phrasing)

**Long-term**
- Calibrate simulation with observation outcomes
- Track correlation metrics across the dataset

**Escape hatch**
- Reframe score as “On-site Sourceability” and use observation as primary KPI if convergence fails.

---

## 12) Clarity Scaffolds (Extract-First, Collaborative)

Clarity Scaffolds are structured modules that:
- reflect the site’s existing language where possible
- make implicit facts explicit
- present info in retrieval-friendly formats
- avoid pretending to be expert copywriting

If drafting is required:
- label as **DRAFT**
- include placeholders: **[YOU FILL IN]**
- keep minimal and concrete

---

## 13) Contradiction Detection (High-Certainty Only in v1)

v1 detects:
- Exact/near-exact field conflicts (pricing, address/phone, founded year, refund windows)
- Schema conflicts
- Duplicated pages with different numeric claims

Everything else:
- Potential inconsistency, human review recommended

---

## 14) Monitoring (Core Product, Not Upsell)

Weekly snapshots:
- Run observed question set for your site + competitors
- Track mention/citation frequency
- Detect drops and shifts
- Show trendlines and deltas over time
- Re-run Fix Impact Estimator for new gaps

Alerts:
- Mention/citation drop
- Competitor overtakes category
- New high-confidence contradictions
- noindex/robots changes that affect retrievability

---

## 15) Pricing and Packaging (Monitoring-First Strategy)

### Starter (one-time): **$299**
- Simulated + Observed audit
- Findable Score with Show the Math
- Simulation Trace + Reality Snapshot
- Fix plan + Fix Impact Estimator
- 1 competitor benchmark
- 4 weekly monitoring snapshots included

After 30 days:
- Monthly snapshots (free)

### Professional (monthly): **$149/mo**
- Weekly snapshots
- 2 competitors
- Alerts
- Trendlines and history
- Re-score after fixes
- Custom questions tracked

Caps and safety nets:
- 2 competitors included (add-on competitor: +$49/mo)
- 5 custom questions included

### Agency (annual): **$1,788/year**
- Everything in Pro
- Up to 10 client sites
- White-label (remove Findable branding on PDFs; agency logo/header allowed)
- Resell allowed
- Additional client sites: $99/year per site

---

## 16) Distribution and Go-to-Market

Primary:
- Agencies/consultants
- Content-led inbound
- Founder-led outbound with competitor wedge

Secondary:
- WordPress plugin / Shopify app later
- Integration marketplaces after proof

---

## 17) MVP 1 Stack Decision (Committed Defaults)

These defaults are selected to minimize moving parts while keeping the architecture production-grade.

- Backend: Python 3.11+, FastAPI (async)
- DB: PostgreSQL + pgvector (one service, retrieval included)
- Cache/Queue: Redis + RQ (simple and robust)
- Crawling: httpx (static) + Playwright (headless when render delta triggers)
- Extraction: trafilatura + BeautifulSoup fallback
- Observation: Provider Layer
  - default aggregator (OpenRouter-style)
  - direct OpenAI fallback
- Hosting: Railway (two services) or Render equivalent
- Storage: Cloudflare R2 or S3 compatible bucket for crawl artifacts and report exports
- Errors/metrics: Sentry + basic Prometheus-style counters (optional)

---

## 18) MVP 1 API Endpoints (Exact Contract)

All endpoints are under `/v1`. Auth required unless noted.

### 18.1 Auth
- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `POST /v1/auth/logout`
- `GET  /v1/auth/me`

Request/response is standard email+password JWT flow (FastAPI-Users recommended).

### 18.2 Sites
- `POST /v1/sites`
  - body: `{ "domain": "example.com", "name": "Example", "settings": { ... } }`
  - resp: `{ "site_id": "...", "status": "created" }`

- `GET /v1/sites`
  - resp: list of sites

- `GET /v1/sites/{site_id}`
  - resp: site metadata + latest runs pointers

- `PATCH /v1/sites/{site_id}`
  - update settings and competitors

### 18.3 Competitors
- `PUT /v1/sites/{site_id}/competitors`
  - body: `{ "competitors": ["comp1.com", "comp2.com"] }`
  - enforce plan caps

### 18.4 Questions
- `POST /v1/sites/{site_id}/questions/generate`
  - body: `{ "custom_questions": ["...","..."] }`
  - resp: `{ "question_set_id": "...", "questions": { "universal": [...], "site_derived": [...], "adaptive": [...], "custom": [...] } }`

- `GET /v1/sites/{site_id}/questions/latest`
  - resp: latest question set (stable across reruns unless content changes or user changes custom questions)

### 18.5 Run an audit (simulated + observed + benchmark)
- `POST /v1/sites/{site_id}/runs`
  - body:
    ```json
    {
      "run_type": "starter_audit",
      "include_observation": true,
      "include_benchmark": true,
      "bands": ["conservative","typical","generous"],
      "provider": {"preferred": "router", "model": "auto"},
      "question_set_id": "optional_override"
    }
    ```
  - resp: `{ "run_id": "...", "job_id": "...", "status": "queued" }`

- `GET /v1/runs/{run_id}`
  - resp: `{ "run_id": "...", "status": "running|complete|failed", "progress": { ... }, "report_id": "..." }`

### 18.6 Reports
- `GET /v1/reports/{report_id}`
  - resp: report JSON contract (Section 19)

- `GET /v1/reports/{report_id}/download`
  - resp: signed URL to PDF/HTML export (optional in MVP; JSON is sufficient)

### 18.7 Fixes and Fix Impact
- `POST /v1/sites/{site_id}/fixes`
  - body: `{ "fix_type": "...", "target_url": "...", "scaffold_text": "...", "effort": "S|M|L" }`
  - resp: `{ "fix_id": "...", "status": "created" }`

- `POST /v1/fixes/{fix_id}/impact/estimate`
  - body: `{ "mode": "tier_c|tier_b", "bands": ["typical"] }`
  - resp: `{ "lift_min": 5, "lift_max": 9, "estimated_new_score": { "min": 66, "max": 70 }, "details": { ... } }`

### 18.8 Monitoring
- `POST /v1/sites/{site_id}/monitoring/enable`
- `POST /v1/sites/{site_id}/monitoring/disable`
- `GET  /v1/sites/{site_id}/snapshots`
- `GET  /v1/sites/{site_id}/alerts`

---

## 19) Report JSON Contract (Benchmark + Proof)

This is the primary product surface. Keep it stable and versioned.

```json
{
  "report_version": "1.0",
  "site": {
    "site_id": "uuid",
    "domain": "example.com",
    "generated_at": "2026-01-28T00:00:00Z"
  },
  "config": {
    "crawl": {"max_pages": 250, "render_mode": "static_or_headless"},
    "retrieval": {"top_k": 7, "hybrid": true, "diversity": true},
    "bands": {
      "conservative": {"max_tokens": 3000},
      "typical": {"max_tokens": 6000},
      "generous": {"max_tokens": 12000}
    },
    "observation": {"provider": "router", "model": "auto"}
  },
  "score": {
    "bands": {"conservative": 61, "typical": 72, "generous": 81},
    "headline_band": "conservative",
    "show_the_math": {
      "coverage": {"answered": 18, "total": 25, "pct": 0.72, "points": 45},
      "extractability": {"points_delta": -5, "drivers": ["weak_internal_links"]},
      "citability": {"points_delta": -7, "drivers": ["no_definition_block"]},
      "trust": {"points_delta": -4, "drivers": ["thin_about_page"]},
      "conflicts": {"points_delta": -2, "drivers": ["pricing_conflict"]},
      "redundancy": {"points_delta": -1, "drivers": ["boilerplate_repeats"]}
    },
    "confidence": {
      "crawl_coverage": 0.88,
      "render_confidence": 0.95,
      "classification_confidence": 0.78,
      "variance": 0.0
    },
    "budget_sensitivity": {
      "notes": ["pricing answers stabilize after ~6000 tokens"]
    }
  },
  "questions": {
    "universal": ["..."],
    "site_derived": ["..."],
    "adaptive": ["..."],
    "custom": ["..."]
  },
  "per_question_results": [
    {
      "question_id": "q01",
      "question": "What is [BRAND]?",
      "band": "conservative",
      "pass": false,
      "points": -4,
      "reasons": ["missing_definition", "not_citable"],
      "evidence": [{"url": "...", "chunk_id": "...", "excerpt": "..."}],
      "fix_mapping": ["fix_def_block_home"]
    }
  ],
  "top_blockers": [
    {"id": "b1", "statement": "No explicit definition of the business on high-authority pages.", "severity": "critical"}
  ],
  "fix_plan": [
    {
      "fix_id": "fix1",
      "fix_type": "definition_block",
      "target_url": "https://example.com/",
      "effort": "S",
      "why": "Fails identity questions; low citability.",
      "clarity_scaffold": {"status": "draft", "text": "DRAFT: ... [YOU FILL IN] ..."},
      "impact_estimate": {"mode": "tier_c", "lift_min": 8, "lift_max": 14, "estimated_new_score_min": 69, "estimated_new_score_max": 75}
    }
  ],
  "simulation_trace": [
    {
      "question_id": "q01",
      "retrieval": {"top_k": 7, "selected_chunks": ["c1","c2"], "dropped": [{"chunk_id": "c7", "reason": "over_budget"}]},
      "analysis": {"failure_reason": "missing_definition"}
    }
  ],
  "observation": {
    "runs": [
      {
        "provider": "router",
        "model": "auto",
        "site_domain": "example.com",
        "observed": {"mentions": 2, "questions": 20, "mention_rate": 0.10},
        "per_question": [{"question_id": "q01", "mentioned": false, "linked": false, "notes": "..." }]
      }
    ]
  },
  "benchmark": {
    "competitors": [
      {"domain": "competitor.com", "observed": {"mention_rate": 0.60}}
    ],
    "wins_losses": [{"question_id": "q01", "you": "loss", "competitor.com": "win"}],
    "deltas": [{"question_id": "q01", "insight": "Competitor has explicit definition block + pricing explainer."}]
  },
  "monitoring": {
    "starter_includes": {"weekly_snapshots": 4, "then_monthly_free": true},
    "next_snapshot": "2026-02-04T00:00:00Z"
  },
  "limitations": [
    "Observed results depend on model provider behavior and may change.",
    "Simulation measures on-site sourceability, not guaranteed citation placement."
  ]
}
```

---

## 20) First 15 Universal Questions (Final Wording)

These are intentionally wide-ranging and stable. They are phrased to avoid vertical assumptions while forcing on-site clarity.

1. What is **[BRAND]**?
2. What does **[BRAND]** do?
3. Who is **[BRAND]** for?
4. What problem does **[BRAND]** solve?
5. What makes **[BRAND]** different from alternatives?
6. How do I get started with **[BRAND]**?
7. What are the main steps to buy, book, or sign up with **[BRAND]**?
8. How much does **[BRAND]** cost?
9. How does pricing work for **[BRAND]**?
10. Where does **[BRAND]** operate, serve, or deliver?
11. How do I contact **[BRAND]**?
12. What are **[BRAND]**’s refund, return, or cancellation policies?
13. How does **[BRAND]** handle customer data and privacy?
14. What should someone expect after they purchase, book, or sign up?
15. What are common reasons someone would choose **[BRAND]**?

---

## 21) Job Queue Flows (RQ + Redis)

All heavy work runs on workers. API only schedules jobs and serves results.

### 21.1 Primary job graph
1) `crawl_site(site_id, run_id)`
2) `extract_pages(site_id, run_id)`
3) `chunk_pages(site_id, run_id)`
4) `embed_chunks(site_id, run_id)`
5) `generate_questions(site_id, run_id)` (if none or invalidated)
6) `simulate_run(site_id, run_id, bands[])`
7) `generate_fixes(site_id, run_id)`
8) `estimate_fix_impact(site_id, run_id)` (Tier C precomputed for top 3–5)
9) `observe_run(site_id, run_id, provider)` (site + competitors)
10) `assemble_report(site_id, run_id)`

### 21.2 Monitoring job graph
- `monitor_snapshot(site_id)` triggers:
  - `observe_run(site_id, snapshot_run_id)`
  - `compare_to_last_snapshot(site_id)`
  - `create_alerts(site_id)`

### 21.3 Retry policy
- Crawl: retry 2 times on transient errors
- Observation: retry 2 times; if provider fails, failover to fallback provider
- Workers log structured errors to Sentry

---

## 22) Database Schema (Postgres + pgvector)

Minimal, buildable schema. Use migrations (Alembic).

### 22.1 Required extensions
- `CREATE EXTENSION IF NOT EXISTS vector;`
- `CREATE EXTENSION IF NOT EXISTS pg_trgm;` (optional, for fuzzy matching)

### 22.2 Core tables (summary)
- `users`
- `sites`
- `competitors`
- `pages`
- `chunks`
- `question_sets`
- `runs`
- `sim_results`
- `fixes`
- `fix_impact`
- `obs_runs`
- `obs_results`
- `snapshots`
- `alerts`

### 22.3 Indexing requirements
- `pages(site_id, url)` unique
- `chunks(page_id, chunk_index)` unique
- `chunks(site_id)` btree
- `chunks(embedding)` ivfflat or hnsw index (pgvector)
- `sim_results(run_id, question_id)`
- `obs_results(run_id, question_id)`
- `alerts(site_id, created_at)`

---

## 23) Day-by-Day MVP 1 Build Plan (Railway + FastAPI + RQ + pgvector)

Assume one repo with:
- `/api` FastAPI app
- `/worker` RQ worker entrypoint
- `/migrations` Alembic
- `/web` server-rendered templates (Jinja2) for MVP UI

### Day 1: Repo, environment, CI
- Create mono-repo structure
- Add Poetry or uv (lockfile)
- Add pre-commit (ruff, black, mypy baseline)
- GitHub Actions: lint + tests

### Day 2: Core FastAPI skeleton
- App factory, settings management (pydantic-settings)
- Health endpoint: `GET /health`
- Versioned router: `/v1`
- Basic error envelope (consistent API responses)

### Day 3: Auth
- Add FastAPI-Users (JWT)
- Implement register/login/me endpoints
- Add `User` model + migrations

### Day 4: Database models v1
- Create tables: sites, competitors, runs
- Create alembic migration
- Add CRUD service layer

### Day 5: RQ setup
- Redis connection
- Worker entrypoint
- Enqueue test job from API
- Job status polling

### Day 6: Site CRUD endpoints
- Implement create/read/update/list for sites
- Competitor list endpoint with plan caps stubbed

### Day 7: Crawler v1 (static)
- URL normalization rules
- robots.txt respect (basic)
- sitemap discovery (basic)
- bounded BFS crawl with page cap and depth
- Store raw HTML in R2/S3 compatible storage (or local dev folder)

### Day 8: Extraction v1
- trafilatura extraction
- fallback BeautifulSoup extraction
- Store extracted text + metadata into `pages`
- Deduplicate by content hash

### Day 9: Render delta rule
- Add Playwright headless render path
- Implement delta trigger:
  - static extraction < threshold → headless fetch + extract
- Persist render_mode used per page

### Day 10: Chunker v1
- Implement semantic chunker:
  - heading path preservation
  - list preservation
  - table preservation heuristic (keep table blocks intact)
- Persist chunks into `chunks` table

### Day 11: Embeddings v1 (pgvector)
- Add embeddings table column (vector)
- Implement embed pipeline (batch)
- Add pgvector index
- Store embedding model id and version

### Day 12: Retrieval v1 (hybrid)
- Lexical: Postgres FTS ranking over chunks
- Vector: pgvector cosine similarity
- Hybrid: RRF fusion with diversity constraint
- Add dedup (near-identical chunk hash) and same-page dominance caps

### Day 13: Question set v1 (universal)
- Add question_sets table
- Implement the 15 universal questions (Section 20)
- Add brand insertion and sanity normalization

### Day 14: Site-derived question generator
- Implement deterministic rule engine (Section 8.3.1)
- Implement selection rule and fast pre-retrieval verification for claim-derived questions
- Persist question set snapshot with version pinning

### Day 15: Simulation runner v1
- For each question:
  - retrieve top-k chunks
  - build context per band using budget cap
  - compute pass/fail for “answer found” using deterministic heuristics first
- Store sim_results with evidence chunk ids

### Day 16: Grader rubric v1
- Add reason codes:
  - missing_definition, missing_pricing, buried_answer, not_citable, trust_gap, conflict
- Add scoring mapping per reason code
- Implement Show the Math aggregation

### Day 17: Fix generator v1 (Clarity Scaffolds)
- Map reason codes → fix templates
- Extract-first scaffold creation:
  - pull candidate sentences from high-authority pages
  - create DRAFT placeholders where missing
- Store fixes in DB

### Day 18: Fix Impact Estimator Tier C
- Hardcode initial pre-computed pattern ranges (conservative defaults)
- Attach top 3–5 impact estimates to fix_plan

### Day 19: Fix Impact Estimator Tier B (synthetic patch)
- Implement in-memory patching on target URL chunk(s)
- Re-run affected questions only
- Output lift range per band

### Day 20: Observation provider layer
- Define provider interface
- Implement router provider (aggregator)
- Implement direct OpenAI fallback provider
- Implement job: `observe_run` for site domain

### Day 21: Observation parsing
- Parse responses for:
  - mentions of brand/domain
  - links (URLs)
  - “source style” citations when present
- Persist obs_results

### Day 22: Competitor benchmark run
- Extend observe_run to competitors
- Build win/loss table and benchmark deltas (simple heuristics)

### Day 23: Report assembler v1 (JSON)
- Implement report JSON contract (Section 19)
- Ensure versioning and stable fields
- Add limitations and divergence protocol triggers

### Day 24: Minimal web UI (Jinja2)
- Site creation page
- Run audit button and job status
- Report viewer page:
  - score bands
  - show the math
  - top blockers
  - fix plan with impact estimates
  - benchmark summary

### Day 25: Monitoring scheduler
- Add cron-style scheduler service (simple)
- Weekly snapshot job enqueue
- Monthly free snapshot enqueue for Starter sites
- Store snapshots and alerts baseline

### Day 26: Alerts v1
- Define alert types:
  - mention_rate_drop
  - competitor_overtake
  - high_conflict_detected
  - crawl_blocked
- Add alert creation rules
- Display alerts in UI

### Day 27: Plan caps and billing hooks (stub)
- Enforce competitor and custom question caps by plan
- Add “plan” field on site/account
- Integrate Stripe later; for MVP use admin-set plan

### Day 28: Hardening and observability
- Add structured logging
- Sentry integration
- Rate limiting (basic)
- Timeouts and retries for crawling and observation

### Day 29: QA and deterministic replay
- Re-run same site twice and assert:
  - same site-derived questions
  - stable score within tolerance
- Add golden test fixture sites (small)

### Day 30: Deployment
- Deploy to Railway:
  - `api` service (FastAPI)
  - `worker` service (RQ worker)
  - `redis` add-on
  - `postgres` add-on with pgvector
- Configure env vars, secrets, and storage bucket

---

## 24) Deployment Guide (Railway, MVP)

### 24.1 Services
- `api`: FastAPI app
- `worker`: RQ worker
- `redis`: managed Redis
- `postgres`: managed Postgres (enable pgvector)
- Optional: `scheduler` as a separate service, or run scheduler inside worker

### 24.2 Environment variables (minimum)
- `DATABASE_URL`
- `REDIS_URL`
- `JWT_SECRET`
- `STORAGE_BUCKET_URL` + credentials
- `PROVIDER_ROUTER_API_KEY`
- `OPENAI_API_KEY` (fallback)
- `ENV=prod`

### 24.3 Migrations
- On deploy: run Alembic migrations at startup (or via one-off job)

### 24.4 Worker scaling
- Start 1 worker instance
- Scale workers horizontally if queue depth rises

---

## 25) Cost Model (COGS Framework, Not Fragile Numbers)

COGS is dominated by observation calls and embeddings. Keep the model formula-based and measured.

### 25.1 Definitions
- `Q`: total questions per snapshot (universal + site-derived + adaptive + custom)
- `S`: number of sites in a run (your site + competitors)
- `R`: runs per month (weekly=4, monthly=1)
- `C_obs`: average cost per observed call (measured per provider/model)
- `C_embed`: average cost per embedding batch (measured)
- `C_fixed`: infra fixed costs (db, redis, storage)

### 25.2 Monitoring cost per month
`COGS_month ≈ (Q * S * R * C_obs) + (C_embed * R) + allocation(C_fixed)`

### 25.3 Margin safety rails
- Hard caps on competitors and custom questions by plan
- Use router provider to route cheap models when possible
- Cache and reuse embeddings unless content hash changes

---

## 26) Updated Implementation Checklist (Final)

**Core simulated engine**
- [ ] Crawl bounds and exclusions
- [ ] Render delta rule
- [ ] Extraction and dedup by hash
- [ ] Semantic chunking
- [ ] Retrieval: hybrid + dedup + diversity
- [ ] Robustness bands
- [ ] Question suite: 15 universal + deterministic 5 site-derived + optional adaptive + 3–5 custom
- [ ] Scoring with Show the Math + per-question contributions
- [ ] Fix generator with Clarity Scaffolds
- [ ] Fix Impact Estimator: Tier C + Tier B + affected-question targeting

**Observed engine + benchmark**
- [ ] Provider interface + router default + direct fallback
- [ ] Reality Snapshot
- [ ] Competitor benchmark and win/loss table
- [ ] Divergence protocol surfaced in report

**Monitoring**
- [ ] Weekly snapshots
- [ ] Monthly free snapshot after Starter
- [ ] Trend storage
- [ ] Alerts

---

*End of document.*
