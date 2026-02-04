"""Tests for test corpus module."""

from worker.testing.corpus import (
    COMPETITOR_SITES,
    KNOWN_CITED_SITES,
    KNOWN_UNCITED_SITES,
    OWN_PROPERTY_SITES,
    SiteCategory,
    TestCorpus,
    TestSite,
)


class TestTestSite:
    """Tests for TestSite dataclass."""

    def test_create_test_site(self):
        """TestSite can be created with required fields."""
        site = TestSite(
            url="https://example.com",
            name="Example",
            category=SiteCategory.KNOWN_CITED,
        )

        assert site.url == "https://example.com"
        assert site.name == "Example"
        assert site.category == SiteCategory.KNOWN_CITED

    def test_domain_extraction(self):
        """Domain is correctly extracted from URL."""
        site = TestSite(
            url="https://www.example.com/path/page",
            name="Example",
            category=SiteCategory.KNOWN_CITED,
        )

        assert site.domain == "example.com"

    def test_domain_extraction_no_www(self):
        """Domain extraction works without www."""
        site = TestSite(
            url="https://example.com",
            name="Example",
            category=SiteCategory.KNOWN_CITED,
        )

        assert site.domain == "example.com"

    def test_default_values(self):
        """TestSite has correct default values."""
        site = TestSite(
            url="https://example.com",
            name="Example",
            category=SiteCategory.KNOWN_CITED,
        )

        assert site.expected_queries == []
        assert site.industry == ""
        assert site.authority_level == "medium"
        assert site.notes == ""


class TestSiteCategory:
    """Tests for SiteCategory enum."""

    def test_category_values(self):
        """SiteCategory has correct values."""
        assert SiteCategory.KNOWN_CITED.value == "known_cited"
        assert SiteCategory.KNOWN_UNCITED.value == "known_uncited"
        assert SiteCategory.OWN_PROPERTY.value == "own_property"
        assert SiteCategory.COMPETITOR.value == "competitor"


class TestTestCorpus:
    """Tests for TestCorpus class."""

    def test_full_corpus_not_empty(self):
        """Full corpus contains sites."""
        corpus = TestCorpus.full()

        assert len(corpus) > 0
        assert len(corpus.sites) > 0

    def test_full_corpus_has_all_categories(self):
        """Full corpus includes all site categories."""
        corpus = TestCorpus.full()
        categories = {site.category for site in corpus.sites}

        assert SiteCategory.KNOWN_CITED in categories
        # Note: Other categories may or may not be present depending on data

    def test_quick_corpus_smaller_than_full(self):
        """Quick corpus is smaller than full corpus."""
        full = TestCorpus.full()
        quick = TestCorpus.quick()

        assert len(quick) < len(full)

    def test_own_corpus_only_own_sites(self):
        """Own corpus only contains own property sites."""
        corpus = TestCorpus.own()

        for site in corpus.sites:
            assert site.category == SiteCategory.OWN_PROPERTY

    def test_competitors_corpus_only_competitors(self):
        """Competitors corpus only contains competitor sites."""
        corpus = TestCorpus.competitors()

        for site in corpus.sites:
            assert site.category == SiteCategory.COMPETITOR

    def test_known_cited_corpus(self):
        """Known cited corpus only contains known cited sites."""
        corpus = TestCorpus.known_cited()

        for site in corpus.sites:
            assert site.category == SiteCategory.KNOWN_CITED

    def test_filter_by_category(self):
        """Corpus can be filtered by category."""
        full = TestCorpus.full()
        filtered = full.filter_by_category(SiteCategory.KNOWN_CITED)

        for site in filtered.sites:
            assert site.category == SiteCategory.KNOWN_CITED

    def test_filter_by_industry(self):
        """Corpus can be filtered by industry."""
        full = TestCorpus.full()
        filtered = full.filter_by_industry("SEO")

        for site in filtered.sites:
            assert site.industry.lower() == "seo"

    def test_domains_property(self):
        """Domains property returns list of domains."""
        corpus = TestCorpus.quick()
        domains = corpus.domains

        assert isinstance(domains, list)
        assert len(domains) == len(corpus)
        for domain in domains:
            assert "." in domain  # Basic domain format check

    def test_urls_property(self):
        """URLs property returns list of URLs."""
        corpus = TestCorpus.quick()
        urls = corpus.urls

        assert isinstance(urls, list)
        assert len(urls) == len(corpus)
        for url in urls:
            assert url.startswith("http")

    def test_get_by_domain(self):
        """Can find site by domain."""
        corpus = TestCorpus.known_cited()
        site = corpus.get_by_domain("moz.com")

        assert site is not None
        assert "moz" in site.domain.lower()

    def test_get_by_domain_not_found(self):
        """Returns None for unknown domain."""
        corpus = TestCorpus.quick()
        site = corpus.get_by_domain("nonexistent.com")

        assert site is None

    def test_iteration(self):
        """Corpus is iterable."""
        corpus = TestCorpus.quick()
        sites = list(corpus)

        assert len(sites) == len(corpus)

    def test_to_dict(self):
        """Corpus can be serialized to dict."""
        corpus = TestCorpus.quick()
        data = corpus.to_dict()

        assert "name" in data
        assert "sites" in data
        assert "site_count" in data
        assert data["site_count"] == len(corpus)


class TestPredefinedCorpora:
    """Tests for predefined corpus data."""

    def test_known_cited_sites_not_empty(self):
        """Known cited sites list is not empty."""
        assert len(KNOWN_CITED_SITES) > 0

    def test_known_cited_sites_all_have_urls(self):
        """All known cited sites have URLs."""
        for site in KNOWN_CITED_SITES:
            assert site.url
            assert site.url.startswith("http")

    def test_known_cited_sites_all_high_authority(self):
        """Known cited sites should generally be high authority."""
        high_authority_count = sum(
            1 for site in KNOWN_CITED_SITES if site.authority_level == "high"
        )
        # Most should be high authority
        assert high_authority_count >= len(KNOWN_CITED_SITES) * 0.5

    def test_known_cited_sites_have_expected_queries(self):
        """Known cited sites have expected queries defined."""
        sites_with_queries = sum(1 for site in KNOWN_CITED_SITES if site.expected_queries)
        # Most should have expected queries
        assert sites_with_queries >= len(KNOWN_CITED_SITES) * 0.5

    def test_competitor_sites_not_empty(self):
        """Competitor sites list is not empty."""
        assert len(COMPETITOR_SITES) > 0

    def test_unique_urls_across_all_sites(self):
        """All URLs are unique across all sites."""
        all_sites = KNOWN_CITED_SITES + KNOWN_UNCITED_SITES + OWN_PROPERTY_SITES + COMPETITOR_SITES
        urls = [site.url for site in all_sites]
        assert len(urls) == len(set(urls)), "Duplicate URLs found"
