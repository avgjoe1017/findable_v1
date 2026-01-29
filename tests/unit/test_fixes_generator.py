"""Tests for fix generator module."""

from datetime import datetime
from uuid import uuid4

from worker.fixes.generator import (
    ExtractedContent,
    Fix,
    FixGenerator,
    FixGeneratorConfig,
    FixPlan,
    generate_fix_plan,
)
from worker.fixes.reason_codes import ReasonCode, get_reason_info
from worker.fixes.templates import get_template
from worker.questions.generator import QuestionSource
from worker.questions.universal import QuestionCategory, QuestionDifficulty
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
        chunks=[],
        total_chunks=total_chunks,
        avg_relevance_score=avg_relevance,
        max_relevance_score=max_relevance,
        source_pages=["https://example.com/page1"],
        content_preview="Test content",
    )


def make_question_result(
    question_id: str | None = None,
    question_text: str = "What does the company do?",
    category: QuestionCategory = QuestionCategory.IDENTITY,
    difficulty: QuestionDifficulty = QuestionDifficulty.EASY,
    answerability: Answerability = Answerability.FULLY_ANSWERABLE,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    score: float = 0.85,
    signals_found: int = 3,
    signals_total: int = 4,
    avg_relevance: float = 0.8,
    total_chunks: int = 3,
) -> QuestionResult:
    """Create a test QuestionResult."""
    return QuestionResult(
        question_id=question_id or str(uuid4()),
        question_text=question_text,
        category=category,
        difficulty=difficulty,
        source=QuestionSource.UNIVERSAL,
        weight=1.0,
        context=make_retrieved_context(
            avg_relevance=avg_relevance,
            total_chunks=total_chunks,
        ),
        answerability=answerability,
        confidence=confidence,
        score=score,
        signals_found=signals_found,
        signals_total=signals_total,
        signal_matches=[
            SignalMatch(signal="company description", found=True, confidence=1.0),
            SignalMatch(signal="mission", found=True, confidence=0.9),
            SignalMatch(signal="value proposition", found=True, confidence=0.8),
            SignalMatch(signal="founding story", found=False, confidence=0.0),
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
        questions_answered=len(question_results),
        questions_partial=0,
        questions_unanswered=0,
        category_scores={"identity": 80.0},
        difficulty_scores={"easy": 80.0},
        overall_score=80.0,
        coverage_score=90.0,
        confidence_score=85.0,
        total_time_ms=500.0,
        started_at=now,
        completed_at=now,
        metadata={},
    )


class TestExtractedContent:
    """Tests for ExtractedContent dataclass."""

    def test_create_extracted_content(self) -> None:
        """Can create extracted content."""
        ec = ExtractedContent(
            text="This is extracted text",
            source_url="https://example.com/page",
            relevance_score=0.85,
            context="What does the company do?",
        )

        assert ec.text == "This is extracted text"
        assert ec.relevance_score == 0.85


class TestFix:
    """Tests for Fix dataclass."""

    def test_create_fix(self) -> None:
        """Can create a fix."""
        fix = Fix(
            id=uuid4(),
            reason_code=ReasonCode.MISSING_DEFINITION,
            reason_info=get_reason_info(ReasonCode.MISSING_DEFINITION),
            template=get_template(ReasonCode.MISSING_DEFINITION),
            affected_question_ids=["q1", "q2"],
            affected_categories=[QuestionCategory.IDENTITY],
            scaffold="## About Us\n[COMPANY_NAME] is a...",
            extracted_content=[],
            priority=1,
            estimated_impact=0.25,
            effort_level="low",
            target_url="/about",
        )

        assert fix.reason_code == ReasonCode.MISSING_DEFINITION
        assert len(fix.affected_question_ids) == 2
        assert fix.priority == 1

    def test_to_dict(self) -> None:
        """Converts to dict."""
        fix = Fix(
            id=uuid4(),
            reason_code=ReasonCode.MISSING_PRICING,
            reason_info=get_reason_info(ReasonCode.MISSING_PRICING),
            template=get_template(ReasonCode.MISSING_PRICING),
            affected_question_ids=["q1"],
            affected_categories=[QuestionCategory.OFFERINGS],
            scaffold="## Pricing",
            extracted_content=[],
            priority=1,
            estimated_impact=0.2,
            effort_level="medium",
            target_url="/pricing",
        )

        d = fix.to_dict()
        assert d["reason_code"] == "missing_pricing"
        assert d["priority"] == 1
        assert d["target_url"] == "/pricing"


class TestFixPlan:
    """Tests for FixPlan dataclass."""

    def test_create_plan(self) -> None:
        """Can create a fix plan."""
        fix = Fix(
            id=uuid4(),
            reason_code=ReasonCode.MISSING_DEFINITION,
            reason_info=get_reason_info(ReasonCode.MISSING_DEFINITION),
            template=get_template(ReasonCode.MISSING_DEFINITION),
            affected_question_ids=["q1"],
            affected_categories=[QuestionCategory.IDENTITY],
            scaffold="Content",
            extracted_content=[],
            priority=1,
            estimated_impact=0.25,
            effort_level="low",
            target_url="/about",
        )

        plan = FixPlan(
            id=uuid4(),
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test Company",
            fixes=[fix],
            total_fixes=1,
            critical_fixes=1,
            high_priority_fixes=0,
            estimated_total_impact=0.25,
            categories_addressed=[QuestionCategory.IDENTITY],
            questions_addressed=1,
        )

        assert plan.total_fixes == 1
        assert plan.critical_fixes == 1

    def test_to_dict(self) -> None:
        """Converts to dict."""
        plan = FixPlan(
            id=uuid4(),
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test Company",
            fixes=[],
            total_fixes=0,
            critical_fixes=0,
            high_priority_fixes=0,
            estimated_total_impact=0.0,
            categories_addressed=[],
            questions_addressed=0,
        )

        d = plan.to_dict()
        assert d["company_name"] == "Test Company"
        assert d["total_fixes"] == 0

    def test_get_top_fixes(self) -> None:
        """Gets top fixes by priority."""
        fixes = [
            Fix(
                id=uuid4(),
                reason_code=ReasonCode.BURIED_ANSWER,
                reason_info=get_reason_info(ReasonCode.BURIED_ANSWER),
                template=get_template(ReasonCode.BURIED_ANSWER),
                affected_question_ids=["q1"],
                affected_categories=[],
                scaffold="Content",
                extracted_content=[],
                priority=3,
                estimated_impact=0.1,
                effort_level="low",
                target_url=None,
            ),
            Fix(
                id=uuid4(),
                reason_code=ReasonCode.MISSING_DEFINITION,
                reason_info=get_reason_info(ReasonCode.MISSING_DEFINITION),
                template=get_template(ReasonCode.MISSING_DEFINITION),
                affected_question_ids=["q2"],
                affected_categories=[QuestionCategory.IDENTITY],
                scaffold="Content",
                extracted_content=[],
                priority=1,
                estimated_impact=0.3,
                effort_level="low",
                target_url="/about",
            ),
        ]

        plan = FixPlan(
            id=uuid4(),
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test",
            fixes=fixes,
            total_fixes=2,
            critical_fixes=1,
            high_priority_fixes=0,
            estimated_total_impact=0.4,
            categories_addressed=[QuestionCategory.IDENTITY],
            questions_addressed=2,
        )

        top = plan.get_top_fixes(1)
        assert len(top) == 1
        assert top[0].priority == 1


class TestFixGeneratorConfig:
    """Tests for FixGeneratorConfig."""

    def test_default_config(self) -> None:
        """Default config has expected values."""
        config = FixGeneratorConfig()

        assert config.low_score_threshold == 0.5
        assert config.partial_threshold == 0.7
        assert config.max_fixes == 10
        assert config.include_examples is True


class TestFixGenerator:
    """Tests for FixGenerator class."""

    def test_create_generator(self) -> None:
        """Can create a generator."""
        generator = FixGenerator()
        assert generator.config is not None

    def test_create_with_custom_config(self) -> None:
        """Can use custom config."""
        config = FixGeneratorConfig(max_fixes=5)
        generator = FixGenerator(config=config)
        assert generator.config.max_fixes == 5

    def test_generate_returns_fix_plan(self) -> None:
        """Generate returns a FixPlan."""
        generator = FixGenerator()

        # Create problem questions
        results = [
            make_question_result(
                question_id="q1",
                answerability=Answerability.NOT_ANSWERABLE,
                score=0.2,
                signals_found=0,
                signals_total=4,
                total_chunks=0,
            ),
        ]
        simulation = make_simulation_result(question_results=results)

        plan = generator.generate(simulation)

        assert isinstance(plan, FixPlan)
        assert plan.company_name == "Test Company"

    def test_identifies_not_answerable(self) -> None:
        """Identifies NOT_ANSWERABLE as problem."""
        generator = FixGenerator()

        results = [
            make_question_result(
                question_id="q1",
                answerability=Answerability.NOT_ANSWERABLE,
                score=0.0,
            ),
        ]
        simulation = make_simulation_result(question_results=results)

        plan = generator.generate(simulation)

        assert plan.total_fixes > 0
        assert plan.questions_addressed == 1

    def test_identifies_contradictory(self) -> None:
        """Identifies CONTRADICTORY as problem."""
        generator = FixGenerator()

        results = [
            make_question_result(
                question_id="q1",
                answerability=Answerability.CONTRADICTORY,
                score=0.3,
            ),
        ]
        simulation = make_simulation_result(question_results=results)

        plan = generator.generate(simulation)

        assert plan.total_fixes > 0
        # Should have INCONSISTENT reason code
        assert any(f.reason_code == ReasonCode.INCONSISTENT for f in plan.fixes)

    def test_identifies_low_score_partial(self) -> None:
        """Identifies low-score PARTIALLY_ANSWERABLE as problem."""
        generator = FixGenerator()

        results = [
            make_question_result(
                question_id="q1",
                answerability=Answerability.PARTIALLY_ANSWERABLE,
                score=0.4,  # Below partial_threshold
                signals_found=1,
                signals_total=4,
            ),
        ]
        simulation = make_simulation_result(question_results=results)

        plan = generator.generate(simulation)

        assert plan.total_fixes > 0

    def test_skips_good_questions(self) -> None:
        """Skips questions with good scores."""
        generator = FixGenerator()

        results = [
            make_question_result(
                question_id="q1",
                answerability=Answerability.FULLY_ANSWERABLE,
                score=0.9,
                confidence=ConfidenceLevel.HIGH,
            ),
        ]
        simulation = make_simulation_result(question_results=results)

        plan = generator.generate(simulation)

        assert plan.total_fixes == 0

    def test_groups_by_reason_code(self) -> None:
        """Groups multiple questions with same reason."""
        generator = FixGenerator()

        results = [
            make_question_result(
                question_id="q1",
                category=QuestionCategory.IDENTITY,
                answerability=Answerability.NOT_ANSWERABLE,
                score=0.0,
                total_chunks=0,
            ),
            make_question_result(
                question_id="q2",
                category=QuestionCategory.IDENTITY,
                answerability=Answerability.NOT_ANSWERABLE,
                score=0.0,
                total_chunks=0,
            ),
        ]
        simulation = make_simulation_result(question_results=results)

        plan = generator.generate(simulation)

        # Should group both questions into fewer fixes
        assert plan.questions_addressed == 2

    def test_respects_max_fixes(self) -> None:
        """Respects max_fixes limit."""
        config = FixGeneratorConfig(max_fixes=2)
        generator = FixGenerator(config=config)

        # Create many problem questions
        results = [
            make_question_result(
                question_id=f"q{i}",
                category=list(QuestionCategory)[i % 5],
                answerability=Answerability.NOT_ANSWERABLE,
                score=0.0,
                total_chunks=0,
            )
            for i in range(10)
        ]
        simulation = make_simulation_result(question_results=results)

        plan = generator.generate(simulation)

        assert plan.total_fixes <= 2

    def test_diagnoses_missing_pricing(self) -> None:
        """Diagnoses MISSING_PRICING for pricing questions."""
        generator = FixGenerator()

        results = [
            make_question_result(
                question_id="q1",
                question_text="What is the pricing for the product?",
                category=QuestionCategory.OFFERINGS,
                answerability=Answerability.NOT_ANSWERABLE,
                score=0.1,
                signals_found=0,
                signals_total=3,
            ),
        ]
        simulation = make_simulation_result(question_results=results)

        plan = generator.generate(simulation)

        assert any(f.reason_code == ReasonCode.MISSING_PRICING for f in plan.fixes)

    def test_diagnoses_trust_gap(self) -> None:
        """Diagnoses TRUST_GAP for trust questions."""
        generator = FixGenerator()

        results = [
            make_question_result(
                question_id="q1",
                question_text="What are the company reviews?",
                category=QuestionCategory.TRUST,
                answerability=Answerability.NOT_ANSWERABLE,
                score=0.1,
                signals_found=0,
                signals_total=3,
            ),
        ]
        simulation = make_simulation_result(question_results=results)

        plan = generator.generate(simulation)

        assert any(f.reason_code == ReasonCode.TRUST_GAP for f in plan.fixes)

    def test_scaffold_includes_company_name(self) -> None:
        """Scaffold includes company name."""
        generator = FixGenerator()

        results = [
            make_question_result(
                question_id="q1",
                answerability=Answerability.NOT_ANSWERABLE,
                score=0.0,
                total_chunks=0,
            ),
        ]
        simulation = make_simulation_result(question_results=results)

        plan = generator.generate(simulation)

        if plan.fixes:
            assert "Test Company" in plan.fixes[0].scaffold

    def test_calculates_estimated_impact(self) -> None:
        """Calculates estimated impact for fixes."""
        generator = FixGenerator()

        results = [
            make_question_result(
                question_id="q1",
                answerability=Answerability.NOT_ANSWERABLE,
                score=0.0,
                total_chunks=0,
            ),
        ]
        simulation = make_simulation_result(question_results=results)

        plan = generator.generate(simulation)

        if plan.fixes:
            assert 0 < plan.fixes[0].estimated_impact <= 0.5
            assert plan.estimated_total_impact > 0

    def test_suggests_target_url(self) -> None:
        """Suggests target URL for fixes."""
        generator = FixGenerator()

        results = [
            make_question_result(
                question_id="q1",
                question_text="What is the pricing?",
                category=QuestionCategory.OFFERINGS,
                answerability=Answerability.NOT_ANSWERABLE,
                score=0.1,
                signals_found=0,
                signals_total=3,
            ),
        ]
        simulation = make_simulation_result(question_results=results)

        plan = generator.generate(simulation)

        # Should suggest /pricing URL
        pricing_fix = next(
            (f for f in plan.fixes if f.reason_code == ReasonCode.MISSING_PRICING),
            None,
        )
        if pricing_fix:
            assert pricing_fix.target_url == "/pricing"


class TestGenerateFixPlan:
    """Tests for generate_fix_plan function."""

    def test_returns_fix_plan(self) -> None:
        """Returns a FixPlan."""
        results = [
            make_question_result(
                answerability=Answerability.NOT_ANSWERABLE,
                score=0.0,
            ),
        ]
        simulation = make_simulation_result(question_results=results)

        plan = generate_fix_plan(simulation)

        assert isinstance(plan, FixPlan)

    def test_uses_custom_config(self) -> None:
        """Uses custom config."""
        results = [
            make_question_result(
                question_id=f"q{i}",
                answerability=Answerability.NOT_ANSWERABLE,
                score=0.0,
                total_chunks=0,
            )
            for i in range(10)
        ]
        simulation = make_simulation_result(question_results=results)

        config = FixGeneratorConfig(max_fixes=1)
        plan = generate_fix_plan(simulation, config=config)

        assert plan.total_fixes <= 1

    def test_matches_generator_result(self) -> None:
        """Matches direct generator usage."""
        results = [
            make_question_result(
                answerability=Answerability.NOT_ANSWERABLE,
                score=0.0,
            ),
        ]
        simulation = make_simulation_result(question_results=results)

        func_plan = generate_fix_plan(simulation)
        gen_plan = FixGenerator().generate(simulation)

        assert func_plan.total_fixes == gen_plan.total_fixes
