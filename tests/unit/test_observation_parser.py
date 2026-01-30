"""Tests for observation parser."""

from worker.observation.parser import (
    Citation,
    CitationType,
    ConfidenceLevel,
    Mention,
    MentionType,
    ObservationParser,
    ParsedObservation,
    Sentiment,
    parse_observation,
)


class TestMention:
    """Tests for Mention dataclass."""

    def test_create_mention(self) -> None:
        """Can create a mention."""
        mention = Mention(
            text="Acme Corp",
            mention_type=MentionType.EXACT,
            position=50,
            context="...information about Acme Corp and their...",
            confidence=1.0,
        )

        assert mention.text == "Acme Corp"
        assert mention.mention_type == MentionType.EXACT

    def test_to_dict(self) -> None:
        """Converts to dict."""
        mention = Mention(
            text="acme.com",
            mention_type=MentionType.DOMAIN,
            position=100,
            context="visit acme.com for more",
            confidence=1.0,
        )

        d = mention.to_dict()

        assert d["text"] == "acme.com"
        assert d["mention_type"] == "domain"


class TestCitation:
    """Tests for Citation dataclass."""

    def test_create_citation(self) -> None:
        """Can create a citation."""
        citation = Citation(
            pattern="according to Acme Corp",
            citation_type=CitationType.DIRECT_QUOTE,
            source_text="Acme Corp",
            url=None,
            position=25,
        )

        assert citation.citation_type == CitationType.DIRECT_QUOTE

    def test_to_dict(self) -> None:
        """Converts to dict."""
        citation = Citation(
            pattern="source: https://acme.com",
            citation_type=CitationType.SOURCE_LINK,
            source_text="https://acme.com",
            url="https://acme.com",
            position=0,
        )

        d = citation.to_dict()

        assert d["url"] == "https://acme.com"


class TestParsedObservation:
    """Tests for ParsedObservation dataclass."""

    def test_create_parsed(self) -> None:
        """Can create a parsed observation."""
        parsed = ParsedObservation(
            mention_count=3,
            has_company_mention=True,
            overall_sentiment=Sentiment.POSITIVE,
        )

        assert parsed.mention_count == 3
        assert parsed.has_company_mention is True

    def test_to_dict(self) -> None:
        """Converts to dict."""
        parsed = ParsedObservation(
            overall_sentiment=Sentiment.NEUTRAL,
            confidence_level=ConfidenceLevel.MEDIUM,
            word_count=150,
        )

        d = parsed.to_dict()

        assert d["overall_sentiment"] == "neutral"
        assert d["confidence_level"] == "medium"


class TestObservationParser:
    """Tests for ObservationParser class."""

    def test_create_parser(self) -> None:
        """Can create a parser."""
        parser = ObservationParser()
        assert parser is not None

    def test_parse_exact_company_mention(self) -> None:
        """Detects exact company name mention."""
        parser = ObservationParser()
        content = "Acme Corporation is a technology company that provides solutions."

        result = parser.parse(content, "Acme Corporation", "acme.com")

        assert result.has_company_mention is True
        assert result.mention_count >= 1
        assert any(m.mention_type == MentionType.EXACT for m in result.mentions)

    def test_parse_partial_company_mention(self) -> None:
        """Detects partial company name mention."""
        parser = ObservationParser()
        content = "Acme is known for their innovative products."

        result = parser.parse(content, "Acme Corporation", "acme.com")

        assert result.has_company_mention is True
        assert any(m.mention_type == MentionType.PARTIAL for m in result.mentions)

    def test_parse_domain_mention(self) -> None:
        """Detects domain mention."""
        parser = ObservationParser()
        content = "For more information, visit acme.com to learn more."

        result = parser.parse(content, "Acme Corp", "acme.com")

        assert result.has_domain_mention is True
        assert any(m.mention_type == MentionType.DOMAIN for m in result.mentions)

    def test_parse_url_citation(self) -> None:
        """Detects URL citation."""
        parser = ObservationParser()
        content = "You can find details at https://acme.com/products for the full list."

        result = parser.parse(content, "Acme Corp", "acme.com")

        assert result.has_url_citation is True
        assert len(result.company_urls) >= 1
        assert any(m.mention_type == MentionType.URL for m in result.mentions)

    def test_parse_branded_terms(self) -> None:
        """Detects branded terms."""
        parser = ObservationParser()
        content = "The AcmeWidget product is highly rated by users."

        result = parser.parse(content, "Acme Corp", "acme.com", branded_terms=["AcmeWidget"])

        assert any(m.mention_type == MentionType.BRANDED for m in result.mentions)

    def test_parse_no_mention(self) -> None:
        """Handles content with no mentions."""
        parser = ObservationParser()
        content = "There are many technology companies in the market today."

        result = parser.parse(content, "Acme Corp", "acme.com")

        assert result.has_company_mention is False
        assert result.mention_count == 0

    def test_parse_extracts_all_urls(self) -> None:
        """Extracts all URLs from content."""
        parser = ObservationParser()
        content = """
        Check out https://acme.com for more info.
        Also see https://competitor.com and https://acme.com/pricing.
        """

        result = parser.parse(content, "Acme", "acme.com")

        assert len(result.all_urls) == 3
        assert len(result.company_urls) == 2
        assert len(result.external_urls) == 1

    def test_parse_citation_pattern_according_to(self) -> None:
        """Detects 'according to' citation pattern."""
        parser = ObservationParser()
        content = "According to Acme Corporation, their product is the best."

        result = parser.parse(content, "Acme Corporation", "acme.com")

        assert result.has_explicit_citation is True
        assert any(c.citation_type == CitationType.DIRECT_QUOTE for c in result.citations)

    def test_parse_citation_pattern_states(self) -> None:
        """Detects 'X states that' citation pattern."""
        parser = ObservationParser()
        content = "Acme Corp states that their technology is revolutionary."

        result = parser.parse(content, "Acme Corp", "acme.com")

        assert len(result.citations) >= 1

    def test_parse_citation_pattern_source(self) -> None:
        """Detects 'source:' citation pattern."""
        parser = ObservationParser()
        content = "The product is highly rated. Source: https://acme.com/reviews"

        result = parser.parse(content, "Acme", "acme.com")

        assert any(c.citation_type == CitationType.SOURCE_LINK for c in result.citations)

    def test_parse_positive_sentiment(self) -> None:
        """Detects positive sentiment."""
        parser = ObservationParser()
        content = "Acme is an excellent company with outstanding products and innovative solutions."

        result = parser.parse(content, "Acme", "acme.com")

        assert result.overall_sentiment == Sentiment.POSITIVE
        assert result.sentiment_score > 0

    def test_parse_negative_sentiment(self) -> None:
        """Detects negative sentiment."""
        parser = ObservationParser()
        content = (
            "Acme has poor customer service and disappointing product quality with many issues."
        )

        result = parser.parse(content, "Acme", "acme.com")

        assert result.overall_sentiment == Sentiment.NEGATIVE
        assert result.sentiment_score < 0

    def test_parse_neutral_sentiment(self) -> None:
        """Detects neutral sentiment."""
        parser = ObservationParser()
        content = "Acme is a company that operates in the technology sector."

        result = parser.parse(content, "Acme", "acme.com")

        assert result.overall_sentiment == Sentiment.NEUTRAL

    def test_parse_high_confidence(self) -> None:
        """Detects high confidence language."""
        parser = ObservationParser()
        content = "I can definitely confirm that Acme is certainly the leader in this space."

        result = parser.parse(content, "Acme", "acme.com")

        assert result.confidence_level == ConfidenceLevel.HIGH
        assert len(result.certainty_phrases) >= 1

    def test_parse_low_confidence(self) -> None:
        """Detects low confidence language."""
        parser = ObservationParser()
        content = "I'm not sure about Acme, and I don't know if they offer this service."

        result = parser.parse(content, "Acme", "acme.com")

        assert result.confidence_level in (ConfidenceLevel.LOW, ConfidenceLevel.UNCERTAIN)
        assert len(result.hedging_phrases) >= 1

    def test_parse_refusal(self) -> None:
        """Detects refusal to answer."""
        parser = ObservationParser()
        content = "I cannot provide information about specific companies."

        result = parser.parse(content, "Acme", "acme.com")

        assert result.is_refusal is True

    def test_parse_uncertainty_flag(self) -> None:
        """Sets uncertainty flag appropriately."""
        parser = ObservationParser()
        content = "I'm not sure, but I believe Acme might be a software company. Perhaps they offer services."

        result = parser.parse(content, "Acme", "acme.com")

        assert result.is_uncertain is True

    def test_parse_hallucination_risk(self) -> None:
        """Detects hallucination risk indicators."""
        parser = ObservationParser()
        content = """
        Acme was definitely founded in 1995 in San Francisco.
        They have $50,000,000 in revenue and 500 employees.
        Their stock is trading at $125.50 per share.
        """

        result = parser.parse(content, "Acme", "acme.com")

        # Specific claims without citations = hallucination risk
        assert result.is_hallucination_risk is True

    def test_parse_content_metrics(self) -> None:
        """Calculates content metrics."""
        parser = ObservationParser()
        content = "This is a test. This has two sentences."

        result = parser.parse(content, "Test", "test.com")

        assert result.word_count == 8  # "This is a test This has two sentences"
        assert result.sentence_count == 2
        assert result.response_length > 0

    def test_generate_name_variations(self) -> None:
        """Generates name variations for fuzzy matching."""
        parser = ObservationParser()

        variations = parser._generate_name_variations("Acme Corporation")

        assert "Acme Corporation" in variations
        assert "Acme" in variations

    def test_generate_name_variations_with_suffix(self) -> None:
        """Handles various company suffixes."""
        parser = ObservationParser()

        variations = parser._generate_name_variations("Tech Solutions Inc.")

        assert "Tech Solutions Inc." in variations
        assert "Tech Solutions" in variations

    def test_generate_name_variations_with_the(self) -> None:
        """Handles 'The' prefix."""
        parser = ObservationParser()

        variations = parser._generate_name_variations("The Acme Company")

        assert "Acme Company" in variations


class TestConvenienceFunction:
    """Tests for parse_observation convenience function."""

    def test_parse_observation_function(self) -> None:
        """Convenience function works."""
        content = "Acme Corporation provides excellent solutions."

        result = parse_observation(content, "Acme Corporation", "acme.com")

        assert isinstance(result, ParsedObservation)
        assert result.has_company_mention is True

    def test_parse_observation_with_branded_terms(self) -> None:
        """Accepts branded terms."""
        content = "The AcmeProduct is widely used."

        result = parse_observation(content, "Acme", "acme.com", branded_terms=["AcmeProduct"])

        assert result.mention_count >= 1


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_content(self) -> None:
        """Handles empty content."""
        parser = ObservationParser()

        result = parser.parse("", "Acme", "acme.com")

        assert result.mention_count == 0
        assert result.word_count == 0

    def test_case_insensitive_matching(self) -> None:
        """Matching is case-insensitive."""
        parser = ObservationParser()
        content = "ACME CORP is a great company. Visit ACME.COM for more."

        result = parser.parse(content, "Acme Corp", "acme.com")

        assert result.has_company_mention is True
        assert result.has_domain_mention is True

    def test_multiple_mentions(self) -> None:
        """Handles multiple mentions of same entity."""
        parser = ObservationParser()
        content = "Acme is great. I love Acme. Acme is the best."

        result = parser.parse(content, "Acme", "acme.com")

        assert result.mention_count >= 3

    def test_special_characters_in_name(self) -> None:
        """Handles special characters in company name."""
        parser = ObservationParser()
        content = "AT&T is a telecommunications company."

        result = parser.parse(content, "AT&T", "att.com")

        assert result.has_company_mention is True

    def test_unicode_content(self) -> None:
        """Handles unicode content."""
        parser = ObservationParser()
        content = "Acme provides solutions worldwide. 日本語テスト."

        result = parser.parse(content, "Acme", "acme.com")

        assert result.has_company_mention is True
