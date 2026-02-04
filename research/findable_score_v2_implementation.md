# Findable Score v2: Implementation Roadmap

**Goal:** Expand from "Can AI retrieve you?" to "Can AI find, access, understand, trust, and cite you?"

---

## New Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    FINDABLE SCORE v2                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  TECHNICAL   │  │  STRUCTURE   │  │   SEMANTIC   │          │
│  │  READINESS   │  │   QUALITY    │  │   RICHNESS   │          │
│  │    (15%)     │  │    (20%)     │  │    (15%)     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         │                 │                 │                   │
│         ▼                 ▼                 ▼                   │
│  • robots.txt      • Heading hierarchy  • Schema types         │
│  • TTFB            • Answer-first       • Schema validity      │
│  • llms.txt        • FAQ sections       • Entity linking       │
│  • JS dependency   • Internal links     • Author schema        │
│  • HTTPS           • Tables/lists       • dateModified         │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  AUTHORITY   │  │ RETRIEVAL    │  │   ANSWER     │          │
│  │   SIGNALS    │  │ SIMULATION   │  │  COVERAGE    │          │
│  │    (15%)     │  │    (25%)     │  │    (10%)     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         │                 │                 │                   │
│         ▼                 ▼                 ▼                   │
│  • Author byline   • Vector search     • Questions answered    │
│  • Credentials     • BM25 search       • Partial answers       │
│  • Citations       • RRF fusion        • Unanswered            │
│  • Freshness       • Relevance scores  • Category coverage     │
│  • Original data   • Signal matching                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Technical Readiness (Week 1-2)

### New Checks to Add

#### 1.1 robots.txt AI Crawler Access

**File:** `worker/crawler/robots_ai.py` (new)

```python
AI_CRAWLERS = {
    "GPTBot": {"required": True, "weight": 30},
    "ChatGPT-User": {"required": True, "weight": 20},
    "ClaudeBot": {"required": True, "weight": 20},
    "PerplexityBot": {"required": True, "weight": 15},
    "Google-Extended": {"required": False, "weight": 10},
    "Bingbot": {"required": False, "weight": 5},
}

async def check_robots_txt_ai_access(domain: str) -> RobotsTxtResult:
    """
    Fetch robots.txt and check if AI crawlers are allowed.
    Returns per-crawler access status and overall score.
    """
    robots_url = f"https://{domain}/robots.txt"
    # ... fetch and parse

    results = {}
    score = 0
    max_score = sum(c["weight"] for c in AI_CRAWLERS.values())

    for crawler, config in AI_CRAWLERS.items():
        allowed = check_crawler_allowed(robots_content, crawler, "/")
        results[crawler] = allowed
        if allowed:
            score += config["weight"]

    return RobotsTxtResult(
        crawlers=results,
        score=score / max_score * 100,
        critical_blocked=[c for c, cfg in AI_CRAWLERS.items()
                         if cfg["required"] and not results[c]]
    )
```

#### 1.2 TTFB Measurement

**File:** `worker/crawler/performance.py` (new)

```python
async def measure_ttfb(url: str, timeout: float = 10.0) -> TTFBResult:
    """
    Measure Time to First Byte for a URL.
    Returns TTFB in milliseconds and score.
    """
    start = time.perf_counter()

    async with httpx.AsyncClient() as client:
        async with client.stream("GET", url, timeout=timeout) as response:
            first_byte_time = time.perf_counter()
            ttfb_ms = (first_byte_time - start) * 1000

    # Score based on research thresholds
    if ttfb_ms < 200:
        score = 100  # Excellent
    elif ttfb_ms < 500:
        score = 80   # Good
    elif ttfb_ms < 1000:
        score = 50   # Acceptable
    elif ttfb_ms < 1500:
        score = 25   # Poor
    else:
        score = 0    # Critical

    return TTFBResult(
        ttfb_ms=ttfb_ms,
        score=score,
        level="excellent" if score >= 80 else "good" if score >= 50 else "poor"
    )
```

#### 1.3 llms.txt Detection

**File:** `worker/crawler/llms_txt.py` (new)

```python
async def check_llms_txt(domain: str) -> LlmsTxtResult:
    """
    Check if llms.txt exists and is properly formatted.
    """
    url = f"https://{domain}/llms.txt"

    try:
        response = await fetch(url)
        if response.status_code == 200:
            content = response.text

            # Validate structure
            has_heading = content.strip().startswith("#")
            has_links = bool(re.findall(r'\[.+\]\(.+\)', content))
            has_description = ">" in content  # Blockquote

            quality_score = (
                40 * has_heading +
                40 * has_links +
                20 * has_description
            )

            return LlmsTxtResult(
                exists=True,
                content=content,
                quality_score=quality_score,
                link_count=len(re.findall(r'\[.+\]\(.+\)', content))
            )
    except:
        pass

    return LlmsTxtResult(exists=False, quality_score=0)
```

#### 1.4 JavaScript Dependency Detection

**File:** `worker/extraction/js_detection.py` (new)

```python
def detect_js_dependency(html: str) -> JSDetectionResult:
    """
    Detect if page content requires JavaScript to render.
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Check for JS framework markers
    js_framework_markers = [
        'id="__next"',           # Next.js
        'id="root"',             # React
        'id="app"',              # Vue
        'ng-app',                # Angular
        'data-reactroot',        # React
    ]

    main_content = soup.find('main') or soup.find('article') or soup.find('body')
    content_length = len(main_content.get_text(strip=True)) if main_content else 0

    # If main content is very short but there are JS frameworks, likely JS-dependent
    has_framework = any(marker in html for marker in js_framework_markers)

    # Heuristic: if content < 500 chars but page has framework markers
    likely_js_dependent = has_framework and content_length < 500

    return JSDetectionResult(
        has_framework_markers=has_framework,
        content_length=content_length,
        likely_js_dependent=likely_js_dependent,
        score=0 if likely_js_dependent else 100
    )
```

### Technical Readiness Score

```python
def calculate_technical_score(
    robots_result: RobotsTxtResult,
    ttfb_result: TTFBResult,
    llms_txt_result: LlmsTxtResult,
    js_result: JSDetectionResult,
    is_https: bool
) -> TechnicalScore:
    """
    Calculate overall technical readiness score.
    """
    components = {
        "robots_txt": robots_result.score * 0.35,
        "ttfb": ttfb_result.score * 0.30,
        "llms_txt": llms_txt_result.quality_score * 0.15,
        "js_accessible": js_result.score * 0.10,
        "https": (100 if is_https else 0) * 0.10,
    }

    total = sum(components.values())

    # Critical failures (score = 0 if any)
    critical_issues = []
    if robots_result.critical_blocked:
        critical_issues.append(f"AI crawlers blocked: {robots_result.critical_blocked}")
    if ttfb_result.ttfb_ms > 2000:
        critical_issues.append(f"TTFB critical: {ttfb_result.ttfb_ms}ms")

    return TechnicalScore(
        total=total,
        components=components,
        critical_issues=critical_issues,
        level=score_to_level(total)
    )
```

---

## Phase 2: Structure Quality (Week 3-4)

### New Checks to Add

#### 2.1 Heading Hierarchy Validation

```python
def validate_heading_hierarchy(html: str) -> HeadingResult:
    """
    Check if heading structure follows proper hierarchy.
    """
    soup = BeautifulSoup(html, 'html.parser')
    headings = []

    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        level = int(tag.name[1])
        headings.append({
            "level": level,
            "text": tag.get_text(strip=True),
            "is_question": tag.get_text(strip=True).endswith("?")
        })

    issues = []

    # Check for single H1
    h1_count = sum(1 for h in headings if h["level"] == 1)
    if h1_count == 0:
        issues.append("Missing H1")
    elif h1_count > 1:
        issues.append(f"Multiple H1s ({h1_count})")

    # Check for level skipping
    prev_level = 0
    for h in headings:
        if h["level"] > prev_level + 1 and prev_level > 0:
            issues.append(f"Level skip: H{prev_level} → H{h['level']}")
        prev_level = h["level"]

    # Count question-format headings (good for AI)
    question_headings = sum(1 for h in headings if h["is_question"])

    score = 100
    score -= len(issues) * 15
    score += min(20, question_headings * 5)  # Bonus for Q&A format

    return HeadingResult(
        h1_count=h1_count,
        total_headings=len(headings),
        question_headings=question_headings,
        issues=issues,
        score=max(0, score)
    )
```

#### 2.2 Answer-First Detection

```python
def detect_answer_first(page: ExtractedPage) -> AnswerFirstResult:
    """
    Check if content leads with answers rather than burying them.
    """
    # For each H2 section, check if answer appears in first paragraph
    sections = split_by_headings(page.main_content)

    answer_first_count = 0
    total_sections = 0

    for section in sections:
        if section.heading_level != 2:
            continue

        total_sections += 1
        first_para = get_first_paragraph(section.content)

        # Heuristics for "answer-first":
        # - Contains numbers/statistics
        # - 40-80 words (optimal nugget size)
        # - Contains definitive language

        word_count = len(first_para.split())
        has_numbers = bool(re.search(r'\d+%?', first_para))
        has_definitive = any(w in first_para.lower() for w in
            ['is', 'are', 'means', 'requires', 'include', 'cost'])

        is_answer_first = (
            40 <= word_count <= 100 and
            (has_numbers or has_definitive)
        )

        if is_answer_first:
            answer_first_count += 1

    ratio = answer_first_count / total_sections if total_sections > 0 else 0

    return AnswerFirstResult(
        answer_first_sections=answer_first_count,
        total_sections=total_sections,
        ratio=ratio,
        score=ratio * 100
    )
```

#### 2.3 FAQ Section Detection

```python
def detect_faq_sections(html: str, schema: dict) -> FAQResult:
    """
    Detect FAQ sections in content and schema.
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Check for FAQ schema
    has_faq_schema = "FAQPage" in str(schema)

    # Check for FAQ in content
    faq_indicators = [
        soup.find(id=re.compile(r'faq', re.I)),
        soup.find(class_=re.compile(r'faq', re.I)),
        soup.find('h2', string=re.compile(r'(FAQ|Frequently Asked|Common Questions)', re.I)),
    ]

    has_faq_section = any(faq_indicators)

    # Count Q&A pairs (heading + following paragraph)
    qa_pairs = 0
    for heading in soup.find_all(['h2', 'h3', 'h4']):
        if heading.get_text(strip=True).endswith('?'):
            qa_pairs += 1

    score = 0
    score += 40 if has_faq_schema else 0
    score += 30 if has_faq_section else 0
    score += min(30, qa_pairs * 5)

    return FAQResult(
        has_faq_schema=has_faq_schema,
        has_faq_section=has_faq_section,
        qa_pair_count=qa_pairs,
        score=score
    )
```

#### 2.4 Internal Link Analysis

```python
def analyze_internal_links(pages: List[ExtractedPage]) -> InternalLinkResult:
    """
    Analyze internal linking structure.
    """
    link_graph = {}
    anchor_texts = []

    for page in pages:
        outbound = extract_internal_links(page.html, page.url)
        link_graph[page.url] = outbound

        for link in outbound:
            anchor_texts.append(link.anchor_text)

    # Calculate metrics
    avg_outbound = sum(len(v) for v in link_graph.values()) / len(link_graph)

    # Check for bidirectional links
    bidirectional_count = 0
    for source, targets in link_graph.items():
        for target in targets:
            if source in link_graph.get(target.url, []):
                bidirectional_count += 1

    # Score anchor text quality
    generic_anchors = ['click here', 'read more', 'learn more', 'here']
    poor_anchor_count = sum(1 for a in anchor_texts if a.lower() in generic_anchors)
    anchor_quality = 1 - (poor_anchor_count / len(anchor_texts)) if anchor_texts else 0

    # Identify potential pillar pages (many inbound links)
    inbound_counts = {}
    for targets in link_graph.values():
        for target in targets:
            inbound_counts[target.url] = inbound_counts.get(target.url, 0) + 1

    pillar_candidates = [url for url, count in inbound_counts.items() if count >= 10]

    score = (
        min(30, avg_outbound * 3) +  # Link density
        min(30, bidirectional_count / len(pages) * 100) +  # Bidirectional
        anchor_quality * 40  # Anchor quality
    )

    return InternalLinkResult(
        avg_links_per_page=avg_outbound,
        bidirectional_ratio=bidirectional_count / len(pages),
        anchor_quality_score=anchor_quality * 100,
        pillar_candidates=pillar_candidates,
        score=score
    )
```

---

## Phase 3: Schema & Semantic Richness (Week 5-6)

### Enhanced Schema Analysis

```python
PRIORITY_SCHEMA_TYPES = {
    "FAQPage": {"weight": 25, "citation_lift": "35-40%"},
    "HowTo": {"weight": 20, "citation_lift": "High"},
    "Article": {"weight": 20, "citation_lift": "Medium"},
    "Organization": {"weight": 15, "citation_lift": "Entity recognition"},
    "Product": {"weight": 10, "citation_lift": "Medium"},
    "VideoObject": {"weight": 5, "citation_lift": "Medium"},
    "Review": {"weight": 5, "citation_lift": "Medium"},
}

def analyze_schema_completeness(pages: List[ExtractedPage]) -> SchemaResult:
    """
    Analyze schema markup presence and quality.
    """
    schema_by_type = {}
    pages_with_schema = 0
    validation_errors = []

    for page in pages:
        schema = extract_schema(page.html)
        if schema:
            pages_with_schema += 1
            for item in schema:
                schema_type = item.get("@type", "Unknown")
                if schema_type not in schema_by_type:
                    schema_by_type[schema_type] = []
                schema_by_type[schema_type].append(page.url)

                # Check for required properties
                errors = validate_schema_item(item)
                validation_errors.extend(errors)

    # Calculate score
    score = 0
    for schema_type, config in PRIORITY_SCHEMA_TYPES.items():
        if schema_type in schema_by_type:
            score += config["weight"]

    # Bonus for high schema coverage
    coverage = pages_with_schema / len(pages)
    score += min(25, coverage * 50)

    # Penalty for validation errors
    score -= min(20, len(validation_errors) * 2)

    # Check for critical signals
    has_author_schema = any("author" in str(s).lower() for s in schema_by_type.values())
    has_date_modified = any("dateModified" in str(s) for s in schema_by_type.values())

    return SchemaResult(
        types_found=list(schema_by_type.keys()),
        coverage_ratio=coverage,
        validation_errors=validation_errors,
        has_author_schema=has_author_schema,
        has_date_modified=has_date_modified,
        score=max(0, min(100, score))
    )
```

---

## Phase 4: Authority Signals (Week 7-8)

### E-E-A-T Detection

```python
def analyze_eeat_signals(pages: List[ExtractedPage]) -> EEATResult:
    """
    Analyze Experience, Expertise, Authoritativeness, Trustworthiness signals.
    """
    results = {
        "author_attribution": 0,
        "author_credentials": 0,
        "primary_citations": 0,
        "original_data": 0,
        "contact_info": False,
    }

    for page in pages:
        html = page.html

        # Author detection
        if detect_author_byline(html):
            results["author_attribution"] += 1

            # Check for credentials
            if detect_credentials(html):  # PhD, CEO, "Director of", years experience
                results["author_credentials"] += 1

        # Citation detection
        citations = extract_outbound_citations(html)
        authoritative_citations = [c for c in citations if is_authoritative_domain(c.domain)]
        results["primary_citations"] += len(authoritative_citations)

        # Original data markers
        if detect_original_research(page.text):
            results["original_data"] += 1

    # Contact page detection
    results["contact_info"] = any(
        "contact" in page.url.lower() for page in pages
    )

    # Calculate score
    page_count = len(pages)
    score = (
        (results["author_attribution"] / page_count * 100) * 0.25 +
        (results["author_credentials"] / page_count * 100) * 0.20 +
        min(100, results["primary_citations"] / page_count * 20) * 0.25 +
        (results["original_data"] / page_count * 100) * 0.20 +
        (100 if results["contact_info"] else 0) * 0.10
    )

    return EEATResult(
        author_attribution_ratio=results["author_attribution"] / page_count,
        credentials_ratio=results["author_credentials"] / page_count,
        avg_citations_per_page=results["primary_citations"] / page_count,
        has_original_data=results["original_data"] > 0,
        has_contact_info=results["contact_info"],
        score=score
    )

def detect_original_research(text: str) -> bool:
    """
    Detect markers of original research/data.
    """
    markers = [
        r"we (surveyed|analyzed|studied|tested|interviewed)",
        r"our (research|data|analysis|study|findings)",
        r"(original|proprietary) (research|data)",
        r"\d+ (respondents|participants|companies|clients)",
        r"methodology:",
    ]

    for marker in markers:
        if re.search(marker, text, re.I):
            return True
    return False

def is_authoritative_domain(domain: str) -> bool:
    """
    Check if domain is an authoritative source.
    """
    authoritative_tlds = ['.gov', '.edu', '.org']
    authoritative_domains = [
        'reuters.com', 'nytimes.com', 'wsj.com', 'bloomberg.com',
        'nature.com', 'science.org', 'pubmed.ncbi.nlm.nih.gov',
        'forrester.com', 'gartner.com', 'mckinsey.com',
        'hbr.org', 'techcrunch.com', 'wired.com'
    ]

    return (
        any(domain.endswith(tld) for tld in authoritative_tlds) or
        any(auth in domain for auth in authoritative_domains)
    )
```

---

## Revised Score Calculator

```python
class FindableScoreV2Calculator:
    """
    Calculate the expanded Findable Score v2.
    """

    WEIGHTS = {
        "technical": 0.15,
        "structure": 0.20,
        "schema": 0.15,
        "authority": 0.15,
        "retrieval": 0.25,
        "coverage": 0.10,
    }

    def calculate(
        self,
        technical: TechnicalScore,
        structure: StructureScore,
        schema: SchemaResult,
        authority: EEATResult,
        retrieval: SimulationResult,  # Existing
        coverage: CoverageStats,  # Existing
    ) -> FindableScoreV2:

        components = {
            "technical": technical.total * self.WEIGHTS["technical"],
            "structure": structure.total * self.WEIGHTS["structure"],
            "schema": schema.score * self.WEIGHTS["schema"],
            "authority": authority.score * self.WEIGHTS["authority"],
            "retrieval": retrieval.overall_score * 100 * self.WEIGHTS["retrieval"],
            "coverage": coverage.percentage * self.WEIGHTS["coverage"],
        }

        total = sum(components.values())

        # Critical issue handling
        critical_issues = technical.critical_issues.copy()
        if schema.coverage_ratio < 0.1:
            critical_issues.append("Schema markup missing on 90%+ of pages")

        return FindableScoreV2(
            total_score=total,
            grade=self.score_to_grade(total),
            components=components,
            critical_issues=critical_issues,
            show_the_math=self.generate_explanation(components)
        )

    def generate_explanation(self, components: dict) -> str:
        return f"""
Findable Score = {sum(components.values()):.1f}

Components:
• Technical Readiness: {components['technical']:.1f} / 15 (Can AI access your site?)
• Structure Quality: {components['structure']:.1f} / 20 (Is content extractable?)
• Schema Richness: {components['schema']:.1f} / 15 (Is content machine-readable?)
• Authority Signals: {components['authority']:.1f} / 15 (Does AI trust you?)
• Retrieval Score: {components['retrieval']:.1f} / 25 (Can AI find relevant content?)
• Answer Coverage: {components['coverage']:.1f} / 10 (Can AI answer questions about you?)

Formula: Technical×15% + Structure×20% + Schema×15% + Authority×15% + Retrieval×25% + Coverage×10%
"""
```

---

## New Fix Generator Categories

```python
FIX_CATEGORIES = {
    "technical": {
        "priority": 1,
        "fixes": [
            ("robots_txt_blocked", "Add {crawlers} to robots.txt Allow list", "HIGH"),
            ("ttfb_slow", "Reduce TTFB from {current}ms to <500ms (currently {level})", "HIGH"),
            ("no_llms_txt", "Create llms.txt file at site root with key content links", "MEDIUM"),
            ("js_dependent", "Implement server-side rendering for main content", "HIGH"),
            ("no_https", "Enable HTTPS site-wide", "MEDIUM"),
        ]
    },
    "schema": {
        "priority": 2,
        "fixes": [
            ("no_faq_schema", "Add FAQPage schema to pages with Q&A content (35-40% citation lift)", "HIGH"),
            ("no_article_schema", "Add Article schema with author and dates to blog posts", "HIGH"),
            ("no_date_modified", "Add dateModified to schema markup", "HIGH"),
            ("schema_errors", "Fix {count} schema validation errors on {pages}", "MEDIUM"),
            ("no_organization_schema", "Add Organization schema to homepage", "MEDIUM"),
        ]
    },
    "structure": {
        "priority": 3,
        "fixes": [
            ("no_answer_first", "Move direct answers to first paragraph under {heading}", "HIGH"),
            ("heading_issues", "Fix heading hierarchy: {issues}", "MEDIUM"),
            ("no_faq_section", "Add FAQ section with 3-5 common questions", "HIGH"),
            ("poor_link_density", "Add more internal links (current: {current}, target: 5-10)", "MEDIUM"),
            ("poor_anchor_text", "Replace generic anchor text ('click here') with descriptive text", "LOW"),
        ]
    },
    "authority": {
        "priority": 4,
        "fixes": [
            ("no_author", "Add author byline with credentials to articles", "HIGH"),
            ("no_citations", "Add links to primary sources for statistics and claims", "HIGH"),
            ("stale_content", "Update content (last modified: {date}, {days} days ago)", "MEDIUM"),
            ("no_original_data", "Create original research or case study with proprietary data", "MEDIUM"),
        ]
    },
    "retrieval": {
        "priority": 5,
        "fixes": [
            # Existing fixes for content gaps
        ]
    }
}
```

---

## Migration Path

### v1 → v2 Score Mapping

To maintain continuity for existing users:

```python
def convert_v1_to_v2(v1_score: float) -> dict:
    """
    Map v1 scores to approximate v2 equivalents during transition.
    """
    # v1 only measured retrieval + coverage (now 35% of v2)
    # Assume average performance on new factors

    assumed_new_factors = {
        "technical": 70,  # Most sites pass basic checks
        "structure": 60,  # Average structure
        "schema": 40,     # Many sites lack schema
        "authority": 50,  # Average
    }

    v2_components = {
        "technical": assumed_new_factors["technical"] * 0.15,
        "structure": assumed_new_factors["structure"] * 0.20,
        "schema": assumed_new_factors["schema"] * 0.15,
        "authority": assumed_new_factors["authority"] * 0.15,
        "retrieval": v1_score * 0.7 * 0.25,  # 70% of v1 was retrieval
        "coverage": v1_score * 0.3 * 0.10,   # 30% was coverage
    }

    return {
        "estimated_v2": sum(v2_components.values()),
        "note": "Run full v2 analysis for accurate score"
    }
```

---

## Timeline

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1-2 | Technical Readiness | robots.txt, TTFB, llms.txt, JS detection |
| 3-4 | Structure Quality | Heading validation, answer-first, FAQ detection, links |
| 5-6 | Schema & Semantic | Enhanced schema analysis, validation, entity linking |
| 7-8 | Authority Signals | E-E-A-T detection, freshness, citation analysis |
| 9-10 | Integration | New calculator, fix generator, report updates |
| 11-12 | Testing & Polish | Validation, calibration, documentation |

---

## Success Metrics

After v2 launch, track:

1. **Fix adoption rate** — Are users implementing more fixes?
2. **Score delta after fixes** — Do scores improve when fixes are applied?
3. **Correlation with actual AI citations** — Does higher v2 score = more AI mentions?
4. **Customer feedback** — Are new components useful?

The goal: A v2 Findable Score that accurately predicts AI sourceability across all dimensions.
