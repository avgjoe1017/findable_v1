"""Tests for ground truth collection module."""

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from worker.testing.config import AIQueryConfig
from worker.testing.ground_truth import (
    CitedSource,
    GroundTruthResult,
    ProviderResponse,
    collect_ground_truth,
    collect_ground_truth_batch,
    extract_domains_from_text,
    get_cache_key,
    load_cached_result,
    query_provider_mock,
    save_cached_result,
)
from worker.testing.queries import QueryCategory, TestQuery


class TestCitedSource:
    """Tests for CitedSource dataclass."""

    def test_create_cited_source(self):
        """CitedSource can be created with required fields."""
        source = CitedSource(
            domain="moz.com",
            url="https://moz.com/blog",
            mention_type="cited",
        )

        assert source.domain == "moz.com"
        assert source.url == "https://moz.com/blog"
        assert source.mention_type == "cited"

    def test_to_dict(self):
        """CitedSource serializes correctly."""
        source = CitedSource(
            domain="example.com",
            url="https://example.com",
            mention_type="linked",
            context="See example.com for more info",
        )

        data = source.to_dict()

        assert data["domain"] == "example.com"
        assert data["mention_type"] == "linked"
        assert data["context"] == "See example.com for more info"

    def test_from_dict(self):
        """CitedSource deserializes correctly."""
        data = {
            "domain": "test.com",
            "url": "https://test.com",
            "mention_type": "mentioned",
            "context": "test context",
        }

        source = CitedSource.from_dict(data)

        assert source.domain == "test.com"
        assert source.mention_type == "mentioned"


class TestProviderResponse:
    """Tests for ProviderResponse dataclass."""

    def test_create_success_response(self):
        """ProviderResponse can be created for success."""
        response = ProviderResponse(
            provider="chatgpt",
            model="gpt-4o-mini",
            response_text="Here is some information...",
            cited_sources=[CitedSource(domain="example.com")],
            response_time_ms=500,
            tokens_used=100,
        )

        assert response.provider == "chatgpt"
        assert response.model == "gpt-4o-mini"
        assert len(response.cited_sources) == 1
        assert response.error is None

    def test_create_error_response(self):
        """ProviderResponse can be created for errors."""
        response = ProviderResponse(
            provider="perplexity",
            model="sonar",
            response_text="",
            error="Rate limit exceeded",
        )

        assert response.error == "Rate limit exceeded"
        assert response.response_text == ""

    def test_roundtrip_serialization(self):
        """ProviderResponse survives roundtrip serialization."""
        original = ProviderResponse(
            provider="claude",
            model="claude-3-haiku",
            response_text="Test response",
            cited_sources=[
                CitedSource(domain="a.com", mention_type="cited"),
                CitedSource(domain="b.com", mention_type="linked"),
            ],
            response_time_ms=250,
            tokens_used=75,
        )

        data = original.to_dict()
        restored = ProviderResponse.from_dict(data)

        assert restored.provider == original.provider
        assert len(restored.cited_sources) == len(original.cited_sources)
        assert restored.response_time_ms == original.response_time_ms


class TestGroundTruthResult:
    """Tests for GroundTruthResult dataclass."""

    def test_create_result(self):
        """GroundTruthResult can be created with basic fields."""
        result = GroundTruthResult(
            query="what is SEO",
            query_id="q-123",
            category="informational",
        )

        assert result.query == "what is SEO"
        assert result.category == "informational"
        assert result.provider_responses == []

    def test_compute_aggregates(self):
        """compute_aggregates correctly aggregates domains."""
        result = GroundTruthResult(
            query="test",
            query_id="q-1",
            category="informational",
            provider_responses=[
                ProviderResponse(
                    provider="chatgpt",
                    model="gpt-4",
                    response_text="...",
                    cited_sources=[
                        CitedSource(domain="moz.com"),
                        CitedSource(domain="ahrefs.com"),
                    ],
                ),
                ProviderResponse(
                    provider="claude",
                    model="claude-3",
                    response_text="...",
                    cited_sources=[
                        CitedSource(domain="moz.com"),
                        CitedSource(domain="semrush.com"),
                    ],
                ),
                ProviderResponse(
                    provider="perplexity",
                    model="sonar",
                    response_text="...",
                    cited_sources=[
                        CitedSource(domain="moz.com"),
                    ],
                ),
            ],
        )

        result.compute_aggregates()

        # moz.com appears in all 3
        assert "moz.com" in result.all_cited_domains
        assert "moz.com" in result.consensus_domains

        # ahrefs.com appears in 1 only
        assert "ahrefs.com" in result.all_cited_domains
        assert "ahrefs.com" not in result.consensus_domains

    def test_compute_aggregates_ignores_errors(self):
        """compute_aggregates ignores error responses."""
        result = GroundTruthResult(
            query="test",
            query_id="q-1",
            category="informational",
            provider_responses=[
                ProviderResponse(
                    provider="chatgpt",
                    model="gpt-4",
                    response_text="...",
                    cited_sources=[CitedSource(domain="good.com")],
                ),
                ProviderResponse(
                    provider="perplexity",
                    model="sonar",
                    response_text="",
                    error="API error",
                    cited_sources=[CitedSource(domain="shouldnt-count.com")],
                ),
            ],
        )

        result.compute_aggregates()

        assert "good.com" in result.all_cited_domains
        assert "shouldnt-count.com" not in result.all_cited_domains

    def test_roundtrip_serialization(self):
        """GroundTruthResult survives roundtrip serialization."""
        original = GroundTruthResult(
            query="test query",
            query_id="q-abc",
            category="technical",
            provider_responses=[
                ProviderResponse(
                    provider="chatgpt",
                    model="gpt-4",
                    response_text="response",
                    cited_sources=[CitedSource(domain="test.com")],
                )
            ],
            all_cited_domains=["test.com"],
            consensus_domains=[],
        )

        data = original.to_dict()
        restored = GroundTruthResult.from_dict(data)

        assert restored.query == original.query
        assert restored.category == original.category
        assert len(restored.provider_responses) == 1


class TestExtractDomainsFromText:
    """Tests for extract_domains_from_text function."""

    def test_extract_full_urls(self):
        """Extracts domains from full URLs."""
        text = "Check out https://moz.com/blog for more info."

        sources = extract_domains_from_text(text)

        assert len(sources) >= 1
        domains = [s.domain for s in sources]
        assert "moz.com" in domains

    def test_extract_www_urls(self):
        """Extracts domains from www URLs."""
        text = "Visit https://www.example.com/page for details."

        sources = extract_domains_from_text(text)

        domains = [s.domain for s in sources]
        assert "example.com" in domains

    def test_extract_domain_mentions(self):
        """Extracts domain mentions without protocol."""
        text = "You can find this at moz.com or ahrefs.com."

        sources = extract_domains_from_text(text)

        domains = [s.domain for s in sources]
        assert "moz.com" in domains
        assert "ahrefs.com" in domains

    def test_extract_reference_citations(self):
        """Extracts reference-style citations."""
        text = "According to [1] moz.com, SEO is important. Source: ahrefs.com"

        sources = extract_domains_from_text(text)

        domains = [s.domain for s in sources]
        assert "moz.com" in domains
        assert "ahrefs.com" in domains

    def test_no_duplicate_domains(self):
        """Doesn't return duplicate domains."""
        text = "Check moz.com and https://moz.com/blog and www.moz.com"

        sources = extract_domains_from_text(text)

        domains = [s.domain for s in sources]
        assert domains.count("moz.com") == 1

    def test_captures_context(self):
        """Captures context around mentions."""
        text = "According to experts at moz.com, this is important."

        sources = extract_domains_from_text(text)

        assert len(sources) >= 1
        assert "moz.com" in sources[0].context

    def test_categorizes_mention_types(self):
        """Correctly categorizes mention types."""
        text = "See https://linked.com/page for details"

        sources = extract_domains_from_text(text)

        types_by_domain = {s.domain: s.mention_type for s in sources}
        # Full URLs should be categorized as "linked"
        assert types_by_domain.get("linked.com") == "linked"

    def test_citation_pattern(self):
        """Recognizes citation patterns."""
        text = "Source: citation-only.com is authoritative"

        sources = extract_domains_from_text(text)

        # Should find the domain
        domains = [s.domain for s in sources]
        assert "citation-only.com" in domains


class TestCaching:
    """Tests for caching functions."""

    def test_cache_key_deterministic(self):
        """Cache key is deterministic."""
        key1 = get_cache_key("test query", ["chatgpt", "claude"])
        key2 = get_cache_key("test query", ["chatgpt", "claude"])

        assert key1 == key2

    def test_cache_key_varies_by_query(self):
        """Cache key varies by query."""
        key1 = get_cache_key("query 1", ["chatgpt"])
        key2 = get_cache_key("query 2", ["chatgpt"])

        assert key1 != key2

    def test_cache_key_varies_by_providers(self):
        """Cache key varies by providers."""
        key1 = get_cache_key("query", ["chatgpt"])
        key2 = get_cache_key("query", ["chatgpt", "claude"])

        assert key1 != key2

    def test_save_and_load_cached_result(self):
        """Can save and load cached results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)

            result = GroundTruthResult(
                query="test query",
                query_id="q-1",
                category="informational",
                all_cited_domains=["moz.com"],
            )

            # Save
            save_cached_result(result, ["chatgpt"], cache_dir)

            # Load
            loaded = load_cached_result("test query", ["chatgpt"], cache_dir, cache_ttl_hours=24)

            assert loaded is not None
            assert loaded.query == "test query"
            assert loaded.cached is True

    def test_load_returns_none_when_missing(self):
        """load_cached_result returns None when not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)

            result = load_cached_result("nonexistent", ["chatgpt"], cache_dir, 24)

            assert result is None

    def test_load_returns_none_when_expired(self):
        """load_cached_result returns None when expired."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)

            # Create expired cache entry
            result = GroundTruthResult(
                query="test",
                query_id="q-1",
                category="informational",
                queried_at="2020-01-01T00:00:00+00:00",  # Old timestamp
            )

            cache_key = get_cache_key("test", ["chatgpt"])
            cache_file = cache_dir / f"ground_truth_{cache_key}.json"
            cache_dir.mkdir(parents=True, exist_ok=True)
            with open(cache_file, "w") as f:
                json.dump(result.to_dict(), f)

            # Should return None due to expiry
            loaded = load_cached_result("test", ["chatgpt"], cache_dir, cache_ttl_hours=1)

            assert loaded is None


class TestQueryProviderMock:
    """Tests for mock provider."""

    @pytest.mark.asyncio
    async def test_mock_returns_response(self):
        """Mock provider returns a valid response."""
        response = await query_provider_mock("what is SEO", "chatgpt")

        assert response.provider == "chatgpt"
        assert response.error is None
        assert len(response.cited_sources) > 0
        assert len(response.response_text) > 0

    @pytest.mark.asyncio
    async def test_mock_seo_queries_return_seo_domains(self):
        """Mock returns SEO-related domains for SEO queries."""
        response = await query_provider_mock("what is SEO", "chatgpt")

        domains = [s.domain for s in response.cited_sources]
        assert any("moz" in d for d in domains) or any("ahrefs" in d for d in domains)

    @pytest.mark.asyncio
    async def test_mock_schema_queries_return_schema_domains(self):
        """Mock returns schema-related domains for schema queries."""
        response = await query_provider_mock("what is schema markup", "chatgpt")

        domains = [s.domain for s in response.cited_sources]
        assert any("schema" in d for d in domains) or any("google" in d for d in domains)


class TestCollectGroundTruth:
    """Tests for collect_ground_truth function."""

    @pytest.mark.asyncio
    async def test_uses_cache(self):
        """Uses cached results when available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            config = AIQueryConfig(cache_ttl_hours=24)

            # Pre-populate cache
            cached_result = GroundTruthResult(
                query="cached query",
                query_id="q-cached",
                category="informational",
                all_cited_domains=["cached.com"],
                queried_at=datetime.now(UTC).isoformat(),
            )
            save_cached_result(cached_result, ["chatgpt", "claude", "perplexity"], cache_dir)

            query = TestQuery(query="cached query", category=QueryCategory.INFORMATIONAL)

            # Should return cached result
            result = await collect_ground_truth(
                query=query,
                config=config,
                cache_dir=cache_dir,
                use_cache=True,
            )

            assert result.cached is True
            assert "cached.com" in result.all_cited_domains

    @pytest.mark.asyncio
    async def test_queries_configured_providers(self):
        """Only queries configured providers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            config = AIQueryConfig(
                query_chatgpt=True,
                query_claude=False,
                query_perplexity=False,
            )

            query = TestQuery(query="test", category=QueryCategory.INFORMATIONAL)

            result = await collect_ground_truth(
                query=query,
                config=config,
                cache_dir=cache_dir,
                use_cache=False,
            )

            # Should only have chatgpt response (mock)
            providers = [r.provider for r in result.provider_responses]
            assert "chatgpt" in providers
            assert "claude" not in providers


class TestCollectGroundTruthBatch:
    """Tests for collect_ground_truth_batch function."""

    @pytest.mark.asyncio
    async def test_processes_multiple_queries(self):
        """Processes multiple queries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            config = AIQueryConfig(query_chatgpt=True, query_claude=False, query_perplexity=False)

            queries = [
                TestQuery(query="what is SEO", category=QueryCategory.INFORMATIONAL),
                TestQuery(query="what is schema", category=QueryCategory.TECHNICAL),
            ]

            results = await collect_ground_truth_batch(
                queries=queries,
                config=config,
                cache_dir=cache_dir,
                use_cache=False,
                concurrency=2,
            )

            assert len(results) == 2
            assert results[0].query == "what is SEO"
            assert results[1].query == "what is schema"

    @pytest.mark.asyncio
    async def test_handles_exceptions(self):
        """Handles exceptions gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)

            queries = [
                TestQuery(query="good query", category=QueryCategory.INFORMATIONAL),
            ]

            with patch("worker.testing.ground_truth.collect_ground_truth") as mock_collect:
                mock_collect.side_effect = Exception("Network error")

                results = await collect_ground_truth_batch(
                    queries=queries,
                    cache_dir=cache_dir,
                    use_cache=False,
                )

                assert len(results) == 1
                assert any(r.error for r in results[0].provider_responses)
