"""Validation tests for real-world HTML analysis accuracy.

These tests verify that our analyzers produce CORRECT results on real HTML,
not just that the code runs. Each test includes:
1. Real HTML (or realistic samples)
2. Expected ground truth
3. Verification that our analysis matches reality
"""

from worker.extraction.authority import (
    AuthorityAnalyzer,
)
from worker.extraction.headings import (
    HeadingAnalyzer,
)
from worker.extraction.schema import (
    SchemaAnalyzer,
)
from worker.extraction.structure import (
    StructureAnalyzer,
)

# ============================================================================
# Real HTML Samples - These represent actual website patterns
# ============================================================================

# A well-structured blog post (like from a major tech blog)
WELL_STRUCTURED_BLOG = """
<!DOCTYPE html>
<html>
<head>
    <title>How to Optimize Your Website for AI Search Engines</title>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "How to Optimize Your Website for AI Search Engines",
        "author": {
            "@type": "Person",
            "name": "Sarah Chen",
            "jobTitle": "Senior SEO Strategist"
        },
        "datePublished": "2026-01-15",
        "dateModified": "2026-01-28"
    }
    </script>
</head>
<body>
    <article>
        <h1>How to Optimize Your Website for AI Search Engines</h1>

        <div class="author-info">
            <span class="author-name">By Sarah Chen</span>
            <span class="author-title">Senior SEO Strategist, 10+ years experience</span>
            <time datetime="2026-01-28">Updated January 28, 2026</time>
        </div>

        <p>AI search engines are changing how users find information. Here's what you need to know to stay visible.</p>

        <h2>Understanding AI Search</h2>
        <p>Unlike traditional search engines, AI systems like ChatGPT and Claude retrieve and synthesize information differently.</p>

        <h3>Key Differences from Traditional SEO</h3>
        <ul>
            <li>Content structure matters more than keywords</li>
            <li>Clear answers are prioritized</li>
            <li>Authority signals are weighted heavily</li>
        </ul>

        <h2>Optimization Strategies</h2>

        <h3>1. Structure Your Content Clearly</h3>
        <p>Use proper heading hierarchy and put answers first.</p>

        <h3>2. Add Schema Markup</h3>
        <p>Structured data helps AI understand your content.</p>

        <h2>Frequently Asked Questions</h2>

        <div class="faq">
            <h3>What is AI SEO?</h3>
            <p>AI SEO is the practice of optimizing content to be discoverable by AI-powered search and answer systems.</p>

            <h3>How long does it take to see results?</h3>
            <p>Most sites see improvements within 2-4 weeks of implementing these changes.</p>
        </div>

        <h2>Conclusion</h2>
        <p>Start with these basics and you'll be ahead of most competitors.</p>

        <div class="citations">
            <p>Sources:</p>
            <ul>
                <li><a href="https://research.google/pubs/">Google Research</a></li>
                <li><a href="https://www.anthropic.com/research">Anthropic Research</a></li>
            </ul>
        </div>
    </article>
</body>
</html>
"""

# A poorly structured SPA-style page (common pattern we should flag)
POORLY_STRUCTURED_SPA = """
<!DOCTYPE html>
<html>
<head>
    <title>Our Products</title>
</head>
<body>
    <div id="app">
        <div class="header">
            <div class="logo">Company Name</div>
            <nav>Home | Products | About</nav>
        </div>

        <div class="content">
            <div class="hero">
                <div class="hero-text">Welcome to our amazing platform</div>
                <div class="cta">Get Started</div>
            </div>

            <div class="section">
                <div class="section-title">Our Products</div>
                <div class="product">Product 1 - Great features</div>
                <div class="product">Product 2 - More features</div>
            </div>

            <div class="section">
                <div class="section-title">Why Choose Us</div>
                <div>We're the best because we say so.</div>
            </div>
        </div>

        <div class="footer">© 2026 Company</div>
    </div>

    <script src="app.bundle.js"></script>
    <script>
        // Client-side rendering
        ReactDOM.render(App, document.getElementById('app'));
    </script>
</body>
</html>
"""

# A page with rich schema markup (e-commerce style)
RICH_SCHEMA_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Premium Widget - Only $49.99</title>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Premium Widget",
        "description": "The best widget for all your needs",
        "offers": {
            "@type": "Offer",
            "price": "49.99",
            "priceCurrency": "USD"
        }
    }
    </script>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": "What is the warranty?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "All widgets come with a 2-year warranty."
                }
            },
            {
                "@type": "Question",
                "name": "Do you offer free shipping?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Yes, free shipping on orders over $25."
                }
            }
        ]
    }
    </script>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Widget Corp",
        "url": "https://widgetcorp.com"
    }
    </script>
</head>
<body>
    <h1>Premium Widget</h1>
    <p>The best widget for all your needs. Only $49.99!</p>

    <h2>Frequently Asked Questions</h2>
    <div class="faq-item">
        <h3>What is the warranty?</h3>
        <p>All widgets come with a 2-year warranty.</p>
    </div>
    <div class="faq-item">
        <h3>Do you offer free shipping?</h3>
        <p>Yes, free shipping on orders over $25.</p>
    </div>
</body>
</html>
"""

# A page with author credentials (medical/health style)
AUTHORITATIVE_HEALTH_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Understanding Diabetes: A Complete Guide</title>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "Understanding Diabetes: A Complete Guide",
        "author": {
            "@type": "Person",
            "name": "Dr. Michael Roberts",
            "jobTitle": "Endocrinologist",
            "affiliation": {
                "@type": "Organization",
                "name": "Mayo Clinic"
            }
        },
        "dateModified": "2026-01-20"
    }
    </script>
</head>
<body>
    <article>
        <h1>Understanding Diabetes: A Complete Guide</h1>

        <div class="author-box">
            <img src="dr-roberts.jpg" alt="Dr. Michael Roberts" class="author-photo">
            <div class="author-details">
                <a href="/authors/dr-roberts" class="author-name">Dr. Michael Roberts, MD, PhD</a>
                <p class="author-credentials">Board-Certified Endocrinologist</p>
                <p class="author-bio">Dr. Roberts has over 20 years of experience treating diabetes patients at Mayo Clinic. He completed his medical degree at Johns Hopkins and his fellowship at Stanford.</p>
            </div>
        </div>

        <p class="summary">Diabetes affects millions of people worldwide. This guide explains the types, symptoms, and management strategies based on the latest clinical research.</p>

        <p class="last-updated">Medically reviewed on January 20, 2026</p>

        <h2>What is Diabetes?</h2>
        <p>Diabetes is a chronic condition that affects how your body processes blood sugar (glucose).</p>

        <p>According to the <a href="https://www.cdc.gov/diabetes/">CDC</a>, over 37 million Americans have diabetes.</p>

        <p>A recent study published in the <a href="https://www.nejm.org/">New England Journal of Medicine</a> found that early intervention can reduce complications by 50%.</p>

        <h2>Our Research</h2>
        <p>In our 2025 patient survey of 5,000 diabetes patients, we found that 73% reported improved outcomes with continuous glucose monitoring.</p>

        <p>Our clinical trial data shows a 40% reduction in HbA1c levels among patients following our protocol.</p>
    </article>
</body>
</html>
"""


# ============================================================================
# Heading Analysis Validation
# ============================================================================


class TestHeadingAnalysisAccuracy:
    """Verify heading analysis produces CORRECT results."""

    def test_well_structured_blog_has_valid_hierarchy(self):
        """Well-structured blog should have valid heading hierarchy."""
        # HeadingAnalyzer.analyze() takes HTML string, not BeautifulSoup
        analyzer = HeadingAnalyzer()
        result = analyzer.analyze(WELL_STRUCTURED_BLOG)

        # Ground truth: This HTML has proper H1 -> H2 -> H3 hierarchy
        assert result.h1_count == 1, "Should detect exactly 1 H1"
        assert result.h2_count >= 4, f"Should detect at least 4 H2s, got {result.h2_count}"
        assert result.h3_count >= 4, f"Should detect at least 4 H3s, got {result.h3_count}"
        assert result.hierarchy_valid, "Hierarchy should be valid - no skips"

    def test_poorly_structured_spa_has_no_headings(self):
        """Poorly structured SPA should be flagged for missing headings."""
        analyzer = HeadingAnalyzer()
        result = analyzer.analyze(POORLY_STRUCTURED_SPA)

        # Ground truth: This HTML uses divs instead of headings
        assert result.h1_count == 0, "Should detect no H1s (uses divs)"
        assert result.h2_count == 0, "Should detect no H2s (uses divs)"
        assert not result.hierarchy_valid, "Should flag invalid hierarchy"

    def test_detects_heading_content_correctly(self):
        """Should extract actual heading text."""
        analyzer = HeadingAnalyzer()
        result = analyzer.analyze(WELL_STRUCTURED_BLOG)

        # Check that we captured the right H1
        assert any(
            "Optimize" in h.text for h in result.headings if h.level == 1
        ), "Should capture H1 text about optimization"

        # Check that FAQ section headings are captured
        h3_texts = [h.text for h in result.headings if h.level == 3]
        assert any("AI SEO" in t for t in h3_texts), "Should capture FAQ question headings"


# ============================================================================
# Structure Analysis Validation
# ============================================================================


class TestStructureAnalysisAccuracy:
    """Verify structure analysis produces CORRECT results."""

    def test_detects_faq_sections_correctly(self):
        """Should detect FAQ sections in well-structured content."""
        analyzer = StructureAnalyzer()
        result = analyzer.analyze(WELL_STRUCTURED_BLOG, "https://example.com/blog/ai-seo")

        # Ground truth: This page has a clear FAQ section with Q&A format
        # FAQAnalysis uses has_faq_section (bool) and faq_count (int)
        assert result.faq.has_faq_section, "Should detect FAQ section"
        # The FAQ has at least 2 questions (question headings ending with ?)
        assert (
            result.faq.faq_count >= 2
        ), f"Should detect at least 2 FAQ questions, got {result.faq.faq_count}"

    def test_detects_answer_first_pattern(self):
        """Should detect when answer is in first paragraph."""
        analyzer = StructureAnalyzer()
        result = analyzer.analyze(WELL_STRUCTURED_BLOG, "https://example.com/blog/ai-seo")

        # Ground truth: First paragraph contains the answer/summary
        # "AI search engines are changing how users find information. Here's what you need to know..."
        # AnswerFirstAnalysis uses answer_in_first_paragraph (bool)
        assert result.answer_first.answer_in_first_paragraph, "Should detect answer-first pattern"

    def test_detects_poor_structure(self):
        """Should detect poor structure in SPA-style pages."""
        analyzer = StructureAnalyzer()
        result = analyzer.analyze(POORLY_STRUCTURED_SPA, "https://example.com/products")

        # Ground truth: No semantic structure, no FAQs, no clear answers
        assert not result.faq.has_faq_section, "Should detect no FAQ section"

    def test_counts_internal_links_correctly(self):
        """Should correctly count internal vs external links."""
        html_with_links = """
        <html><body>
            <a href="/about">About</a>
            <a href="/products">Products</a>
            <a href="/contact">Contact</a>
            <a href="https://external.com">External</a>
            <a href="https://another-external.com">Another External</a>
        </body></html>
        """
        analyzer = StructureAnalyzer()
        result = analyzer.analyze(html_with_links, "https://example.com/page")

        # Ground truth: 3 internal links, 2 external links
        # StructureAnalysis has links.internal_links and links.external_links
        assert (
            result.links.internal_links == 3
        ), f"Should detect 3 internal links, got {result.links.internal_links}"
        assert (
            result.links.external_links == 2
        ), f"Should detect 2 external links, got {result.links.external_links}"


# ============================================================================
# Schema Extraction Validation
# ============================================================================


class TestSchemaExtractionAccuracy:
    """Verify schema extraction produces CORRECT results."""

    def test_extracts_article_schema_correctly(self):
        """Should correctly extract Article schema with author."""
        analyzer = SchemaAnalyzer()
        result = analyzer.analyze(WELL_STRUCTURED_BLOG, "https://example.com/blog")

        # Ground truth: Has Article schema with author "Sarah Chen"
        assert result.has_article, "Should detect Article schema"
        assert result.has_author, "Should detect author in Article schema"
        assert "Sarah Chen" in (
            result.author_name or ""
        ), f"Author should be Sarah Chen, got {result.author_name}"

    def test_extracts_faq_schema_correctly(self):
        """Should correctly extract FAQPage schema with questions."""
        analyzer = SchemaAnalyzer()
        result = analyzer.analyze(RICH_SCHEMA_PAGE, "https://example.com/product")

        # Ground truth: Has FAQPage with 2 questions
        assert result.has_faq_page, "Should detect FAQPage schema"
        assert result.faq_count == 2, f"Should have 2 FAQ questions, got {result.faq_count}"

        # Verify question content
        question_texts = [item.question for item in result.faq_items]
        assert any("warranty" in q.lower() for q in question_texts), "Should have warranty question"
        assert any("shipping" in q.lower() for q in question_texts), "Should have shipping question"

    def test_extracts_date_modified(self):
        """Should correctly extract dateModified."""
        analyzer = SchemaAnalyzer()
        result = analyzer.analyze(WELL_STRUCTURED_BLOG, "https://example.com/blog")

        # Ground truth: dateModified is 2026-01-28
        assert result.has_date_modified, "Should detect dateModified"
        assert "2026-01-28" in str(
            result.date_modified
        ), f"dateModified should contain 2026-01-28, got {result.date_modified}"

    def test_extracts_organization_schema(self):
        """Should correctly extract Organization schema."""
        analyzer = SchemaAnalyzer()
        result = analyzer.analyze(RICH_SCHEMA_PAGE, "https://example.com/product")

        # Ground truth: Has Organization schema for "Widget Corp"
        assert result.has_organization, "Should detect Organization schema"

    def test_detects_missing_schema_correctly(self):
        """Should correctly detect when schema is missing."""
        analyzer = SchemaAnalyzer()
        result = analyzer.analyze(POORLY_STRUCTURED_SPA, "https://example.com/spa")

        # Ground truth: No schema markup at all
        assert not result.has_article, "Should detect no Article schema"
        assert not result.has_faq_page, "Should detect no FAQPage schema"
        assert not result.has_organization, "Should detect no Organization schema"
        assert result.total_schemas == 0, "Should have no schemas"


# ============================================================================
# Authority Analysis Validation
# ============================================================================


class TestAuthorityAnalysisAccuracy:
    """Verify authority signal detection is CORRECT."""

    def test_detects_author_correctly(self):
        """Should correctly detect author name and credentials."""
        analyzer = AuthorityAnalyzer()
        result = analyzer.analyze(
            AUTHORITATIVE_HEALTH_PAGE,
            "https://example.com/health/diabetes",
            "Diabetes affects millions...",
        )

        # Ground truth: Author is "Dr. Michael Roberts, MD, PhD"
        assert result.has_author, "Should detect author"
        assert result.primary_author is not None, "Should have primary author"

        # Check author name
        author_name = result.primary_author.name
        assert (
            "Michael Roberts" in author_name or "Roberts" in author_name
        ), f"Should detect Dr. Michael Roberts, got {author_name}"

    def test_detects_credentials_correctly(self):
        """Should correctly detect author credentials."""
        analyzer = AuthorityAnalyzer()
        result = analyzer.analyze(
            AUTHORITATIVE_HEALTH_PAGE,
            "https://example.com/health/diabetes",
            "Diabetes affects millions...",
        )

        # Ground truth: Has MD, PhD, Board-Certified credentials
        assert result.has_credentials, "Should detect credentials"

        # Check for credential markers
        credentials = result.credentials_found
        assert any(
            "MD" in c or "PhD" in c or "Board" in c for c in credentials
        ), f"Should detect medical credentials, got {credentials}"

    def test_detects_citations_correctly(self):
        """Should correctly detect citations to authoritative sources."""
        analyzer = AuthorityAnalyzer()
        result = analyzer.analyze(
            AUTHORITATIVE_HEALTH_PAGE,
            "https://example.com/health/diabetes",
            "According to the CDC...",
        )

        # Ground truth: Links to CDC and NEJM
        # AuthorityAnalysis uses total_citations (int)
        assert (
            result.total_citations >= 2
        ), f"Should detect at least 2 citations, got {result.total_citations}"

        # Check citation domains
        citation_urls = [c.url for c in result.citations]
        assert any(
            "cdc.gov" in url for url in citation_urls
        ), f"Should detect CDC citation, got {citation_urls}"

    def test_detects_original_research_markers(self):
        """Should detect original research/data markers."""
        analyzer = AuthorityAnalyzer()
        # Don't pass main_content - let analyzer extract from HTML to get full text
        result = analyzer.analyze(
            AUTHORITATIVE_HEALTH_PAGE,
            "https://example.com/health/diabetes",
        )

        # Ground truth: HTML contains "Our Research", "we found", "our clinical trial data"
        assert result.has_original_data, "Should detect original research markers"

        markers = result.original_data_markers
        assert len(markers) >= 1, f"Should have original data markers, got {markers}"

    def test_detects_visible_date_correctly(self):
        """Should detect visible publication/update dates."""
        analyzer = AuthorityAnalyzer()
        result = analyzer.analyze(
            AUTHORITATIVE_HEALTH_PAGE, "https://example.com/health/diabetes", ""
        )

        # Ground truth: Has "Medically reviewed on January 20, 2026"
        assert result.has_visible_date, "Should detect visible date"

    def test_detects_missing_authority_signals(self):
        """Should correctly flag missing authority signals."""
        analyzer = AuthorityAnalyzer()
        result = analyzer.analyze(
            POORLY_STRUCTURED_SPA, "https://example.com/products", "Welcome to our amazing platform"
        )

        # Ground truth: No author, no credentials, no citations, no dates
        assert not result.has_author, "Should detect no author"
        assert not result.has_credentials, "Should detect no credentials"
        assert result.total_citations == 0, "Should detect no citations"
        assert not result.has_original_data, "Should detect no original data"


# ============================================================================
# Integration: Full Pipeline Accuracy
# ============================================================================


class TestFullPipelineAccuracy:
    """Test that the full analysis pipeline produces correct results."""

    def test_good_page_scores_higher_than_bad_page(self):
        """Well-structured authoritative page should score higher than SPA."""
        from worker.scoring.authority import calculate_authority_score
        from worker.scoring.schema import calculate_schema_score
        from worker.scoring.structure import calculate_structure_score

        # Analyze good page
        good_structure = StructureAnalyzer().analyze(
            WELL_STRUCTURED_BLOG, "https://example.com/good"
        )
        good_schema = SchemaAnalyzer().analyze(WELL_STRUCTURED_BLOG, "https://example.com/good")
        good_authority = AuthorityAnalyzer().analyze(
            WELL_STRUCTURED_BLOG, "https://example.com/good", ""
        )

        good_structure_score = calculate_structure_score(good_structure)
        good_schema_score = calculate_schema_score(good_schema)
        good_authority_score = calculate_authority_score(good_authority)

        # Analyze bad page
        bad_structure = StructureAnalyzer().analyze(
            POORLY_STRUCTURED_SPA, "https://example.com/bad"
        )
        bad_schema = SchemaAnalyzer().analyze(POORLY_STRUCTURED_SPA, "https://example.com/bad")
        bad_authority = AuthorityAnalyzer().analyze(
            POORLY_STRUCTURED_SPA, "https://example.com/bad", ""
        )

        bad_structure_score = calculate_structure_score(bad_structure)
        bad_schema_score = calculate_schema_score(bad_schema)
        bad_authority_score = calculate_authority_score(bad_authority)

        # Ground truth: Good page should score significantly higher
        assert (
            good_structure_score.total_score > bad_structure_score.total_score + 15
        ), f"Good structure ({good_structure_score.total_score}) should be 15+ pts higher than bad ({bad_structure_score.total_score})"

        assert (
            good_schema_score.total_score > bad_schema_score.total_score + 20
        ), f"Good schema ({good_schema_score.total_score}) should be 20+ pts higher than bad ({bad_schema_score.total_score})"

        assert (
            good_authority_score.total_score > bad_authority_score.total_score + 15
        ), f"Good authority ({good_authority_score.total_score}) should be 15+ pts higher than bad ({bad_authority_score.total_score})"
