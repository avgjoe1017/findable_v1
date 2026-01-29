"""Simulation result analysis and utilities."""

from dataclasses import dataclass, field
from typing import Any

from worker.questions.universal import QuestionCategory
from worker.simulation.runner import (
    Answerability,
    ConfidenceLevel,
    QuestionResult,
    SimulationResult,
)


@dataclass
class CategoryAnalysis:
    """Analysis of a question category."""

    category: QuestionCategory
    total_questions: int
    answerable_count: int
    partial_count: int
    unanswerable_count: int
    avg_score: float
    avg_confidence: float
    top_gaps: list[str]  # Questions with lowest scores

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "total_questions": self.total_questions,
            "answerable_count": self.answerable_count,
            "partial_count": self.partial_count,
            "unanswerable_count": self.unanswerable_count,
            "avg_score": self.avg_score,
            "avg_confidence": self.avg_confidence,
            "top_gaps": self.top_gaps,
        }


@dataclass
class SignalAnalysis:
    """Analysis of expected signals across all questions."""

    total_signals: int
    signals_found: int
    signals_missing: int
    coverage_percentage: float
    most_common_missing: list[str]
    most_common_found: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_signals": self.total_signals,
            "signals_found": self.signals_found,
            "signals_missing": self.signals_missing,
            "coverage_percentage": self.coverage_percentage,
            "most_common_missing": self.most_common_missing,
            "most_common_found": self.most_common_found,
        }


@dataclass
class GapAnalysis:
    """Analysis of content gaps."""

    unanswerable_questions: list[QuestionResult]
    partial_questions: list[QuestionResult]
    missing_signals: list[str]
    weak_categories: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "unanswerable_count": len(self.unanswerable_questions),
            "partial_count": len(self.partial_questions),
            "unanswerable_questions": [
                {"id": q.question_id, "question": q.question_text}
                for q in self.unanswerable_questions
            ],
            "partial_questions": [
                {"id": q.question_id, "question": q.question_text, "score": q.score}
                for q in self.partial_questions
            ],
            "missing_signals": self.missing_signals,
            "weak_categories": self.weak_categories,
            "recommendations": self.recommendations,
        }


@dataclass
class SimulationSummary:
    """Summary of simulation results for reporting."""

    site_id: str
    company_name: str
    overall_score: float
    grade: str  # A, B, C, D, F
    coverage_score: float
    confidence_score: float

    # Breakdown
    questions_total: int
    questions_answered: int
    questions_partial: int
    questions_unanswered: int

    # Category breakdown
    category_analysis: dict[str, CategoryAnalysis]

    # Signal analysis
    signal_analysis: SignalAnalysis

    # Gaps
    gap_analysis: GapAnalysis

    # Metadata
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "site_id": self.site_id,
            "company_name": self.company_name,
            "overall_score": self.overall_score,
            "grade": self.grade,
            "coverage_score": self.coverage_score,
            "confidence_score": self.confidence_score,
            "questions_total": self.questions_total,
            "questions_answered": self.questions_answered,
            "questions_partial": self.questions_partial,
            "questions_unanswered": self.questions_unanswered,
            "category_analysis": {k: v.to_dict() for k, v in self.category_analysis.items()},
            "signal_analysis": self.signal_analysis.to_dict(),
            "gap_analysis": self.gap_analysis.to_dict(),
            "metadata": self.metadata,
        }


def calculate_grade(score: float) -> str:
    """Calculate letter grade from score."""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"


def analyze_simulation(result: SimulationResult) -> SimulationSummary:
    """
    Analyze simulation results and generate summary.

    Args:
        result: SimulationResult to analyze

    Returns:
        SimulationSummary with detailed analysis
    """
    # Analyze by category
    category_analysis = _analyze_categories(result.question_results)

    # Analyze signals
    signal_analysis = _analyze_signals(result.question_results)

    # Analyze gaps
    gap_analysis = _analyze_gaps(result.question_results, category_analysis)

    # Calculate grade
    grade = calculate_grade(result.overall_score)

    return SimulationSummary(
        site_id=str(result.site_id),
        company_name=result.company_name,
        overall_score=result.overall_score,
        grade=grade,
        coverage_score=result.coverage_score,
        confidence_score=result.confidence_score,
        questions_total=result.total_questions,
        questions_answered=result.questions_answered,
        questions_partial=result.questions_partial,
        questions_unanswered=result.questions_unanswered,
        category_analysis=category_analysis,
        signal_analysis=signal_analysis,
        gap_analysis=gap_analysis,
    )


def _analyze_categories(
    results: list[QuestionResult],
) -> dict[str, CategoryAnalysis]:
    """Analyze results by category."""
    categories: dict[str, list[QuestionResult]] = {}

    for r in results:
        cat = r.category.value
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)

    analysis: dict[str, CategoryAnalysis] = {}

    for cat, cat_results in categories.items():
        answerable = sum(
            1 for r in cat_results if r.answerability == Answerability.FULLY_ANSWERABLE
        )
        partial = sum(
            1 for r in cat_results if r.answerability == Answerability.PARTIALLY_ANSWERABLE
        )
        unanswerable = sum(
            1 for r in cat_results if r.answerability == Answerability.NOT_ANSWERABLE
        )

        avg_score = sum(r.score for r in cat_results) / len(cat_results)

        confidence_values = {
            ConfidenceLevel.HIGH: 1.0,
            ConfidenceLevel.MEDIUM: 0.6,
            ConfidenceLevel.LOW: 0.3,
        }
        avg_confidence = sum(confidence_values[r.confidence] for r in cat_results) / len(
            cat_results
        )

        # Find top gaps (lowest scoring questions)
        sorted_results = sorted(cat_results, key=lambda r: r.score)
        top_gaps = [r.question_text for r in sorted_results[:3] if r.score < 0.5]

        analysis[cat] = CategoryAnalysis(
            category=QuestionCategory(cat),
            total_questions=len(cat_results),
            answerable_count=answerable,
            partial_count=partial,
            unanswerable_count=unanswerable,
            avg_score=avg_score * 100,
            avg_confidence=avg_confidence * 100,
            top_gaps=top_gaps,
        )

    return analysis


def _analyze_signals(results: list[QuestionResult]) -> SignalAnalysis:
    """Analyze signal coverage across all questions."""
    found_signals: list[str] = []
    missing_signals: list[str] = []

    for r in results:
        for match in r.signal_matches:
            if match.found:
                found_signals.append(match.signal)
            else:
                missing_signals.append(match.signal)

    total = len(found_signals) + len(missing_signals)
    coverage = (len(found_signals) / total * 100) if total > 0 else 0.0

    # Count frequency
    from collections import Counter

    missing_counter = Counter(missing_signals)
    found_counter = Counter(found_signals)

    most_common_missing = [s for s, _ in missing_counter.most_common(5)]
    most_common_found = [s for s, _ in found_counter.most_common(5)]

    return SignalAnalysis(
        total_signals=total,
        signals_found=len(found_signals),
        signals_missing=len(missing_signals),
        coverage_percentage=coverage,
        most_common_missing=most_common_missing,
        most_common_found=most_common_found,
    )


def _analyze_gaps(
    results: list[QuestionResult],
    category_analysis: dict[str, CategoryAnalysis],
) -> GapAnalysis:
    """Analyze content gaps and generate recommendations."""
    unanswerable = [r for r in results if r.answerability == Answerability.NOT_ANSWERABLE]
    partial = [r for r in results if r.answerability == Answerability.PARTIALLY_ANSWERABLE]

    # Collect missing signals
    missing_signals: list[str] = []
    for r in unanswerable + partial:
        for match in r.signal_matches:
            if not match.found:
                missing_signals.append(match.signal)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_missing: list[str] = []
    for s in missing_signals:
        if s not in seen:
            seen.add(s)
            unique_missing.append(s)

    # Find weak categories (below 50% score)
    weak_categories = [
        cat for cat, analysis in category_analysis.items() if analysis.avg_score < 50
    ]

    # Generate recommendations
    recommendations = _generate_recommendations(
        unanswerable, partial, unique_missing, weak_categories
    )

    return GapAnalysis(
        unanswerable_questions=unanswerable,
        partial_questions=partial,
        missing_signals=unique_missing[:10],
        weak_categories=weak_categories,
        recommendations=recommendations,
    )


def _generate_recommendations(
    unanswerable: list[QuestionResult],
    partial: list[QuestionResult],
    missing_signals: list[str],
    weak_categories: list[str],
) -> list[str]:
    """Generate actionable recommendations."""
    recommendations: list[str] = []

    # Category-specific recommendations
    category_recommendations = {
        "identity": "Add a clear 'About Us' page with company history, founders, and location",
        "offerings": "Create detailed product/service pages with features and pricing",
        "contact": "Add a prominent contact page with multiple contact methods",
        "trust": "Add customer testimonials, case studies, and certifications",
        "differentiation": "Highlight unique value propositions and competitive advantages",
    }

    for cat in weak_categories:
        if cat in category_recommendations:
            recommendations.append(category_recommendations[cat])

    # Signal-specific recommendations
    if "pricing" in " ".join(missing_signals).lower():
        recommendations.append("Add clear pricing information or pricing page")

    if "founder" in " ".join(missing_signals).lower():
        recommendations.append("Add founder/leadership team information")

    if "contact" in " ".join(missing_signals).lower():
        recommendations.append("Make contact information more prominent")

    # General recommendations based on gaps
    if len(unanswerable) > 5:
        recommendations.append("Significant content gaps detected - consider a content audit")

    if len(partial) > len(unanswerable):
        recommendations.append(
            "Many partial answers found - enhance existing content with more detail"
        )

    # Limit recommendations
    return recommendations[:5]


def get_question_details(
    result: SimulationResult,
    question_id: str,
) -> QuestionResult | None:
    """Get detailed results for a specific question."""
    for q in result.question_results:
        if q.question_id == question_id:
            return q
    return None


def get_category_results(
    result: SimulationResult,
    category: QuestionCategory,
) -> list[QuestionResult]:
    """Get all results for a specific category."""
    return [r for r in result.question_results if r.category == category]


def get_unanswerable_questions(
    result: SimulationResult,
) -> list[QuestionResult]:
    """Get all unanswerable questions."""
    return [r for r in result.question_results if r.answerability == Answerability.NOT_ANSWERABLE]


def compare_simulations(
    baseline: SimulationResult,
    current: SimulationResult,
) -> dict[str, Any]:
    """
    Compare two simulation results.

    Args:
        baseline: Previous simulation result
        current: Current simulation result

    Returns:
        Dictionary with comparison metrics
    """
    return {
        "overall_score_change": current.overall_score - baseline.overall_score,
        "coverage_change": current.coverage_score - baseline.coverage_score,
        "confidence_change": current.confidence_score - baseline.confidence_score,
        "questions_improved": _count_improved(baseline, current),
        "questions_regressed": _count_regressed(baseline, current),
        "category_changes": _compare_categories(baseline, current),
    }


def _count_improved(
    baseline: SimulationResult,
    current: SimulationResult,
) -> int:
    """Count questions that improved."""
    baseline_scores = {r.question_id: r.score for r in baseline.question_results}
    improved = 0

    for r in current.question_results:
        if r.question_id in baseline_scores and r.score > baseline_scores[r.question_id]:
            improved += 1

    return improved


def _count_regressed(
    baseline: SimulationResult,
    current: SimulationResult,
) -> int:
    """Count questions that regressed."""
    baseline_scores = {r.question_id: r.score for r in baseline.question_results}
    regressed = 0

    for r in current.question_results:
        if r.question_id in baseline_scores and r.score < baseline_scores[r.question_id]:
            regressed += 1

    return regressed


def _compare_categories(
    baseline: SimulationResult,
    current: SimulationResult,
) -> dict[str, float]:
    """Compare category scores between runs."""
    changes: dict[str, float] = {}

    for cat in current.category_scores:
        baseline_score = baseline.category_scores.get(cat, 0)
        current_score = current.category_scores[cat]
        changes[cat] = current_score - baseline_score

    return changes
