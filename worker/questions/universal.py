"""Universal questions for AI sourceability evaluation.

These 15 questions are designed to evaluate any website's ability to
serve as a reliable source for AI systems. They cover key aspects
that AI models need to accurately cite and reference information.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class QuestionCategory(StrEnum):
    """Categories for universal questions."""

    IDENTITY = "identity"  # Who/what is this organization
    OFFERINGS = "offerings"  # Products, services, capabilities
    CONTACT = "contact"  # How to reach/engage
    TRUST = "trust"  # Credibility signals
    DIFFERENTIATION = "differentiation"  # What makes them unique


class QuestionDifficulty(StrEnum):
    """Difficulty levels for questions."""

    EASY = "easy"  # Should be clearly stated
    MEDIUM = "medium"  # May require inference
    HARD = "hard"  # Complex or multi-part


@dataclass
class UniversalQuestion:
    """A universal evaluation question."""

    id: str
    question: str
    category: QuestionCategory
    difficulty: QuestionDifficulty
    description: str  # Why this question matters
    expected_signals: list[str]  # What good answers contain
    weight: float = 1.0  # Scoring weight
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "question": self.question,
            "category": self.category.value,
            "difficulty": self.difficulty.value,
            "description": self.description,
            "expected_signals": self.expected_signals,
            "weight": self.weight,
            "metadata": self.metadata,
        }


# The 15 Universal Questions
UNIVERSAL_QUESTIONS: list[UniversalQuestion] = [
    # === IDENTITY (3 questions) ===
    UniversalQuestion(
        id="UQ-01",
        question="What does {company} do?",
        category=QuestionCategory.IDENTITY,
        difficulty=QuestionDifficulty.EASY,
        description="Core business description - the fundamental question AI must answer correctly",
        expected_signals=[
            "clear business description",
            "industry/sector mentioned",
            "primary activity stated",
        ],
        weight=1.5,
    ),
    UniversalQuestion(
        id="UQ-02",
        question="Who founded {company} and when was it established?",
        category=QuestionCategory.IDENTITY,
        difficulty=QuestionDifficulty.MEDIUM,
        description="Origin story establishes credibility and context",
        expected_signals=[
            "founder name(s)",
            "founding year",
            "founding story/context",
        ],
        weight=1.0,
    ),
    UniversalQuestion(
        id="UQ-03",
        question="Where is {company} headquartered and where do they operate?",
        category=QuestionCategory.IDENTITY,
        difficulty=QuestionDifficulty.EASY,
        description="Geographic presence affects relevance for location-based queries",
        expected_signals=[
            "headquarters location",
            "operating regions",
            "office locations",
        ],
        weight=1.0,
    ),
    # === OFFERINGS (4 questions) ===
    UniversalQuestion(
        id="UQ-04",
        question="What products or services does {company} offer?",
        category=QuestionCategory.OFFERINGS,
        difficulty=QuestionDifficulty.EASY,
        description="Core offerings are essential for AI to recommend or cite",
        expected_signals=[
            "product/service names",
            "clear descriptions",
            "key features",
        ],
        weight=1.5,
    ),
    UniversalQuestion(
        id="UQ-05",
        question="What is {company}'s pricing or how much do their services cost?",
        category=QuestionCategory.OFFERINGS,
        difficulty=QuestionDifficulty.MEDIUM,
        description="Pricing information is crucial for purchase decisions",
        expected_signals=[
            "pricing tiers",
            "specific prices",
            "pricing model explanation",
        ],
        weight=1.0,
    ),
    UniversalQuestion(
        id="UQ-06",
        question="Who are the typical customers or target audience for {company}?",
        category=QuestionCategory.OFFERINGS,
        difficulty=QuestionDifficulty.MEDIUM,
        description="Target audience helps AI match users to appropriate solutions",
        expected_signals=[
            "customer segments",
            "use cases",
            "industry verticals",
        ],
        weight=1.0,
    ),
    UniversalQuestion(
        id="UQ-07",
        question="What problems does {company} solve for their customers?",
        category=QuestionCategory.OFFERINGS,
        difficulty=QuestionDifficulty.MEDIUM,
        description="Problem-solution framing is how users often search",
        expected_signals=[
            "pain points addressed",
            "solutions provided",
            "outcomes achieved",
        ],
        weight=1.2,
    ),
    # === CONTACT (2 questions) ===
    UniversalQuestion(
        id="UQ-08",
        question="How can I contact {company} or get in touch with them?",
        category=QuestionCategory.CONTACT,
        difficulty=QuestionDifficulty.EASY,
        description="Contact information enables user action",
        expected_signals=[
            "email address",
            "phone number",
            "contact form mention",
            "physical address",
        ],
        weight=1.0,
    ),
    UniversalQuestion(
        id="UQ-09",
        question="How do I get started with {company} or sign up for their service?",
        category=QuestionCategory.CONTACT,
        difficulty=QuestionDifficulty.EASY,
        description="Onboarding path is critical for conversion",
        expected_signals=[
            "signup process",
            "getting started steps",
            "trial/demo availability",
        ],
        weight=1.2,
    ),
    # === TRUST (3 questions) ===
    UniversalQuestion(
        id="UQ-10",
        question="What notable clients or customers does {company} have?",
        category=QuestionCategory.TRUST,
        difficulty=QuestionDifficulty.MEDIUM,
        description="Social proof through recognizable clients builds trust",
        expected_signals=[
            "client names",
            "case studies",
            "testimonials",
            "logos/partnerships",
        ],
        weight=1.0,
    ),
    UniversalQuestion(
        id="UQ-11",
        question="What awards, certifications, or recognition has {company} received?",
        category=QuestionCategory.TRUST,
        difficulty=QuestionDifficulty.HARD,
        description="Third-party validation signals quality and reliability",
        expected_signals=[
            "awards mentioned",
            "certifications listed",
            "industry recognition",
            "press coverage",
        ],
        weight=0.8,
    ),
    UniversalQuestion(
        id="UQ-12",
        question="What is {company}'s track record or history of success?",
        category=QuestionCategory.TRUST,
        difficulty=QuestionDifficulty.HARD,
        description="Performance history demonstrates reliability",
        expected_signals=[
            "years in business",
            "growth metrics",
            "success stories",
            "customer count",
        ],
        weight=1.0,
    ),
    # === DIFFERENTIATION (3 questions) ===
    UniversalQuestion(
        id="UQ-13",
        question="What makes {company} different from competitors?",
        category=QuestionCategory.DIFFERENTIATION,
        difficulty=QuestionDifficulty.MEDIUM,
        description="Unique value proposition helps AI recommend appropriately",
        expected_signals=[
            "unique features",
            "competitive advantages",
            "proprietary technology",
            "differentiating factors",
        ],
        weight=1.2,
    ),
    UniversalQuestion(
        id="UQ-14",
        question="Why should someone choose {company} over alternatives?",
        category=QuestionCategory.DIFFERENTIATION,
        difficulty=QuestionDifficulty.HARD,
        description="Compelling reasons to choose drive recommendations",
        expected_signals=[
            "value propositions",
            "benefits over alternatives",
            "unique selling points",
        ],
        weight=1.2,
    ),
    UniversalQuestion(
        id="UQ-15",
        question="What is {company}'s mission, vision, or core values?",
        category=QuestionCategory.DIFFERENTIATION,
        difficulty=QuestionDifficulty.MEDIUM,
        description="Purpose and values help AI understand brand positioning",
        expected_signals=[
            "mission statement",
            "vision statement",
            "core values",
            "company purpose",
        ],
        weight=0.8,
    ),
]


def get_universal_questions() -> list[UniversalQuestion]:
    """Get all 15 universal questions."""
    return UNIVERSAL_QUESTIONS.copy()


def get_questions_by_category(category: QuestionCategory) -> list[UniversalQuestion]:
    """Get questions filtered by category."""
    return [q for q in UNIVERSAL_QUESTIONS if q.category == category]


def get_questions_by_difficulty(
    difficulty: QuestionDifficulty,
) -> list[UniversalQuestion]:
    """Get questions filtered by difficulty."""
    return [q for q in UNIVERSAL_QUESTIONS if q.difficulty == difficulty]


def get_question_by_id(question_id: str) -> UniversalQuestion | None:
    """Get a specific question by ID."""
    for q in UNIVERSAL_QUESTIONS:
        if q.id == question_id:
            return q
    return None


def format_question(question: UniversalQuestion, company_name: str) -> str:
    """
    Format a question template with the company name.

    Args:
        question: UniversalQuestion with {company} placeholder
        company_name: Name to substitute

    Returns:
        Formatted question string
    """
    return question.question.format(company=company_name)


def get_category_weights() -> dict[QuestionCategory, float]:
    """Get total weight for each category."""
    weights: dict[QuestionCategory, float] = {}
    for q in UNIVERSAL_QUESTIONS:
        if q.category not in weights:
            weights[q.category] = 0.0
        weights[q.category] += q.weight
    return weights


def get_total_weight() -> float:
    """Get sum of all question weights."""
    return sum(q.weight for q in UNIVERSAL_QUESTIONS)


# Question statistics
QUESTION_STATS = {
    "total_questions": len(UNIVERSAL_QUESTIONS),
    "total_weight": get_total_weight(),
    "categories": {cat.value: len(get_questions_by_category(cat)) for cat in QuestionCategory},
    "difficulties": {
        diff.value: len(get_questions_by_difficulty(diff)) for diff in QuestionDifficulty
    },
}
