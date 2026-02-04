# Findable Score v2: Master Implementation Plan

**Created:** February 1, 2026
**Status:** In Progress
**Goal:** Expand from "Can AI retrieve you?" to "Can AI find, access, understand, trust, and cite you?"

---

## Strategic Summary

Current Findable Score measures ~30% of AI sourceability factors. v2 expands to cover all 6 pillars that determine whether AI systems will cite a website.

**New pitch:**
> "We diagnose your complete AI sourceability—technical access, content structure, authority signals, and retrieval performance—then give you prioritized fixes with impact estimates."

---

## New Scoring Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    FINDABLE SCORE v2 (100 pts)                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  TECHNICAL   │  │  STRUCTURE   │  │   SCHEMA     │          │
│  │  READINESS   │  │   QUALITY    │  │   RICHNESS   │          │
│  │  15 points   │  │  20 points   │  │  15 points   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  • robots.txt     • Heading         • FAQPage                   │
│  • TTFB           • Answer-first    • Article                   │
│  • llms.txt       • FAQ sections    • HowTo                     │
│  • JS dependency  • Internal links  • dateModified              │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  AUTHORITY   │  │  RETRIEVAL   │  │   ANSWER     │          │
│  │  SIGNALS     │  │  SIMULATION  │  │  COVERAGE    │          │
│  │  15 points   │  │  25 points   │  │  10 points   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  • Author byline  • Vector search   • Questions answered        │
│  • Credentials    • BM25 search     • Partial answers           │
│  • Citations      • Relevance       • Category coverage         │
│  • Freshness                                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Technical Readiness (Weeks 1-2) ✅ COMPLETE
**Goal:** Answer "Can AI even access your site?"

| Component | Points | File | Status |
|-----------|--------|------|--------|
| robots.txt AI access | 5 | `worker/crawler/robots_ai.py` | ✅ DONE |
| TTFB measurement | 4 | `worker/crawler/performance.py` | ✅ DONE |
| llms.txt detection | 3 | `worker/crawler/llms_txt.py` | ✅ DONE |
| JS dependency check | 2 | `worker/extraction/js_detection.py` | ✅ DONE |
| HTTPS enabled | 1 | (inline check in technical.py) | ✅ DONE |

**Deliverables:**
- [x] `worker/crawler/robots_ai.py` - AI crawler whitelist check
- [x] `worker/crawler/performance.py` - TTFB measurement
- [x] `worker/crawler/llms_txt.py` - llms.txt detection and validation
- [x] `worker/extraction/js_detection.py` - JS dependency detection
- [x] `worker/scoring/technical.py` - Technical readiness score calculator
- [x] `worker/tasks/technical_check.py` - Runner combining all checks
- [x] Updated `worker/tasks/audit.py` - Integrated technical checks (Step 0)

---

### Phase 2: Structure Quality (Weeks 3-4) ✅ COMPLETE
**Goal:** Answer "Is your content extractable?"

| Component | Points | Implementation | Status |
|-----------|--------|----------------|--------|
| Heading hierarchy valid | 5 | Validate H1→H2→H3 flow | ✅ DONE |
| Answer-first detection | 5 | Check if answer in first 500 chars | ✅ DONE |
| FAQ sections present | 4 | Count Q&A formatted sections | ✅ DONE |
| Internal link density | 3 | 5-10 links per page target | ✅ DONE |
| Extractable formats | 3 | Tables, lists prevalence | ✅ DONE |

**Deliverables:**
- [x] `worker/extraction/headings.py` - Heading hierarchy validation
- [x] `worker/extraction/links.py` - Internal link analysis
- [x] `worker/extraction/structure.py` - Combined structure analysis
- [x] `worker/scoring/structure.py` - Structure score calculator
- [x] `worker/tasks/structure_check.py` - Structure check task runner
- [x] `tests/unit/test_structure_checks.py` - 25 unit tests
- [x] Updated `worker/reports/contract.py` - Added StructureSection
- [x] Updated `worker/reports/assembler.py` - Builds structure section
- [x] Updated `worker/tasks/audit.py` - Integrated structure checks

---

### Phase 3: Schema Richness (Weeks 5-6) ✅ COMPLETE
**Goal:** Answer "Is your content machine-readable?"

| Component | Points | Implementation | Status |
|-----------|--------|----------------|--------|
| FAQPage schema | 4 | 35-40% citation lift | ✅ DONE |
| Article schema w/ author | 3 | Author, dates required | ✅ DONE |
| dateModified present | 3 | Freshness signal | ✅ DONE |
| Organization schema | 2 | Entity recognition | ✅ DONE |
| HowTo schema | 2 | For procedural content | ✅ DONE |
| Schema validation | 1 | Zero errors | ✅ DONE |

**Deliverables:**
- [x] `worker/extraction/schema.py` - JSON-LD & Microdata extraction, validation
- [x] `worker/scoring/schema.py` - Schema richness calculator (6 weighted components)
- [x] `worker/tasks/schema_check.py` - Task runner with aggregation & fix generation
- [x] `tests/unit/test_schema_checks.py` - 26 unit tests
- [x] Updated `worker/reports/contract.py` - Added SchemaSection
- [x] Updated `worker/reports/assembler.py` - Builds schema section
- [x] Updated `worker/tasks/audit.py` - Integrated schema checks (Step 2.85)

---

### Phase 4: Authority Signals (Weeks 7-8) ✅ COMPLETE
**Goal:** Answer "Does AI trust your content?"

| Component | Points | Implementation | Status |
|-----------|--------|----------------|--------|
| Author attribution | 4 | Byline detection | ✅ DONE |
| Author credentials | 3 | Bio, title, expertise | ✅ DONE |
| Primary source citations | 3 | Links to research/data | ✅ DONE |
| Content freshness | 3 | Visible dates + freshness | ✅ DONE |
| Original data markers | 2 | "Our research..." patterns | ✅ DONE |

**Deliverables:**
- [x] `worker/extraction/authority.py` - E-E-A-T signal extraction (author, credentials, citations, dates, original data)
- [x] `worker/scoring/authority.py` - Authority score calculator (5 weighted components)
- [x] `worker/tasks/authority_check.py` - Task runner with aggregation & fix generation
- [x] `tests/unit/test_authority_checks.py` - 28 unit tests
- [x] Updated `worker/reports/contract.py` - Added AuthoritySection
- [x] Updated `worker/reports/assembler.py` - Builds authority section
- [x] Updated `worker/tasks/audit.py` - Integrated authority checks (Step 2.9)

---

### Phase 5: Integration & UI (Weeks 9-10) ✅ COMPLETE
**Goal:** Connect new scoring + improve fix presentation

**Deliverables:**
- [x] `worker/scoring/calculator_v2.py` - 6-pillar unified score calculator with letter grades
- [x] `worker/fixes/generator_v2.py` - Unified fix generator with Action Center
- [x] Update `worker/reports/contract.py` - ScoreSectionV2, ActionCenterSection dataclasses
- [x] Update `worker/reports/assembler.py` - v2 score and action center builders
- [x] Update `worker/scoring/__init__.py` - v2 exports
- [x] Update `worker/fixes/__init__.py` - v2 exports
- [x] `tests/unit/test_calculator_v2.py` - 36 unit tests
- [x] `tests/unit/test_generator_v2.py` - 28 unit tests

**Implementation Notes:**
- FindableScoreV2 calculates unified score from all 6 pillars (Technical 15%, Structure 20%, Schema 15%, Authority 15%, Retrieval 25%, Coverage 10%)
- Letter grades A+ through F with thresholds and descriptions
- ActionCenter organizes fixes into quick_wins (low effort + high impact), high_priority (critical), and by_category
- Helper methods normalize different fix formats from pillar generators
- Used lazy imports to avoid circular dependencies

---

### Phase 6: Testing & Polish (Weeks 11-12) ✅ COMPLETE
**Goal:** Validate and calibrate

**Deliverables:**
- [x] `tests/unit/test_v2_calibration.py` - 14 calibration tests
- [x] v1→v2 migration formula (retrieval=v1_score, coverage=v1_coverage)
- [x] API schema updates (`api/schemas/run.py`) - ScoreV2Summary, ActionCenterSummary
- [x] Documentation updates (PROGRESS.md, IMPLEMENTATION_PLAN.md)

**Calibration Tests:**
- Site archetype tests (excellent enterprise, poor JS SPA, average blog)
- Score differentiation validation (30+ point spread between archetypes)
- Grade assignment validation (A+ for excellent, D/F for poor)
- Fix generation validation
- v1→v2 migration formula tests
- Pillar weight balance tests (sum to 100, no single >30%)

**v1→v2 Migration Formula:**
- Retrieval pillar (25pts) = v1 total_score × 0.25
- Coverage pillar (10pts) = v1 coverage_percentage × 0.10
- New pillars (65pts) = 0 if not analyzed yet
- Users upgrading from v1 will see lower scores until new pillars are analyzed

---

## New Fix Categories

### Technical Fixes (NEW)
```
- "Add GPTBot to robots.txt Allow list"
- "Reduce TTFB from {current}ms to <500ms"
- "Create llms.txt file at site root"
- "Implement server-side rendering for {pages}"
```

### Schema Fixes (NEW)
```
- "Add FAQPage schema to {page} (35-40% citation lift)"
- "Add Article schema with author credentials"
- "Add dateModified to schema (currently missing)"
- "Fix schema validation errors on {pages}"
```

### Structure Fixes (NEW)
```
- "Move answer to first paragraph (currently buried {n} words down)"
- "Fix heading hierarchy on {page} (skips H{n} to H{m})"
- "Add FAQ section with 3-5 common questions"
- "Increase internal link density from {current} to 5-10 per page"
```

### Authority Fixes (NEW)
```
- "Add author byline with credentials to articles"
- "Add publication/update date visibly on page"
- "Link to primary sources for statistics"
- "Update stale content (last modified: {date})"
```

### Content Fixes (EXISTING)
```
- "Add content about {topic} (gap identified)"
- "Expand {section} to address {question}"
- "Add specific data points for {claim}"
```

---

## File Structure

### New Files to Create
```
worker/crawler/robots_ai.py          # Phase 1
worker/crawler/performance.py        # Phase 1
worker/crawler/llms_txt.py           # Phase 1
worker/extraction/js_detection.py    # Phase 1
worker/scoring/technical.py          # Phase 1
worker/extraction/structure.py       # Phase 2
worker/extraction/headings.py        # Phase 2
worker/extraction/links.py           # Phase 2
worker/scoring/structure.py          # Phase 2
worker/scoring/schema.py             # Phase 3
worker/extraction/authority.py       # Phase 4
worker/extraction/freshness.py       # Phase 4
worker/scoring/authority.py          # Phase 4
worker/scoring/calculator_v2.py      # Phase 5
worker/fixes/generator_v2.py         # Phase 5
```

### Files to Modify
```
worker/extraction/metadata.py        # Expand schema detection
worker/tasks/audit.py                # Add technical checks
worker/reports/contract.py           # v2 report structure
worker/reports/assembler.py          # Include new components
api/routers/runs.py                  # Return v2 structure
```

---

## Database Considerations

### New Fields for Run Model
```python
# Technical readiness results
technical_score: float
robots_txt_access: dict  # {crawler: allowed}
ttfb_ms: int
llms_txt_exists: bool
js_dependent: bool

# Structure quality results
structure_score: float
heading_hierarchy_valid: bool
answer_first_ratio: float
faq_count: int
internal_link_density: float

# Schema richness results
schema_score: float
schema_types_found: list[str]
schema_validation_errors: int
has_date_modified: bool

# Authority signals results
authority_score: float
author_attribution_ratio: float
citation_count: int
days_since_modified: int
```

---

## Success Metrics

1. **Fix adoption rate** — Are users implementing more fixes?
2. **Score delta after fixes** — Do scores improve when applied?
3. **Correlation with citations** — Does higher v2 = more AI mentions?
4. **Customer feedback** — Are new components useful?

---

## Competitive Positioning After v2

| Capability | Competitors | Findable v1 | Findable v2 |
|------------|-------------|-------------|-------------|
| AI mention tracking | ✅ | ❌ | ❌ (intentionally) |
| Retrieval simulation | ❌ | ✅ | ✅ (unique moat) |
| Technical crawlability | ✅ | ❌ | ✅ |
| Schema analysis | ⚠️ Basic | ⚠️ Detect | ✅ Score + validate |
| Structure scoring | ❌ | ⚠️ Partial | ✅ Full |
| E-E-A-T assessment | ❌ | ❌ | ✅ |
| Action prioritization | ✅ | ⚠️ List | ✅ Impact estimates |
| Show the math | ❌ | ✅ | ✅ (unique moat) |
| Citation gap analysis | ⚠️ | ❌ | ✅ |

---

## Features NOT to Build

| Feature | Why Skip |
|---------|----------|
| Real-time AI mention monitoring | Commodity, high cost, not differentiator |
| AI traffic attribution | Requires analytics integration |
| Content generation | Commodity (every AI writing tool) |
| Geographic query simulation | Low priority, complex |

---

## Quick Start (Phase 1)

```bash
# Start with technical readiness
# 1. Create robots_ai.py (AI crawler access check)
# 2. Create performance.py (TTFB measurement)
# 3. Create llms_txt.py (llms.txt detection)
# 4. Create js_detection.py (JS dependency check)
# 5. Create scoring/technical.py (combine into score)
# 6. Update audit.py to run technical checks
```
