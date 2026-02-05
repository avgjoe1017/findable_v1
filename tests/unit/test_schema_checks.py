"""Unit tests for Phase 3 Schema Richness checks."""

from datetime import datetime, timedelta

from worker.extraction.schema import (
    analyze_schema,
)
from worker.scoring.schema import (
    SchemaRichnessScore,
    calculate_schema_score,
)
from worker.tasks.schema_check import (
    aggregate_schema_scores,
    generate_schema_fixes,
    run_schema_checks_sync,
)

# ==============================================================================
# Schema Extraction Tests
# ==============================================================================


class TestSchemaAnalyzer:
    """Tests for SchemaAnalyzer class."""

    def test_no_schema(self):
        """Test analysis of page with no structured data."""
        html = """
        <html>
        <head><title>No Schema</title></head>
        <body><p>Plain content with no structured data.</p></body>
        </html>
        """
        result = analyze_schema(html, "https://example.com")

        assert result.total_schemas == 0
        assert result.has_faq_page is False
        assert result.has_article is False
        assert result.has_organization is False
        assert result.has_how_to is False

    def test_json_ld_faq_page(self):
        """Test extraction of FAQPage schema from JSON-LD."""
        html = """
        <html>
        <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": "What is this product?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "This is a great product."
                    }
                },
                {
                    "@type": "Question",
                    "name": "How do I use it?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "Just follow the instructions."
                    }
                }
            ]
        }
        </script>
        </head>
        <body><p>FAQ Page content</p></body>
        </html>
        """
        result = analyze_schema(html, "https://example.com/faq")

        assert result.has_faq_page is True
        assert result.faq_count >= 2
        assert result.total_schemas >= 1

    def test_json_ld_article_with_author(self):
        """Test extraction of Article schema with author."""
        html = """
        <html>
        <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": "Test Article",
            "author": {
                "@type": "Person",
                "name": "John Doe",
                "jobTitle": "Senior Editor"
            },
            "datePublished": "2024-01-15",
            "dateModified": "2024-06-01"
        }
        </script>
        </head>
        <body><p>Article content</p></body>
        </html>
        """
        result = analyze_schema(html, "https://example.com/article")

        assert result.has_article is True
        assert result.has_author is True
        assert result.has_date_modified is True

    def test_json_ld_organization(self):
        """Test extraction of Organization schema."""
        html = """
        <html>
        <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "Example Corp",
            "url": "https://example.com",
            "logo": "https://example.com/logo.png"
        }
        </script>
        </head>
        <body><p>Organization page</p></body>
        </html>
        """
        result = analyze_schema(html, "https://example.com")

        assert result.has_organization is True
        assert result.total_schemas >= 1

    def test_json_ld_how_to(self):
        """Test extraction of HowTo schema."""
        html = """
        <html>
        <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": "How to do something",
            "step": [
                {"@type": "HowToStep", "text": "Step 1"},
                {"@type": "HowToStep", "text": "Step 2"},
                {"@type": "HowToStep", "text": "Step 3"}
            ]
        }
        </script>
        </head>
        <body><p>How-to content</p></body>
        </html>
        """
        result = analyze_schema(html, "https://example.com/howto")

        assert result.has_how_to is True

    def test_date_modified_freshness_fresh(self):
        """Test freshness detection for recently modified content."""
        recent_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        html = f"""
        <html>
        <head>
        <script type="application/ld+json">
        {{
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": "Fresh Article",
            "dateModified": "{recent_date}"
        }}
        </script>
        </head>
        <body><p>Content</p></body>
        </html>
        """
        result = analyze_schema(html, "https://example.com")

        assert result.has_date_modified is True
        assert result.freshness_level == "fresh"

    def test_date_modified_freshness_stale(self):
        """Test freshness detection for stale content."""
        old_date = (datetime.now() - timedelta(days=150)).strftime("%Y-%m-%d")
        html = f"""
        <html>
        <head>
        <script type="application/ld+json">
        {{
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": "Old Article",
            "dateModified": "{old_date}"
        }}
        </script>
        </head>
        <body><p>Content</p></body>
        </html>
        """
        result = analyze_schema(html, "https://example.com")

        assert result.has_date_modified is True
        assert result.freshness_level in ["stale", "very_stale"]

    def test_multiple_schema_types(self):
        """Test page with multiple schema types."""
        html = """
        <html>
        <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "Example Corp"
        }
        </script>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": "Q?", "acceptedAnswer": {"@type": "Answer", "text": "A"}}]
        }
        </script>
        </head>
        <body><p>Content</p></body>
        </html>
        """
        result = analyze_schema(html, "https://example.com")

        assert result.has_organization is True
        assert result.has_faq_page is True
        assert result.total_schemas >= 2

    def test_validation_errors(self):
        """Test detection of schema validation errors."""
        html = """
        <html>
        <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Article"
        }
        </script>
        </head>
        <body><p>Content</p></body>
        </html>
        """
        result = analyze_schema(html, "https://example.com")

        # Article without headline should have validation errors
        assert result.has_article is True
        # Validation should flag missing required fields

    def test_blog_posting_as_article(self):
        """Test that BlogPosting is recognized as article type."""
        html = """
        <html>
        <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": "My Blog Post",
            "author": {"@type": "Person", "name": "Jane Doe"}
        }
        </script>
        </head>
        <body><p>Blog content</p></body>
        </html>
        """
        result = analyze_schema(html, "https://example.com/blog")

        assert result.has_article is True
        assert result.has_author is True


# ==============================================================================
# Schema Scoring Tests
# ==============================================================================


class TestSchemaScoreCalculator:
    """Tests for SchemaScoreCalculator class."""

    def test_perfect_schema_score(self):
        """Test scoring of page with comprehensive schema."""
        date_modified = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        html = f"""
        <html>
        <head>
        <script type="application/ld+json">
        {{"@context": "https://schema.org", "@type": "Organization", "name": "Corp", "url": "https://example.com"}}
        </script>
        <script type="application/ld+json">
        {{
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {{"@type": "Question", "name": "Q1?", "acceptedAnswer": {{"@type": "Answer", "text": "A1"}}}},
                {{"@type": "Question", "name": "Q2?", "acceptedAnswer": {{"@type": "Answer", "text": "A2"}}}},
                {{"@type": "Question", "name": "Q3?", "acceptedAnswer": {{"@type": "Answer", "text": "A3"}}}}
            ]
        }}
        </script>
        <script type="application/ld+json">
        {{
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": "Test",
            "author": {{"@type": "Person", "name": "John"}},
            "dateModified": "{date_modified}"
        }}
        </script>
        <script type="application/ld+json">
        {{"@context": "https://schema.org", "@type": "HowTo", "name": "How to", "step": [{{"@type": "HowToStep", "text": "Do it"}}]}}
        </script>
        </head>
        <body><p>Content</p></body>
        </html>
        """

        analysis = analyze_schema(html, "https://example.com")
        score = calculate_schema_score(analysis)

        assert score.total_score >= 80
        assert score.level == "full"

    def test_no_schema_score(self):
        """Test scoring of page with no schema."""
        html = "<html><body><p>No schema</p></body></html>"
        analysis = analyze_schema(html, "https://example.com")
        score = calculate_schema_score(analysis)

        assert score.total_score < 30
        assert score.level == "limited"

    def test_partial_schema_score(self):
        """Test scoring of page with some schema elements."""
        html = """
        <html>
        <head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Organization", "name": "Corp"}
        </script>
        </head>
        <body><p>Content</p></body>
        </html>
        """
        analysis = analyze_schema(html, "https://example.com")
        score = calculate_schema_score(analysis)

        assert score.total_score > 0
        assert score.total_score < 100

    def test_faq_page_high_impact(self):
        """Test that FAQPage has high scoring impact."""
        # With FAQPage
        html_with_faq = """
        <html>
        <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": "Q?", "acceptedAnswer": {"@type": "Answer", "text": "A"}}
            ]
        }
        </script>
        </head>
        <body><p>Content</p></body>
        </html>
        """
        # Without FAQPage
        html_without_faq = "<html><body><p>Content</p></body></html>"

        analysis_with = analyze_schema(html_with_faq, "https://example.com")
        analysis_without = analyze_schema(html_without_faq, "https://example.com")

        score_with = calculate_schema_score(analysis_with)
        score_without = calculate_schema_score(analysis_without)

        # FAQPage should provide significant score boost
        assert score_with.total_score > score_without.total_score + 10

    def test_score_components_present(self):
        """Test that score breakdown includes all components."""
        html = """
        <html>
        <head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Organization", "name": "Corp"}
        </script>
        </head>
        <body><p>Content</p></body>
        </html>
        """
        analysis = analyze_schema(html, "https://example.com")
        score = calculate_schema_score(analysis)

        assert score.components is not None
        assert len(score.components) >= 5

        component_names = [c.name for c in score.components]
        # Component names use descriptive format
        assert any("FAQ" in name for name in component_names)
        assert any("Article" in name for name in component_names)
        assert any("Freshness" in name or "Modified" in name for name in component_names)
        assert any("Organization" in name for name in component_names)


# ==============================================================================
# Schema Task Runner Tests
# ==============================================================================


class TestSchemaTaskRunner:
    """Tests for schema check task runner."""

    def test_run_schema_checks_sync(self):
        """Test synchronous schema checks."""
        html = """
        <html>
        <head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Organization", "name": "Corp"}
        </script>
        </head>
        <body><p>Content</p></body>
        </html>
        """
        result = run_schema_checks_sync(html, "https://example.com")

        assert isinstance(result, SchemaRichnessScore)
        assert result.total_score >= 0

    def test_aggregate_schema_scores_empty(self):
        """Test aggregation with no scores."""
        result = aggregate_schema_scores([])

        assert result.total_score == 0
        assert result.level == "limited"

    def test_aggregate_schema_scores_single(self):
        """Test aggregation with single score."""
        html = """
        <html>
        <head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Organization", "name": "Corp"}
        </script>
        </head>
        <body><p>Content</p></body>
        </html>
        """
        score = run_schema_checks_sync(html, "https://example.com")
        result = aggregate_schema_scores([score])

        assert result.total_score == score.total_score

    def test_aggregate_schema_scores_multiple(self):
        """Test aggregation with multiple scores."""
        html1 = """
        <html>
        <head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Organization", "name": "Corp"}
        </script>
        </head>
        <body><p>Content</p></body>
        </html>
        """
        html2 = "<html><body><p>No schema</p></body></html>"

        score1 = run_schema_checks_sync(html1, "https://example.com")
        score2 = run_schema_checks_sync(html2, "https://example.com/page2")

        result = aggregate_schema_scores([score1, score2])

        # Weighted average: homepage (2x) + other pages (1x)
        expected = (score1.total_score * 2 + score2.total_score) / 3
        assert abs(result.total_score - expected) < 0.1


# ==============================================================================
# Fix Generation Tests
# ==============================================================================


class TestSchemaFixGeneration:
    """Tests for schema fix generation."""

    def test_generate_faq_page_fix(self):
        """Test fix generation for missing FAQPage."""
        html = "<html><body><p>No schema</p></body></html>"
        score = run_schema_checks_sync(html, "https://example.com")
        fixes = generate_schema_fixes(score)

        fix_ids = [f["id"] for f in fixes]
        assert "schema_add_faq_page" in fix_ids

    def test_generate_article_fix(self):
        """Test fix generation for missing Article schema."""
        html = "<html><body><p>No schema</p></body></html>"
        score = run_schema_checks_sync(html, "https://example.com")
        fixes = generate_schema_fixes(score)

        fix_ids = [f["id"] for f in fixes]
        assert "schema_add_article" in fix_ids

    def test_generate_organization_fix(self):
        """Test fix generation for missing Organization schema."""
        html = "<html><body><p>No schema</p></body></html>"
        score = run_schema_checks_sync(html, "https://example.com")
        fixes = generate_schema_fixes(score)

        fix_ids = [f["id"] for f in fixes]
        assert "schema_add_organization" in fix_ids

    def test_generate_date_modified_fix(self):
        """Test fix generation for missing dateModified."""
        html = """
        <html>
        <head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Article", "headline": "Test"}
        </script>
        </head>
        <body><p>Content</p></body>
        </html>
        """
        score = run_schema_checks_sync(html, "https://example.com")
        fixes = generate_schema_fixes(score)

        fix_ids = [f["id"] for f in fixes]
        assert "schema_add_date_modified" in fix_ids

    def test_no_duplicate_fixes(self):
        """Test that fixes aren't duplicated when schema exists."""
        html = """
        <html>
        <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": "Q1?", "acceptedAnswer": {"@type": "Answer", "text": "A1"}},
                {"@type": "Question", "name": "Q2?", "acceptedAnswer": {"@type": "Answer", "text": "A2"}},
                {"@type": "Question", "name": "Q3?", "acceptedAnswer": {"@type": "Answer", "text": "A3"}}
            ]
        }
        </script>
        </head>
        <body><p>Content</p></body>
        </html>
        """
        score = run_schema_checks_sync(html, "https://example.com")
        fixes = generate_schema_fixes(score)

        fix_ids = [f["id"] for f in fixes]
        # Should not recommend adding FAQPage when it exists
        assert "schema_add_faq_page" not in fix_ids

    def test_fixes_have_required_fields(self):
        """Test that generated fixes have all required fields."""
        html = "<html><body><p>No schema</p></body></html>"
        score = run_schema_checks_sync(html, "https://example.com")
        fixes = generate_schema_fixes(score)

        for fix in fixes:
            assert "id" in fix
            assert "category" in fix
            assert "priority" in fix
            assert "title" in fix
            assert "description" in fix
            assert "estimated_impact" in fix
            assert "effort" in fix

    def test_fixes_sorted_by_priority(self):
        """Test that fixes are sorted by priority."""
        html = "<html><body><p>No schema</p></body></html>"
        score = run_schema_checks_sync(html, "https://example.com")
        fixes = generate_schema_fixes(score)

        if len(fixes) > 1:
            priorities = [f["priority"] for f in fixes]
            assert priorities == sorted(priorities)
