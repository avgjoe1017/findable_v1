"""Tests for observation comparison."""

from datetime import datetime
from uuid import uuid4

import pytest

from worker.observation.comparison import (
    ComparisonSummary,
    OutcomeMatch,
    QuestionComparison,
    SimulationObservationComparator,
    SourceabilityOutcome,
    compare_simulation_observation,
)
from worker.observation.models import (
    ObservationResponse,
    ObservationResult,
    ObservationRun,
    ObservationStatus,
    ProviderType,
)
from worker.observation.parser import ConfidenceLevel, ParsedObservation, Sentiment
from worker.questions.generator import QuestionSource
from worker.questions.universal import QuestionCategory, QuestionDifficulty
from worker.simulation.runner import (
    Answerability,
    QuestionResult,
    RetrievedContext,
    SimulationResult,
)
from worker.simulation.runner import (
    ConfidenceLevel as SimConfidence,
)


def make_question_result(
    question_id: str = "q1",
    answerability: Answerability = Answerability.PARTIALLY_ANSWERABLE,
    score: float = 0.5,
    signals_found: int = 2,
    signals_total: int = 4,
) -> QuestionResult:
    """Create a test QuestionResult."""
    return QuestionResult(
        question_id=question_id,
        question_text=f"Question {question_id}",
        category=QuestionCategory.IDENTITY,
        difficulty=QuestionDifficulty.EASY,
        source=QuestionSource.UNIVERSAL,
        weight=1.0,
        context=RetrievedContext(
            chunks=[],
            total_chunks=3,
            avg_relevance_score=0.6,
            max_relevance_score=0.8,
            source_pages=["https://example.com"],
            content_preview="Test content",
        ),
        answerability=answerability,
        confidence=SimConfidence.MEDIUM,
        score=score,
        signals_found=signals_found,
        signals_total=signals_total,
        signal_matches=[],
        retrieval_time_ms=50.0,
        evaluation_time_ms=10.0,
    )


def make_simulation_result(
    question_results: list[QuestionResult] | None = None,
) -> SimulationResult:
    """Create a test SimulationResult."""
    now = datetime.utcnow()

    if question_results is None:
        question_results = [make_question_result()]

    return SimulationResult(
        site_id=uuid4(),
        run_id=uuid4(),
        company_name="Test Company",
        question_results=question_results,
        total_questions=len(question_results),
        questions_answered=0,
        questions_partial=len(question_results),
        questions_unanswered=0,
        category_scores={"identity": 50.0},
        difficulty_scores={"easy": 50.0},
        overall_score=50.0,
        coverage_score=50.0,
        confidence_score=50.0,
        total_time_ms=500.0,
        started_at=now,
        completed_at=now,
        metadata={},
    )


def make_observation_result(
    question_id: str = "q1",
    mentions_company: bool = True,
    mentions_domain: bool = False,
    mentions_url: bool = False,
) -> ObservationResult:
    """Create a test ObservationResult."""
    return ObservationResult(
        question_id=question_id,
        question_text=f"Question {question_id}",
        company_name="Test Company",
        domain="test.com",
        response=ObservationResponse(
            request_id=uuid4(),
            provider=ProviderType.MOCK,
            model="mock",
            content="Test response mentioning Test Company",
            success=True,
        ),
        mentions_company=mentions_company,
        mentions_domain=mentions_domain,
        mentions_url=mentions_url,
        cited_urls=["https://test.com"] if mentions_url else [],
        confidence_expressed="medium",
    )


def make_observation_run(
    results: list[ObservationResult] | None = None,
) -> ObservationRun:
    """Create a test ObservationRun."""
    if results is None:
        results = [make_observation_result()]

    run = ObservationRun(
        site_id=uuid4(),
        company_name="Test Company",
        domain="test.com",
        total_questions=len(results),
        status=ObservationStatus.COMPLETED,
    )

    for result in results:
        run.add_result(result)

    return run


class TestQuestionComparison:
    """Tests for QuestionComparison dataclass."""

    def test_create_comparison(self) -> None:
        """Can create a comparison."""
        comparison = QuestionComparison(
            question_id="q1",
            question_text="Test question",
            sim_answerability=Answerability.FULLY_ANSWERABLE,
            sim_score=0.8,
            obs_mentioned=True,
            obs_cited=True,
            outcome_match=OutcomeMatch.CORRECT,
        )

        assert comparison.question_id == "q1"
        assert comparison.outcome_match == OutcomeMatch.CORRECT

    def test_to_dict(self) -> None:
        """Converts to dict."""
        comparison = QuestionComparison(
            question_id="q1",
            question_text="Test",
            sim_answerability=Answerability.PARTIALLY_ANSWERABLE,
            sourceability_outcome=SourceabilityOutcome.MENTIONED,
        )

        d = comparison.to_dict()

        assert d["question_id"] == "q1"
        assert d["sim_answerability"] == "partially_answerable"
        assert d["sourceability_outcome"] == "mentioned"


class TestComparisonSummary:
    """Tests for ComparisonSummary dataclass."""

    def test_create_summary(self) -> None:
        """Can create a summary."""
        summary = ComparisonSummary(
            total_questions=10,
            correct_predictions=7,
            prediction_accuracy=0.7,
        )

        assert summary.prediction_accuracy == 0.7

    def test_to_dict(self) -> None:
        """Converts to dict."""
        summary = ComparisonSummary(
            total_questions=5,
            correct_predictions=4,
            mention_rate_sim=0.6,
            mention_rate_obs=0.8,
        )

        d = summary.to_dict()

        assert d["total_questions"] == 5
        assert d["mention_rate_obs"] == 0.8


class TestSimulationObservationComparator:
    """Tests for SimulationObservationComparator class."""

    def test_create_comparator(self) -> None:
        """Can create a comparator."""
        comparator = SimulationObservationComparator()
        assert comparator is not None

    def test_compare_correct_prediction(self) -> None:
        """Detects correct prediction."""
        comparator = SimulationObservationComparator()

        # Simulation predicts answerable, observation confirms mention
        sim_result = make_question_result(
            question_id="q1",
            answerability=Answerability.FULLY_ANSWERABLE,
        )
        simulation = make_simulation_result([sim_result])

        obs_result = make_observation_result(
            question_id="q1",
            mentions_company=True,
        )
        observation = make_observation_run([obs_result])

        summary = comparator.compare(simulation, observation)

        assert summary.correct_predictions >= 1
        assert summary.comparisons[0].outcome_match == OutcomeMatch.CORRECT

    def test_compare_optimistic_prediction(self) -> None:
        """Detects optimistic prediction."""
        comparator = SimulationObservationComparator()

        # Simulation predicts answerable, observation shows no mention
        sim_result = make_question_result(
            question_id="q1",
            answerability=Answerability.FULLY_ANSWERABLE,
        )
        simulation = make_simulation_result([sim_result])

        obs_result = make_observation_result(
            question_id="q1",
            mentions_company=False,
            mentions_domain=False,
        )
        observation = make_observation_run([obs_result])

        summary = comparator.compare(simulation, observation)

        assert summary.optimistic_predictions >= 1
        assert summary.comparisons[0].outcome_match == OutcomeMatch.OPTIMISTIC

    def test_compare_pessimistic_prediction(self) -> None:
        """Detects pessimistic prediction."""
        comparator = SimulationObservationComparator()

        # Simulation predicts not answerable, observation shows mention
        sim_result = make_question_result(
            question_id="q1",
            answerability=Answerability.NOT_ANSWERABLE,
        )
        simulation = make_simulation_result([sim_result])

        obs_result = make_observation_result(
            question_id="q1",
            mentions_company=True,
        )
        observation = make_observation_run([obs_result])

        summary = comparator.compare(simulation, observation)

        assert summary.pessimistic_predictions >= 1
        assert summary.comparisons[0].outcome_match == OutcomeMatch.PESSIMISTIC

    def test_compare_multiple_questions(self) -> None:
        """Compares multiple questions."""
        comparator = SimulationObservationComparator()

        sim_results = [
            make_question_result(f"q{i}", Answerability.PARTIALLY_ANSWERABLE) for i in range(3)
        ]
        simulation = make_simulation_result(sim_results)

        obs_results = [make_observation_result(f"q{i}", mentions_company=True) for i in range(3)]
        observation = make_observation_run(obs_results)

        summary = comparator.compare(simulation, observation)

        assert summary.total_questions == 3
        assert len(summary.comparisons) == 3

    def test_compare_calculates_accuracy(self) -> None:
        """Calculates prediction accuracy."""
        comparator = SimulationObservationComparator()

        # 2 correct, 1 wrong
        sim_results = [
            make_question_result("q1", Answerability.FULLY_ANSWERABLE),
            make_question_result("q2", Answerability.FULLY_ANSWERABLE),
            make_question_result("q3", Answerability.NOT_ANSWERABLE),
        ]
        simulation = make_simulation_result(sim_results)

        obs_results = [
            make_observation_result("q1", mentions_company=True),  # Correct
            make_observation_result("q2", mentions_company=True),  # Correct
            make_observation_result("q3", mentions_company=True),  # Wrong (pessimistic)
        ]
        observation = make_observation_run(obs_results)

        summary = comparator.compare(simulation, observation)

        # Should be around 2/3 accuracy
        assert summary.correct_predictions == 2
        assert summary.prediction_accuracy == pytest.approx(2 / 3, rel=0.01)

    def test_compare_calculates_mention_rates(self) -> None:
        """Calculates mention rates."""
        comparator = SimulationObservationComparator()

        sim_results = [
            make_question_result("q1", Answerability.FULLY_ANSWERABLE),
            make_question_result("q2", Answerability.NOT_ANSWERABLE),
        ]
        simulation = make_simulation_result(sim_results)

        # 1 mention, 1 no mention
        obs_results = [
            make_observation_result("q1", mentions_company=True),
            make_observation_result("q2", mentions_company=False),
        ]
        observation = make_observation_run(obs_results)

        summary = comparator.compare(simulation, observation)

        assert summary.mention_rate_sim == 0.5  # 1/2 answerable
        assert summary.mention_rate_obs == 0.5  # 1/2 mentioned

    def test_compare_with_parsed_results(self) -> None:
        """Uses parsed observations when provided."""
        comparator = SimulationObservationComparator()

        sim_result = make_question_result("q1")
        simulation = make_simulation_result([sim_result])

        obs_result = make_observation_result("q1")
        observation = make_observation_run([obs_result])

        parsed = {
            "q1": ParsedObservation(
                has_company_mention=True,
                has_url_citation=True,
                overall_sentiment=Sentiment.POSITIVE,
                confidence_level=ConfidenceLevel.HIGH,
            )
        }

        summary = comparator.compare(simulation, observation, parsed)

        assert summary.comparisons[0].obs_cited is True
        assert summary.comparisons[0].obs_sentiment == "positive"

    def test_compare_generates_insights(self) -> None:
        """Generates insights from comparison."""
        comparator = SimulationObservationComparator()

        sim_results = [
            make_question_result(f"q{i}", Answerability.FULLY_ANSWERABLE) for i in range(5)
        ]
        simulation = make_simulation_result(sim_results)

        # All wrong (optimistic)
        obs_results = [make_observation_result(f"q{i}", mentions_company=False) for i in range(5)]
        observation = make_observation_run(obs_results)

        summary = comparator.compare(simulation, observation)

        assert len(summary.insights) > 0

    def test_compare_generates_recommendations(self) -> None:
        """Generates recommendations from comparison."""
        comparator = SimulationObservationComparator()

        sim_results = [make_question_result("q1")]
        simulation = make_simulation_result(sim_results)

        obs_result = make_observation_result("q1", mentions_company=True)
        observation = make_observation_run([obs_result])

        summary = comparator.compare(simulation, observation)

        # May or may not have recommendations depending on results
        assert isinstance(summary.recommendations, list)

    def test_sourceability_outcome_cited(self) -> None:
        """Detects CITED outcome."""
        comparator = SimulationObservationComparator()

        sim_result = make_question_result("q1")
        simulation = make_simulation_result([sim_result])

        obs_result = make_observation_result("q1", mentions_url=True)
        observation = make_observation_run([obs_result])

        summary = comparator.compare(simulation, observation)

        assert summary.comparisons[0].sourceability_outcome == SourceabilityOutcome.CITED

    def test_sourceability_outcome_mentioned(self) -> None:
        """Detects MENTIONED outcome."""
        comparator = SimulationObservationComparator()

        sim_result = make_question_result("q1")
        simulation = make_simulation_result([sim_result])

        obs_result = make_observation_result("q1", mentions_company=True, mentions_url=False)
        observation = make_observation_run([obs_result])

        summary = comparator.compare(simulation, observation)

        assert summary.comparisons[0].sourceability_outcome == SourceabilityOutcome.MENTIONED

    def test_sourceability_outcome_omitted(self) -> None:
        """Detects OMITTED outcome."""
        comparator = SimulationObservationComparator()

        sim_result = make_question_result("q1")
        simulation = make_simulation_result([sim_result])

        obs_result = make_observation_result("q1", mentions_company=False, mentions_domain=False)
        observation = make_observation_run([obs_result])

        summary = comparator.compare(simulation, observation)

        assert summary.comparisons[0].sourceability_outcome == SourceabilityOutcome.OMITTED

    def test_handles_missing_observation(self) -> None:
        """Handles missing observation for a question."""
        comparator = SimulationObservationComparator()

        sim_results = [
            make_question_result("q1"),
            make_question_result("q2"),
        ]
        simulation = make_simulation_result(sim_results)

        # Only q1 has observation
        obs_result = make_observation_result("q1")
        observation = make_observation_run([obs_result])

        summary = comparator.compare(simulation, observation)

        assert summary.total_questions == 2
        q2_comparison = next(c for c in summary.comparisons if c.question_id == "q2")
        assert q2_comparison.outcome_match == OutcomeMatch.UNKNOWN


class TestConvenienceFunction:
    """Tests for compare_simulation_observation convenience function."""

    def test_compare_function(self) -> None:
        """Convenience function works."""
        simulation = make_simulation_result()
        observation = make_observation_run()

        summary = compare_simulation_observation(simulation, observation)

        assert isinstance(summary, ComparisonSummary)
        assert summary.total_questions == 1

    def test_compare_function_with_parsed(self) -> None:
        """Accepts parsed results."""
        simulation = make_simulation_result()
        observation = make_observation_run()
        parsed = {"q1": ParsedObservation(has_company_mention=True)}

        summary = compare_simulation_observation(simulation, observation, parsed)

        assert summary.comparisons[0].obs_mentioned is True
