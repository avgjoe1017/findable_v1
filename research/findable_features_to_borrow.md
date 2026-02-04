# Competitor Tool Analysis: Features to Borrow for Findable

**Date:** February 1, 2026

---

## What I Tested/Researched

### Otterly AI Free Tools
1. **AI Crawler Simulation** — Tests if a website blocks AI crawlers by sending actual HTTP requests with specific user-agent strings (GPTBot, ClaudeBot, PerplexityBot, etc.)
2. **GEO Content Check** — Analyzes a URL for GEO compliance and optimization
3. **AI Keyword Research** — Turns keywords into conversational AI prompts
4. **Query Fan Out** — Expands a seed query into related AI search prompts
5. **GEO Audit** — 25+ on-page factors with Domain and URL audit modes

### Rankscale AI Features
1. **AI Readiness Score** — Website audit that evaluates content, authority, technical structure
2. **Visibility Score** — Aggregates mention frequency, citation share, positional prominence
3. **Sentiment Analysis** — Radar charts showing positive/negative/neutral themes
4. **Citation Analysis** — Which domains AI cites, frequency, influential sources
5. **Side-by-side content comparison** — Original vs AI-optimized versions

### Goodie AI Features
1. **Optimization Hub** — Prioritized action steps, not just dashboards
2. **Citation Gap Analysis** — Shows which domains competitors get cited from but you don't
3. **AEO Content Writer** — Generates AI-optimized content
4. **Traffic & Attribution** — Connects AI visibility to actual conversions
5. **Topic Explorer** — Find high-intent topics based on AI prompts

---

## Features to Borrow (Prioritized)

### 🔴 HIGH PRIORITY — Add These First

#### 1. AI Crawler Access Check (from Otterly)
**What it does:** Tests if robots.txt blocks AI crawlers
**Why borrow it:**
- This is a BINARY gate — if blocked, nothing else matters
- Simple to implement
- High value signal users don't know to check
- We identified this as a gap in our methodology audit

**Implementation:**
```python
async def check_ai_crawler_access(domain: str) -> dict:
    """Test if site blocks AI crawlers."""
    crawlers = {
        "GPTBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.0",
        "ClaudeBot": "ClaudeBot/1.0",
        "PerplexityBot": "PerplexityBot/1.0",
        "Google-Extended": "Google-Extended",
    }

    results = {}
    for name, ua in crawlers.items():
        # Fetch robots.txt and check rules
        # Also try actual HTTP request with UA
        results[name] = {
            "robots_txt_allows": check_robots_txt(domain, ua),
            "http_accessible": test_http_request(domain, ua),
        }

    return results
```

**Display:** Traffic light system (🟢 Allowed / 🟡 Partial / 🔴 Blocked)

---

#### 2. AI Readiness Score Breakdown (from Rankscale)
**What it does:** Single score with component breakdown
**Why borrow it:**
- Rankscale's $20/mo plan includes this — it's a market expectation
- Perfect for our "show the math" philosophy
- Creates a comparable metric to track over time

**Our advantage:** We can make ours BETTER by including retrieval simulation (which they don't have)

**Implementation:**
```
AI Readiness Score: 67/100

Breakdown:
├── Technical Access: 85/100 ✅
│   ├── robots.txt: All AI crawlers allowed
│   ├── TTFB: 342ms (Good)
│   └── llms.txt: Not found
├── Content Structure: 72/100 ⚠️
│   ├── Heading hierarchy: Valid
│   ├── Answer-first: 4/10 pages
│   └── FAQ sections: 2 found
├── Schema Richness: 45/100 ⚠️
│   ├── FAQPage: Missing
│   ├── Article: Found (no author)
│   └── Organization: Found
├── Authority Signals: 58/100 ⚠️
│   ├── Author attribution: 30%
│   ├── Citations: 2.1/page avg
│   └── Freshness: 8 months old
└── Retrieval Simulation: 75/100 ✅  ← OUR UNIQUE COMPONENT
    ├── Questions answered: 12/15
    ├── Avg relevance: 0.72
    └── Signal coverage: 68%
```

---

#### 3. Sentiment Analysis (from Rankscale)
**What it does:** Analyzes whether content is perceived positively/negatively
**Why borrow it:**
- Adds another dimension to our analysis
- Users care about HOW they're described, not just IF
- Can be derived from our existing retrieval results

**Implementation:**
```python
def analyze_chunk_sentiment(chunks: List[Chunk]) -> SentimentResult:
    """Analyze sentiment of retrieved content."""
    # Use simple keyword matching or LLM classification
    positive_markers = ["best", "leading", "trusted", "recommended", "excellent"]
    negative_markers = ["avoid", "problem", "issue", "expensive", "limited"]

    # Score each chunk
    for chunk in chunks:
        chunk.sentiment = classify_sentiment(chunk.text)

    return SentimentResult(
        overall=aggregate_sentiment(chunks),
        positive_themes=extract_themes(positive_chunks),
        negative_themes=extract_themes(negative_chunks),
    )
```

---

#### 4. Citation Gap Analysis (from Goodie)
**What it does:** Shows domains that cite competitors but not you
**Why borrow it:**
- Extremely actionable
- Creates a "hit list" of sites to target for mentions
- Adds competitive intelligence dimension

**Implementation:**
In competitor benchmarking, track:
- Which pages/domains would AI cite for similar queries?
- Where do competitors have coverage that user doesn't?
- What content types are competitors using that user lacks?

---

### 🟡 MEDIUM PRIORITY — Add in V2

#### 5. Action Center / Optimization Hub (from Goodie/AthenaHQ)
**What it does:** Prioritized list of specific actions to take
**Why borrow it:**
- We already have "fixes" — just need better presentation
- Competitors call this their differentiator
- "Insights to action" is a key selling point

**Enhancement for Findable:**
```
📋 Action Center (12 items)

🔴 CRITICAL (Do this week)
1. Add GPTBot to robots.txt Allow list
   Impact: +15 points | Effort: 5 min | [Copy code]

2. Add FAQPage schema to /pricing
   Impact: +8 points | Effort: 30 min | [View template]

🟡 HIGH PRIORITY (Do this month)
3. Move answer to first paragraph on /services
   Current: Answer at paragraph 4
   Impact: +5 points | Effort: 15 min | [See example]

4. Add author credentials to blog posts
   Current: 3/12 posts have author
   Impact: +7 points | Effort: 1 hour | [See template]

🟢 OPTIMIZATION (When you have time)
5. Update dateModified on /about (last: 18 months ago)
6. Add 3 more FAQ questions to /features
...
```

---

#### 6. Query Fan Out (from Otterly)
**What it does:** Expands a seed keyword into conversational AI prompts
**Why borrow it:**
- Helps users understand what questions to optimize for
- We generate questions — we could also show variations
- Useful for content planning

**Example:**
```
Seed: "email marketing software"

Fan Out:
├── What is the best email marketing software for small business?
├── How much does email marketing software cost?
├── What features should I look for in email marketing software?
├── Is Mailchimp better than Constant Contact?
├── How do I choose email marketing software for e-commerce?
└── What's the easiest email marketing software to use?
```

---

#### 7. Content Comparison (from Rankscale)
**What it does:** Side-by-side view of original vs optimized content
**Why borrow it:**
- Makes fixes concrete and visual
- Users can see exactly what to change
- Increases fix adoption rate

**Implementation:**
```
Page: /services

┌─────────────────────────────┬─────────────────────────────┐
│ CURRENT                     │ OPTIMIZED                   │
├─────────────────────────────┼─────────────────────────────┤
│ <h1>Our Services</h1>       │ <h1>Marketing Automation    │
│                             │ Services for B2B SaaS</h1>  │
│ <p>We offer a wide range    │                             │
│ of marketing services to    │ <p>Our marketing automation │
│ help your business grow...  │ services help B2B SaaS      │
│                             │ companies increase lead     │
│ [Answer buried 400 words    │ conversion by 35% through   │
│ down the page]              │ personalized campaigns.</p> │
│                             │                             │
│                             │ <h2>What is Marketing       │
│                             │ Automation?</h2>            │
│                             │ <p>Marketing automation is  │
│                             │ software that...</p>        │
└─────────────────────────────┴─────────────────────────────┘

Changes: +Entity specificity, +Answer-first, +FAQ format
Expected impact: +12 points
```

---

### 🟢 LOWER PRIORITY — Nice to Have

#### 8. Geographic Query Simulation (from Rankscale/Otterly)
**What it does:** Simulates AI queries from different locations
**Why borrow it:**
- Some businesses need local optimization
- AI responses vary by region
- Could be a premium feature

#### 9. Topic Explorer (from Goodie)
**What it does:** Finds high-intent topics based on AI prompts
**Why borrow it:**
- Content planning tool
- Helps users know what to write
- Could use our question generation as basis

#### 10. Share of Voice Tracking (from multiple)
**What it does:** % of category mentions vs competitors
**Why borrow it:**
- Standard metric in GEO space
- We have competitor benchmarking — this is the roll-up

---

## What NOT to Borrow

### ❌ Real-time AI mention monitoring
**Why skip:**
- This is what everyone else does
- We're differentiated by testing WHY, not tracking WHEN
- Would require constant API calls to AI platforms
- High cost, commodity feature

### ❌ AI traffic attribution
**Why skip:**
- Requires integration with user's analytics
- Complex to implement
- Not core to our value prop
- Goodie/Profound already own this

### ❌ Content generation
**Why skip:**
- Commodity feature (many AI writing tools)
- Not our core competency
- Would distract from audit/fix focus

---

## Competitive Positioning After Updates

### Current State
| | Competitors | Findable |
|---|---|---|
| AI mention tracking | ✅ | ❌ |
| Retrieval simulation | ❌ | ✅ |
| Technical audit | ✅ | ❌ |
| Action prioritization | ✅ | ⚠️ |
| Show the math | ❌ | ✅ |

### After Borrowing
| | Competitors | Findable |
|---|---|---|
| AI mention tracking | ✅ | ❌ (intentionally) |
| Retrieval simulation | ❌ | ✅ (unique) |
| Technical audit | ✅ | ✅ (with robots.txt, TTFB) |
| Schema analysis | ⚠️ | ✅ (deeper) |
| Action prioritization | ✅ | ✅ (with impact estimates) |
| Show the math | ❌ | ✅ (unique) |
| Sentiment analysis | ✅ | ✅ |
| Citation gaps | ⚠️ | ✅ |

---

## Implementation Roadmap

### Week 1-2: Technical Checks
- [ ] AI crawler access check (robots.txt + HTTP test)
- [ ] TTFB measurement
- [ ] llms.txt detection
- [ ] Display as "Technical Readiness" component

### Week 3-4: Enhanced Fixes
- [ ] Action Center UI (prioritized list)
- [ ] Impact estimates on all fixes
- [ ] Copy-paste code snippets for technical fixes
- [ ] "Before/After" content comparison

### Week 5-6: Schema & Sentiment
- [ ] Schema scoring (not just detection)
- [ ] Sentiment analysis of retrieved content
- [ ] Authority signals detection (author, citations, freshness)

### Week 7-8: Competitive Features
- [ ] Citation gap analysis in competitor benchmarking
- [ ] Share of voice calculation
- [ ] Query fan-out tool (optional)

---

## Summary

**Steal these ideas:**
1. ✅ AI Crawler Access Check — Binary gate, high value
2. ✅ AI Readiness Score Breakdown — Market expectation
3. ✅ Sentiment Analysis — Adds dimension to analysis
4. ✅ Citation Gap Analysis — Extremely actionable
5. ✅ Action Center UI — Better fix presentation
6. ⚠️ Content Comparison — Visual before/after
7. ⚠️ Query Fan Out — Content planning helper

**Keep our moat:**
- Retrieval simulation (no one else does this)
- "Show the math" transparency (everyone else is black box)
- Impact estimates on fixes (makes ROI clear)

**The pitch evolves from:**
> "We test if AI can cite you"

**To:**
> "We diagnose your complete AI sourceability — technical access, content structure, authority signals, and retrieval performance — then give you prioritized fixes with impact estimates"

This is a complete GEO diagnostic, not just monitoring.
