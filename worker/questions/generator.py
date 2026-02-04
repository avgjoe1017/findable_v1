"""Question generator for site-specific questions.

Generates additional questions based on site content, metadata,
and extracted information.
"""

import re
from dataclasses import dataclass, field
from enum import Enum

from worker.questions.universal import (
    QuestionCategory,
    QuestionDifficulty,
    format_question,
    get_universal_questions,
)


class QuestionSource(str, Enum):
    """Source of generated question."""

    UNIVERSAL = "universal"  # From universal set
    SCHEMA = "schema"  # From schema.org data
    METADATA = "metadata"  # From page metadata
    CONTENT = "content"  # From page content
    HEADING = "heading"  # From page headings


@dataclass
class GeneratedQuestion:
    """A generated question with context."""

    question: str
    source: QuestionSource
    category: QuestionCategory
    difficulty: QuestionDifficulty
    weight: float = 1.0
    context: str | None = None  # Where this question came from
    expected_signals: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        """Generate deterministic ID from question text or use universal_id from metadata."""
        if "universal_id" in self.metadata:
            return self.metadata["universal_id"]
        import hashlib

        return hashlib.md5(self.question.encode()).hexdigest()[:8]

    @property
    def text(self) -> str:
        """Alias for question attribute."""
        return self.question

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "question": self.question,
            "source": self.source.value,
            "category": self.category.value,
            "difficulty": self.difficulty.value,
            "weight": self.weight,
            "context": self.context,
            "expected_signals": self.expected_signals,
            "metadata": self.metadata,
        }


@dataclass
class GeneratorConfig:
    """Configuration for question generator."""

    include_universal: bool = True  # Include 15 universal questions
    max_schema_questions: int = 3  # Max questions from schema.org
    max_heading_questions: int = 2  # Max questions from headings
    max_content_questions: int = 0  # Max questions from content analysis
    total_question_limit: int = 20  # Total questions to generate


@dataclass
class SiteContext:
    """Context about a site for question generation."""

    company_name: str
    domain: str
    title: str | None = None
    description: str | None = None
    schema_types: list[str] = field(default_factory=list)
    headings: dict[str, list[str]] = field(default_factory=dict)
    keywords: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# Schema type to question templates
SCHEMA_QUESTION_TEMPLATES: dict[str, list[tuple[str, QuestionCategory]]] = {
    "Product": [
        ("What are the features of {product}?", QuestionCategory.OFFERINGS),
        ("How much does {product} cost?", QuestionCategory.OFFERINGS),
        ("What are the reviews for {product}?", QuestionCategory.TRUST),
    ],
    "LocalBusiness": [
        ("What are the hours of operation for {company}?", QuestionCategory.CONTACT),
        ("What is the address of {company}?", QuestionCategory.CONTACT),
        ("What services does {company} offer?", QuestionCategory.OFFERINGS),
    ],
    "Organization": [
        ("How many employees does {company} have?", QuestionCategory.IDENTITY),
        ("What is {company}'s annual revenue?", QuestionCategory.TRUST),
    ],
    "SoftwareApplication": [
        ("What platforms does {product} support?", QuestionCategory.OFFERINGS),
        ("What are the system requirements for {product}?", QuestionCategory.OFFERINGS),
        ("Is there a free trial for {product}?", QuestionCategory.OFFERINGS),
    ],
    "Service": [
        ("How long does {service} take?", QuestionCategory.OFFERINGS),
        ("What is included in {service}?", QuestionCategory.OFFERINGS),
    ],
    "Article": [
        ("What is the main topic of this article?", QuestionCategory.IDENTITY),
        ("Who wrote this article?", QuestionCategory.TRUST),
    ],
    "FAQPage": [
        ("What are the most common questions about {company}?", QuestionCategory.OFFERINGS),
    ],
    "HowTo": [
        ("How do I use {product}?", QuestionCategory.OFFERINGS),
        ("What steps are involved in {process}?", QuestionCategory.OFFERINGS),
    ],
}


# Heading patterns that suggest questions
HEADING_QUESTION_PATTERNS: list[tuple[re.Pattern, str, QuestionCategory]] = [
    (
        re.compile(r"pricing|plans|cost", re.I),
        "What are {company}'s pricing plans?",
        QuestionCategory.OFFERINGS,
    ),
    (
        re.compile(r"features?|capabilities", re.I),
        "What features does {company} offer?",
        QuestionCategory.OFFERINGS,
    ),
    (
        re.compile(r"about\s+us|our\s+story|who\s+we\s+are", re.I),
        "What is {company}'s background and history?",
        QuestionCategory.IDENTITY,
    ),
    (
        re.compile(r"team|leadership|founders?", re.I),
        "Who are the key people at {company}?",
        QuestionCategory.IDENTITY,
    ),
    (
        re.compile(r"testimonials?|reviews?|customers?\s+say", re.I),
        "What do customers say about {company}?",
        QuestionCategory.TRUST,
    ),
    (
        re.compile(r"case\s+stud|success\s+stor", re.I),
        "What are some success stories from {company}?",
        QuestionCategory.TRUST,
    ),
    (
        re.compile(r"integrations?|connect|works?\s+with", re.I),
        "What does {company} integrate with?",
        QuestionCategory.OFFERINGS,
    ),
    (
        re.compile(r"faq|frequently\s+asked", re.I),
        "What are frequently asked questions about {company}?",
        QuestionCategory.OFFERINGS,
    ),
    (
        re.compile(r"security|privacy|compliance", re.I),
        "How does {company} handle security and privacy?",
        QuestionCategory.TRUST,
    ),
    (
        re.compile(r"support|help|contact", re.I),
        "How can I get support from {company}?",
        QuestionCategory.CONTACT,
    ),
]


class QuestionGenerator:
    """Generates questions for evaluating a site's AI sourceability."""

    def __init__(self, config: GeneratorConfig | None = None):
        self.config = config or GeneratorConfig()

    def generate(self, context: SiteContext) -> list[GeneratedQuestion]:
        """
        Generate questions for a site.

        Args:
            context: Site context with company info and metadata

        Returns:
            List of generated questions
        """
        questions: list[GeneratedQuestion] = []

        # Add universal questions
        if self.config.include_universal:
            universal = self._generate_universal(context)
            questions.extend(universal)

        # Add schema-based questions
        if self.config.max_schema_questions > 0:
            schema_qs = self._generate_from_schema(context)
            questions.extend(schema_qs[: self.config.max_schema_questions])

        # Add heading-based questions
        if self.config.max_heading_questions > 0:
            heading_qs = self._generate_from_headings(context)
            questions.extend(heading_qs[: self.config.max_heading_questions])

        # Deduplicate and limit
        questions = self._deduplicate(questions)
        questions = questions[: self.config.total_question_limit]

        return questions

    def _generate_universal(self, context: SiteContext) -> list[GeneratedQuestion]:
        """Generate formatted universal questions."""
        questions: list[GeneratedQuestion] = []

        for uq in get_universal_questions():
            formatted = format_question(uq, context.company_name)
            questions.append(
                GeneratedQuestion(
                    question=formatted,
                    source=QuestionSource.UNIVERSAL,
                    category=uq.category,
                    difficulty=uq.difficulty,
                    weight=uq.weight,
                    context=f"Universal question {uq.id}",
                    expected_signals=uq.expected_signals,
                    metadata={"universal_id": uq.id},
                )
            )

        return questions

    def _generate_from_schema(self, context: SiteContext) -> list[GeneratedQuestion]:
        """Generate questions based on schema.org types found on site."""
        questions: list[GeneratedQuestion] = []

        for schema_type in context.schema_types:
            if schema_type not in SCHEMA_QUESTION_TEMPLATES:
                continue

            templates = SCHEMA_QUESTION_TEMPLATES[schema_type]
            for template, category in templates:
                # Format question with context
                question = template.format(
                    company=context.company_name,
                    product=context.company_name,
                    service=context.company_name,
                    process=context.company_name,
                )

                questions.append(
                    GeneratedQuestion(
                        question=question,
                        source=QuestionSource.SCHEMA,
                        category=category,
                        difficulty=QuestionDifficulty.MEDIUM,
                        weight=0.8,
                        context=f"Schema type: {schema_type}",
                        metadata={"schema_type": schema_type},
                    )
                )

        return questions

    def _generate_from_headings(self, context: SiteContext) -> list[GeneratedQuestion]:
        """Generate questions based on page headings."""
        questions: list[GeneratedQuestion] = []

        # Collect all headings
        all_headings: list[str] = []
        for level in ["h1", "h2", "h3"]:
            all_headings.extend(context.headings.get(level, []))

        # Check each heading against patterns
        for heading in all_headings:
            for pattern, template, category in HEADING_QUESTION_PATTERNS:
                if pattern.search(heading):
                    question = template.format(company=context.company_name)
                    questions.append(
                        GeneratedQuestion(
                            question=question,
                            source=QuestionSource.HEADING,
                            category=category,
                            difficulty=QuestionDifficulty.MEDIUM,
                            weight=0.7,
                            context=f"Heading: {heading[:50]}",
                            metadata={"heading": heading},
                        )
                    )
                    break  # Only one question per heading

        return questions

    def _deduplicate(self, questions: list[GeneratedQuestion]) -> list[GeneratedQuestion]:
        """Remove duplicate or very similar questions."""
        seen: set[str] = set()
        unique: list[GeneratedQuestion] = []

        for q in questions:
            # Normalize for comparison
            normalized = q.question.lower().strip()
            normalized = re.sub(r"\s+", " ", normalized)

            if normalized not in seen:
                seen.add(normalized)
                unique.append(q)

        return unique

    def generate_for_site(
        self,
        company_name: str,
        domain: str,
        schema_types: list[str] | None = None,
        headings: dict[str, list[str]] | None = None,
        **kwargs: object,
    ) -> list[GeneratedQuestion]:
        """
        Convenience method to generate questions from basic site info.

        Args:
            company_name: Name of the company
            domain: Site domain
            schema_types: Schema.org types found
            headings: Page headings by level
            **kwargs: Additional context fields (title, description, keywords, metadata)

        Returns:
            List of generated questions
        """
        # Extract optional SiteContext fields from kwargs to satisfy type checker
        title = kwargs.get("title")
        description = kwargs.get("description")
        keywords = kwargs.get("keywords") or []
        metadata = kwargs.get("metadata") or {}
        context = SiteContext(
            company_name=company_name,
            domain=domain,
            title=title if isinstance(title, str | type(None)) else None,
            description=description if isinstance(description, str | type(None)) else None,
            schema_types=schema_types or [],
            headings=headings or {},
            keywords=keywords if isinstance(keywords, list) else [],
            metadata=metadata if isinstance(metadata, dict) else {},
        )

        return self.generate(context)


def generate_questions(
    company_name: str,
    domain: str,
    schema_types: list[str] | None = None,
    headings: dict[str, list[str]] | None = None,
    config: GeneratorConfig | None = None,
) -> list[GeneratedQuestion]:
    """
    Convenience function to generate questions.

    Args:
        company_name: Company name for question formatting
        domain: Site domain
        schema_types: Schema.org types found on site
        headings: Page headings
        config: Generator configuration

    Returns:
        List of generated questions
    """
    generator = QuestionGenerator(config)
    return generator.generate_for_site(
        company_name=company_name,
        domain=domain,
        schema_types=schema_types,
        headings=headings,
    )
