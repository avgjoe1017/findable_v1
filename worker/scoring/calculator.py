"""Score calculator with "Show the Math" functionality.

Provides transparent score calculations with detailed breakdowns
showing exactly how each component contributes to the final score.
"""

from dataclasses import dataclass, field

from worker.questions.universal import QuestionCategory, QuestionDifficulty
from worker.scoring.rubric import (
    DEFAULT_RUBRIC,
    RubricCriterion,
    ScoreLevel,
    ScoringRubric,
)
from worker.simulation.runner import (
    Answerability,
    ConfidenceLevel,
    QuestionResult,
    SimulationResult,
)


@dataclass
class CriterionScore:
    """Score for a single rubric criterion."""

    criterion: RubricCriterion
    raw_score: float  # 0.0-1.0
    weighted_score: float  # After applying weight
    points_earned: float  # Actual points
    max_points: float
    level: ScoreLevel
    explanation: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "criterion_id": self.criterion.id,
            "criterion_name": self.criterion.name,
            "raw_score": round(self.raw_score, 4),
            "weighted_score": round(self.weighted_score, 4),
            "points_earned": round(self.points_earned, 2),
            "max_points": self.max_points,
            "level": self.level.value,
            "explanation": self.explanation,
        }


@dataclass
class QuestionScore:
    """Detailed score breakdown for a single question."""

    question_id: str
    question_text: str
    category: QuestionCategory
    difficulty: QuestionDifficulty

    # Raw scores
    relevance_score: float
    signal_score: float
    confidence_score: float

    # Weighted and adjusted
    base_score: float
    difficulty_multiplier: float
    category_weight: float
    final_score: float

    # Explanation
    calculation_steps: list[str]
    signals_matched: list[str]
    signals_missing: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "category": self.category.value,
            "difficulty": self.difficulty.value,
            "relevance_score": round(self.relevance_score, 4),
            "signal_score": round(self.signal_score, 4),
            "confidence_score": round(self.confidence_score, 4),
            "base_score": round(self.base_score, 4),
            "difficulty_multiplier": self.difficulty_multiplier,
            "category_weight": self.category_weight,
            "final_score": round(self.final_score, 4),
            "calculation_steps": self.calculation_steps,
            "signals_matched": self.signals_matched,
            "signals_missing": self.signals_missing,
        }


@dataclass
class CategoryBreakdown:
    """Score breakdown for a question category."""

    category: QuestionCategory
    weight: float
    question_count: int
    questions_answered: int
    questions_partial: int
    questions_unanswered: int

    # Scores
    raw_score: float  # Average of question scores
    weighted_score: float  # After applying category weight
    contribution: float  # Points contributed to total

    # Details
    question_scores: list[QuestionScore]
    explanation: str
    recommendations: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "weight": self.weight,
            "question_count": self.question_count,
            "questions_answered": self.questions_answered,
            "questions_partial": self.questions_partial,
            "questions_unanswered": self.questions_unanswered,
            "raw_score": round(self.raw_score, 2),
            "weighted_score": round(self.weighted_score, 2),
            "contribution": round(self.contribution, 2),
            "explanation": self.explanation,
            "recommendations": self.recommendations,
            "question_scores": [q.to_dict() for q in self.question_scores],
        }


@dataclass
class ScoreBreakdown:
    """Complete score breakdown with full transparency."""

    # Final results
    total_score: float  # 0-100
    grade: str
    grade_description: str

    # Criterion breakdowns
    criterion_scores: list[CriterionScore]

    # Category breakdowns
    category_breakdowns: dict[str, CategoryBreakdown]

    # Question-level details
    question_scores: list[QuestionScore]

    # Summary stats
    total_questions: int
    questions_answered: int
    questions_partial: int
    questions_unanswered: int
    coverage_percentage: float

    # The math - step by step calculation
    calculation_summary: list[str]
    formula_used: str

    # Rubric reference
    rubric_version: str

    # Coverage by question bucket
    entity_coverage: float = 0.0  # % entity-fact questions answerable
    product_coverage: float = 0.0  # % product/how-to questions answerable

    # Metadata
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_score": round(self.total_score, 2),
            "grade": self.grade,
            "grade_description": self.grade_description,
            "criterion_scores": [c.to_dict() for c in self.criterion_scores],
            "category_breakdowns": {k: v.to_dict() for k, v in self.category_breakdowns.items()},
            "question_scores": [q.to_dict() for q in self.question_scores],
            "total_questions": self.total_questions,
            "questions_answered": self.questions_answered,
            "questions_partial": self.questions_partial,
            "questions_unanswered": self.questions_unanswered,
            "coverage_percentage": round(self.coverage_percentage, 2),
            "calculation_summary": self.calculation_summary,
            "formula_used": self.formula_used,
            "rubric_version": self.rubric_version,
            "metadata": self.metadata,
        }

    def show_the_math(self) -> str:
        """Generate human-readable calculation breakdown."""
        lines = [
            "=" * 60,
            "FINDABLE SCORE CALCULATION BREAKDOWN",
            "=" * 60,
            "",
            f"Final Score: {self.total_score:.1f}/100 (Grade: {self.grade})",
            f"Grade Description: {self.grade_description}",
            "",
            "-" * 60,
            "FORMULA",
            "-" * 60,
            self.formula_used,
            "",
            "-" * 60,
            "CALCULATION STEPS",
            "-" * 60,
        ]

        for i, step in enumerate(self.calculation_summary, 1):
            lines.append(f"{i}. {step}")

        lines.extend(
            [
                "",
                "-" * 60,
                "CRITERION BREAKDOWN",
                "-" * 60,
            ]
        )

        for cs in self.criterion_scores:
            lines.append(
                f"  {cs.criterion.name}: {cs.points_earned:.1f}/{cs.max_points} "
                f"({cs.level.value})"
            )
            lines.append(f"    → {cs.explanation}")

        lines.extend(
            [
                "",
                "-" * 60,
                "CATEGORY BREAKDOWN",
                "-" * 60,
            ]
        )

        for cat_name, cat in self.category_breakdowns.items():
            lines.append(
                f"  {cat_name.upper()}: {cat.raw_score:.1f}% "
                f"(weight: {cat.weight:.0%}, contribution: {cat.contribution:.1f}pts)"
            )
            lines.append(
                f"    → {cat.questions_answered} answered, "
                f"{cat.questions_partial} partial, "
                f"{cat.questions_unanswered} unanswered"
            )

        lines.extend(
            [
                "",
                "-" * 60,
                "COVERAGE",
                "-" * 60,
                f"  Questions Answered: {self.questions_answered}/{self.total_questions}",
                f"  Coverage: {self.coverage_percentage:.1f}%",
                "",
                "=" * 60,
            ]
        )

        return "\n".join(lines)


class ScoreCalculator:
    """Calculates scores with full transparency."""

    def __init__(self, rubric: ScoringRubric | None = None):
        self.rubric = rubric or DEFAULT_RUBRIC

    def calculate(self, simulation: SimulationResult) -> ScoreBreakdown:
        """
        Calculate score with full breakdown.

        Args:
            simulation: Simulation result to score

        Returns:
            ScoreBreakdown with complete transparency
        """
        if not simulation.question_results:
            grade = self.rubric.get_grade(0.0)
            return ScoreBreakdown(
                total_score=0.0,
                grade=grade,
                grade_description=self.rubric.get_grade_description(grade),
                criterion_scores=[],
                category_breakdowns={},
                question_scores=[],
                total_questions=0,
                questions_answered=0,
                questions_partial=0,
                questions_unanswered=0,
                coverage_percentage=0.0,
                entity_coverage=getattr(simulation, "entity_coverage", 0.0),
                product_coverage=getattr(simulation, "product_coverage", 0.0),
                calculation_summary=["No questions to score."],
                formula_used=self._get_formula(),
                rubric_version=self.rubric.version,
            )

        # Calculate question-level scores
        question_scores = self._calculate_question_scores(simulation.question_results)

        # Calculate category breakdowns
        category_breakdowns = self._calculate_category_breakdowns(
            simulation.question_results,
            question_scores,
        )

        # Calculate criterion scores
        criterion_scores = self._calculate_criterion_scores(simulation)

        # Calculate total score
        total_score = self._calculate_total_score(
            criterion_scores,
            category_breakdowns,
        )

        # Get grade
        grade = self.rubric.get_grade(total_score)
        grade_description = self.rubric.get_grade_description(grade)

        # Generate calculation summary
        calculation_summary = self._generate_calculation_summary(
            criterion_scores,
            category_breakdowns,
            total_score,
        )

        # Count questions
        answered = sum(
            1
            for r in simulation.question_results
            if r.answerability == Answerability.FULLY_ANSWERABLE
        )
        partial = sum(
            1
            for r in simulation.question_results
            if r.answerability == Answerability.PARTIALLY_ANSWERABLE
        )
        unanswered = sum(
            1
            for r in simulation.question_results
            if r.answerability == Answerability.NOT_ANSWERABLE
        )
        coverage = (
            (answered + partial * 0.5) / len(simulation.question_results) * 100
            if simulation.question_results
            else 0
        )

        return ScoreBreakdown(
            total_score=total_score,
            grade=grade,
            grade_description=grade_description,
            criterion_scores=criterion_scores,
            category_breakdowns=category_breakdowns,
            question_scores=question_scores,
            total_questions=len(simulation.question_results),
            questions_answered=answered,
            questions_partial=partial,
            questions_unanswered=unanswered,
            coverage_percentage=coverage,
            entity_coverage=getattr(simulation, "entity_coverage", 0.0),
            product_coverage=getattr(simulation, "product_coverage", 0.0),
            calculation_summary=calculation_summary,
            formula_used=self._get_formula(),
            rubric_version=self.rubric.version,
        )

    def _calculate_question_scores(
        self,
        results: list[QuestionResult],
    ) -> list[QuestionScore]:
        """Calculate detailed scores for each question."""
        question_scores: list[QuestionScore] = []

        for result in results:
            # Get raw scores
            # Normalize RRF scores (0.001-0.03) to 0-1 range
            raw_relevance = result.context.avg_relevance_score
            relevance = min(1.0, raw_relevance / 0.02) if raw_relevance < 0.1 else raw_relevance
            signal = (
                result.signals_found / result.signals_total if result.signals_total > 0 else 0.5
            )
            confidence = self._confidence_to_score(result.confidence)

            # Calculate base score
            base = 0.4 * relevance + 0.4 * signal + 0.2 * confidence

            # Get multipliers
            diff_mult = self.rubric.get_difficulty_multiplier(result.difficulty)
            cat_weight = self.rubric.get_category_weight(result.category)

            # Calculate final score (capped at 1.0)
            final = min(1.0, base * diff_mult) * cat_weight

            # Build calculation steps
            steps = [
                f"Relevance: {relevance:.2f} × 0.4 = {relevance * 0.4:.3f}",
                f"Signal: {signal:.2f} × 0.4 = {signal * 0.4:.3f}",
                f"Confidence: {confidence:.2f} × 0.2 = {confidence * 0.2:.3f}",
                f"Base Score: {base:.3f}",
                f"Difficulty Multiplier ({result.difficulty.value}): × {diff_mult}",
                f"Category Weight ({result.category.value}): × {cat_weight:.2f}",
                f"Final: {final:.3f}",
            ]

            # Get signals
            matched = [m.signal for m in result.signal_matches if m.found]
            missing = [m.signal for m in result.signal_matches if not m.found]

            question_scores.append(
                QuestionScore(
                    question_id=result.question_id,
                    question_text=result.question_text,
                    category=result.category,
                    difficulty=result.difficulty,
                    relevance_score=relevance,
                    signal_score=signal,
                    confidence_score=confidence,
                    base_score=base,
                    difficulty_multiplier=diff_mult,
                    category_weight=cat_weight,
                    final_score=final,
                    calculation_steps=steps,
                    signals_matched=matched,
                    signals_missing=missing,
                )
            )

        return question_scores

    def _calculate_category_breakdowns(
        self,
        results: list[QuestionResult],
        question_scores: list[QuestionScore],
    ) -> dict[str, CategoryBreakdown]:
        """Calculate breakdowns by category."""
        breakdowns: dict[str, CategoryBreakdown] = {}

        # Group by category
        by_category: dict[QuestionCategory, list[tuple[QuestionResult, QuestionScore]]] = {}
        for result, qs in zip(results, question_scores, strict=True):
            if result.category not in by_category:
                by_category[result.category] = []
            by_category[result.category].append((result, qs))

        for category, items in by_category.items():
            cat_results = [r for r, _ in items]
            cat_scores = [qs for _, qs in items]

            # Count by answerability
            answered = sum(
                1 for r in cat_results if r.answerability == Answerability.FULLY_ANSWERABLE
            )
            partial = sum(
                1 for r in cat_results if r.answerability == Answerability.PARTIALLY_ANSWERABLE
            )
            unanswered = sum(
                1 for r in cat_results if r.answerability == Answerability.NOT_ANSWERABLE
            )

            # Calculate scores
            raw = sum(r.score for r in cat_results) / len(cat_results) * 100
            weight = self.rubric.get_category_weight(category)
            weighted = raw * weight
            contribution = weighted

            # Generate explanation
            explanation = self._generate_category_explanation(
                category, answered, partial, unanswered, raw
            )

            # Generate recommendations
            recommendations = self._generate_category_recommendations(category, cat_results)

            breakdowns[category.value] = CategoryBreakdown(
                category=category,
                weight=weight,
                question_count=len(items),
                questions_answered=answered,
                questions_partial=partial,
                questions_unanswered=unanswered,
                raw_score=raw,
                weighted_score=weighted,
                contribution=contribution,
                question_scores=cat_scores,
                explanation=explanation,
                recommendations=recommendations,
            )

        return breakdowns

    def _calculate_criterion_scores(
        self,
        simulation: SimulationResult,
    ) -> list[CriterionScore]:
        """Calculate scores for each rubric criterion."""
        scores: list[CriterionScore] = []

        for criterion in self.rubric.criteria:
            if criterion.id == "content_relevance":
                raw = self._calculate_relevance_score(simulation)
                explanation = (
                    f"Average content relevance across {len(simulation.question_results)} questions"
                )
            elif criterion.id == "signal_coverage":
                raw = self._calculate_signal_score(simulation)
                explanation = "Expected signals found in retrieved content"
            elif criterion.id == "answer_confidence":
                raw = self._calculate_confidence_score(simulation)
                explanation = "Confidence in answer completeness and accuracy"
            elif criterion.id == "source_quality":
                raw = self._calculate_source_quality(simulation)
                explanation = "Quality and diversity of source pages"
            else:
                raw = 0.5
                explanation = "Unknown criterion"

            weighted = raw * criterion.weight
            points = raw * criterion.max_points
            level = criterion.get_level(raw)

            scores.append(
                CriterionScore(
                    criterion=criterion,
                    raw_score=raw,
                    weighted_score=weighted,
                    points_earned=points,
                    max_points=criterion.max_points,
                    level=level,
                    explanation=explanation,
                )
            )

        return scores

    def _calculate_total_score(
        self,
        criterion_scores: list[CriterionScore],
        category_breakdowns: dict[str, CategoryBreakdown],
    ) -> float:
        """Calculate final total score."""
        # Method 1: Sum of criterion points
        criterion_total = sum(cs.points_earned for cs in criterion_scores)

        # Method 2: Weighted category average
        if category_breakdowns:
            category_total = sum(cb.weighted_score for cb in category_breakdowns.values())
        else:
            category_total = 0

        # Blend both methods (favor criterion-based)
        return criterion_total * 0.7 + category_total * 0.3

    def _calculate_relevance_score(self, simulation: SimulationResult) -> float:
        """Calculate average relevance score."""
        if not simulation.question_results:
            return 0.0
        # Normalize RRF scores (0.001-0.03) to 0-1 range
        normalized_scores = []
        for r in simulation.question_results:
            raw = r.context.avg_relevance_score
            normalized = min(1.0, raw / 0.02) if raw < 0.1 else raw
            normalized_scores.append(normalized)
        return sum(normalized_scores) / len(normalized_scores)

    def _calculate_signal_score(self, simulation: SimulationResult) -> float:
        """Calculate overall signal coverage."""
        questions_with_signals = [r for r in simulation.question_results if r.signals_total > 0]
        if not questions_with_signals:
            return 0.0

        total_signals = sum(r.signals_total for r in questions_with_signals)
        found_signals = sum(r.signals_found for r in questions_with_signals)
        return found_signals / total_signals if total_signals > 0 else 0.0

    def _calculate_confidence_score(self, simulation: SimulationResult) -> float:
        """Calculate average confidence score."""
        if not simulation.question_results:
            return 0.0
        return sum(
            self._confidence_to_score(r.confidence) for r in simulation.question_results
        ) / len(simulation.question_results)

    def _calculate_source_quality(self, simulation: SimulationResult) -> float:
        """Calculate source quality score."""
        if not simulation.question_results:
            return 0.0

        # Based on number of unique sources and max relevance
        all_sources: set[str] = set()
        max_scores: list[float] = []

        for r in simulation.question_results:
            all_sources.update(r.context.source_pages)
            max_scores.append(r.context.max_relevance_score)

        # Diversity bonus
        diversity = min(1.0, len(all_sources) / 10)

        # Quality from max scores
        quality = sum(max_scores) / len(max_scores) if max_scores else 0

        return diversity * 0.3 + quality * 0.7

    def _confidence_to_score(self, confidence: ConfidenceLevel) -> float:
        """Convert confidence level to numeric score."""
        mapping = {
            ConfidenceLevel.HIGH: 1.0,
            ConfidenceLevel.MEDIUM: 0.6,
            ConfidenceLevel.LOW: 0.3,
        }
        return mapping.get(confidence, 0.5)

    def _generate_calculation_summary(
        self,
        criterion_scores: list[CriterionScore],
        category_breakdowns: dict[str, CategoryBreakdown],
        total_score: float,
    ) -> list[str]:
        """Generate step-by-step calculation summary."""
        steps = [
            "Calculate criterion scores:",
        ]

        for cs in criterion_scores:
            steps.append(
                f"  {cs.criterion.name}: {cs.raw_score:.2f} × {cs.criterion.weight:.2f} "
                f"= {cs.weighted_score:.3f} ({cs.points_earned:.1f} pts)"
            )

        criterion_total = sum(cs.points_earned for cs in criterion_scores)
        steps.append(f"Criterion subtotal: {criterion_total:.1f} points")

        steps.append("")
        steps.append("Calculate category contributions:")

        for name, cb in category_breakdowns.items():
            steps.append(
                f"  {name}: {cb.raw_score:.1f}% × {cb.weight:.2f} = {cb.contribution:.1f} pts"
            )

        category_total = sum(cb.weighted_score for cb in category_breakdowns.values())
        steps.append(f"Category subtotal: {category_total:.1f} points")

        steps.append("")
        steps.append("Final calculation:")
        steps.append(
            f"  ({criterion_total:.1f} × 0.7) + ({category_total:.1f} × 0.3) = {total_score:.1f}"
        )

        return steps

    def _generate_category_explanation(
        self,
        category: QuestionCategory,
        answered: int,
        partial: int,
        unanswered: int,
        raw_score: float,
    ) -> str:
        """Generate explanation for category score."""
        total = answered + partial + unanswered
        if raw_score >= 80:
            status = "Strong performance"
        elif raw_score >= 60:
            status = "Adequate coverage"
        else:
            status = "Needs improvement"

        return (
            f"{status} in {category.value}: "
            f"{answered}/{total} fully answered, "
            f"{partial} partial, {unanswered} unanswered"
        )

    def _generate_category_recommendations(
        self,
        category: QuestionCategory,
        results: list[QuestionResult],
    ) -> list[str]:
        """Generate recommendations for a category."""
        recommendations: list[str] = []

        unanswered = [r for r in results if r.answerability == Answerability.NOT_ANSWERABLE]

        if unanswered:
            if category == QuestionCategory.IDENTITY:
                recommendations.append(
                    "Add or enhance your 'About Us' page with company history and mission"
                )
            elif category == QuestionCategory.OFFERINGS:
                recommendations.append(
                    "Create detailed product/service pages with features and benefits"
                )
            elif category == QuestionCategory.CONTACT:
                recommendations.append("Make contact information more prominent and accessible")
            elif category == QuestionCategory.TRUST:
                recommendations.append(
                    "Add customer testimonials, case studies, and certifications"
                )
            elif category == QuestionCategory.DIFFERENTIATION:
                recommendations.append(
                    "Highlight unique value propositions and competitive advantages"
                )

        return recommendations[:3]

    def _get_formula(self) -> str:
        """Get the scoring formula as a string."""
        return (
            "Score = (Criterion Points × 0.7) + (Category Weighted Average × 0.3)\n"
            "Where:\n"
            "  Criterion Points = Σ(raw_score × weight × max_points)\n"
            "  Category Average = Σ(category_score × category_weight)\n"
            "  Question Score = (0.4×relevance + 0.4×signals + 0.2×confidence) × difficulty_mult"
        )


def calculate_score(
    simulation: SimulationResult,
    rubric: ScoringRubric | None = None,
) -> ScoreBreakdown:
    """
    Convenience function to calculate score with breakdown.

    Args:
        simulation: Simulation result to score
        rubric: Optional custom rubric

    Returns:
        ScoreBreakdown with full transparency
    """
    calculator = ScoreCalculator(rubric)
    return calculator.calculate(simulation)
