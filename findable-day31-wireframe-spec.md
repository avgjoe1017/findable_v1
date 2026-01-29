# Findable Score Analyzer — Day 31 Wireframe Spec (Scope-Locked)
Version: v1.0 (Day 31 target)  
Audience: AI programmer implementing MVP UI + bindings  
Principle: Consistent, deterministic experience. No ad hoc pages, no hidden “magic.”

---

## 0) Day 31 Scope Lock

### 0.1 In Scope (must ship by Day 31)
1. **Auth**
   - Login
   - Register
   - Logout
2. **Sites**
   - Create a site (domain)
   - Add **1 competitor** (required for Starter)
   - Optional business model override (dropdown)
3. **Question suite**
   - Generate: **15 Universal + 5 Site-derived**
   - Optional: add up to **5 custom questions**
   - Deterministic: same site content → same derived questions
4. **Run Starter Audit**
   - Run pipeline: crawl → extract → chunk/index → simulate (3 budgets) → observe (routed provider) → benchmark → report
   - Progress screen with stepper and counts
5. **Report page (primary product surface)**
   - Score bands + “Show the Math”
   - Competitive benchmark near top
   - Fix plan with **Tier C impact ranges** and **Clarity Scaffolds**
   - Per-question table (simulation + observation signals)
   - Divergence banner (when triggered)
   - Monitoring section (Starter includes 4 weekly snapshots + monthly free after)
6. **Snapshots list (per site)**
   - Simple table of snapshots and links to snapshot reports
7. **Basic “Notices” (minimal alerts replacement)**
   - Surface up to 3 notices on Dashboard and Site detail pages (no full alerts system UI)
8. **Deployment readiness**
   - UI runs against versioned API
   - Report rendering requires **only report JSON** (plus optional “current status” strip)

### 0.2 Out of Scope for Day 31 (explicitly NOT shipping)
1. Full **Alerts** page + alert management UI
2. Tier B “Run exact impact test” **UI flow** (on-demand compute button)
3. Agency white-label UI and multi-site management UI
4. Billing/Stripe UI (plans may exist as flags/caps only)
5. PDF export UI (HTML report view is sufficient)
6. Advanced semantic contradiction detection UI (only high-confidence conflicts in report)
7. Deep adaptive question suites beyond the capped structure

### 0.3 MVP Acceptance Criteria (Day 31 demo-ready)
A real user can:
- Create an account → add a site + competitor → generate questions → run audit → view report
- Understand “why the score is what it is” from **Show the Math**
- See “you vs competitor” within the first scroll of the report
- Copy at least one **Clarity Scaffold** and know where it belongs
- See monitoring expectations **before** running the audit and again in the report
- View snapshot history for the site

---

## 1) UX Rules (Day 31)
- **One primary CTA per page.** Secondary actions are links.
- **Show the Math is always adjacent to scores.** Never a black box.
- **Benchmark is never buried.** Competitor is required for Starter and visible near top.
- **Fix cards follow: Why → Where → Scaffold → Impact.**
- **Monitoring rhythm is visible early.** Next snapshot date appears on Site and Report.
- **Determinism:** Derived questions are stable; report is immutable; comparisons are explicit.

---

## 2) Global Layout

### 2.1 App Chrome
- Left sidebar (fixed)
- Top bar (H1 + optional actions)
- Main content (max width 1100–1200px)

### 2.2 Sidebar Navigation (Day 31)
1. Dashboard
2. Sites
3. Snapshots
4. Account

> Note: No “Alerts” tab in Day 31. Replace with “Notices” summaries where relevant.

### 2.3 Shared Components

#### A) Section Card
- Title (H2)
- Optional subtitle
- Body
- Optional footer actions

#### B) Status Badge
- States: `Queued`, `Running`, `Complete`, `Failed`
- Monitoring: `Weekly`, `Monthly`

#### C) Empty State
- Title
- One-sentence explanation
- One CTA

#### D) Error Banner
- Title: “Something went wrong.”
- One-line message
- Expand “Details” for raw error

#### E) “Notices” Mini-Panel (Day 31)
- Shows up to 3 items, newest first
- Each notice: title + 1-line detail + link

---

## 3) Routes (Day 31)
- `/login`
- `/register`
- `/dashboard`
- `/sites`
- `/sites/new`
- `/sites/{site_id}` (site overview + run)
- `/sites/{site_id}/questions`
- `/sites/{site_id}/run/{run_id}` (progress)
- `/reports/{report_id}` (primary product page)
- `/sites/{site_id}/snapshots`
- `/account`

---

## 4) API Binding Conventions (UI)
- All API routes are versioned: `/v1/...`
- UI never computes score math; it renders server output.
- Report page must render from **report JSON** only.
- Optional live strip may call a single “latest snapshot” endpoint.

---

# 5) Auth Pages

## 5.1 Login — `/login`

### Components
- Card: “Sign in”
  - Email input
  - Password input
  - Primary button: **Sign in**
  - Link: “Create an account”

### Copy (exact)
- H1: “Sign in”
- Helper: “Use your email and password to access your reports.”

### Data bindings
- Submit: `POST /v1/auth/login`
- Success → `/dashboard`
- Failure → Error banner

---

## 5.2 Register — `/register`

### Components
- Card: “Create account”
  - Email
  - Password
  - Primary button: **Create account**
  - Link: “Already have an account? Sign in.”

### Data bindings
- Submit: `POST /v1/auth/register`
- Success → `/dashboard` (or `/login`)

---

# 6) Dashboard

## 6.1 Dashboard — `/dashboard`
**Goal:** Show value immediately: last score, observed performance, next snapshot.

### Layout
- Row 1: 3 summary tiles
- Row 2: Sites table
- Row 3: Notices mini-panel

### Components + Copy

#### A) Summary Tiles
1. “Sites”
   - Value: count of sites
2. “Latest Findable Score (Typical)”
   - Value: latest report `score.bands.typical`
   - Subtext: “Last run: {date}”
3. “Observed Mention Rate”
   - Value: latest `observation.you.mention_rate`
   - Subtext: “Competitor: {competitor_rate}”

#### B) Sites Table
Columns:
- Site (domain)
- Latest score (Typical)
- Observed mention rate (you)
- Observed mention rate (competitor)
- Next snapshot date
- Status
- Action: **View**

Empty state:
- Title: “Run your first audit”
- Text: “Add your site and one competitor to generate a Findable Score and proof.”
- CTA: **Add a site**

#### C) Notices (Day 31)
- Title: “Notices”
- Show up to 3 items (if any)
- Link: “View site” for relevant notice

### Data bindings
- Sites list: `GET /v1/sites`
- For each site: include or derive:
  - `latest_report.summary` (score + mention rates)
  - `monitoring.next_snapshot_at`
  - `status`
- Notices:
  - Prefer: `GET /v1/sites` includes `notices_preview[]`
  - Or fallback: `GET /v1/notices?limit=3`

---

# 7) Sites

## 7.1 Sites List — `/sites`
**Goal:** Manage sites and start runs.

### Components
- H1: “Sites”
- Primary: **Add site**
- Table (same as dashboard, with “Run audit” secondary action per site)

### Data bindings
- `GET /v1/sites`

---

## 7.2 Add Site Wizard — `/sites/new`
**Goal:** Guided setup with clear competitor guidance and monitoring expectations.

### Wizard steps
1. Site
2. Questions
3. Run

---

### Step 1: Site — “Add your site”
#### Components
1. Input: “Your domain”
   - Placeholder: `example.com`
   - Help: “No protocol needed. We’ll crawl a bounded set of pages.”
2. Input: “Competitor domain (required)”
   - Placeholder: `competitor.com`
   - Help (exact): “Pick someone you actually compete with in the same market. Avoid the biggest national brand unless you truly compete with them.”
   - Expandable “Not sure?” helper:
     - “Choose a peer competitor: similar size, similar service area, similar offering.”
3. Toggle: “Advanced settings” (optional)
   - Max pages (default 250)
   - Crawl depth (default 3)
4. Business model selector (auto + override)
   - Line: “Detected: {model} (confidence {pct})”
   - Dropdown list + “Unknown”
   - Help: “You can override detection at any time.”

#### Buttons
- Primary: **Next: Generate questions**
- Secondary: “Cancel”

#### Data binding
- Create site: `POST /v1/sites`
  - `{ domain, competitor_domains:[...], settings, business_model_override? }`
- On success: route to `/sites/{site_id}/questions`

---

## 7.3 Questions — `/sites/{site_id}/questions`
**Goal:** Question suite feels credible, deliberate, and bounded.

### Layout
- Section: Question suite
- Section: Custom questions
- Footer: navigation controls

### Components + Copy

#### A) Question suite card
- Title: “Question suite (20 questions)”
- Credibility line (exact):
  - “This suite covers the most common ways people ask AI to evaluate a business: identity, differentiation, pricing, how it works, where you operate, trust, and policies.”
  - “We cap it to keep results repeatable (so you can compare before/after) and costs predictable.”
  - “Add custom questions for your business-specific edge.”

Accordion groups:
1. “Universal (15)”
2. “Derived from your site (5)”
   - Each shows a small chip: `FAQ`, `Nav`, `Policy`, `Homepage claim`

Derived explainer (exact):
- “Derived questions are generated deterministically for repeatable monitoring.”

#### B) Custom questions card
- Title: “Add custom questions (optional)”
- Helper: “Add up to 5 money questions you want AI to answer about you.”
- Input: textarea + “Add”
- List with remove icon
- Counter: “{n}/5”

#### Footer buttons
- Secondary: “Back”
- Primary: **Next: Run audit**

### Data bindings
- Generate suite: `POST /v1/sites/{site_id}/questions/generate`
  - Body: `{ custom_questions: [] }`
  - Response:
    - `question_set_id`
    - `questions.universal[]`
    - `questions.site_derived[]` + `source_type`
    - `questions.custom[]`
- Save `question_set_id` to site or run payload

---

## 7.4 Site Overview + Run — `/sites/{site_id}`
**Goal:** One-click run with expectations set before they press the button.

### Components

#### A) Site header
- H1: `{domain}`
- Sub: “Competitor: {competitor_domain}”
- Badges: monitoring cadence + status

#### B) Notices panel (Day 31)
- Title: “Notices”
- Up to 3 items

#### C) “Run Starter Audit” card
Bullets (exact):
- “Simulated Findable Score (Conservative / Typical / Generous)”
- “Observed reality snapshot (automated)”
- “Competitor benchmark (included)”
- “Fix plan with impact estimates + Clarity Scaffolds”
- Monitoring expectations (exact):
  - “Includes 4 weekly snapshots. After that, monthly snapshots continue for free. Weekly cadence and notices are available on Professional.”

Buttons:
- Primary: **Run Starter Audit**
- Secondary link: “Edit questions”

#### D) “Question set” summary
- “20 questions (15 universal + 5 derived)”
- “Custom questions: {n}”
- Link: “View questions”

### Data bindings
- Site detail: `GET /v1/sites/{site_id}`
- Run creation: `POST /v1/sites/{site_id}/runs`
  - Body:
    - `run_type: "starter_audit"`
    - `question_set_id`
    - `include_observation: true`
    - `include_benchmark: true`
    - `bands: ["conservative","typical","generous"]`
- Response returns `{ run_id }`
- Route to `/sites/{site_id}/run/{run_id}`

---

# 8) Run Progress

## 8.1 Progress — `/sites/{site_id}/run/{run_id}`
**Goal:** Deterministic progress UI for long jobs.

### Components

#### A) Run summary card
- Title: “Audit in progress”
- Sub: “Run ID: {run_id}”
- Badges: status
- “Site: {domain}”
- “Competitor: {competitor_domain}”

#### B) Stepper (fixed order)
1. Crawling pages
2. Extracting content
3. Chunking + indexing
4. Running simulation (3 budgets)
5. Running observation (you + competitor)
6. Assembling report

Each step shows:
- status icon
- count: “{n} pages crawled”, “{m} chunks indexed”
- elapsed time (optional)

#### C) Footer actions
- If running: disabled button “Running…”
- If failed: **Retry run** + “View error details”
- If complete: **View report**

### Data bindings
- Poll: `GET /v1/runs/{run_id}`
  - includes step statuses + counts
  - when complete: includes `report_id`
- Route: `/reports/{report_id}`

---

# 9) Report Page (Primary Product Surface)

## 9.1 Report — `/reports/{report_id}`
**Goal:** In one scroll: score + why + proof + competitor + fixes.

### Rendering rule (Day 31)
- Report page renders from `GET /v1/reports/{report_id}` JSON only.
- Optional “Current status” strip may fetch latest snapshot summary.

---

## 9.2 Layout (fixed order)

### Section 1: Header Summary
**Components**
- H1: “Findable Report”
- Meta line: “Generated {generated_at}”
- “Site: {site.domain}”
- “Competitor: {benchmark.competitors[0].domain}”
- Badge: “Headline budget: {score.headline_band}”

**Optional: Current status strip (live)**
- Title: “Current status (latest snapshot)”
- Lines:
  - “Mention rate: {current_you_rate} (was {report_you_rate} at report time)”
  - “Competitor: {current_comp_rate}”
  - “Last snapshot: {current_snapshot_date}”
- Hide if no snapshots exist.

**Score pills**
- “Conservative {score.bands.conservative}”
- “Typical {score.bands.typical}”
- “Generous {score.bands.generous}”

**Verdict line (1–2 sentences)**
Template:
- “You answer {coverage.answered}/{coverage.total} core questions, but you lose citations on {top blockers}. Fixing the top {2} items is estimated to lift you by {impact range}.”

---

### Divergence Banner (conditional, above score pills)
**Trigger condition**
- `score.bands.typical >= 70` AND `observation.you.mention_rate <= 0.10`

**Banner copy (exact)**
- Title: “Simulation vs reality mismatch”
- Body: “Your site looks structurally sourceable, but observed results are lower than expected. This usually means authority, recency, or source-diversity behavior is suppressing you even when the content is correct.”
- CTA: “See why” (scroll to Divergence section)

---

### Section 2: Show the Math
**Card: “Show the Math”**
Rows:
- Coverage: `{answered}/{total} ({pct})` + points
- Extractability: points delta + driver list
- Citability: points delta + driver list
- Trust: points delta + driver list
- Conflicts: points delta + driver list
- Redundancy: points delta + driver list

Note:
- “Budget sensitivity: {score.budget_sensitivity.notes[0]}”

---

### Section 3: Competitive Benchmark (near top)
**Card: “Competitive benchmark”**
Top row:
- “Observed mention rate”
  - You: `{observation.you.mention_rate}`
  - Competitor: `{benchmark.competitors[0].mention_rate}`

Table: “Question wins and losses”
- Columns: Question | You | Competitor
- Rows: `benchmark.wins_losses[]`

List: “Key deltas”
- `benchmark.deltas[]`

---

### Section 4: Top Blockers
**Card: “Top blockers”**
- Show top 3–5 blocker cards

Blocker card fields:
- Title: `{blocker.title}`
- Severity badge
- “What it breaks” (1 line)
- Link: “View impacted questions” (filters questions table)

---

### Section 5: Fix Plan (ranked)
**Card: “Fix plan”**
Show top fixes (at least 5)

Each fix card includes:
1. Title: `{fix.title}`
2. “Why this matters”: `{fix.why}`
3. “Where to place it”: `{fix.target_url}` (or “Recommended location: {place}”)
4. **Impact estimate (Tier C only in Day 31 UI)**
   - “Estimated lift: +{lift_min} to +{lift_max} (Typical)”
   - “Estimated new score: {score_min}–{score_max}”
5. **Clarity Scaffold**
   - Collapsible text block
   - Label: “DRAFT (extract-first)”
   - Button: “Copy scaffold”
6. Optional: “Mark as done” (UI-only, local state)

> Day 31 note: No “Run exact impact test” button.

---

### Section 6: Per-question Results (truth table)
**Card: “Per-question results”**
Table columns:
- Question
- Simulation (headline band): Pass/Fail
- Points (+/−)
- Primary reason
- Evidence: “View”
- Observation: Mentioned? Linked?

Row expand reveals:
- Evidence excerpt(s) (top 1–2)
- Simulation trace summary
- Observed response excerpt (first ~300 chars)
- “Mapped fix” links (anchors to fix cards)

---

### Section 7: Divergence Protocol (expanded explanation)
Only show if divergence triggered.

**Card title:** “Why simulation and observation can diverge”
**Copy (exact)**
- “We treat observed results as the headline truth when they disagree.”
- “We use simulation to recommend fixes and to measure progress before/after changes.”
- “Common causes: authority preference, recency behavior, and source diversity constraints.”
- “If divergence persists, the product shifts toward observation-first reporting.”

---

### Section 8: Monitoring
**Card: “Monitoring”**
- “Starter includes 4 weekly snapshots.”
- “After that, monthly snapshots continue for free.”
- “Next snapshot: {monitoring.next_snapshot_at}”

Buttons:
- Primary: “View snapshots”
- Secondary: “Upgrade to weekly monitoring” (link placeholder if billing not live)

---

## 9.3 Report Data Bindings (JSON fields)
UI expects these in `GET /v1/reports/{report_id}`:

- `site.domain`
- `generated_at`
- `score.headline_band`
- `score.bands.conservative|typical|generous`
- `score.show_the_math` (subscores + drivers)
- `score.budget_sensitivity.notes[]`
- `observation.you.mention_rate`
- `observation.you.per_question[]` (question_id, mentioned, linked, excerpt)
- `benchmark.competitors[0].domain`
- `benchmark.competitors[0].mention_rate`
- `benchmark.wins_losses[]`
- `benchmark.deltas[]`
- `top_blockers[]`
- `fix_plan[]` (title, why, target_url/place, impact_tier_c, scaffold_text)
- `per_question_results[]` (question text, band pass/fail, points, reason, evidence)
- `monitoring.next_snapshot_at`

Optional live strip (separate call):
- `GET /v1/sites/{site_id}/snapshots?limit=1` → latest mention rate, date

---

# 10) Snapshots

## 10.1 Snapshots List — `/sites/{site_id}/snapshots`
**Goal:** Monitoring becomes visible and repeatable.

### Components
- H1: “Snapshots”
- Table:
  - Date
  - Mention rate (you)
  - Mention rate (competitor)
  - Score (Typical)
  - Notices count
  - Action: “View report”

Empty state:
- Title: “No snapshots yet”
- Text: “Your first snapshot will appear after your audit runs.”

### Data bindings
- `GET /v1/sites/{site_id}/snapshots`

---

# 11) Account

## 11.1 Account — `/account`
**Goal:** Simple plan visibility and session controls.

### Components
- Card: “Account”
  - Email: `{user.email}`
  - Button: “Log out”
- Card: “Plan”
  - “Current plan: {plan_name}”
  - “Limits: competitors {n}, custom questions {n}”
- Card: “Observation”
  - “Provider: Auto (routed)”

### Data bindings
- `GET /v1/auth/me`

---

# 12) Copy Library (exact strings)

### CTAs
- “Add a site”
- “Generate questions”
- “Run Starter Audit”
- “View report”
- “View snapshots”
- “Copy scaffold”
- “Retry run”

### Monitoring expectations (wizard + report)
- “Includes 4 weekly snapshots. After that, monthly snapshots continue for free. Weekly cadence and notices are available on Professional.”

### Competitor helper
- “Pick someone you actually compete with in the same market. Avoid the biggest national brand unless you truly compete with them.”

### Derived determinism
- “Derived questions are generated deterministically for repeatable monitoring.”

---

# 13) Day 31 Implementation Notes (for the programmer)
1. **Keep the report immutable.** The report page should not change when new snapshots arrive.
2. **Optional “Current status” strip is additive.** It can ship later without altering report JSON.
3. **Notices replace alerts for Day 31.** Do not build a full alerts UI; surface up to 3 items where relevant.
4. **No Tier B UI.** Show Tier C impact ranges only.
5. **All report sections have fixed ordering.** No rearranging per site type in Day 31.

---

## Appendix A: Page Build Checklist (Day 31)
- [ ] Auth pages functional
- [ ] Site wizard (site → questions → run) complete
- [ ] Progress stepper reflects server state
- [ ] Report sections render with correct bindings
- [ ] Divergence banner triggers correctly
- [ ] Snapshots list renders
- [ ] Notices panel renders (up to 3)
- [ ] No Alerts page exists in nav
- [ ] No Tier B UI exists
