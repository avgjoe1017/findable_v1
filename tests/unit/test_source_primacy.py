"""Tests for source primacy detection."""

from worker.extraction.site_type import SiteType
from worker.extraction.source_primacy import (
    PRIMACY_CITATION_RATES,
    PrimacyLevel,
    SourcePrimacyResult,
    analyze_source_primacy,
)


class TestPrimacyLevel:
    """Tests for PrimacyLevel enum."""

    def test_primary_has_highest_citation_rate(self):
        assert (
            PRIMACY_CITATION_RATES[PrimacyLevel.PRIMARY]
            > PRIMACY_CITATION_RATES[PrimacyLevel.AUTHORITATIVE]
        )
        assert (
            PRIMACY_CITATION_RATES[PrimacyLevel.AUTHORITATIVE]
            > PRIMACY_CITATION_RATES[PrimacyLevel.DERIVATIVE]
        )


class TestSourcePrimacyResult:
    """Tests for SourcePrimacyResult dataclass."""

    def test_to_dict(self):
        result = SourcePrimacyResult(
            primacy_level=PrimacyLevel.PRIMARY,
            primacy_score=0.85,
            expected_citation_rate=0.90,
        )
        d = result.to_dict()
        assert d["primacy_level"] == "primary"
        assert d["primacy_score"] == 0.85
        assert d["expected_citation_rate"] == 0.90


class TestAnalyzeSourcePrimacy:
    """Tests for the main analysis function."""

    def test_documentation_site_is_primary(self):
        """Documentation sites should score as primary sources."""
        result = analyze_source_primacy(
            domain="docs.python.org",
            site_type=SiteType.DOCUMENTATION,
            page_urls=[
                "https://docs.python.org/3/library/",
                "https://docs.python.org/3/reference/",
                "https://docs.python.org/3/tutorial/",
            ],
            brand_name="Python",
        )
        assert result.primacy_level == PrimacyLevel.PRIMARY
        assert result.primacy_score >= 0.65

    def test_news_site_is_derivative(self):
        """News sites covering others' content should score as derivative."""
        result = analyze_source_primacy(
            domain="bbc.com",
            site_type=SiteType.NEWS_MEDIA,
            page_urls=[
                "https://bbc.com/news/technology",
                "https://bbc.com/news/business",
                "https://bbc.com/news/world",
            ],
        )
        assert result.primacy_level == PrimacyLevel.DERIVATIVE
        assert result.primacy_score < 0.40

    def test_saas_with_docs_is_authoritative(self):
        """SaaS sites with docs section should score as authoritative."""
        result = analyze_source_primacy(
            domain="stripe.com",
            site_type=SiteType.SAAS_MARKETING,
            page_urls=[
                "https://stripe.com/",
                "https://stripe.com/docs/api",
                "https://stripe.com/docs/getting-started",
                "https://stripe.com/pricing",
                "https://stripe.com/blog/new-feature",
            ],
            brand_name="Stripe",
        )
        # Should be at least authoritative due to docs + brand match
        assert result.primacy_level in (PrimacyLevel.PRIMARY, PrimacyLevel.AUTHORITATIVE)
        assert result.primacy_score >= 0.40

    def test_blog_with_reviews_is_derivative(self):
        """Blogs about others' products should score as derivative."""
        result = analyze_source_primacy(
            domain="reviewsite.com",
            site_type=SiteType.BLOG,
            page_urls=[
                "https://reviewsite.com/best-crm-tools",
                "https://reviewsite.com/alternatives-to-salesforce",
                "https://reviewsite.com/hubspot-vs-salesforce",
                "https://reviewsite.com/top-10-email-tools",
            ],
        )
        assert result.primacy_level == PrimacyLevel.DERIVATIVE
        assert result.primacy_score < 0.40

    def test_reference_site_is_primary(self):
        """Reference sites should score as primary."""
        result = analyze_source_primacy(
            domain="schema.org",
            site_type=SiteType.REFERENCE,
            page_urls=[
                "https://schema.org/",
                "https://schema.org/docs/documents.html",
            ],
        )
        assert result.primacy_level == PrimacyLevel.PRIMARY

    def test_returns_signals(self):
        """Result should include analysis signals."""
        result = analyze_source_primacy(
            domain="example.com",
            site_type=SiteType.MIXED,
            page_urls=["https://example.com/"],
        )
        assert len(result.signals) >= 3  # At least site_type, url_patterns, domain_alignment
        signal_names = [s.name for s in result.signals]
        assert "site_type" in signal_names
        assert "url_patterns" in signal_names

    def test_empty_urls_handled(self):
        """Should handle empty URL list gracefully."""
        result = analyze_source_primacy(
            domain="example.com",
            site_type=SiteType.MIXED,
            page_urls=[],
        )
        assert result.primacy_level in (
            PrimacyLevel.PRIMARY,
            PrimacyLevel.AUTHORITATIVE,
            PrimacyLevel.DERIVATIVE,
        )
        assert 0.0 <= result.primacy_score <= 1.0

    def test_brand_domain_match_boosts_primacy(self):
        """Brand name matching domain should increase primacy."""
        with_brand = analyze_source_primacy(
            domain="stripe.com",
            site_type=SiteType.SAAS_MARKETING,
            page_urls=["https://stripe.com/"],
            brand_name="Stripe",
        )
        without_brand = analyze_source_primacy(
            domain="stripe.com",
            site_type=SiteType.SAAS_MARKETING,
            page_urls=["https://stripe.com/"],
        )
        assert with_brand.primacy_score >= without_brand.primacy_score

    def test_expected_citation_rate_matches_level(self):
        """Expected citation rate should match the primacy level."""
        result = analyze_source_primacy(
            domain="docs.python.org",
            site_type=SiteType.DOCUMENTATION,
            page_urls=["https://docs.python.org/3/reference/"],
        )
        assert result.expected_citation_rate == PRIMACY_CITATION_RATES[result.primacy_level]
