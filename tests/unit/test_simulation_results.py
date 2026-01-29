"""Tests for simulation results analysis."""

from datetime import datetime
from uuid import uuid4

from worker.questions.generator import QuestionSource
from worker.questions.universal import QuestionCategory, QuestionDifficulty
from worker.simulation.results import (
    CategoryAnalysis,
    GapAnalysis,
    SignalAnalysis,
    SimulationSummary,
    analyze_simulation,
    calculate_grade,
    compare_simulations,
    get_category_results,
    get_question_details,
    get_unanswerable_questions,
)
from worker.simulation.runner import (
    Answerability,
    ConfidenceLevel,
    QuestionResult,
    RetrievedContext,
    SignalMatch,
    SimulationResult,
)


def make_question_result(
    question_id: str = "UQ-01",
    question_text: str = "What does TestCo do?",
    category: QuestionCategory = QuestionCategory.IDENTITY,
    answerability: Answerability = Answerability.FULLY_ANSWERABLE,
    score: float = 0.8,
    signals_found: int = 2,
    signals_total: int = 3,
) -> QuestionResult:
    """Create a test question result."""
    return QuestionResult(
        question_id=question_id,
        question_text=question_text,
        category=category,
        difficulty=QuestionDifficulty.EASY,
        source=QuestionSource.UNIVERSAL,
        weight=1.0,
        answerability=answerability,
        confidence=ConfidenceLevel.HIGH,
        score=score,
        context=RetrievedContext(
            chunks=[],
            total_chunks=1,
            avg_relevance_score=0.8,
            max_relevance_score=0.8,
            source_pages=["https://test.com"],
            content_preview="Test content",
        ),
        signal_matches=[
            SignalMatch("signal1", True, 1.0, "evidence"),
            SignalMatch("signal2", True, 0.8, "evidence"),
            SignalMatch("signal3", False, 0.0, None),
        ][:signals_total],
        signals_found=signals_found,
        signals_total=signals_total,
        retrieval_time_ms=10.0,
        evaluation_time_ms=5.0,
    )


def make_simulation_result(
    question_results: list[QuestionResult] | None = None,
) -> SimulationResult:
    """Create a test simulation result."""
    if question_results is None:
        question_results = [
            make_question_result("UQ-01", category=QuestionCategory.IDENTITY),
            make_question_result("UQ-02", category=QuestionCategory.OFFERINGS),
            make_question_result(
                "UQ-03",
                category=QuestionCategory.CONTACT,
                answerability=Answerability.NOT_ANSWERABLE,
                score=0.0,
            ),
        ]

    answered = sum(1 for r in question_results if r.answerability == Answerability.FULLY_ANSWERABLE)
    partial = sum(
        1 for r in question_results if r.answerability == Answerability.PARTIALLY_ANSWERABLE
    )
    unanswered = sum(1 for r in question_results if r.answerability == Answerability.NOT_ANSWERABLE)

    return SimulationResult(
        site_id=uuid4(),
        run_id=uuid4(),
        company_name="TestCo",
        question_results=question_results,
        total_questions=len(question_results),
        questions_answered=answered,
        questions_partial=partial,
        questions_unanswered=unanswered,
        category_scores={"identity": 80.0, "offerings": 75.0, "contact": 0.0},
        difficulty_scores={"easy": 70.0},
        overall_score=70.0,
        coverage_score=66.7,
        confidence_score=80.0,
        total_time_ms=100.0,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )


class TestCalculateGrade:
    """Tests for calculate_grade function."""

    def test_grade_a(self) -> None:
        """Score >= 90 is A."""
        assert calculate_grade(95) == "A"
        assert calculate_grade(90) == "A"

    def test_grade_b(self) -> None:
        """Score 80-89 is B."""
        assert calculate_grade(89) == "B"
        assert calculate_grade(80) == "B"

    def test_grade_c(self) -> None:
        """Score 70-79 is C."""
        assert calculate_grade(79) == "C"
        assert calculate_grade(70) == "C"

    def test_grade_d(self) -> None:
        """Score 60-69 is D."""
        assert calculate_grade(69) == "D"
        assert calculate_grade(60) == "D"

    def test_grade_f(self) -> None:
        """Score < 60 is F."""
        assert calculate_grade(59) == "F"
        assert calculate_grade(0) == "F"


class TestCategoryAnalysis:
    """Tests for CategoryAnalysis."""

    def test_to_dict(self) -> None:
        """Converts to dict."""
        analysis = CategoryAnalysis(
            category=QuestionCategory.IDENTITY,
            total_questions=3,
            answerable_count=2,
            partial_count=1,
            unanswerable_count=0,
            avg_score=75.0,
            avg_confidence=80.0,
            top_gaps=["What is the mission?"],
        )

        d = analysis.to_dict()
        assert d["category"] == "identity"
        assert d["total_questions"] == 3
        assert d["avg_score"] == 75.0


class TestSignalAnalysis:
    """Tests for SignalAnalysis."""

    def test_to_dict(self) -> None:
        """Converts to dict."""
        analysis = SignalAnalysis(
            total_signals=10,
            signals_found=7,
            signals_missing=3,
            coverage_percentage=70.0,
            most_common_missing=["pricing"],
            most_common_found=["business description"],
        )

        d = analysis.to_dict()
        assert d["total_signals"] == 10
        assert d["coverage_percentage"] == 70.0


class TestGapAnalysis:
    """Tests for GapAnalysis."""

    def test_to_dict(self) -> None:
        """Converts to dict."""
        unanswerable = make_question_result(answerability=Answerability.NOT_ANSWERABLE)
        analysis = GapAnalysis(
            unanswerable_questions=[unanswerable],
            partial_questions=[],
            missing_signals=["pricing"],
            weak_categories=["contact"],
            recommendations=["Add contact page"],
        )

        d = analysis.to_dict()
        assert d["unanswerable_count"] == 1
        assert len(d["missing_signals"]) == 1


class TestAnalyzeSimulation:
    """Tests for analyze_simulation function."""

    def test_analyze_basic(self) -> None:
        """Basic analysis works."""
        result = make_simulation_result()
        summary = analyze_simulation(result)

        assert isinstance(summary, SimulationSummary)
        assert summary.company_name == "TestCo"
        assert summary.overall_score == 70.0

    def test_analyze_grade(self) -> None:
        """Calculates grade correctly."""
        result = make_simulation_result()
        summary = analyze_simulation(result)

        assert summary.grade == "C"  # 70 score

    def test_analyze_categories(self) -> None:
        """Analyzes categories."""
        result = make_simulation_result()
        summary = analyze_simulation(result)

        assert "identity" in summary.category_analysis
        assert summary.category_analysis["identity"].total_questions == 1

    def test_analyze_signals(self) -> None:
        """Analyzes signals."""
        result = make_simulation_result()
        summary = analyze_simulation(result)

        assert summary.signal_analysis.total_signals > 0

    def test_analyze_gaps(self) -> None:
        """Analyzes gaps."""
        result = make_simulation_result()
        summary = analyze_simulation(result)

        assert len(summary.gap_analysis.unanswerable_questions) == 1

    def test_summary_to_dict(self) -> None:
        """Summary converts to dict."""
        result = make_simulation_result()
        summary = analyze_simulation(result)

        d = summary.to_dict()
        assert "overall_score" in d
        assert "grade" in d
        assert "category_analysis" in d


class TestGetQuestionDetails:
    """Tests for get_question_details function."""

    def test_find_question(self) -> None:
        """Finds existing question."""
        result = make_simulation_result()
        question = get_question_details(result, "UQ-01")

        assert question is not None
        assert question.question_id == "UQ-01"

    def test_not_found(self) -> None:
        """Returns None for missing question."""
        result = make_simulation_result()
        question = get_question_details(result, "UNKNOWN")

        assert question is None


class TestGetCategoryResults:
    """Tests for get_category_results function."""

    def test_filter_by_category(self) -> None:
        """Filters results by category."""
        result = make_simulation_result()
        identity_results = get_category_results(result, QuestionCategory.IDENTITY)

        assert len(identity_results) == 1
        assert all(r.category == QuestionCategory.IDENTITY for r in identity_results)

    def test_empty_category(self) -> None:
        """Returns empty for category with no questions."""
        result = make_simulation_result()
        trust_results = get_category_results(result, QuestionCategory.TRUST)

        assert len(trust_results) == 0


class TestGetUnanswerableQuestions:
    """Tests for get_unanswerable_questions function."""

    def test_get_unanswerable(self) -> None:
        """Gets unanswerable questions."""
        result = make_simulation_result()
        unanswerable = get_unanswerable_questions(result)

        assert len(unanswerable) == 1
        assert all(r.answerability == Answerability.NOT_ANSWERABLE for r in unanswerable)


class TestCompareSimulations:
    """Tests for compare_simulations function."""

    def test_compare_improvement(self) -> None:
        """Detects improvement."""
        baseline = make_simulation_result()
        baseline.overall_score = 60.0

        current = make_simulation_result()
        current.overall_score = 75.0

        comparison = compare_simulations(baseline, current)

        assert comparison["overall_score_change"] == 15.0

    def test_compare_regression(self) -> None:
        """Detects regression."""
        baseline = make_simulation_result()
        baseline.overall_score = 80.0

        current = make_simulation_result()
        current.overall_score = 70.0

        comparison = compare_simulations(baseline, current)

        assert comparison["overall_score_change"] == -10.0

    def test_compare_category_changes(self) -> None:
        """Compares category changes."""
        baseline = make_simulation_result()
        current = make_simulation_result()

        comparison = compare_simulations(baseline, current)

        assert "category_changes" in comparison
        assert isinstance(comparison["category_changes"], dict)


class TestRecommendations:
    """Tests for recommendation generation."""

    def test_generates_recommendations(self) -> None:
        """Generates recommendations for gaps."""
        # Create result with weak category
        results = [
            make_question_result(
                "UQ-01",
                category=QuestionCategory.CONTACT,
                answerability=Answerability.NOT_ANSWERABLE,
                score=0.0,
            ),
            make_question_result(
                "UQ-02",
                category=QuestionCategory.CONTACT,
                answerability=Answerability.NOT_ANSWERABLE,
                score=0.1,
            ),
        ]
        sim_result = make_simulation_result(results)
        sim_result.category_scores = {"contact": 5.0}

        summary = analyze_simulation(sim_result)

        assert len(summary.gap_analysis.recommendations) > 0

    def test_limits_recommendations(self) -> None:
        """Limits number of recommendations."""
        result = make_simulation_result()
        summary = analyze_simulation(result)

        assert len(summary.gap_analysis.recommendations) <= 5
