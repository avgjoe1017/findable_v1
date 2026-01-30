"""Enhanced observation parsing for extracting structured signals from AI responses."""

import re
from dataclasses import dataclass, field
from enum import Enum


class MentionType(str, Enum):
    """Type of mention detected."""

    EXACT = "exact"  # Exact company name match
    PARTIAL = "partial"  # Partial match (e.g., "Acme" for "Acme Corporation")
    DOMAIN = "domain"  # Domain mentioned
    URL = "url"  # Full URL cited
    BRANDED = "branded"  # Branded term (e.g., product name)


class CitationType(str, Enum):
    """Type of citation pattern."""

    DIRECT_QUOTE = "direct_quote"  # "According to X..."
    ATTRIBUTION = "attribution"  # "X states that..."
    SOURCE_LINK = "source_link"  # URL with context
    REFERENCE = "reference"  # "As reported by X..."
    IMPLICIT = "implicit"  # Mentions without explicit citation


class Sentiment(str, Enum):
    """Sentiment of the mention."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"


class ConfidenceLevel(str, Enum):
    """Confidence level expressed in response."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"
    UNKNOWN = "unknown"


@dataclass
class Mention:
    """A detected mention of the company/brand."""

    text: str  # The actual text matched
    mention_type: MentionType
    position: int  # Character position in response
    context: str  # Surrounding text for context
    confidence: float  # 0-1 confidence in the match

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "mention_type": self.mention_type.value,
            "position": self.position,
            "context": self.context[:100] if len(self.context) > 100 else self.context,
            "confidence": round(self.confidence, 2),
        }


@dataclass
class Citation:
    """A detected citation or attribution."""

    pattern: str  # The citation pattern matched
    citation_type: CitationType
    source_text: str  # What was cited
    url: str | None  # URL if present
    position: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "pattern": self.pattern,
            "citation_type": self.citation_type.value,
            "source_text": self.source_text,
            "url": self.url,
            "position": self.position,
        }


@dataclass
class ParsedObservation:
    """Fully parsed observation result."""

    # Mentions
    mentions: list[Mention] = field(default_factory=list)
    mention_count: int = 0
    has_company_mention: bool = False
    has_domain_mention: bool = False
    has_url_citation: bool = False

    # Citations
    citations: list[Citation] = field(default_factory=list)
    citation_count: int = 0
    has_explicit_citation: bool = False

    # URLs
    all_urls: list[str] = field(default_factory=list)
    company_urls: list[str] = field(default_factory=list)
    external_urls: list[str] = field(default_factory=list)

    # Sentiment
    overall_sentiment: Sentiment = Sentiment.NEUTRAL
    sentiment_score: float = 0.0  # -1 to 1

    # Confidence
    confidence_level: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    hedging_phrases: list[str] = field(default_factory=list)
    certainty_phrases: list[str] = field(default_factory=list)

    # Content metrics
    response_length: int = 0
    word_count: int = 0
    sentence_count: int = 0

    # Quality indicators
    is_refusal: bool = False  # Model refused to answer
    is_uncertain: bool = False  # Model expressed uncertainty
    is_hallucination_risk: bool = False  # Signs of potential hallucination

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "mentions": [m.to_dict() for m in self.mentions],
            "mention_count": self.mention_count,
            "has_company_mention": self.has_company_mention,
            "has_domain_mention": self.has_domain_mention,
            "has_url_citation": self.has_url_citation,
            "citations": [c.to_dict() for c in self.citations],
            "citation_count": self.citation_count,
            "has_explicit_citation": self.has_explicit_citation,
            "all_urls": self.all_urls,
            "company_urls": self.company_urls,
            "external_urls": self.external_urls,
            "overall_sentiment": self.overall_sentiment.value,
            "sentiment_score": round(self.sentiment_score, 2),
            "confidence_level": self.confidence_level.value,
            "hedging_phrases": self.hedging_phrases,
            "certainty_phrases": self.certainty_phrases,
            "response_length": self.response_length,
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "is_refusal": self.is_refusal,
            "is_uncertain": self.is_uncertain,
            "is_hallucination_risk": self.is_hallucination_risk,
        }


class ObservationParser:
    """Parser for extracting structured signals from AI observation responses."""

    # Citation patterns (regex)
    CITATION_PATTERNS = [
        # Direct attribution
        (r"according to ([^,\.]+)", CitationType.DIRECT_QUOTE),
        (r"as (?:stated|reported|mentioned) by ([^,\.]+)", CitationType.ATTRIBUTION),
        (r"([^,\.]+) (?:states?|reports?|says?|mentions?) that", CitationType.ATTRIBUTION),
        # Source references
        (r"source:\s*([^\n]+)", CitationType.SOURCE_LINK),
        (r"from (?:the )?([^,\.]+) website", CitationType.REFERENCE),
        (r"based on (?:information from )?([^,\.]+)", CitationType.REFERENCE),
        # URL with context
        (r"(?:visit|see|check out|more at)\s+(https?://[^\s]+)", CitationType.SOURCE_LINK),
    ]

    # Hedging phrases indicating uncertainty
    HEDGING_PHRASES = [
        "i'm not sure",
        "i don't know",
        "i cannot confirm",
        "i'm unable to verify",
        "it's unclear",
        "i don't have information",
        "i cannot find",
        "may or may not",
        "might be",
        "could be",
        "possibly",
        "perhaps",
        "it seems",
        "appears to be",
        "reportedly",
        "allegedly",
        "i believe",
        "i think",
        "as far as i know",
        "to my knowledge",
    ]

    # Certainty phrases indicating confidence
    CERTAINTY_PHRASES = [
        "definitely",
        "certainly",
        "absolutely",
        "without a doubt",
        "i can confirm",
        "it is clear that",
        "clearly",
        "obviously",
        "undoubtedly",
        "for certain",
        "in fact",
        "indeed",
        "specifically",
        "precisely",
    ]

    # Refusal patterns
    REFUSAL_PATTERNS = [
        r"i (?:cannot|can't|am unable to) (?:provide|give|answer)",
        r"i don't have (?:access to|information about)",
        r"i'm not able to",
        r"this is outside (?:my|the scope)",
        r"i cannot assist with",
        r"i'm sorry,? but i (?:cannot|can't)",
    ]

    # Positive sentiment indicators
    POSITIVE_INDICATORS = [
        "excellent",
        "great",
        "outstanding",
        "impressive",
        "innovative",
        "leading",
        "best",
        "top",
        "premier",
        "trusted",
        "reliable",
        "recommended",
        "praised",
        "acclaimed",
        "award-winning",
        "renowned",
        "successful",
        "effective",
        "efficient",
        "quality",
        "superior",
    ]

    # Negative sentiment indicators
    NEGATIVE_INDICATORS = [
        "poor",
        "bad",
        "disappointing",
        "problematic",
        "issues",
        "complaints",
        "criticized",
        "concerns",
        "lacking",
        "limited",
        "struggling",
        "failed",
        "controversial",
        "negative",
        "unreliable",
        "questionable",
        "inferior",
        "subpar",
        "inadequate",
        "deficient",
    ]

    def __init__(self) -> None:
        """Initialize parser with compiled patterns."""
        self._compiled_citations = [
            (re.compile(pattern, re.IGNORECASE), ctype) for pattern, ctype in self.CITATION_PATTERNS
        ]
        self._compiled_refusals = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.REFUSAL_PATTERNS
        ]

    def parse(
        self,
        content: str,
        company_name: str,
        domain: str,
        branded_terms: list[str] | None = None,
    ) -> ParsedObservation:
        """
        Parse an observation response for structured signals.

        Args:
            content: The AI response content
            company_name: Company name to look for
            domain: Domain to look for
            branded_terms: Additional branded terms to detect

        Returns:
            ParsedObservation with all extracted signals
        """
        result = ParsedObservation()
        content_lower = content.lower()

        # Basic metrics
        result.response_length = len(content)
        result.word_count = len(content.split())
        result.sentence_count = len(re.findall(r"[.!?]+", content))

        # Extract mentions
        result.mentions = self._extract_mentions(content, company_name, domain, branded_terms or [])
        result.mention_count = len(result.mentions)
        result.has_company_mention = any(
            m.mention_type in (MentionType.EXACT, MentionType.PARTIAL) for m in result.mentions
        )
        result.has_domain_mention = any(
            m.mention_type == MentionType.DOMAIN for m in result.mentions
        )
        result.has_url_citation = any(m.mention_type == MentionType.URL for m in result.mentions)

        # Extract URLs
        result.all_urls, result.company_urls, result.external_urls = self._extract_urls(
            content, domain
        )

        # Extract citations
        result.citations = self._extract_citations(content, company_name, domain)
        result.citation_count = len(result.citations)
        result.has_explicit_citation = any(
            c.citation_type != CitationType.IMPLICIT for c in result.citations
        )

        # Analyze sentiment
        result.overall_sentiment, result.sentiment_score = self._analyze_sentiment(
            content_lower, company_name.lower()
        )

        # Analyze confidence
        (
            result.confidence_level,
            result.hedging_phrases,
            result.certainty_phrases,
        ) = self._analyze_confidence(content_lower)

        # Check for refusal
        result.is_refusal = self._check_refusal(content_lower)

        # Check uncertainty
        result.is_uncertain = (
            result.confidence_level in (ConfidenceLevel.LOW, ConfidenceLevel.UNCERTAIN)
            or len(result.hedging_phrases) > 2
        )

        # Check hallucination risk
        result.is_hallucination_risk = self._check_hallucination_risk(content, result)

        return result

    def _extract_mentions(
        self,
        content: str,
        company_name: str,
        domain: str,
        branded_terms: list[str],
    ) -> list[Mention]:
        """Extract all mentions of company, domain, and branded terms."""
        mentions = []
        content_lower = content.lower()

        # Generate name variations
        name_variations = self._generate_name_variations(company_name)

        # Check for exact and partial name matches
        for variation in name_variations:
            var_lower = variation.lower()
            for match in re.finditer(re.escape(var_lower), content_lower):
                # Get context (50 chars before and after)
                start = max(0, match.start() - 50)
                end = min(len(content), match.end() + 50)
                context = content[start:end]

                # Determine match type
                if var_lower == company_name.lower():
                    match_type = MentionType.EXACT
                    confidence = 1.0
                else:
                    match_type = MentionType.PARTIAL
                    confidence = len(variation) / len(company_name)

                mentions.append(
                    Mention(
                        text=content[match.start() : match.end()],
                        mention_type=match_type,
                        position=match.start(),
                        context=context,
                        confidence=confidence,
                    )
                )

        # Check for domain mentions (without http)
        domain_lower = domain.lower()
        for match in re.finditer(re.escape(domain_lower), content_lower):
            start = max(0, match.start() - 50)
            end = min(len(content), match.end() + 50)

            mentions.append(
                Mention(
                    text=content[match.start() : match.end()],
                    mention_type=MentionType.DOMAIN,
                    position=match.start(),
                    context=content[start:end],
                    confidence=1.0,
                )
            )

        # Check for URL mentions
        url_pattern = rf"https?://(?:www\.)?{re.escape(domain_lower)}[^\s]*"
        for match in re.finditer(url_pattern, content_lower):
            start = max(0, match.start() - 30)
            end = min(len(content), match.end() + 30)

            mentions.append(
                Mention(
                    text=content[match.start() : match.end()],
                    mention_type=MentionType.URL,
                    position=match.start(),
                    context=content[start:end],
                    confidence=1.0,
                )
            )

        # Check branded terms
        for term in branded_terms:
            term_lower = term.lower()
            for match in re.finditer(re.escape(term_lower), content_lower):
                start = max(0, match.start() - 50)
                end = min(len(content), match.end() + 50)

                mentions.append(
                    Mention(
                        text=content[match.start() : match.end()],
                        mention_type=MentionType.BRANDED,
                        position=match.start(),
                        context=content[start:end],
                        confidence=0.9,
                    )
                )

        # Remove duplicates by position
        seen_positions: set[int] = set()
        unique_mentions = []
        for mention in sorted(mentions, key=lambda m: -m.confidence):
            if mention.position not in seen_positions:
                unique_mentions.append(mention)
                seen_positions.add(mention.position)

        return sorted(unique_mentions, key=lambda m: m.position)

    def _generate_name_variations(self, company_name: str) -> list[str]:
        """Generate variations of company name for fuzzy matching."""
        variations = [company_name]

        # Common suffixes to try removing/adding
        suffixes = [
            " Inc",
            " Inc.",
            " LLC",
            " Ltd",
            " Ltd.",
            " Co",
            " Co.",
            " Corp",
            " Corp.",
            " Corporation",
            " Company",
            " Technologies",
            " Tech",
            " Software",
            " Solutions",
            " Services",
            " Group",
            " Holdings",
        ]

        name_lower = company_name.lower()

        # Try removing suffixes
        for suffix in suffixes:
            if name_lower.endswith(suffix.lower()):
                base = company_name[: -len(suffix)].strip()
                if base and base not in variations:
                    variations.append(base)

        # Try removing "The" prefix
        if name_lower.startswith("the "):
            without_the = company_name[4:]
            if without_the not in variations:
                variations.append(without_the)

        # Add first word if multi-word (skip "The")
        words = company_name.split()
        start_idx = 1 if words and words[0].lower() == "the" else 0
        if (
            len(words) > start_idx + 1
            and len(words[start_idx]) >= 3
            and words[start_idx] not in variations
        ):
            variations.append(words[start_idx])

        return variations

    def _extract_urls(
        self,
        content: str,
        domain: str,
    ) -> tuple[list[str], list[str], list[str]]:
        """Extract and categorize URLs from content."""
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        all_urls = re.findall(url_pattern, content)

        domain_lower = domain.lower()
        company_urls = []
        external_urls = []

        for url in all_urls:
            if domain_lower in url.lower():
                company_urls.append(url)
            else:
                external_urls.append(url)

        return all_urls, company_urls, external_urls

    def _extract_citations(
        self,
        content: str,
        company_name: str,
        _domain: str,
    ) -> list[Citation]:
        """Extract citation patterns from content."""
        citations = []

        for pattern, citation_type in self._compiled_citations:
            for match in pattern.finditer(content):
                source_text = match.group(1) if match.groups() else match.group(0)

                # Check if URL is in the citation
                url = None
                url_match = re.search(r"https?://[^\s]+", source_text)
                if url_match:
                    url = url_match.group(0)

                citations.append(
                    Citation(
                        pattern=match.group(0),
                        citation_type=citation_type,
                        source_text=source_text.strip(),
                        url=url,
                        position=match.start(),
                    )
                )

        # Check for implicit mentions of company as source
        company_lower = company_name.lower()
        if company_lower in content.lower() and not citations:
            # Find first mention position
            pos = content.lower().find(company_lower)
            citations.append(
                Citation(
                    pattern=f"mentions {company_name}",
                    citation_type=CitationType.IMPLICIT,
                    source_text=company_name,
                    url=None,
                    position=pos,
                )
            )

        return sorted(citations, key=lambda c: c.position)

    def _analyze_sentiment(
        self,
        content_lower: str,
        _company_lower: str,
    ) -> tuple[Sentiment, float]:
        """Analyze sentiment of content regarding the company."""
        # Count positive and negative indicators
        positive_count = sum(1 for word in self.POSITIVE_INDICATORS if word in content_lower)
        negative_count = sum(1 for word in self.NEGATIVE_INDICATORS if word in content_lower)

        # Calculate sentiment score (-1 to 1)
        total = positive_count + negative_count
        if total == 0:
            return Sentiment.NEUTRAL, 0.0

        score = (positive_count - negative_count) / total

        # Determine sentiment category
        if score > 0.3:
            sentiment = Sentiment.POSITIVE
        elif score < -0.3:
            sentiment = Sentiment.NEGATIVE
        elif positive_count > 0 and negative_count > 0:
            sentiment = Sentiment.MIXED
        else:
            sentiment = Sentiment.NEUTRAL

        return sentiment, score

    def _analyze_confidence(
        self,
        content_lower: str,
    ) -> tuple[ConfidenceLevel, list[str], list[str]]:
        """Analyze confidence level expressed in the response."""
        found_hedging = [phrase for phrase in self.HEDGING_PHRASES if phrase in content_lower]
        found_certainty = [phrase for phrase in self.CERTAINTY_PHRASES if phrase in content_lower]

        # Determine confidence level
        hedging_count = len(found_hedging)
        certainty_count = len(found_certainty)

        if hedging_count == 0 and certainty_count == 0:
            level = ConfidenceLevel.UNKNOWN
        elif hedging_count > certainty_count * 2:
            level = ConfidenceLevel.LOW
        elif certainty_count > hedging_count * 2:
            level = ConfidenceLevel.HIGH
        elif hedging_count > certainty_count:
            level = ConfidenceLevel.UNCERTAIN
        else:
            level = ConfidenceLevel.MEDIUM

        return level, found_hedging, found_certainty

    def _check_refusal(self, content_lower: str) -> bool:
        """Check if the response is a refusal to answer."""
        return any(pattern.search(content_lower) for pattern in self._compiled_refusals)

    def _check_hallucination_risk(
        self,
        content: str,
        parsed: ParsedObservation,
    ) -> bool:
        """Check for signs of potential hallucination."""
        # High confidence with no citations is risky
        if (
            parsed.confidence_level == ConfidenceLevel.HIGH
            and not parsed.has_explicit_citation
            and parsed.mention_count > 0
        ):
            return True

        # Very specific claims without sources
        specific_patterns = [
            r"\$[\d,]+",  # Dollar amounts
            r"\d{4}",  # Years
            r"\d+%",  # Percentages
            r"founded in \d{4}",
            r"headquartered in [A-Z][a-z]+",
        ]

        specific_claims = sum(1 for pattern in specific_patterns if re.search(pattern, content))

        return specific_claims >= 3 and not parsed.has_explicit_citation


def parse_observation(
    content: str,
    company_name: str,
    domain: str,
    branded_terms: list[str] | None = None,
) -> ParsedObservation:
    """
    Convenience function to parse an observation.

    Args:
        content: AI response content
        company_name: Company name to look for
        domain: Domain to track
        branded_terms: Additional branded terms

    Returns:
        ParsedObservation
    """
    parser = ObservationParser()
    return parser.parse(content, company_name, domain, branded_terms)
