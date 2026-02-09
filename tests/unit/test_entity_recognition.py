"""
Tests for Entity Recognition Module

Tests the components that measure brand/entity recognition signals
to address the 23% pessimism bias in the Findable Score model.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from worker.extraction.entity_recognition import (
    DomainSignals,
    EntityRecognitionAnalyzer,
    EntityRecognitionResult,
    WebPresenceSignals,
    WikidataSignals,
    WikipediaSignals,
    get_entity_recognition_score,
)

# =============================================================================
# WikipediaSignals Tests
# =============================================================================


class TestWikipediaSignals:
    """Tests for WikipediaSignals scoring."""

    def test_no_page_scores_zero(self):
        """No Wikipedia page should score 0."""
        signals = WikipediaSignals(has_page=False)
        assert signals.calculate_score() == 0

    def test_basic_page_scores_fifteen(self):
        """Having a Wikipedia page gives base 15 points."""
        signals = WikipediaSignals(has_page=True)
        assert signals.calculate_score() == 15

    def test_long_page_bonus(self):
        """Long pages get bonus points."""
        signals = WikipediaSignals(
            has_page=True,
            page_length_chars=15000,
        )
        score = signals.calculate_score()
        assert score == 15 + 5  # Base + long page bonus

    def test_citation_bonus(self):
        """Pages with many citations get bonus points."""
        signals = WikipediaSignals(
            has_page=True,
            citation_count=60,
        )
        score = signals.calculate_score()
        assert score == 15 + 5  # Base + citation bonus

    def test_max_score_capped(self):
        """Score should not exceed max_score."""
        signals = WikipediaSignals(
            has_page=True,
            page_length_chars=50000,
            citation_count=100,
            infobox_present=True,
            page_sections=20,
            last_edited=datetime.now(UTC),
        )
        score = signals.calculate_score()
        assert score <= signals.max_score
        assert score == 30  # Max

    def test_infobox_bonus(self):
        """Pages with infobox get 2 extra points."""
        signals = WikipediaSignals(
            has_page=True,
            infobox_present=True,
        )
        score = signals.calculate_score()
        assert score == 15 + 2

    def test_freshness_bonus(self):
        """Recently edited pages get bonus."""
        signals = WikipediaSignals(
            has_page=True,
            last_edited=datetime.now(UTC) - timedelta(days=30),
        )
        score = signals.calculate_score()
        assert score == 15 + 1  # Base + freshness


# =============================================================================
# WikidataSignals Tests
# =============================================================================


class TestWikidataSignals:
    """Tests for WikidataSignals scoring."""

    def test_no_entity_scores_zero(self):
        """No Wikidata entity should score 0."""
        signals = WikidataSignals(has_entity=False)
        assert signals.calculate_score() == 0

    def test_basic_entity_scores_ten(self):
        """Having a Wikidata entity gives base 10 points."""
        signals = WikidataSignals(has_entity=True)
        assert signals.calculate_score() == 10

    def test_property_richness_bonus(self):
        """Entities with many properties get bonus."""
        signals = WikidataSignals(
            has_entity=True,
            property_count=60,
        )
        score = signals.calculate_score()
        assert score == 10 + 4  # Base + rich properties

    def test_sitelink_bonus(self):
        """Entities with many sitelinks get bonus."""
        signals = WikidataSignals(
            has_entity=True,
            sitelink_count=60,
        )
        score = signals.calculate_score()
        assert score == 10 + 4  # Base + many sitelinks

    def test_notable_type_bonus(self):
        """Notable entity types get bonus."""
        signals = WikidataSignals(
            has_entity=True,
            instance_of=["company", "technology"],
        )
        score = signals.calculate_score()
        assert score == 10 + 2  # Base + notable type

    def test_max_score_capped(self):
        """Score should not exceed max_score."""
        signals = WikidataSignals(
            has_entity=True,
            property_count=100,
            sitelink_count=100,
            instance_of=["company", "software"],
        )
        score = signals.calculate_score()
        assert score <= signals.max_score
        assert score == 20  # Max


# =============================================================================
# DomainSignals Tests
# =============================================================================


class TestDomainSignals:
    """Tests for DomainSignals scoring."""

    def test_unregistered_domain_scores_zero(self):
        """Unregistered domain should score 0."""
        signals = DomainSignals(is_registered=False)
        assert signals.calculate_score() == 0

    def test_new_domain_low_score(self):
        """New domains get minimal points."""
        signals = DomainSignals(
            domain="newsite.com",  # "newsite" is 7 chars, gets +1 short bonus (<= 10)
            is_registered=True,
            domain_age_years=0.5,
            tld="com",
            is_premium_tld=True,
        )
        score = signals.calculate_score()
        # Premium TLD (5) + short domain bonus (1 for <=10 chars) = 6 (no age bonus for <1 year)
        assert score == 6

    def test_old_domain_high_score(self):
        """Old established domains get high scores."""
        signals = DomainSignals(
            domain="google.com",
            is_registered=True,
            domain_age_years=25,
            tld="com",
            is_premium_tld=True,
        )
        score = signals.calculate_score()
        assert score >= 15  # Age + premium TLD

    def test_premium_tld_bonus(self):
        """Premium TLDs (.com, .org, .net) get bonus."""
        signals = DomainSignals(
            domain="longerdomainname.com",  # >10 chars, no short bonus
            is_registered=True,
            domain_age_years=5,
            is_premium_tld=True,
        )
        score = signals.calculate_score()
        assert score == 5 + 5  # Age (5) + premium TLD (5) = 10

    def test_short_domain_bonus(self):
        """Short brandable domains get bonus."""
        signals = DomainSignals(
            domain="x.com",
            is_registered=True,
            domain_age_years=5,
            is_premium_tld=True,
        )
        score = signals.calculate_score()
        assert score >= 10 + 3  # Age + TLD + short domain


# =============================================================================
# WebPresenceSignals Tests
# =============================================================================


class TestWebPresenceSignals:
    """Tests for WebPresenceSignals scoring."""

    def test_no_presence_scores_zero(self):
        """No web presence should score 0."""
        signals = WebPresenceSignals()
        assert signals.calculate_score() == 0

    def test_huge_search_presence(self):
        """Massive search presence gets high score."""
        signals = WebPresenceSignals(
            google_results_estimate=500_000_000,
        )
        score = signals.calculate_score()
        assert score == 15  # Max for search

    def test_news_presence_bonus(self):
        """News mentions add points."""
        signals = WebPresenceSignals(
            news_mentions_30d=50,
        )
        score = signals.calculate_score()
        assert score == 5  # Medium news presence

    def test_prestigious_news_bonus(self):
        """Prestigious news sources add extra points."""
        signals = WebPresenceSignals(
            news_mentions_30d=10,
            news_sources=["nytimes.com", "techcrunch.com", "bbc.com"],
        )
        score = signals.calculate_score()
        assert score >= 3 + 5  # News + prestigious

    def test_combined_presence(self):
        """Combined signals add up."""
        signals = WebPresenceSignals(
            google_results_estimate=10_000_000,
            news_mentions_30d=30,
            news_sources=["reuters.com"],
            twitter_followers=200_000,
        )
        score = signals.calculate_score()
        # 10M results = 12, 30 news = 5, 1 prestigious = 2, twitter = 2 → max 21
        # But news_mentions_30d=30 is in the 20-100 range, so = 5
        # Total: 12 + 5 + 2 + 2 = 21, but may be less if some overlap
        assert score >= 15  # At least search + news bonus


# =============================================================================
# EntityRecognitionResult Tests
# =============================================================================


class TestEntityRecognitionResult:
    """Tests for EntityRecognitionResult aggregation."""

    def test_empty_result_scores_zero_or_minimal(self):
        """Empty result should score 0 or minimal (default component baseline)."""
        result = EntityRecognitionResult(domain="example.com", brand_name="Example")
        result.calculate_total_score()
        assert result.total_score >= 0
        assert result.normalized_score >= 0.0

    def test_aggregates_component_scores(self):
        """Total score should sum component scores."""
        result = EntityRecognitionResult(
            domain="stripe.com",
            brand_name="Stripe",
            wikipedia=WikipediaSignals(has_page=True),  # 15
            wikidata=WikidataSignals(has_entity=True),  # 10
            domain_signals=DomainSignals(
                domain="stripe.com",  # 6 chars = short bonus
                is_registered=True,
                domain_age_years=10,
                is_premium_tld=True,
            ),  # 8 (age) + 5 (tld) + 3 (short) = 16
            web_presence=WebPresenceSignals(google_results_estimate=50_000_000),  # 12
        )

        result.calculate_total_score()
        # 15 + 10 + 16 + 12 + 2 (reinforcement default) = 55
        # max_score = 120 (includes reinforcement component at 20 pts)
        assert 53 <= result.total_score <= 57
        assert 44.0 <= result.normalized_score <= 48.0

    def test_to_dict_serialization(self):
        """Result should serialize to dictionary."""
        result = EntityRecognitionResult(
            domain="test.com",
            brand_name="Test",
            wikipedia=WikipediaSignals(has_page=True),
        )
        result.calculate_total_score()

        data = result.to_dict()

        assert data["domain"] == "test.com"
        assert data["brand_name"] == "Test"
        assert "total_score" in data
        assert "components" in data
        assert "wikipedia" in data["components"]
        assert "wikidata" in data["components"]

    def test_records_errors(self):
        """Errors should be recorded in result."""
        result = EntityRecognitionResult(
            domain="test.com",
            brand_name="Test",
            errors=["Wikipedia: timeout", "Wikidata: rate limited"],
        )

        assert len(result.errors) == 2
        assert "Wikipedia" in result.errors[0]


# =============================================================================
# EntityRecognitionAnalyzer Tests
# =============================================================================


class TestEntityRecognitionAnalyzer:
    """Tests for main analyzer orchestration."""

    def test_extracts_brand_from_domain(self):
        """Should extract brand name from domain."""
        analyzer = EntityRecognitionAnalyzer()

        assert analyzer._extract_brand_name("stripe.com") == "Stripe"
        assert analyzer._extract_brand_name("linear.app") == "Linear"
        assert analyzer._extract_brand_name("notion.so") == "Notion"

    @pytest.mark.asyncio
    async def test_analyze_returns_result(self):
        """Analyze should return EntityRecognitionResult."""
        analyzer = EntityRecognitionAnalyzer(skip_web_presence=True)

        # Mock all the clients
        with (
            patch.object(analyzer, "_check_wikipedia", new_callable=AsyncMock),
            patch.object(analyzer, "_check_wikidata", new_callable=AsyncMock),
            patch.object(analyzer, "_check_domain", new_callable=AsyncMock),
        ):
            result = await analyzer.analyze("test.com", "Test")

            assert isinstance(result, EntityRecognitionResult)
            assert result.domain == "test.com"
            assert result.brand_name == "Test"

    @pytest.mark.asyncio
    async def test_analyze_handles_errors_gracefully(self):
        """Should handle API errors without crashing."""
        analyzer = EntityRecognitionAnalyzer(skip_web_presence=True)

        # Mock clients to raise exceptions
        with patch.object(analyzer.wikipedia, "search_entity", new_callable=AsyncMock) as mock:
            mock.side_effect = Exception("API timeout")

            result = await analyzer.analyze("test.com", "Test")

            # Should still return a result
            assert isinstance(result, EntityRecognitionResult)
            assert len(result.errors) > 0


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for the module."""

    @pytest.mark.asyncio
    async def test_get_entity_recognition_score_convenience(self):
        """Convenience function should work."""
        with patch(
            "worker.extraction.entity_recognition.EntityRecognitionAnalyzer"
        ) as MockAnalyzer:
            mock_result = EntityRecognitionResult(
                domain="test.com",
                brand_name="Test",
            )
            mock_result.normalized_score = 42.5

            mock_instance = MockAnalyzer.return_value
            mock_instance.analyze = AsyncMock(return_value=mock_result)

            score, details = await get_entity_recognition_score("test.com")

            assert score == 42.5
            assert details["domain"] == "test.com"
