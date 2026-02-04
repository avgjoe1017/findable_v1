# Findable Score Gap Analysis: Current vs. GEO/AEO Best Practices

**Analysis Date:** February 1, 2026
**Source:** Perplexity Deep Research on GEO/AEO (117 sources analyzed)

---

## Executive Summary

The current Findable Score measures **retrieval simulation** well but misses **70% of the factors** that determine whether AI systems will actually cite a website. The research identifies 8 major pillars of AI sourceability — we're strong on 1.5 of them.

**Current Coverage:**
- ✅ Strong: Content chunking, retrieval simulation
- ⚠️ Partial: Content structure (headings), basic metadata
- ❌ Missing: Technical crawlability, schema markup, E-E-A-T signals, freshness, topic authority, entity optimization

**Recommendation:** Expand the analysis to include technical, structural, and trust signals. This creates a more complete picture AND more actionable recommendations.

---

## Gap Analysis by Pillar

### 1. Technical Crawlability & Infrastructure

| Factor | Research Says | We Measure | Gap |
|--------|---------------|------------|-----|
| robots.txt AI crawler access | Critical — must allow GPTBot, ClaudeBot, PerplexityBot | ❌ No | **HIGH** |
| TTFB (Time to First Byte) | <500ms target, >1.5s = skipped by crawlers | ❌ No | **HIGH** |
| Server-side vs Client-side rendering | AI crawlers can't execute JS | ❌ No | **MEDIUM** |
| llms.txt file presence | New standard for AI content indexing | ❌ No | **MEDIUM** |
| CDN/firewall bot blocking | Common cause of invisible sites | ❌ No | **LOW** (hard to detect externally) |

**Impact if not measured:** Sites may be completely invisible to AI crawlers despite great content. We'd give them a score based on simulation, but AI can't even access them.

**Recommended additions:**
```python
# Technical checks to add
technical_score = {
    "robots_txt_ai_access": check_robots_txt_for_ai_bots(domain),
    "ttfb_ms": measure_ttfb(url),
    "llms_txt_exists": check_llms_txt(domain),
    "js_rendering_required": detect_js_dependency(html),
    "https_enabled": url.startswith("https")
}
```

---

### 2. Content Structure & Formatting

| Factor | Research Says | We Measure | Gap |
|--------|---------------|------------|-----|
| Answer-first content (40-80 word nuggets) | "Inverted pyramid" — answer in first 2 scrolls | ⚠️ Partial (chunk position) | **MEDIUM** |
| Chunk size (256-512 tokens optimal) | AI systems chunk at this size | ✅ Yes (max=512) | None |
| Heading hierarchy (H1→H2→H3) | Must be logical, no level skipping | ⚠️ Partial (extract headings) | **MEDIUM** |
| Modular/self-contained sections | Each H2 should stand alone | ❌ No | **HIGH** |
| FAQ sections | "Very High" citation lift | ❌ No (detect but don't score) | **HIGH** |
| Tables | "Very High" citation lift | ⚠️ Detect chunk type only | **MEDIUM** |
| Numbered/bullet lists | "High" citation lift | ⚠️ Detect chunk type only | **MEDIUM** |
| Paragraph length (≤4 sentences) | Scannable, extractable | ❌ No | **LOW** |

**Impact if not measured:** We score retrieval but miss WHY content gets retrieved. A site with poor structure will get poor scores but won't know how to fix it.

**Recommended additions:**
```python
structure_score = {
    "answer_first": detect_answer_in_first_500_chars(page),
    "heading_hierarchy_valid": validate_heading_hierarchy(headings),
    "faq_section_count": count_faq_sections(html),
    "table_count": count_tables(html),
    "avg_paragraph_length": calculate_avg_paragraph_sentences(html),
    "self_contained_sections": score_section_independence(chunks)
}
```

---

### 3. Schema Markup & Structured Data

| Factor | Research Says | We Measure | Gap |
|--------|---------------|------------|-----|
| FAQPage schema | 35-40% higher citation rate | ⚠️ Detect schema types | **HIGH** (don't score presence) |
| HowTo schema | Structures procedural content | ⚠️ Detect schema types | **MEDIUM** |
| Article schema | Author, dates, publisher | ⚠️ Detect schema types | **HIGH** |
| Organization schema | Entity recognition | ⚠️ Detect schema types | **MEDIUM** |
| Author schema w/ credentials | E-E-A-T signal | ❌ No | **HIGH** |
| datePublished/dateModified | Freshness signal | ❌ No (don't extract) | **HIGH** |
| Entity linking (sameAs) | Wikidata/Wikipedia connections | ❌ No | **MEDIUM** |
| Schema validation | Zero errors required | ❌ No | **MEDIUM** |

**Impact if not measured:** Schema is the #1 optimization by effect size (2.8x citation rate). We're detecting it but not scoring or recommending it.

**Research finding:** "Sites implementing FAQPage schema see 35-40% higher citation rates"

**Recommended additions:**
```python
schema_score = {
    "has_faq_schema": bool,
    "has_article_schema": bool,
    "has_howto_schema": bool,
    "has_organization_schema": bool,
    "has_author_with_credentials": bool,
    "has_date_modified": bool,
    "date_modified_recent": bool,  # within 6 months
    "has_entity_links": bool,  # sameAs to Wikidata/LinkedIn/etc
    "schema_validation_errors": int
}
```

---

### 4. Content Freshness & Update Signals

| Factor | Research Says | We Measure | Gap |
|--------|---------------|------------|-----|
| dateModified in schema | AI cites 25.7% fresher content | ❌ No | **HIGH** |
| Visible update date on page | "Updated February 2026" | ❌ No | **MEDIUM** |
| Textual freshness cues | "As of 2026..." | ❌ No | **MEDIUM** |
| Changelog/revision history | Shows active maintenance | ❌ No | **LOW** |
| Statistics recency | Current year data | ❌ No | **MEDIUM** |

**Research finding:** "ChatGPT favors sources 393-458 days newer than Google's organic rankings"

**Impact if not measured:** We can't tell users their content is stale even though AI systems heavily penalize it.

**Recommended additions:**
```python
freshness_score = {
    "date_modified": extract_date_modified(schema),
    "days_since_modified": calculate_days_since(date_modified),
    "has_visible_update_date": detect_update_date_in_content(html),
    "has_current_year_references": detect_year_mentions(text, current_year),
    "has_changelog": detect_changelog_section(html)
}
```

---

### 5. Topical Authority & Content Clusters

| Factor | Research Says | We Measure | Gap |
|--------|---------------|------------|-----|
| Pillar pages exist | 2,000-4,000 word comprehensive guides | ❌ No | **HIGH** |
| Cluster page structure | 1,000-2,000 word deep dives | ❌ No | **MEDIUM** |
| Internal link density | 5-10 links per cluster page | ❌ No | **HIGH** |
| Bidirectional linking | Pillar ↔ Cluster connections | ❌ No | **HIGH** |
| Anchor text quality | Descriptive, not "click here" | ❌ No | **MEDIUM** |
| Topic coverage breadth | Multiple related pages | ⚠️ Partial (see crawled pages) | **MEDIUM** |

**Research finding:** "Clustered content generates 30% more organic traffic and maintains rankings 2.5x longer"

**Impact if not measured:** We crawl 250 pages but don't assess whether they form coherent topic clusters or just random content.

**Recommended additions:**
```python
authority_score = {
    "pillar_pages_detected": identify_pillar_pages(pages),
    "cluster_structure_score": analyze_cluster_formation(pages, links),
    "internal_link_density": avg_internal_links_per_page(pages),
    "bidirectional_link_ratio": calculate_bidirectional_links(links),
    "anchor_text_quality": score_anchor_text_descriptiveness(links),
    "topic_coverage_depth": semantic_clustering_analysis(chunks)
}
```

---

### 6. E-E-A-T Signals (Experience, Expertise, Authority, Trust)

| Factor | Research Says | We Measure | Gap |
|--------|---------------|------------|-----|
| Author credentials displayed | "67% citation increase" | ❌ No | **HIGH** |
| Author bio pages | Links to credentials | ❌ No | **MEDIUM** |
| Primary source citations | Links to research/data | ❌ No | **HIGH** |
| Original data/research | "30-40% citation increase" | ❌ No | **HIGH** |
| Contact information clear | Trust signal | ❌ No | **LOW** |
| HTTPS enabled | Trust signal | ❌ No | **LOW** |
| External authority mentions | Brand mentions on other sites | ❌ No (out of scope) | N/A |

**Research finding:** "In YMYL categories, E-E-A-T signals are non-negotiable for AI citation"

**Impact if not measured:** We can't distinguish authoritative content from anonymous blog posts.

**Recommended additions:**
```python
eeat_score = {
    "has_author_attribution": detect_author_byline(html),
    "has_author_credentials": detect_credentials_in_bio(html),
    "has_author_schema": bool,
    "outbound_citation_count": count_external_citations(html),
    "citation_quality": score_citation_domains(citations),
    "has_original_data": detect_original_research_markers(text),
    "has_contact_info": detect_contact_page(pages)
}
```

---

### 7. Multimodal Optimization

| Factor | Research Says | We Measure | Gap |
|--------|---------------|------------|-----|
| Image alt text quality | Descriptive, not "image.jpg" | ❌ No | **MEDIUM** |
| ImageObject schema | Caption, dimensions | ❌ No | **LOW** |
| Video transcripts | AI reads transcripts | ❌ No | **LOW** |
| VideoObject schema | Duration, thumbnail | ❌ No | **LOW** |

**Impact if not measured:** As AI goes multimodal, image/video optimization will matter more. Currently low priority.

---

### 8. Question-Answer Alignment

| Factor | Research Says | We Measure | Gap |
|--------|---------------|------------|-----|
| PAA question matching | Use exact "People Also Ask" phrasing | ⚠️ Partial (universal questions) | **MEDIUM** |
| Conversational query support | Long-tail, natural language | ⚠️ Partial | **MEDIUM** |
| FAQ format in content | H2 questions with direct answers | ❌ No | **HIGH** |

**What we do well:** Our universal questions test standard queries.

**What we miss:** We don't detect if the site itself uses question-format headings or FAQ structures.

---

## Scoring Weight Recommendations

Based on research effect sizes, here's how criteria should be weighted:

| Factor | Current Weight | Recommended Weight | Research Basis |
|--------|----------------|-------------------|----------------|
| Content Relevance | 35% | 20% | Still important, but overweighted |
| Signal Coverage | 35% | 15% | Matters, but structure matters more |
| Schema Implementation | 0% | **20%** | 2.8x citation rate increase |
| Content Structure | 0% | **15%** | Answer-first = 40-55% improvement |
| E-E-A-T Signals | 0% | **15%** | 67% citation increase |
| Technical Access | 0% | **10%** | Binary — if blocked, nothing else matters |
| Freshness | 0% | **10%** | 25.7% fresher content cited |
| Topic Authority | 0% | **10%** | 30% more traffic, 2.5x longevity |
| Source Quality | 10% | 5% | Keep but reduce |

---

## Implementation Priority

### Phase 1: Quick Wins (1-2 weeks)

**Add to current crawl/extraction:**
1. **robots.txt check** — Are AI crawlers allowed?
2. **TTFB measurement** — Is the site fast enough?
3. **llms.txt detection** — Does it exist?
4. **Schema extraction** — What types are present? (already partial)
5. **dateModified extraction** — From schema
6. **FAQ section detection** — Count FAQ blocks

**New score component:**
```
Technical Readiness Score (0-100)
- robots.txt AI access: 40 points
- TTFB < 500ms: 30 points
- HTTPS: 10 points
- llms.txt: 10 points
- No JS-only content: 10 points
```

### Phase 2: Structure Analysis (2-4 weeks)

1. **Heading hierarchy validation**
2. **Answer-first detection** (is the answer in first 500 chars under H2?)
3. **Internal link analysis** (count, anchor text quality)
4. **FAQ format detection** (Q&A structured content)
5. **Table/list prevalence**

**New score component:**
```
Structure Score (0-100)
- Heading hierarchy valid: 25 points
- Answer-first content: 25 points
- FAQ sections present: 20 points
- Internal link density: 15 points
- Extractable formats (tables/lists): 15 points
```

### Phase 3: Authority Signals (4-6 weeks)

1. **Author detection and schema**
2. **Citation/source link analysis**
3. **Freshness signals extraction**
4. **Topic cluster analysis** (semantic grouping of pages)
5. **Original data markers**

**New score component:**
```
Authority Score (0-100)
- Author attribution: 20 points
- Author credentials: 15 points
- Primary source citations: 20 points
- Content freshness: 20 points
- Topic cluster structure: 15 points
- Original data: 10 points
```

---

## Revised Findable Score Formula

**Current:**
```
Findable Score = (Criterion Total × 70%) + (Category Total × 30%)
```

**Proposed:**
```
Findable Score =
    (Technical Readiness × 15%) +     # Can AI access you?
    (Structure Score × 20%) +          # Is content extractable?
    (Schema Score × 15%) +             # Is content machine-readable?
    (Authority Score × 15%) +          # Are you trustworthy?
    (Retrieval Score × 25%) +          # Can AI find relevant chunks?
    (Answer Coverage × 10%)            # Can AI answer questions about you?
```

**Or simplified to 4 pillars:**
```
Findable Score =
    (Accessibility × 20%) +    # Technical + Schema
    (Extractability × 25%) +   # Structure + Chunking
    (Authority × 20%) +        # E-E-A-T + Freshness
    (Answerability × 35%)      # Retrieval + Coverage (current focus)
```

---

## New Fix Categories

Current fixes focus on content gaps. Research suggests we need:

### Technical Fixes
- "Add GPTBot to robots.txt Allow list"
- "Reduce TTFB from 2.3s to <500ms"
- "Create llms.txt file"
- "Implement server-side rendering for [pages]"

### Schema Fixes
- "Add FAQPage schema to [page] (35-40% citation lift expected)"
- "Add Article schema with author credentials"
- "Add dateModified to schema (currently missing)"
- "Fix schema validation errors on [pages]"

### Structure Fixes
- "Move answer to first paragraph (currently buried 400 words down)"
- "Fix heading hierarchy on [page] (skips from H2 to H4)"
- "Add FAQ section with 3-5 common questions"
- "Break [page] into modular sections with clear H2s"

### Authority Fixes
- "Add author byline with credentials"
- "Add publication/update date visibly on page"
- "Link to primary sources for statistics"
- "Create original research/data piece for [topic]"

### Freshness Fixes
- "Update dateModified (last update: 18 months ago)"
- "Refresh statistics with 2026 data"
- "Add visible 'Last updated: [date]' to content"

---

## Competitive Differentiation

This expansion creates major differentiation:

| Capability | Competitors | Findable (Current) | Findable (Expanded) |
|------------|-------------|-------------------|---------------------|
| AI mention tracking | ✅ | ❌ | ❌ (not our focus) |
| Content audit | Basic | ✅ | ✅✅ |
| Technical crawlability check | ❌ | ❌ | ✅ |
| Schema analysis | Basic | ⚠️ | ✅✅ |
| Structure scoring | ❌ | ⚠️ | ✅✅ |
| E-E-A-T assessment | ❌ | ❌ | ✅ |
| Retrieval simulation | ❌ | ✅✅ | ✅✅ |
| Actionable fixes | Generic | ✅ | ✅✅✅ |

**The pitch becomes:** "We don't just tell you if AI mentions you — we tell you exactly WHY it does or doesn't, and give you the specific fixes to improve."

---

## Summary

**What we do well:**
- Retrieval simulation (unique differentiator)
- Chunking quality
- Answer coverage testing

**What we're missing:**
- Technical accessibility checks (robots.txt, TTFB, llms.txt)
- Schema presence and quality scoring
- Content structure analysis (answer-first, heading hierarchy)
- E-E-A-T signal detection
- Freshness signal extraction
- Topic authority/cluster analysis

**Bottom line:** The current score answers "Can AI retrieve your content?" but misses "Can AI ACCESS your content?" and "Does AI TRUST your content?"

Adding these dimensions creates a complete AI sourceability picture — and much more actionable recommendations.
