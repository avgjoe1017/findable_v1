"""Question service for generating evaluation questions.

Combines universal and site-derived questions for AI sourceability evaluation.
"""

from dataclasses import dataclass

from worker.questions.derived import (
    ContentAnalysis,
    DerivedConfig,
    DerivedQuestionGenerator,
)
from worker.questions.generator import (
    GeneratedQuestion,
    GeneratorConfig,
    QuestionGenerator,
    SiteContext,
)
from worker.questions.universal import (
    QUESTION_STATS,
    QuestionCategory,
    QuestionDifficulty,
    UniversalQuestion,
    get_question_by_id,
    get_questions_by_category,
    get_questions_by_difficulty,
    get_universal_questions,
)


@dataclass
class QuestionSet:
    """A complete set of questions for evaluation."""

    universal: list[GeneratedQuestion]
    derived: list[GeneratedQuestion]
    total_count: int
    total_weight: float

    def all_questions(self) -> list[GeneratedQuestion]:
        """Get all questions combined."""
        return self.universal + self.derived

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "universal": [q.to_dict() for q in self.universal],
            "derived": [q.to_dict() for q in self.derived],
            "total_count": self.total_count,
            "total_weight": self.total_weight,
            "stats": {
                "universal_count": len(self.universal),
                "derived_count": len(self.derived),
            },
        }


class QuestionService:
    """Service for generating and managing evaluation questions."""

    def __init__(
        self,
        generator_config: GeneratorConfig | None = None,
        derived_config: DerivedConfig | None = None,
    ):
        self.generator_config = generator_config or GeneratorConfig(
            include_universal=True,
            max_schema_questions=0,  # Schema questions handled by derived
            max_heading_questions=0,  # Heading questions handled by derived
        )
        self.derived_config = derived_config or DerivedConfig()
        self.generator = QuestionGenerator(self.generator_config)
        self.derived_generator = DerivedQuestionGenerator(self.derived_config)

    def generate_for_site(
        self,
        company_name: str,
        domain: str,
        schema_types: list[str] | None = None,
        headings: dict[str, list[str]] | None = None,
        texts: list[str] | None = None,
        title: str | None = None,
        description: str | None = None,
        keywords: list[str] | None = None,
    ) -> QuestionSet:
        """
        Generate a complete question set for a site.

        Args:
            company_name: Name of the company
            domain: Site domain
            schema_types: Schema.org types found
            headings: Page headings by level
            texts: Page text content for analysis
            title: Site title
            description: Site description
            keywords: Extracted keywords

        Returns:
            QuestionSet with universal and derived questions
        """
        # Create context
        context = SiteContext(
            company_name=company_name,
            domain=domain,
            title=title,
            description=description,
            schema_types=schema_types or [],
            headings=headings or {},
            keywords=keywords or [],
            metadata={
                "title": title,
                "description": description,
            },
        )

        # Generate universal questions (15)
        universal = self.generator.generate(context)

        # Generate derived questions (up to 5)
        derived = self.derived_generator.generate(context, texts)

        # Calculate totals
        all_questions = universal + derived
        total_weight = sum(q.weight for q in all_questions)

        return QuestionSet(
            universal=universal,
            derived=derived,
            total_count=len(all_questions),
            total_weight=total_weight,
        )

    def get_universal_questions(self) -> list[UniversalQuestion]:
        """Get all 15 universal questions."""
        return get_universal_questions()

    def get_question_by_id(self, question_id: str) -> UniversalQuestion | None:
        """Get a specific universal question by ID."""
        return get_question_by_id(question_id)

    def get_questions_by_category(self, category: QuestionCategory) -> list[UniversalQuestion]:
        """Get universal questions filtered by category."""
        return get_questions_by_category(category)

    def get_questions_by_difficulty(
        self, difficulty: QuestionDifficulty
    ) -> list[UniversalQuestion]:
        """Get universal questions filtered by difficulty."""
        return get_questions_by_difficulty(difficulty)

    def get_stats(self) -> dict:
        """Get question statistics."""
        return QUESTION_STATS

    def analyze_content(
        self,
        texts: list[str],
        headings: dict[str, list[str]] | None = None,
        metadata: dict | None = None,
    ) -> ContentAnalysis:
        """
        Analyze site content for question derivation.

        Args:
            texts: List of page texts
            headings: Page headings
            metadata: Site metadata

        Returns:
            ContentAnalysis with extracted information
        """
        return self.derived_generator.analyzer.analyze(texts, headings, metadata)


# Module-level instance for convenience
_service: QuestionService | None = None


def get_question_service() -> QuestionService:
    """Get or create the question service singleton."""
    global _service
    if _service is None:
        _service = QuestionService()
    return _service
