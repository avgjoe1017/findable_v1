"""Tests for simulation runner."""

from uuid import uuid4

from worker.questions.generator import GeneratedQuestion, QuestionSource
from worker.questions.universal import QuestionCategory, QuestionDifficulty
from worker.retrieval.retriever import RetrievalResult
from worker.simulation.runner import (
    Answerability,
    RetrievedContext,
    SignalMatch,
    SimulationConfig,
    SimulationResult,
    SimulationRunner,
    run_simulation,
)


class MockRetriever:
    """Mock retriever for testing."""

    def __init__(self, results: list[RetrievalResult] | None = None):
        self.results = results or []
        self.search_calls: list[dict] = []

    def search(
        self,
        query: str,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[RetrievalResult]:
        self.search_calls.append(
            {
                "query": query,
                "limit": limit,
                "min_score": min_score,
            }
        )
        return self.results


def make_question(
    question: str = "What does TestCo do?",
    category: QuestionCategory = QuestionCategory.IDENTITY,
    difficulty: QuestionDifficulty = QuestionDifficulty.EASY,
    signals: list[str] | None = None,
    weight: float = 1.0,
) -> GeneratedQuestion:
    """Create a test question."""
    return GeneratedQuestion(
        question=question,
        source=QuestionSource.UNIVERSAL,
        category=category,
        difficulty=difficulty,
        weight=weight,
        expected_signals=signals or ["business description"],
        metadata={"universal_id": "UQ-TEST"},
    )


def make_result(
    content: str = "TestCo is a software company that builds tools.",
    score: float = 0.8,
    source_url: str = "https://test.com/about",
) -> RetrievalResult:
    """Create a test retrieval result."""
    return RetrievalResult(
        doc_id="chunk-1",
        content=content,
        score=score,
        bm25_score=0.5,
        vector_score=0.8,
        metadata={"source_url": source_url},
    )


class TestSimulationConfig:
    """Tests for SimulationConfig."""

    def test_default_config(self) -> None:
        """Default config has expected values."""
        config = SimulationConfig()

        assert config.chunks_per_question == 5
        assert config.min_relevance_score == 0.3
        assert config.fully_answerable_threshold == 0.7
        assert config.partially_answerable_threshold == 0.3

    def test_custom_config(self) -> None:
        """Can create custom config."""
        config = SimulationConfig(
            chunks_per_question=10,
            min_relevance_score=0.5,
        )

        assert config.chunks_per_question == 10
        assert config.min_relevance_score == 0.5


class TestRetrievedContext:
    """Tests for RetrievedContext."""

    def test_empty_context(self) -> None:
        """Empty context has zero values."""
        context = RetrievedContext(
            chunks=[],
            total_chunks=0,
            avg_relevance_score=0.0,
            max_relevance_score=0.0,
            source_pages=[],
            content_preview="",
        )

        assert context.total_chunks == 0
        assert context.avg_relevance_score == 0.0

    def test_to_dict(self) -> None:
        """Context converts to dict."""
        context = RetrievedContext(
            chunks=[make_result()],
            total_chunks=1,
            avg_relevance_score=0.8,
            max_relevance_score=0.8,
            source_pages=["https://test.com"],
            content_preview="Test content",
        )

        d = context.to_dict()
        assert d["total_chunks"] == 1
        assert d["avg_relevance_score"] == 0.8
        assert len(d["chunks"]) == 1


class TestSignalMatch:
    """Tests for SignalMatch."""

    def test_found_signal(self) -> None:
        """Found signal has high confidence."""
        match = SignalMatch(
            signal="business description",
            found=True,
            confidence=1.0,
            evidence="TestCo is a software company",
        )

        assert match.found is True
        assert match.confidence == 1.0

    def test_to_dict(self) -> None:
        """Signal match converts to dict."""
        match = SignalMatch(
            signal="pricing",
            found=False,
            confidence=0.0,
        )

        d = match.to_dict()
        assert d["signal"] == "pricing"
        assert d["found"] is False


class TestSimulationRunner:
    """Tests for SimulationRunner."""

    def test_create_runner(self) -> None:
        """Can create simulation runner."""
        retriever = MockRetriever()
        runner = SimulationRunner(retriever)  # type: ignore

        assert runner.retriever == retriever
        assert runner.config is not None

    def test_run_no_results(self) -> None:
        """Run with no retrieval results."""
        retriever = MockRetriever([])
        runner = SimulationRunner(retriever)  # type: ignore

        result = runner.run(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="TestCo",
            questions=[make_question()],
        )

        assert result.total_questions == 1
        assert result.questions_unanswered == 1
        assert result.overall_score == 0.0

    def test_run_with_results(self) -> None:
        """Run with retrieval results."""
        retriever = MockRetriever(
            [make_result("TestCo is a software company with business description.")]
        )
        runner = SimulationRunner(retriever)  # type: ignore

        result = runner.run(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="TestCo",
            questions=[make_question()],
        )

        assert result.total_questions == 1
        assert result.overall_score > 0

    def test_run_multiple_questions(self) -> None:
        """Run with multiple questions."""
        retriever = MockRetriever([make_result()])
        runner = SimulationRunner(retriever)  # type: ignore

        questions = [
            make_question("What does TestCo do?", QuestionCategory.IDENTITY),
            make_question("What products does TestCo offer?", QuestionCategory.OFFERINGS),
        ]

        result = runner.run(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="TestCo",
            questions=questions,
        )

        assert result.total_questions == 2
        assert len(result.question_results) == 2

    def test_category_scores(self) -> None:
        """Calculates category scores."""
        retriever = MockRetriever([make_result()])
        runner = SimulationRunner(retriever)  # type: ignore

        questions = [
            make_question("Q1", QuestionCategory.IDENTITY),
            make_question("Q2", QuestionCategory.IDENTITY),
            make_question("Q3", QuestionCategory.OFFERINGS),
        ]

        result = runner.run(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="TestCo",
            questions=questions,
        )

        assert "identity" in result.category_scores
        assert "offerings" in result.category_scores

    def test_difficulty_scores(self) -> None:
        """Calculates difficulty scores."""
        retriever = MockRetriever([make_result()])
        runner = SimulationRunner(retriever)  # type: ignore

        questions = [
            make_question("Q1", difficulty=QuestionDifficulty.EASY),
            make_question("Q2", difficulty=QuestionDifficulty.MEDIUM),
            make_question("Q3", difficulty=QuestionDifficulty.HARD),
        ]

        result = runner.run(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="TestCo",
            questions=questions,
        )

        assert "easy" in result.difficulty_scores
        assert "medium" in result.difficulty_scores
        assert "hard" in result.difficulty_scores


class TestQuestionEvaluation:
    """Tests for question evaluation."""

    def test_evaluate_with_matching_signal(self) -> None:
        """Question with matching signal gets high score."""
        retriever = MockRetriever(
            [make_result("TestCo business description: We are a software company.")]
        )
        runner = SimulationRunner(retriever)  # type: ignore

        question = make_question(signals=["business description"])
        result = runner._evaluate_question(question)

        assert result.signals_found >= 1
        assert result.score > 0

    def test_evaluate_without_matching_signal(self) -> None:
        """Question without matching signal gets lower score."""
        retriever = MockRetriever([make_result("Some random content without signals.")])
        runner = SimulationRunner(retriever)  # type: ignore

        question = make_question(signals=["pricing information", "cost details"])
        result = runner._evaluate_question(question)

        assert result.signals_found == 0

    def test_evaluate_no_content(self) -> None:
        """Question with no content is not answerable."""
        retriever = MockRetriever([])
        runner = SimulationRunner(retriever)  # type: ignore

        question = make_question()
        result = runner._evaluate_question(question)

        assert result.answerability == Answerability.NOT_ANSWERABLE
        assert result.score == 0.0


class TestAnswerability:
    """Tests for answerability determination."""

    def test_fully_answerable(self) -> None:
        """High score means fully answerable."""
        retriever = MockRetriever(
            [make_result("Complete business description with all details.", score=0.9)]
        )
        config = SimulationConfig(fully_answerable_threshold=0.5)
        runner = SimulationRunner(retriever, config)  # type: ignore

        question = make_question(signals=["business description"])
        result = runner._evaluate_question(question)

        # With high relevance and matching signal
        assert result.score > 0.5

    def test_not_answerable(self) -> None:
        """No content means not answerable."""
        retriever = MockRetriever([])
        runner = SimulationRunner(retriever)  # type: ignore

        question = make_question()
        result = runner._evaluate_question(question)

        assert result.answerability == Answerability.NOT_ANSWERABLE


class TestSimulationResult:
    """Tests for SimulationResult."""

    def test_to_dict(self) -> None:
        """Result converts to dict."""
        retriever = MockRetriever([make_result()])
        runner = SimulationRunner(retriever)  # type: ignore

        result = runner.run(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="TestCo",
            questions=[make_question()],
        )

        d = result.to_dict()
        assert "site_id" in d
        assert "company_name" in d
        assert "overall_score" in d
        assert "question_results" in d
        assert "category_scores" in d

    def test_timing_recorded(self) -> None:
        """Timing is recorded."""
        retriever = MockRetriever([make_result()])
        runner = SimulationRunner(retriever)  # type: ignore

        result = runner.run(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="TestCo",
            questions=[make_question()],
        )

        assert result.total_time_ms > 0
        assert result.started_at is not None
        assert result.completed_at is not None


class TestRunSimulationFunction:
    """Tests for run_simulation convenience function."""

    def test_run_simulation(self) -> None:
        """Convenience function works."""
        retriever = MockRetriever([make_result()])

        result = run_simulation(
            retriever=retriever,  # type: ignore
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="TestCo",
            questions=[make_question()],
        )

        assert isinstance(result, SimulationResult)
        assert result.total_questions == 1

    def test_run_simulation_with_config(self) -> None:
        """Convenience function accepts config."""
        retriever = MockRetriever([make_result()])
        config = SimulationConfig(chunks_per_question=3)

        result = run_simulation(
            retriever=retriever,  # type: ignore
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="TestCo",
            questions=[make_question()],
            config=config,
        )

        assert result is not None


class TestSignalMatching:
    """Tests for signal matching logic."""

    def test_exact_match(self) -> None:
        """Exact signal match is detected."""
        retriever = MockRetriever([make_result("This is the business description of our company.")])
        runner = SimulationRunner(retriever)  # type: ignore

        question = make_question(signals=["business description"])
        result = runner._evaluate_question(question)

        matched = [m for m in result.signal_matches if m.found]
        assert len(matched) >= 1

    def test_fuzzy_match(self) -> None:
        """Fuzzy signal match is detected."""
        retriever = MockRetriever([make_result("Our business provides description of services.")])
        config = SimulationConfig(use_fuzzy_matching=True)
        runner = SimulationRunner(retriever, config)  # type: ignore

        question = make_question(signals=["business description"])
        result = runner._evaluate_question(question)

        # Should find partial match
        matched = [m for m in result.signal_matches if m.confidence > 0]
        assert len(matched) >= 1

    def test_no_fuzzy_match(self) -> None:
        """Fuzzy matching can be disabled."""
        retriever = MockRetriever([make_result("Completely unrelated content here.")])
        config = SimulationConfig(use_fuzzy_matching=False)
        runner = SimulationRunner(retriever, config)  # type: ignore

        question = make_question(signals=["business description"])
        result = runner._evaluate_question(question)

        matched = [m for m in result.signal_matches if m.found]
        assert len(matched) == 0
