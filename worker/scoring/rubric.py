"""Scoring rubric definitions for AI sourceability evaluation.

Defines the criteria, weights, and thresholds used to calculate
the Findable Score. Provides transparency into how scores are derived.
"""

from dataclasses import dataclass, field
from enum import Enum

from worker.questions.universal import QuestionCategory, QuestionDifficulty


class ScoreLevel(str, Enum):
    """Score level classifications."""

    EXCELLENT = "excellent"  # 90-100
    GOOD = "good"  # 80-89
    FAIR = "fair"  # 70-79
    NEEDS_WORK = "needs_work"  # 60-69
    POOR = "poor"  # 0-59


@dataclass
class RubricCriterion:
    """A single criterion in the scoring rubric."""

    id: str
    name: str
    description: str
    weight: float  # Relative weight (0.0-1.0)
    max_points: float  # Maximum points possible

    # Thresholds for score levels
    excellent_threshold: float = 0.9
    good_threshold: float = 0.8
    fair_threshold: float = 0.7
    needs_work_threshold: float = 0.6

    def get_level(self, score: float) -> ScoreLevel:
        """Get score level for a normalized score (0-1)."""
        if score >= self.excellent_threshold:
            return ScoreLevel.EXCELLENT
        elif score >= self.good_threshold:
            return ScoreLevel.GOOD
        elif score >= self.fair_threshold:
            return ScoreLevel.FAIR
        elif score >= self.needs_work_threshold:
            return ScoreLevel.NEEDS_WORK
        else:
            return ScoreLevel.POOR

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "weight": self.weight,
            "max_points": self.max_points,
        }


@dataclass
class CategoryWeight:
    """Weight configuration for a question category."""

    category: QuestionCategory
    weight: float  # Relative weight within total
    description: str
    importance: str  # Why this category matters

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "weight": self.weight,
            "description": self.description,
            "importance": self.importance,
        }


@dataclass
class DifficultyMultiplier:
    """Score multiplier based on question difficulty."""

    difficulty: QuestionDifficulty
    multiplier: float
    description: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "difficulty": self.difficulty.value,
            "multiplier": self.multiplier,
            "description": self.description,
        }


@dataclass
class ScoringRubric:
    """Complete scoring rubric for AI sourceability evaluation."""

    name: str = "Findable Score Rubric v1"
    version: str = "1.0"
    description: str = (
        "Evaluates how well AI systems can find and cite information about your business"
    )

    # Main scoring criteria
    criteria: list[RubricCriterion] = field(default_factory=list)

    # Category weights
    category_weights: dict[QuestionCategory, CategoryWeight] = field(default_factory=dict)

    # Difficulty multipliers
    difficulty_multipliers: dict[QuestionDifficulty, DifficultyMultiplier] = field(
        default_factory=dict
    )

    # Grade thresholds
    grade_thresholds: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize default rubric if not provided."""
        if not self.criteria:
            self.criteria = self._default_criteria()
        if not self.category_weights:
            self.category_weights = self._default_category_weights()
        if not self.difficulty_multipliers:
            self.difficulty_multipliers = self._default_difficulty_multipliers()
        if not self.grade_thresholds:
            self.grade_thresholds = self._default_grade_thresholds()

    def _default_criteria(self) -> list[RubricCriterion]:
        """Default scoring criteria."""
        return [
            RubricCriterion(
                id="content_relevance",
                name="Content Relevance",
                description="How well retrieved content matches the question",
                weight=0.35,
                max_points=35,
            ),
            RubricCriterion(
                id="signal_coverage",
                name="Signal Coverage",
                description="Presence of expected information signals",
                weight=0.35,
                max_points=35,
            ),
            RubricCriterion(
                id="answer_confidence",
                name="Answer Confidence",
                description="Confidence that the answer is correct and complete",
                weight=0.20,
                max_points=20,
            ),
            RubricCriterion(
                id="source_quality",
                name="Source Quality",
                description="Quality and authority of source pages",
                weight=0.10,
                max_points=10,
            ),
        ]

    def _default_category_weights(self) -> dict[QuestionCategory, CategoryWeight]:
        """Default category weights."""
        return {
            QuestionCategory.IDENTITY: CategoryWeight(
                category=QuestionCategory.IDENTITY,
                weight=0.25,
                description="Who you are and what you do",
                importance="Foundation for AI to accurately describe your business",
            ),
            QuestionCategory.OFFERINGS: CategoryWeight(
                category=QuestionCategory.OFFERINGS,
                weight=0.30,
                description="Products, services, and capabilities",
                importance="Critical for AI recommendations and purchase decisions",
            ),
            QuestionCategory.CONTACT: CategoryWeight(
                category=QuestionCategory.CONTACT,
                weight=0.15,
                description="How to reach and engage with you",
                importance="Enables conversions from AI-driven traffic",
            ),
            QuestionCategory.TRUST: CategoryWeight(
                category=QuestionCategory.TRUST,
                weight=0.15,
                description="Credibility and social proof",
                importance="Builds confidence in AI recommendations",
            ),
            QuestionCategory.DIFFERENTIATION: CategoryWeight(
                category=QuestionCategory.DIFFERENTIATION,
                weight=0.15,
                description="What makes you unique",
                importance="Helps AI recommend you over competitors",
            ),
        }

    def _default_difficulty_multipliers(
        self,
    ) -> dict[QuestionDifficulty, DifficultyMultiplier]:
        """Default difficulty multipliers."""
        return {
            QuestionDifficulty.EASY: DifficultyMultiplier(
                difficulty=QuestionDifficulty.EASY,
                multiplier=1.0,
                description="Basic information that should be clearly stated",
            ),
            QuestionDifficulty.MEDIUM: DifficultyMultiplier(
                difficulty=QuestionDifficulty.MEDIUM,
                multiplier=1.2,
                description="Information that may require some inference",
            ),
            QuestionDifficulty.HARD: DifficultyMultiplier(
                difficulty=QuestionDifficulty.HARD,
                multiplier=1.5,
                description="Complex information that may span multiple pages",
            ),
        }

    def _default_grade_thresholds(self) -> dict[str, float]:
        """Default grade thresholds."""
        return {
            "A+": 97,
            "A": 93,
            "A-": 90,
            "B+": 87,
            "B": 83,
            "B-": 80,
            "C+": 77,
            "C": 73,
            "C-": 70,
            "D+": 67,
            "D": 63,
            "D-": 60,
            "F": 0,
        }

    def get_grade(self, score: float) -> str:
        """Get letter grade for a score."""
        for grade, threshold in sorted(
            self.grade_thresholds.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            if score >= threshold:
                return grade
        return "F"

    def get_grade_description(self, grade: str) -> str:
        """Get description for a grade."""
        descriptions = {
            "A+": "Exceptional - Your site is highly optimized for AI discovery",
            "A": "Excellent - AI systems can easily find and cite your information",
            "A-": "Very Good - Strong AI sourceability with minor gaps",
            "B+": "Good - Solid foundation with room for improvement",
            "B": "Above Average - Most key information is discoverable",
            "B-": "Satisfactory - Some important information may be missed",
            "C+": "Fair - Noticeable gaps in AI discoverability",
            "C": "Average - Significant improvements needed",
            "C-": "Below Average - Many questions cannot be answered",
            "D+": "Poor - Major content gaps affecting AI discovery",
            "D": "Very Poor - Critical information is missing",
            "D-": "Failing - AI systems struggle to find your information",
            "F": "Critical - Immediate action required",
        }
        return descriptions.get(grade, "Unknown grade")

    def get_category_weight(self, category: QuestionCategory) -> float:
        """Get weight for a category."""
        if category in self.category_weights:
            return self.category_weights[category].weight
        return 0.2  # Default equal weight

    def get_difficulty_multiplier(self, difficulty: QuestionDifficulty) -> float:
        """Get multiplier for a difficulty level."""
        if difficulty in self.difficulty_multipliers:
            return self.difficulty_multipliers[difficulty].multiplier
        return 1.0  # Default no multiplier

    def to_dict(self) -> dict:
        """Convert rubric to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "criteria": [c.to_dict() for c in self.criteria],
            "category_weights": {k.value: v.to_dict() for k, v in self.category_weights.items()},
            "difficulty_multipliers": {
                k.value: v.to_dict() for k, v in self.difficulty_multipliers.items()
            },
            "grade_thresholds": self.grade_thresholds,
        }


# Default rubric instance
DEFAULT_RUBRIC = ScoringRubric()


def get_rubric() -> ScoringRubric:
    """Get the default scoring rubric."""
    return DEFAULT_RUBRIC
