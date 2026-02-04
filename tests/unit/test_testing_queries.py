"""Tests for test queries module."""

from worker.testing.queries import (
    BRAND_QUERIES,
    HOW_TO_QUERIES,
    INFORMATIONAL_QUERIES,
    TECHNICAL_QUERIES,
    TEST_QUERIES,
    TOOL_COMPARISON_QUERIES,
    QueryCategory,
    TestQuery,
    get_geo_queries,
    get_queries_by_category,
    get_queries_for_domain,
)


class TestTestQuery:
    """Tests for TestQuery dataclass."""

    def test_create_test_query(self):
        """TestQuery can be created with required fields."""
        query = TestQuery(
            query="what is SEO",
            category=QueryCategory.INFORMATIONAL,
        )

        assert query.query == "what is SEO"
        assert query.category == QueryCategory.INFORMATIONAL

    def test_default_values(self):
        """TestQuery has correct default values."""
        query = TestQuery(
            query="test query",
            category=QueryCategory.INFORMATIONAL,
        )

        assert query.expected_sources == []
        assert query.difficulty == "medium"
        assert query.notes == ""

    def test_query_hashable(self):
        """TestQuery is hashable (for use in sets)."""
        query1 = TestQuery(query="test", category=QueryCategory.INFORMATIONAL)
        query2 = TestQuery(query="test", category=QueryCategory.INFORMATIONAL)

        # Same query should hash the same
        assert hash(query1) == hash(query2)

        # Can be used in set
        query_set = {query1, query2}
        assert len(query_set) == 1

    def test_query_equality(self):
        """TestQuery equality is based on query string."""
        query1 = TestQuery(query="test", category=QueryCategory.INFORMATIONAL)
        query2 = TestQuery(query="test", category=QueryCategory.HOW_TO)

        # Same query string = equal
        assert query1 == query2


class TestQueryCategory:
    """Tests for QueryCategory enum."""

    def test_category_values(self):
        """QueryCategory has correct values."""
        assert QueryCategory.INFORMATIONAL.value == "informational"
        assert QueryCategory.TOOL_COMPARISON.value == "tool_comparison"
        assert QueryCategory.HOW_TO.value == "how_to"
        assert QueryCategory.TECHNICAL.value == "technical"
        assert QueryCategory.BRAND.value == "brand"


class TestPredefinedQueries:
    """Tests for predefined query data."""

    def test_test_queries_not_empty(self):
        """TEST_QUERIES list is not empty."""
        assert len(TEST_QUERIES) > 0

    def test_informational_queries_not_empty(self):
        """Informational queries list is not empty."""
        assert len(INFORMATIONAL_QUERIES) > 0

    def test_tool_comparison_queries_not_empty(self):
        """Tool comparison queries list is not empty."""
        assert len(TOOL_COMPARISON_QUERIES) > 0

    def test_how_to_queries_not_empty(self):
        """How-to queries list is not empty."""
        assert len(HOW_TO_QUERIES) > 0

    def test_technical_queries_not_empty(self):
        """Technical queries list is not empty."""
        assert len(TECHNICAL_QUERIES) > 0

    def test_brand_queries_not_empty(self):
        """Brand queries list is not empty."""
        assert len(BRAND_QUERIES) > 0

    def test_all_queries_have_categories(self):
        """All queries have valid categories."""
        for query in TEST_QUERIES:
            assert isinstance(query.category, QueryCategory)

    def test_all_queries_have_query_text(self):
        """All queries have non-empty query text."""
        for query in TEST_QUERIES:
            assert query.query
            assert len(query.query) > 5  # Reasonable minimum length

    def test_unique_queries(self):
        """All queries are unique."""
        query_texts = [q.query for q in TEST_QUERIES]
        assert len(query_texts) == len(set(query_texts)), "Duplicate queries found"

    def test_informational_queries_are_informational(self):
        """All informational queries have correct category."""
        for query in INFORMATIONAL_QUERIES:
            assert query.category == QueryCategory.INFORMATIONAL

    def test_how_to_queries_are_how_to(self):
        """All how-to queries have correct category."""
        for query in HOW_TO_QUERIES:
            assert query.category == QueryCategory.HOW_TO


class TestQueryHelpers:
    """Tests for query helper functions."""

    def test_get_queries_by_category_informational(self):
        """get_queries_by_category returns informational queries."""
        queries = get_queries_by_category(QueryCategory.INFORMATIONAL)

        assert len(queries) > 0
        for query in queries:
            assert query.category == QueryCategory.INFORMATIONAL

    def test_get_queries_by_category_how_to(self):
        """get_queries_by_category returns how-to queries."""
        queries = get_queries_by_category(QueryCategory.HOW_TO)

        assert len(queries) > 0
        for query in queries:
            assert query.category == QueryCategory.HOW_TO

    def test_get_queries_for_domain_moz(self):
        """get_queries_for_domain returns queries expecting Moz."""
        queries = get_queries_for_domain("moz.com")

        assert len(queries) > 0
        for query in queries:
            assert any("moz" in src.lower() for src in query.expected_sources)

    def test_get_queries_for_domain_schema_org(self):
        """get_queries_for_domain returns queries expecting schema.org."""
        queries = get_queries_for_domain("schema.org")

        assert len(queries) > 0
        for query in queries:
            assert any("schema.org" in src.lower() for src in query.expected_sources)

    def test_get_queries_for_domain_unknown(self):
        """get_queries_for_domain returns empty for unknown domain."""
        queries = get_queries_for_domain("unknown-domain-xyz.com")

        assert len(queries) == 0

    def test_get_geo_queries(self):
        """get_geo_queries returns GEO-related queries."""
        queries = get_geo_queries()

        assert len(queries) > 0
        # At least some should contain GEO-related terms
        geo_terms = ["geo", "generative engine", "ai search", "ai visibility"]
        has_geo_term = False
        for query in queries:
            if any(term in query.query.lower() for term in geo_terms):
                has_geo_term = True
                break
        assert has_geo_term


class TestQueryQuality:
    """Tests for query data quality."""

    def test_expected_sources_are_domains(self):
        """Expected sources should be domain names."""
        for query in TEST_QUERIES:
            for source in query.expected_sources:
                # Should look like a domain (has a dot, no spaces)
                assert "." in source
                assert " " not in source

    def test_difficulty_values_valid(self):
        """Difficulty values are valid."""
        valid_difficulties = {"easy", "medium", "hard"}
        for query in TEST_QUERIES:
            assert query.difficulty in valid_difficulties

    def test_category_distribution_reasonable(self):
        """Categories are reasonably distributed."""
        category_counts = {}
        for query in TEST_QUERIES:
            cat = query.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1

        # Each category should have at least some queries
        for cat in QueryCategory:
            assert category_counts.get(cat.value, 0) > 0, f"No queries for {cat}"

    def test_queries_cover_key_topics(self):
        """Queries cover key topics we care about."""
        all_query_text = " ".join(q.query.lower() for q in TEST_QUERIES)

        key_topics = [
            "seo",
            "schema",
            "ai",
            "marketing",
        ]

        for topic in key_topics:
            assert topic in all_query_text, f"No queries about {topic}"
