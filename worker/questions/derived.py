"""Site-derived question generator.

Generates additional questions based on actual crawled site content,
metadata, and extracted entities. Produces up to 5 site-specific
questions that complement the 15 universal questions.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from worker.questions.generator import (
    GeneratedQuestion,
    QuestionSource,
    SiteContext,
)
from worker.questions.universal import QuestionCategory, QuestionDifficulty


@dataclass
class ContentAnalysis:
    """Results of analyzing site content."""

    products: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    has_pricing: bool = False
    has_blog: bool = False
    has_careers: bool = False
    has_api: bool = False
    has_integrations: bool = False


@dataclass
class DerivedConfig:
    """Configuration for derived question generation."""

    max_questions: int = 5  # Maximum derived questions to generate
    min_keyword_frequency: int = 3  # Min occurrences to consider a keyword
    max_keywords: int = 10  # Max keywords to extract


# Patterns for detecting content types
CONTENT_PATTERNS = {
    "pricing": re.compile(
        r"\b(pricing|prices?|costs?|plans?|tiers?|subscription|free trial|demo)\b", re.I
    ),
    "blog": re.compile(r"\b(blog|articles?|posts?|news|insights?|resources?)\b", re.I),
    "careers": re.compile(r"\b(careers?|jobs?|hiring|join us|openings?)\b", re.I),
    "api": re.compile(r"\b(api|developers?|sdk|documentation|endpoints?)\b", re.I),
    "integrations": re.compile(r"\b(integrat\w*|connects?|partners?|plugins?|app store)\b", re.I),
}

# Patterns for extracting entities
ENTITY_PATTERNS = {
    "products": [
        re.compile(r"our\s+(\w+(?:\s+\w+)?)\s+(?:product|platform|solution)", re.I),
        re.compile(r"introducing\s+(\w+(?:\s+\w+)?)", re.I),
        re.compile(r"(\w+(?:\s+\w+)?)\s+is\s+(?:a|our|the)\s+", re.I),
    ],
    "features": [
        re.compile(r"(?:with|includes?|offers?)\s+(\w+(?:\s+\w+)?)\s+feature", re.I),
        re.compile(r"(\w+(?:\s+\w+)?)\s+capability", re.I),
    ],
    "locations": [
        re.compile(
            r"(?:headquartered|based|located)\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        ),
        re.compile(r"offices?\s+in\s+([A-Z][a-z]+(?:,\s+[A-Z][a-z]+)*)", re.I),
    ],
}

# Stop words to filter from keywords
STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "as",
    "is",
    "was",
    "are",
    "were",
    "been",
    "be",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "must",
    "shall",
    "can",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "they",
    "them",
    "their",
    "we",
    "us",
    "our",
    "you",
    "your",
    "he",
    "she",
    "him",
    "her",
    "his",
    "who",
    "what",
    "which",
    "when",
    "where",
    "why",
    "how",
    "all",
    "each",
    "every",
    "both",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "not",
    "only",
    "same",
    "so",
    "than",
    "too",
    "very",
    "just",
    "also",
    "now",
    "here",
    "there",
    "about",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "under",
    "again",
    "further",
    "then",
    "once",
    "any",
    "many",
    "much",
    "get",
    "got",
    "make",
    "made",
    "use",
    "used",
    "using",
    "click",
    "learn",
    "read",
    "see",
    "view",
    "find",
    "contact",
    "home",
    "page",
    "site",
    "website",
}


class ContentAnalyzer:
    """Analyzes site content to extract entities and patterns."""

    def __init__(self, config: DerivedConfig | None = None):
        self.config = config or DerivedConfig()

    def analyze(
        self,
        texts: list[str],
        headings: dict[str, list[str]] | None = None,
        metadata: dict | None = None,
    ) -> ContentAnalysis:
        """
        Analyze site content to extract entities and patterns.

        Args:
            texts: List of text content from pages
            headings: Page headings by level (h1, h2, h3)
            metadata: Site metadata (title, description, etc.)

        Returns:
            ContentAnalysis with extracted information
        """
        analysis = ContentAnalysis()

        # Combine all text for analysis
        all_text = " ".join(texts)
        all_headings = []
        if headings:
            for level in ["h1", "h2", "h3"]:
                all_headings.extend(headings.get(level, []))

        # Detect content types
        analysis.has_pricing = bool(CONTENT_PATTERNS["pricing"].search(all_text))
        analysis.has_blog = bool(CONTENT_PATTERNS["blog"].search(all_text))
        analysis.has_careers = bool(CONTENT_PATTERNS["careers"].search(all_text))
        analysis.has_api = bool(CONTENT_PATTERNS["api"].search(all_text))
        analysis.has_integrations = bool(CONTENT_PATTERNS["integrations"].search(all_text))

        # Extract entities
        analysis.products = self._extract_entities(all_text, "products")
        analysis.features = self._extract_entities(all_text, "features")
        analysis.locations = self._extract_entities(all_text, "locations")

        # Extract keywords
        analysis.keywords = self._extract_keywords(all_text)

        # Analyze headings for additional signals
        self._analyze_headings(all_headings, analysis)

        # Analyze metadata
        if metadata:
            self._analyze_metadata(metadata, analysis)

        return analysis

    def _extract_entities(self, text: str, entity_type: str) -> list[str]:
        """Extract entities of a specific type from text."""
        entities: list[str] = []
        patterns = ENTITY_PATTERNS.get(entity_type, [])

        for pattern in patterns:
            matches = pattern.findall(text)
            for match in matches:
                cleaned = match.strip()
                if len(cleaned) > 2 and cleaned.lower() not in STOP_WORDS:
                    entities.append(cleaned)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for entity in entities:
            lower = entity.lower()
            if lower not in seen:
                seen.add(lower)
                unique.append(entity)

        return unique[:10]  # Limit to 10 entities

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract significant keywords from text."""
        # Tokenize
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())

        # Filter stop words
        filtered = [w for w in words if w not in STOP_WORDS]

        # Count frequencies
        counter = Counter(filtered)

        # Get top keywords above threshold
        keywords = [
            word
            for word, count in counter.most_common(self.config.max_keywords * 2)
            if count >= self.config.min_keyword_frequency
        ]

        return keywords[: self.config.max_keywords]

    def _analyze_headings(self, headings: list[str], analysis: ContentAnalysis) -> None:
        """Analyze headings for additional signals."""
        for heading in headings:
            lower = heading.lower()

            # Check for industry indicators
            industry_patterns = [
                (r"healthcare|medical|health", "Healthcare"),
                (r"fintech|financial|banking", "Finance"),
                (r"ecommerce|retail|shop", "E-commerce"),
                (r"saas|software|tech", "Technology"),
                (r"education|learning|school", "Education"),
                (r"real estate|property", "Real Estate"),
            ]

            for pattern, industry in industry_patterns:
                if re.search(pattern, lower) and industry not in analysis.industries:
                    analysis.industries.append(industry)

    def _analyze_metadata(self, metadata: dict, analysis: ContentAnalysis) -> None:
        """Analyze metadata for additional signals."""
        description = metadata.get("description", "")
        if description:
            # Extract keywords from description
            desc_keywords = self._extract_keywords(description)
            for kw in desc_keywords:
                if kw not in analysis.keywords:
                    analysis.keywords.append(kw)


class DerivedQuestionGenerator:
    """Generates site-derived questions based on content analysis."""

    def __init__(self, config: DerivedConfig | None = None):
        self.config = config or DerivedConfig()
        self.analyzer = ContentAnalyzer(config)

    def generate(
        self,
        context: SiteContext,
        texts: list[str] | None = None,
    ) -> list[GeneratedQuestion]:
        """
        Generate derived questions for a site.

        Args:
            context: Site context with company info
            texts: Optional list of page texts for analysis

        Returns:
            List of up to 5 derived questions
        """
        questions: list[GeneratedQuestion] = []

        # Analyze content if provided
        if texts:
            analysis = self.analyzer.analyze(
                texts=texts,
                headings=context.headings,
                metadata=context.metadata,
            )
        else:
            # Create minimal analysis from context
            analysis = ContentAnalysis(
                keywords=context.keywords,
                has_pricing=any("pricing" in h.lower() for h in context.headings.get("h2", [])),
            )

        # Generate questions from analysis
        questions.extend(self._generate_from_products(context, analysis))
        questions.extend(self._generate_from_features(context, analysis))
        questions.extend(self._generate_from_content_types(context, analysis))
        questions.extend(self._generate_from_metadata(context))
        questions.extend(self._generate_from_keywords(context, analysis))

        # Deduplicate and limit
        questions = self._deduplicate(questions)
        return questions[: self.config.max_questions]

    def _generate_from_products(
        self, context: SiteContext, analysis: ContentAnalysis
    ) -> list[GeneratedQuestion]:
        """Generate questions about detected products."""
        questions: list[GeneratedQuestion] = []

        for product in analysis.products[:2]:  # Max 2 product questions
            questions.append(
                GeneratedQuestion(
                    question=f"What is {context.company_name}'s {product} and how does it work?",
                    source=QuestionSource.CONTENT,
                    category=QuestionCategory.OFFERINGS,
                    difficulty=QuestionDifficulty.MEDIUM,
                    weight=0.9,
                    context=f"Product detected: {product}",
                    expected_signals=["product description", "functionality"],
                    metadata={"product": product, "derived_type": "product"},
                )
            )

        return questions

    def _generate_from_features(
        self, context: SiteContext, analysis: ContentAnalysis
    ) -> list[GeneratedQuestion]:
        """Generate questions about detected features."""
        questions: list[GeneratedQuestion] = []

        for feature in analysis.features[:1]:  # Max 1 feature question
            questions.append(
                GeneratedQuestion(
                    question=f"How does {context.company_name}'s {feature} feature work?",
                    source=QuestionSource.CONTENT,
                    category=QuestionCategory.OFFERINGS,
                    difficulty=QuestionDifficulty.MEDIUM,
                    weight=0.8,
                    context=f"Feature detected: {feature}",
                    expected_signals=["feature explanation", "use case"],
                    metadata={"feature": feature, "derived_type": "feature"},
                )
            )

        return questions

    def _generate_from_content_types(
        self, context: SiteContext, analysis: ContentAnalysis
    ) -> list[GeneratedQuestion]:
        """Generate questions based on detected content types."""
        questions: list[GeneratedQuestion] = []

        if analysis.has_api:
            questions.append(
                GeneratedQuestion(
                    question=f"Does {context.company_name} have an API or developer tools?",
                    source=QuestionSource.CONTENT,
                    category=QuestionCategory.OFFERINGS,
                    difficulty=QuestionDifficulty.MEDIUM,
                    weight=0.8,
                    context="API content detected",
                    expected_signals=["API availability", "developer docs"],
                    metadata={"derived_type": "api"},
                )
            )

        if analysis.has_integrations:
            questions.append(
                GeneratedQuestion(
                    question=f"What apps and services does {context.company_name} integrate with?",
                    source=QuestionSource.CONTENT,
                    category=QuestionCategory.OFFERINGS,
                    difficulty=QuestionDifficulty.MEDIUM,
                    weight=0.8,
                    context="Integrations content detected",
                    expected_signals=["integration list", "partner apps"],
                    metadata={"derived_type": "integrations"},
                )
            )

        if analysis.has_careers:
            questions.append(
                GeneratedQuestion(
                    question=f"Is {context.company_name} hiring and what positions are available?",
                    source=QuestionSource.CONTENT,
                    category=QuestionCategory.IDENTITY,
                    difficulty=QuestionDifficulty.EASY,
                    weight=0.6,
                    context="Careers content detected",
                    expected_signals=["job openings", "hiring status"],
                    metadata={"derived_type": "careers"},
                )
            )

        if analysis.has_blog:
            questions.append(
                GeneratedQuestion(
                    question=f"What topics does {context.company_name} write about on their blog?",
                    source=QuestionSource.CONTENT,
                    category=QuestionCategory.TRUST,
                    difficulty=QuestionDifficulty.EASY,
                    weight=0.5,
                    context="Blog content detected",
                    expected_signals=["blog topics", "thought leadership"],
                    metadata={"derived_type": "blog"},
                )
            )

        return questions

    def _generate_from_metadata(self, context: SiteContext) -> list[GeneratedQuestion]:
        """Generate questions from site metadata."""
        questions: list[GeneratedQuestion] = []

        # Generate from description if it mentions specific things
        description = context.description or ""

        if "enterprise" in description.lower():
            questions.append(
                GeneratedQuestion(
                    question=f"Does {context.company_name} offer enterprise solutions?",
                    source=QuestionSource.METADATA,
                    category=QuestionCategory.OFFERINGS,
                    difficulty=QuestionDifficulty.MEDIUM,
                    weight=0.7,
                    context="Enterprise mentioned in description",
                    expected_signals=["enterprise features", "enterprise pricing"],
                    metadata={"derived_type": "enterprise"},
                )
            )

        if any(term in description.lower() for term in ["ai", "machine learning", "ml"]):
            questions.append(
                GeneratedQuestion(
                    question=f"How does {context.company_name} use AI or machine learning?",
                    source=QuestionSource.METADATA,
                    category=QuestionCategory.DIFFERENTIATION,
                    difficulty=QuestionDifficulty.MEDIUM,
                    weight=0.8,
                    context="AI/ML mentioned in description",
                    expected_signals=["AI capabilities", "ML features"],
                    metadata={"derived_type": "ai"},
                )
            )

        return questions

    def _generate_from_keywords(
        self, context: SiteContext, analysis: ContentAnalysis
    ) -> list[GeneratedQuestion]:
        """Generate questions from significant keywords."""
        questions: list[GeneratedQuestion] = []

        # Map common keywords to question templates
        keyword_templates = {
            "automation": (
                "What can {company} automate?",
                QuestionCategory.OFFERINGS,
            ),
            "analytics": (
                "What analytics does {company} provide?",
                QuestionCategory.OFFERINGS,
            ),
            "security": (
                "What security certifications does {company} have?",
                QuestionCategory.TRUST,
            ),
            "compliance": (
                "What compliance standards does {company} meet?",
                QuestionCategory.TRUST,
            ),
            "scalable": (
                "How does {company} scale for large organizations?",
                QuestionCategory.OFFERINGS,
            ),
            "support": (
                "What support options does {company} offer?",
                QuestionCategory.CONTACT,
            ),
            "onboarding": (
                "What is {company}'s onboarding process?",
                QuestionCategory.CONTACT,
            ),
            "training": (
                "Does {company} offer training or certification?",
                QuestionCategory.OFFERINGS,
            ),
        }

        for keyword in analysis.keywords[:5]:
            if keyword in keyword_templates:
                template, category = keyword_templates[keyword]
                questions.append(
                    GeneratedQuestion(
                        question=template.format(company=context.company_name),
                        source=QuestionSource.CONTENT,
                        category=category,
                        difficulty=QuestionDifficulty.MEDIUM,
                        weight=0.7,
                        context=f"Keyword detected: {keyword}",
                        expected_signals=[f"{keyword} details"],
                        metadata={"keyword": keyword, "derived_type": "keyword"},
                    )
                )
                break  # Only one keyword question

        return questions

    def _deduplicate(self, questions: list[GeneratedQuestion]) -> list[GeneratedQuestion]:
        """Remove duplicate questions."""
        seen: set[str] = set()
        unique: list[GeneratedQuestion] = []

        for q in questions:
            normalized = q.question.lower().strip()
            normalized = re.sub(r"\s+", " ", normalized)

            if normalized not in seen:
                seen.add(normalized)
                unique.append(q)

        return unique


def derive_questions(
    context: SiteContext,
    texts: list[str] | None = None,
    config: DerivedConfig | None = None,
) -> list[GeneratedQuestion]:
    """
    Convenience function to derive site-specific questions.

    Args:
        context: Site context with company info
        texts: Optional page texts for content analysis
        config: Optional configuration

    Returns:
        List of up to 5 derived questions
    """
    generator = DerivedQuestionGenerator(config)
    return generator.generate(context, texts)
