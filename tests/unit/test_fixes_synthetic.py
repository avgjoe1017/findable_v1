"""Tests for Tier B synthetic patching impact estimator."""

from datetime import datetime
from uuid import uuid4

from worker.fixes.generator import Fix, FixPlan
from worker.fixes.impact import (
    ConfidenceLevel,
    FixPlanImpact,
    ImpactRange,
    ImpactTier,
)
from worker.fixes.reason_codes import ReasonCode, get_reason_info
from worker.fixes.synthetic import (
    PatchedQuestionResult,
    SyntheticChunk,
    TierBConfig,
    TierBEstimate,
    TierBEstimator,
    estimate_fix_tier_b,
    estimate_plan_tier_b,
)
from worker.fixes.templates import get_template
from worker.questions.generator import QuestionSource
from worker.questions.universal import QuestionCategory, QuestionDifficulty
from worker.simulation.runner import (
    Answerability,
    QuestionResult,
    RetrievedContext,
    SignalMatch,
    SimulationResult,
)
from worker.simulation.runner import (
    ConfidenceLevel as SimConfidence,
)


def make_retrieved_context(
    total_chunks: int = 3,
    avg_relevance: float = 0.5,
    max_relevance: float = 0.7,
) -> RetrievedContext:
    """Create a test RetrievedContext."""
    return RetrievedContext(
        chunks=[],
        total_chunks=total_chunks,
        avg_relevance_score=avg_relevance,
        max_relevance_score=max_relevance,
        source_pages=["https://example.com/page1"],
        content_preview="Test content",
    )


def make_question_result(
    question_id: str = "q1",
    category: QuestionCategory = QuestionCategory.IDENTITY,
    answerability: Answerability = Answerability.PARTIALLY_ANSWERABLE,
    confidence: SimConfidence = SimConfidence.MEDIUM,
    score: float = 0.4,
    signals_found: int = 1,
    signals_total: int = 4,
    avg_relevance: float = 0.5,
) -> QuestionResult:
    """Create a test QuestionResult."""
    return QuestionResult(
        question_id=question_id,
        question_text="What does the company do?",
        category=category,
        difficulty=QuestionDifficulty.EASY,
        source=QuestionSource.UNIVERSAL,
        weight=1.0,
        context=make_retrieved_context(avg_relevance=avg_relevance),
        answerability=answerability,
        confidence=confidence,
        score=score,
        signals_found=signals_found,
        signals_total=signals_total,
        signal_matches=[
            SignalMatch(signal="company description", found=True, confidence=0.8),
            SignalMatch(signal="value proposition", found=False, confidence=0.0),
            SignalMatch(signal="mission", found=False, confidence=0.0),
            SignalMatch(signal="what we do", found=False, confidence=0.0),
        ],
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
        category_scores={"identity": 40.0},
        difficulty_scores={"easy": 40.0},
        overall_score=40.0,
        coverage_score=50.0,
        confidence_score=60.0,
        total_time_ms=500.0,
        started_at=now,
        completed_at=now,
        metadata={},
    )


def make_fix(
    reason_code: ReasonCode = ReasonCode.MISSING_DEFINITION,
    affected_question_ids: list[str] | None = None,
    scaffold: str | None = None,
) -> Fix:
    """Create a test fix."""
    if scaffold is None:
        scaffold = """Test Company is a technology company that provides innovative solutions.

We help businesses achieve their goals through our value proposition.

Our mission is to make technology accessible."""

    return Fix(
        id=uuid4(),
        reason_code=reason_code,
        reason_info=get_reason_info(reason_code),
        template=get_template(reason_code),
        affected_question_ids=affected_question_ids or ["q1"],
        affected_categories=[QuestionCategory.IDENTITY],
        scaffold=scaffold,
        extracted_content=[],
        priority=1,
        estimated_impact=0.2,
        effort_level="low",
        target_url="/about",
    )


def make_fix_plan(fixes: list[Fix] | None = None) -> FixPlan:
    """Create a test fix plan."""
    if fixes is None:
        fixes = [make_fix()]

    return FixPlan(
        id=uuid4(),
        site_id=uuid4(),
        run_id=uuid4(),
        company_name="Test Company",
        fixes=fixes,
        total_fixes=len(fixes),
        critical_fixes=1,
        high_priority_fixes=0,
        estimated_total_impact=0.2,
        categories_addressed=[QuestionCategory.IDENTITY],
        questions_addressed=1,
    )


class TestSyntheticChunk:
    """Tests for SyntheticChunk dataclass."""

    def test_create_chunk(self) -> None:
        """Can create a synthetic chunk."""
        chunk = SyntheticChunk(
            content="Test content for patching",
            source_url="/about",
            relevance_boost=0.3,
            signals_added=["value proposition", "mission"],
        )

        assert chunk.content == "Test content for patching"
        assert chunk.relevance_boost == 0.3
        assert len(chunk.signals_added) == 2

    def test_to_dict(self) -> None:
        """Converts to dict."""
        chunk = SyntheticChunk(
            content="Short content",
            source_url="/test",
            relevance_boost=0.2,
            signals_added=["signal1"],
        )

        d = chunk.to_dict()
        assert d["source_url"] == "/test"
        assert d["relevance_boost"] == 0.2

    def test_to_dict_truncates_long_content(self) -> None:
        """Long content is truncated in dict."""
        long_content = "x" * 500
        chunk = SyntheticChunk(
            content=long_content,
            source_url="/test",
            relevance_boost=0.1,
            signals_added=[],
        )

        d = chunk.to_dict()
        assert len(d["content"]) < len(long_content)
        assert d["content"].endswith("...")


class TestPatchedQuestionResult:
    """Tests for PatchedQuestionResult dataclass."""

    def test_create_result(self) -> None:
        """Can create a patched result."""
        result = PatchedQuestionResult(
            question_id="q1",
            original_score=0.4,
            patched_score=0.7,
            score_delta=0.3,
            original_answerability=Answerability.PARTIALLY_ANSWERABLE,
            patched_answerability=Answerability.FULLY_ANSWERABLE,
            original_signals_found=1,
            patched_signals_found=3,
            signals_total=4,
            new_signals_matched=["mission", "value proposition"],
            explanation="Test explanation",
        )

        assert result.score_delta == 0.3
        assert result.patched_answerability == Answerability.FULLY_ANSWERABLE

    def test_to_dict(self) -> None:
        """Converts to dict."""
        result = PatchedQuestionResult(
            question_id="q2",
            original_score=0.3,
            patched_score=0.5,
            score_delta=0.2,
            original_answerability=Answerability.NOT_ANSWERABLE,
            patched_answerability=Answerability.PARTIALLY_ANSWERABLE,
            original_signals_found=0,
            patched_signals_found=2,
            signals_total=4,
            new_signals_matched=["signal1", "signal2"],
            explanation="Improved",
        )

        d = result.to_dict()
        assert d["question_id"] == "q2"
        assert d["score_delta"] == 0.2
        assert d["patched_answerability"] == "partially_answerable"


class TestTierBEstimate:
    """Tests for TierBEstimate dataclass."""

    def test_create_estimate(self) -> None:
        """Can create a Tier B estimate."""
        estimate = TierBEstimate(
            fix_id="fix-123",
            reason_code=ReasonCode.MISSING_DEFINITION,
            impact_range=ImpactRange(
                min_points=2.0,
                max_points=5.0,
                expected_points=3.5,
                confidence=ConfidenceLevel.MEDIUM,
                tier=ImpactTier.TIER_B,
            ),
            patched_questions=[],
            total_score_improvement=3.5,
            questions_improved=2,
            questions_unchanged=0,
            synthetic_chunks=[],
            tier_c_expected=3.0,
            tier_b_expected=3.5,
            estimation_difference=0.5,
            computation_time_ms=15.0,
        )

        assert estimate.tier_b_expected == 3.5
        assert estimate.impact_range.tier == ImpactTier.TIER_B

    def test_to_dict(self) -> None:
        """Converts to dict."""
        estimate = TierBEstimate(
            fix_id="fix-456",
            reason_code=ReasonCode.MISSING_PRICING,
            impact_range=ImpactRange(
                min_points=1.0,
                max_points=3.0,
                expected_points=2.0,
                confidence=ConfidenceLevel.HIGH,
                tier=ImpactTier.TIER_B,
            ),
            patched_questions=[],
            total_score_improvement=2.0,
            questions_improved=1,
            questions_unchanged=0,
            synthetic_chunks=[],
            tier_c_expected=2.5,
            tier_b_expected=2.0,
            estimation_difference=-0.5,
            computation_time_ms=10.0,
        )

        d = estimate.to_dict()
        assert d["fix_id"] == "fix-456"
        assert d["tier_b_expected"] == 2.0
        assert d["estimation_difference"] == -0.5


class TestTierBConfig:
    """Tests for TierBConfig."""

    def test_default_config(self) -> None:
        """Default config has expected values."""
        config = TierBConfig()

        assert config.fully_answerable_threshold == 0.7
        assert config.base_relevance_boost == 0.3
        assert config.relevance_weight == 0.4


class TestTierBEstimator:
    """Tests for TierBEstimator class."""

    def test_create_estimator(self) -> None:
        """Can create an estimator."""
        estimator = TierBEstimator()
        assert estimator.config is not None

    def test_create_with_custom_config(self) -> None:
        """Can use custom config."""
        config = TierBConfig(base_relevance_boost=0.5)
        estimator = TierBEstimator(config=config)
        assert estimator.config.base_relevance_boost == 0.5

    def test_estimate_fix_returns_tier_b_estimate(self) -> None:
        """estimate_fix returns TierBEstimate."""
        estimator = TierBEstimator()
        fix = make_fix()
        simulation = make_simulation_result()

        estimate = estimator.estimate_fix(fix, simulation)

        assert isinstance(estimate, TierBEstimate)
        assert estimate.impact_range.tier == ImpactTier.TIER_B

    def test_estimate_improves_low_score_questions(self) -> None:
        """Patching improves low-score questions."""
        estimator = TierBEstimator()

        question = make_question_result(
            question_id="q1",
            score=0.3,
            signals_found=1,
            signals_total=4,
            avg_relevance=0.4,
        )
        simulation = make_simulation_result(question_results=[question])

        fix = make_fix(
            affected_question_ids=["q1"],
            scaffold="Our value proposition is excellence. Our mission is quality.",
        )

        estimate = estimator.estimate_fix(fix, simulation)

        # Should show improvement
        assert len(estimate.patched_questions) == 1
        patched = estimate.patched_questions[0]
        assert patched.patched_score > patched.original_score

    def test_estimate_identifies_new_signals(self) -> None:
        """Estimate identifies new signals matched."""
        estimator = TierBEstimator()

        question = make_question_result(signals_found=1, signals_total=4)
        simulation = make_simulation_result(question_results=[question])

        fix = make_fix(
            scaffold="Our value proposition is to help customers. Our mission is growth.",
        )

        estimate = estimator.estimate_fix(fix, simulation)

        patched = estimate.patched_questions[0]
        assert patched.patched_signals_found >= patched.original_signals_found

    def test_estimate_creates_synthetic_chunks(self) -> None:
        """Estimate creates synthetic chunks from scaffold."""
        estimator = TierBEstimator()
        fix = make_fix()
        simulation = make_simulation_result()

        estimate = estimator.estimate_fix(fix, simulation)

        assert len(estimate.synthetic_chunks) > 0
        assert estimate.synthetic_chunks[0].source_url == fix.target_url

    def test_estimate_tracks_computation_time(self) -> None:
        """Estimate tracks computation time."""
        estimator = TierBEstimator()
        fix = make_fix()
        simulation = make_simulation_result()

        estimate = estimator.estimate_fix(fix, simulation)

        assert estimate.computation_time_ms > 0

    def test_estimate_compares_to_tier_c(self) -> None:
        """Estimate compares to Tier C estimate."""
        estimator = TierBEstimator()
        fix = make_fix()
        simulation = make_simulation_result()

        estimate = estimator.estimate_fix(fix, simulation, tier_c_expected=3.0)

        assert estimate.tier_c_expected == 3.0
        assert estimate.estimation_difference == estimate.tier_b_expected - 3.0

    def test_estimate_plan_returns_plan_impact(self) -> None:
        """estimate_plan returns FixPlanImpact."""
        estimator = TierBEstimator()
        plan = make_fix_plan()
        simulation = make_simulation_result()

        impact = estimator.estimate_plan(plan, simulation)

        assert isinstance(impact, FixPlanImpact)
        assert impact.tier == ImpactTier.TIER_B

    def test_estimate_plan_processes_top_n_fixes(self) -> None:
        """estimate_plan processes only top N fixes."""
        estimator = TierBEstimator()

        fixes = [make_fix(affected_question_ids=[f"q{i}"]) for i in range(5)]
        plan = make_fix_plan(fixes=fixes)

        questions = [make_question_result(question_id=f"q{i}") for i in range(5)]
        simulation = make_simulation_result(question_results=questions)

        impact = estimator.estimate_plan(plan, simulation, top_n=3)

        assert len(impact.estimates) == 3

    def test_estimate_plan_has_notes(self) -> None:
        """estimate_plan includes notes."""
        estimator = TierBEstimator()
        plan = make_fix_plan()
        simulation = make_simulation_result()

        impact = estimator.estimate_plan(plan, simulation)

        assert len(impact.notes) > 0
        assert any("Tier B" in note for note in impact.notes)

    def test_empty_affected_questions_handled(self) -> None:
        """Handles fix with no matching questions."""
        estimator = TierBEstimator()

        fix = make_fix(affected_question_ids=["nonexistent"])
        simulation = make_simulation_result()

        estimate = estimator.estimate_fix(fix, simulation)

        assert len(estimate.patched_questions) == 0
        assert estimate.total_score_improvement == 0


class TestSignalExtraction:
    """Tests for signal extraction from scaffolds."""

    def test_extracts_definition_signals(self) -> None:
        """Extracts signals for MISSING_DEFINITION."""
        estimator = TierBEstimator()

        fix = make_fix(
            reason_code=ReasonCode.MISSING_DEFINITION,
            scaffold="We are a company that provides value proposition to customers.",
        )
        simulation = make_simulation_result()

        estimate = estimator.estimate_fix(fix, simulation)

        chunk = estimate.synthetic_chunks[0]
        assert "value proposition" in chunk.signals_added

    def test_extracts_pricing_signals(self) -> None:
        """Extracts signals for MISSING_PRICING."""
        estimator = TierBEstimator()

        fix = make_fix(
            reason_code=ReasonCode.MISSING_PRICING,
            scaffold="Our pricing starts at $29 per month with a free trial.",
        )
        simulation = make_simulation_result()

        estimate = estimator.estimate_fix(fix, simulation)

        chunk = estimate.synthetic_chunks[0]
        assert any("pricing" in s or "per month" in s for s in chunk.signals_added)


class TestAnswerabilityTransitions:
    """Tests for answerability transitions after patching."""

    def test_not_answerable_to_partial(self) -> None:
        """NOT_ANSWERABLE can become PARTIALLY_ANSWERABLE."""
        estimator = TierBEstimator()

        question = make_question_result(
            answerability=Answerability.NOT_ANSWERABLE,
            score=0.2,
            signals_found=0,
            avg_relevance=0.2,
        )
        simulation = make_simulation_result(question_results=[question])
        fix = make_fix()

        estimate = estimator.estimate_fix(fix, simulation)

        patched = estimate.patched_questions[0]
        # With boost, should at least become partial
        assert patched.patched_score > patched.original_score

    def test_partial_to_fully_answerable(self) -> None:
        """PARTIALLY_ANSWERABLE can become FULLY_ANSWERABLE."""
        estimator = TierBEstimator()

        question = make_question_result(
            answerability=Answerability.PARTIALLY_ANSWERABLE,
            score=0.5,
            signals_found=2,
            avg_relevance=0.5,
        )
        simulation = make_simulation_result(question_results=[question])

        fix = make_fix(
            scaffold="Our mission is to excel. We provide clear value proposition.",
        )

        estimate = estimator.estimate_fix(fix, simulation)

        patched = estimate.patched_questions[0]
        # Should improve significantly
        assert patched.patched_score > patched.original_score


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_estimate_fix_tier_b(self) -> None:
        """estimate_fix_tier_b returns estimate."""
        fix = make_fix()
        simulation = make_simulation_result()

        estimate = estimate_fix_tier_b(fix, simulation)

        assert isinstance(estimate, TierBEstimate)

    def test_estimate_fix_tier_b_with_comparison(self) -> None:
        """estimate_fix_tier_b accepts tier_c comparison."""
        fix = make_fix()
        simulation = make_simulation_result()

        estimate = estimate_fix_tier_b(fix, simulation, tier_c_expected=5.0)

        assert estimate.tier_c_expected == 5.0

    def test_estimate_plan_tier_b(self) -> None:
        """estimate_plan_tier_b returns plan impact."""
        plan = make_fix_plan()
        simulation = make_simulation_result()

        impact = estimate_plan_tier_b(plan, simulation)

        assert isinstance(impact, FixPlanImpact)
        assert impact.tier == ImpactTier.TIER_B

    def test_estimate_plan_tier_b_with_top_n(self) -> None:
        """estimate_plan_tier_b accepts top_n."""
        fixes = [make_fix() for _ in range(5)]
        plan = make_fix_plan(fixes=fixes)
        simulation = make_simulation_result()

        impact = estimate_plan_tier_b(plan, simulation, top_n=2)

        assert len(impact.estimates) == 2


class TestConfidenceDetermination:
    """Tests for confidence level determination."""

    def test_high_confidence_when_most_improved(self) -> None:
        """High confidence when most questions improved."""
        estimator = TierBEstimator()

        # Create multiple questions that will improve
        questions = [
            make_question_result(
                question_id=f"q{i}",
                score=0.3,
                signals_found=1,
                avg_relevance=0.3,
            )
            for i in range(3)
        ]
        simulation = make_simulation_result(question_results=questions)

        fix = make_fix(
            affected_question_ids=["q0", "q1", "q2"],
            scaffold="Our mission and value proposition drive what we do.",
        )

        estimate = estimator.estimate_fix(fix, simulation)

        # Most questions should improve, giving high confidence
        improved = sum(1 for p in estimate.patched_questions if p.score_delta > 0.05)
        if improved > len(estimate.patched_questions) * 0.7:
            assert estimate.impact_range.confidence == ConfidenceLevel.HIGH
