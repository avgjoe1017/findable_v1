"""Tests for scoring calculator."""

from datetime import datetime
from uuid import uuid4

from worker.questions.generator import QuestionSource
from worker.questions.universal import QuestionCategory, QuestionDifficulty
from worker.scoring.calculator import (
    CategoryBreakdown,
    CriterionScore,
    QuestionScore,
    ScoreBreakdown,
    ScoreCalculator,
    calculate_score,
)
from worker.scoring.rubric import RubricCriterion, ScoreLevel, ScoringRubric
from worker.simulation.runner import (
    Answerability,
    ConfidenceLevel,
    QuestionResult,
    RetrievedContext,
    SignalMatch,
    SimulationResult,
)


def make_retrieved_context(
    total_chunks: int = 3,
    avg_relevance: float = 0.8,
    max_relevance: float = 0.95,
) -> RetrievedContext:
    """Create a test RetrievedContext."""
    return RetrievedContext(
        chunks=[],  # Empty list for testing
        total_chunks=total_chunks,
        avg_relevance_score=avg_relevance,
        max_relevance_score=max_relevance,
        source_pages=["https://example.com/page1", "https://example.com/page2"],
        content_preview="Test content preview for simulation.",
    )


def make_question_result(
    question_id: str | None = None,
    category: QuestionCategory = QuestionCategory.IDENTITY,
    difficulty: QuestionDifficulty = QuestionDifficulty.EASY,
    answerability: Answerability = Answerability.FULLY_ANSWERABLE,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    score: float = 0.85,
    signals_found: int = 3,
    signals_total: int = 4,
    avg_relevance: float = 0.8,
) -> QuestionResult:
    """Create a test QuestionResult."""
    return QuestionResult(
        question_id=question_id or str(uuid4()),
        question_text="What is the company's mission?",
        category=category,
        difficulty=difficulty,
        source=QuestionSource.UNIVERSAL,
        weight=1.0,
        context=make_retrieved_context(avg_relevance=avg_relevance),
        answerability=answerability,
        confidence=confidence,
        score=score,
        signals_found=signals_found,
        signals_total=signals_total,
        signal_matches=[
            SignalMatch(signal="mission statement", found=True, confidence=1.0),
            SignalMatch(signal="company values", found=True, confidence=0.9),
            SignalMatch(signal="founding story", found=True, confidence=0.8),
            SignalMatch(signal="team info", found=False, confidence=0.0),
        ],
        retrieval_time_ms=50.0,
        evaluation_time_ms=10.0,
    )


def make_simulation_result(
    question_count: int = 5,
    avg_score: float = 0.75,
) -> SimulationResult:
    """Create a test SimulationResult."""
    categories = [
        QuestionCategory.IDENTITY,
        QuestionCategory.OFFERINGS,
        QuestionCategory.CONTACT,
        QuestionCategory.TRUST,
        QuestionCategory.DIFFERENTIATION,
    ]
    difficulties = [
        QuestionDifficulty.EASY,
        QuestionDifficulty.MEDIUM,
        QuestionDifficulty.HARD,
    ]

    results = []
    for i in range(question_count):
        results.append(
            make_question_result(
                question_id=f"q{i+1}",
                category=categories[i % len(categories)],
                difficulty=difficulties[i % len(difficulties)],
                score=avg_score + (i - question_count // 2) * 0.05,
            )
        )

    now = datetime.utcnow()
    return SimulationResult(
        site_id=uuid4(),
        run_id=uuid4(),
        company_name="Test Company",
        question_results=results,
        total_questions=question_count,
        questions_answered=question_count - 1,
        questions_partial=1,
        questions_unanswered=0,
        category_scores={"identity": 75.0, "offerings": 80.0},
        difficulty_scores={"easy": 80.0, "medium": 75.0, "hard": 70.0},
        overall_score=avg_score * 100,
        coverage_score=90.0,
        confidence_score=85.0,
        total_time_ms=500.0,
        started_at=now,
        completed_at=now,
        metadata={},
    )


class TestCriterionScore:
    """Tests for CriterionScore."""

    def test_create_score(self) -> None:
        """Can create a criterion score."""
        criterion = RubricCriterion(
            id="test",
            name="Test Criterion",
            description="Test description",
            weight=0.25,
            max_points=25,
        )

        score = CriterionScore(
            criterion=criterion,
            raw_score=0.85,
            weighted_score=0.2125,
            points_earned=21.25,
            max_points=25,
            level=ScoreLevel.GOOD,
            explanation="Test explanation",
        )

        assert score.raw_score == 0.85
        assert score.weighted_score == 0.2125
        assert score.points_earned == 21.25
        assert score.level == ScoreLevel.GOOD

    def test_to_dict(self) -> None:
        """Converts to dict."""
        criterion = RubricCriterion(
            id="test",
            name="Test Criterion",
            description="Test",
            weight=0.25,
            max_points=25,
        )

        score = CriterionScore(
            criterion=criterion,
            raw_score=0.85,
            weighted_score=0.2125,
            points_earned=21.25,
            max_points=25,
            level=ScoreLevel.GOOD,
            explanation="Test explanation",
        )

        d = score.to_dict()
        assert d["criterion_id"] == "test"
        assert d["criterion_name"] == "Test Criterion"
        assert d["raw_score"] == 0.85
        assert d["level"] == "good"


class TestQuestionScore:
    """Tests for QuestionScore."""

    def test_create_score(self) -> None:
        """Can create a question score."""
        score = QuestionScore(
            question_id="q1",
            question_text="What is the mission?",
            category=QuestionCategory.IDENTITY,
            difficulty=QuestionDifficulty.EASY,
            relevance_score=0.8,
            signal_score=0.75,
            confidence_score=1.0,
            base_score=0.82,
            difficulty_multiplier=1.0,
            category_weight=0.25,
            final_score=0.205,
            calculation_steps=["Step 1", "Step 2"],
            signals_matched=["mission", "values"],
            signals_missing=["team"],
        )

        assert score.question_id == "q1"
        assert score.relevance_score == 0.8
        assert score.base_score == 0.82

    def test_to_dict(self) -> None:
        """Converts to dict."""
        score = QuestionScore(
            question_id="q1",
            question_text="What is the mission?",
            category=QuestionCategory.IDENTITY,
            difficulty=QuestionDifficulty.EASY,
            relevance_score=0.8,
            signal_score=0.75,
            confidence_score=1.0,
            base_score=0.82,
            difficulty_multiplier=1.0,
            category_weight=0.25,
            final_score=0.205,
            calculation_steps=["Step 1"],
            signals_matched=["mission"],
            signals_missing=["team"],
        )

        d = score.to_dict()
        assert d["question_id"] == "q1"
        assert d["category"] == "identity"
        assert d["difficulty"] == "easy"
        assert d["signals_matched"] == ["mission"]


class TestCategoryBreakdown:
    """Tests for CategoryBreakdown."""

    def test_create_breakdown(self) -> None:
        """Can create a category breakdown."""
        breakdown = CategoryBreakdown(
            category=QuestionCategory.IDENTITY,
            weight=0.25,
            question_count=3,
            questions_answered=2,
            questions_partial=1,
            questions_unanswered=0,
            raw_score=75.0,
            weighted_score=18.75,
            contribution=18.75,
            question_scores=[],
            explanation="Test explanation",
            recommendations=["Add about page"],
        )

        assert breakdown.category == QuestionCategory.IDENTITY
        assert breakdown.weight == 0.25
        assert breakdown.raw_score == 75.0

    def test_to_dict(self) -> None:
        """Converts to dict."""
        breakdown = CategoryBreakdown(
            category=QuestionCategory.OFFERINGS,
            weight=0.30,
            question_count=4,
            questions_answered=3,
            questions_partial=1,
            questions_unanswered=0,
            raw_score=80.0,
            weighted_score=24.0,
            contribution=24.0,
            question_scores=[],
            explanation="Good coverage",
            recommendations=[],
        )

        d = breakdown.to_dict()
        assert d["category"] == "offerings"
        assert d["weight"] == 0.30
        assert d["question_count"] == 4


class TestScoreBreakdown:
    """Tests for ScoreBreakdown."""

    def test_create_breakdown(self) -> None:
        """Can create a score breakdown."""
        breakdown = ScoreBreakdown(
            total_score=85.5,
            grade="B",
            grade_description="Above Average",
            criterion_scores=[],
            category_breakdowns={},
            question_scores=[],
            total_questions=15,
            questions_answered=12,
            questions_partial=2,
            questions_unanswered=1,
            coverage_percentage=86.7,
            calculation_summary=["Step 1", "Step 2"],
            formula_used="Score = x + y",
            rubric_version="1.0",
        )

        assert breakdown.total_score == 85.5
        assert breakdown.grade == "B"
        assert breakdown.total_questions == 15

    def test_to_dict(self) -> None:
        """Converts to dict."""
        breakdown = ScoreBreakdown(
            total_score=85.5,
            grade="B",
            grade_description="Above Average",
            criterion_scores=[],
            category_breakdowns={},
            question_scores=[],
            total_questions=15,
            questions_answered=12,
            questions_partial=2,
            questions_unanswered=1,
            coverage_percentage=86.7,
            calculation_summary=["Step 1"],
            formula_used="Score = x + y",
            rubric_version="1.0",
        )

        d = breakdown.to_dict()
        assert d["total_score"] == 85.5
        assert d["grade"] == "B"
        assert d["rubric_version"] == "1.0"

    def test_show_the_math(self) -> None:
        """Generates human-readable breakdown."""
        breakdown = ScoreBreakdown(
            total_score=85.5,
            grade="B",
            grade_description="Above Average - Most key information is discoverable",
            criterion_scores=[],
            category_breakdowns={},
            question_scores=[],
            total_questions=15,
            questions_answered=12,
            questions_partial=2,
            questions_unanswered=1,
            coverage_percentage=86.7,
            calculation_summary=["Calculate criterion scores", "Apply weights"],
            formula_used="Score = (Criterion × 0.7) + (Category × 0.3)",
            rubric_version="1.0",
        )

        output = breakdown.show_the_math()
        assert "FINDABLE SCORE CALCULATION BREAKDOWN" in output
        assert "85.5" in output
        assert "Grade: B" in output
        assert "FORMULA" in output


class TestScoreCalculator:
    """Tests for ScoreCalculator."""

    def test_create_calculator(self) -> None:
        """Can create a calculator."""
        calculator = ScoreCalculator()
        assert calculator.rubric is not None
        assert calculator.rubric.name == "Findable Score Rubric v1"

    def test_create_with_custom_rubric(self) -> None:
        """Can use custom rubric."""
        custom_rubric = ScoringRubric(name="Custom Rubric", version="2.0")
        calculator = ScoreCalculator(rubric=custom_rubric)
        assert calculator.rubric.name == "Custom Rubric"

    def test_calculate_returns_breakdown(self) -> None:
        """Calculate returns ScoreBreakdown."""
        calculator = ScoreCalculator()
        simulation = make_simulation_result()

        result = calculator.calculate(simulation)

        assert isinstance(result, ScoreBreakdown)
        assert 0 <= result.total_score <= 100
        assert result.grade in [
            "A+",
            "A",
            "A-",
            "B+",
            "B",
            "B-",
            "C+",
            "C",
            "C-",
            "D+",
            "D",
            "D-",
            "F",
        ]

    def test_calculate_counts_questions(self) -> None:
        """Counts answered, partial, unanswered questions."""
        calculator = ScoreCalculator()

        # Create results with different answerabilities
        results = [
            make_question_result(
                question_id="q1",
                answerability=Answerability.FULLY_ANSWERABLE,
            ),
            make_question_result(
                question_id="q2",
                answerability=Answerability.FULLY_ANSWERABLE,
            ),
            make_question_result(
                question_id="q3",
                answerability=Answerability.PARTIALLY_ANSWERABLE,
            ),
            make_question_result(
                question_id="q4",
                answerability=Answerability.NOT_ANSWERABLE,
            ),
        ]

        now = datetime.utcnow()
        simulation = SimulationResult(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test",
            question_results=results,
            total_questions=4,
            questions_answered=2,
            questions_partial=1,
            questions_unanswered=1,
            category_scores={"identity": 60.0},
            difficulty_scores={"easy": 60.0},
            overall_score=50.0,
            coverage_score=75.0,
            confidence_score=70.0,
            total_time_ms=100.0,
            started_at=now,
            completed_at=now,
            metadata={},
        )

        breakdown = calculator.calculate(simulation)

        assert breakdown.total_questions == 4
        assert breakdown.questions_answered == 2
        assert breakdown.questions_partial == 1
        assert breakdown.questions_unanswered == 1

    def test_calculate_criterion_scores(self) -> None:
        """Calculates all criterion scores."""
        calculator = ScoreCalculator()
        simulation = make_simulation_result()

        breakdown = calculator.calculate(simulation)

        # Should have 4 criteria
        assert len(breakdown.criterion_scores) == 4

        criterion_ids = [cs.criterion.id for cs in breakdown.criterion_scores]
        assert "content_relevance" in criterion_ids
        assert "signal_coverage" in criterion_ids
        assert "answer_confidence" in criterion_ids
        assert "source_quality" in criterion_ids

    def test_calculate_category_breakdowns(self) -> None:
        """Calculates category breakdowns."""
        calculator = ScoreCalculator()
        simulation = make_simulation_result()

        breakdown = calculator.calculate(simulation)

        # Should have breakdowns for categories in the simulation
        assert len(breakdown.category_breakdowns) > 0

        for _cat_name, cat_breakdown in breakdown.category_breakdowns.items():
            assert cat_breakdown.weight > 0
            assert cat_breakdown.question_count > 0

    def test_calculate_question_scores(self) -> None:
        """Calculates question-level scores."""
        calculator = ScoreCalculator()
        simulation = make_simulation_result(question_count=5)

        breakdown = calculator.calculate(simulation)

        assert len(breakdown.question_scores) == 5

        for qs in breakdown.question_scores:
            assert qs.question_id is not None
            assert 0 <= qs.relevance_score <= 1
            assert 0 <= qs.signal_score <= 1
            assert 0 <= qs.confidence_score <= 1
            assert len(qs.calculation_steps) > 0

    def test_high_score_gets_high_grade(self) -> None:
        """High scores result in high grades."""
        calculator = ScoreCalculator()

        # Create excellent results across multiple categories
        categories = [
            QuestionCategory.IDENTITY,
            QuestionCategory.OFFERINGS,
            QuestionCategory.CONTACT,
            QuestionCategory.TRUST,
            QuestionCategory.DIFFERENTIATION,
        ]
        results = [
            make_question_result(
                question_id=f"q{i}",
                category=categories[i],
                score=0.95,
                signals_found=4,
                signals_total=4,
                avg_relevance=0.95,
                confidence=ConfidenceLevel.HIGH,
            )
            for i in range(5)
        ]

        now = datetime.utcnow()
        simulation = SimulationResult(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test",
            question_results=results,
            total_questions=5,
            questions_answered=5,
            questions_partial=0,
            questions_unanswered=0,
            category_scores={
                "identity": 95.0,
                "offerings": 95.0,
                "contact": 95.0,
                "trust": 95.0,
                "differentiation": 95.0,
            },
            difficulty_scores={"easy": 95.0},
            overall_score=95.0,
            coverage_score=100.0,
            confidence_score=100.0,
            total_time_ms=100.0,
            started_at=now,
            completed_at=now,
            metadata={},
        )

        breakdown = calculator.calculate(simulation)

        # Should get A range grade
        assert breakdown.grade in ["A+", "A", "A-"]
        assert breakdown.total_score >= 90

    def test_low_score_gets_low_grade(self) -> None:
        """Low scores result in low grades."""
        calculator = ScoreCalculator()

        # Create poor results
        results = [
            make_question_result(
                question_id=f"q{i}",
                score=0.3,
                signals_found=1,
                signals_total=5,
                avg_relevance=0.3,
                confidence=ConfidenceLevel.LOW,
                answerability=Answerability.NOT_ANSWERABLE,
            )
            for i in range(5)
        ]

        now = datetime.utcnow()
        simulation = SimulationResult(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test",
            question_results=results,
            total_questions=5,
            questions_answered=0,
            questions_partial=0,
            questions_unanswered=5,
            category_scores={"identity": 30.0},
            difficulty_scores={"easy": 30.0},
            overall_score=30.0,
            coverage_score=0.0,
            confidence_score=30.0,
            total_time_ms=100.0,
            started_at=now,
            completed_at=now,
            metadata={},
        )

        breakdown = calculator.calculate(simulation)

        # Should get low grade
        assert breakdown.grade in ["D+", "D", "D-", "F"]
        assert breakdown.total_score < 70

    def test_confidence_to_score(self) -> None:
        """Converts confidence levels to scores."""
        calculator = ScoreCalculator()

        assert calculator._confidence_to_score(ConfidenceLevel.HIGH) == 1.0
        assert calculator._confidence_to_score(ConfidenceLevel.MEDIUM) == 0.6
        assert calculator._confidence_to_score(ConfidenceLevel.LOW) == 0.3

    def test_calculation_summary_populated(self) -> None:
        """Calculation summary is populated."""
        calculator = ScoreCalculator()
        simulation = make_simulation_result()

        breakdown = calculator.calculate(simulation)

        assert len(breakdown.calculation_summary) > 0
        assert any("criterion" in step.lower() for step in breakdown.calculation_summary)

    def test_formula_returned(self) -> None:
        """Formula is returned."""
        calculator = ScoreCalculator()
        simulation = make_simulation_result()

        breakdown = calculator.calculate(simulation)

        assert len(breakdown.formula_used) > 0
        assert "Score" in breakdown.formula_used

    def test_empty_simulation_handled(self) -> None:
        """Handles simulation with no results."""
        calculator = ScoreCalculator()

        now = datetime.utcnow()
        simulation = SimulationResult(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Empty",
            question_results=[],
            total_questions=0,
            questions_answered=0,
            questions_partial=0,
            questions_unanswered=0,
            category_scores={},
            difficulty_scores={},
            overall_score=0,
            coverage_score=0,
            confidence_score=0,
            total_time_ms=0,
            started_at=now,
            completed_at=now,
            metadata={},
        )

        breakdown = calculator.calculate(simulation)

        assert breakdown.total_score == 0
        assert breakdown.total_questions == 0
        assert breakdown.grade == "F"


class TestCalculateScore:
    """Tests for calculate_score function."""

    def test_returns_breakdown(self) -> None:
        """Returns a ScoreBreakdown."""
        simulation = make_simulation_result()

        result = calculate_score(simulation)

        assert isinstance(result, ScoreBreakdown)

    def test_uses_default_rubric(self) -> None:
        """Uses default rubric when none provided."""
        simulation = make_simulation_result()

        result = calculate_score(simulation)

        assert result.rubric_version == "1.0"

    def test_uses_custom_rubric(self) -> None:
        """Uses custom rubric when provided."""
        simulation = make_simulation_result()
        custom_rubric = ScoringRubric(name="Custom", version="2.5")

        result = calculate_score(simulation, rubric=custom_rubric)

        assert result.rubric_version == "2.5"

    def test_matches_calculator_result(self) -> None:
        """Matches direct calculator usage."""
        simulation = make_simulation_result()

        func_result = calculate_score(simulation)
        calc_result = ScoreCalculator().calculate(simulation)

        assert func_result.total_score == calc_result.total_score
        assert func_result.grade == calc_result.grade
