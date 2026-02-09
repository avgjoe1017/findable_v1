"""Tests for report assembler."""

from datetime import datetime
from uuid import uuid4

from worker.fixes.generator import Fix, FixPlan
from worker.fixes.reason_codes import ReasonCode, get_reason_info
from worker.fixes.templates import get_template
from worker.observation.benchmark import (
    BenchmarkResult,
    CompetitorInfo,
    CompetitorResult,
    HeadToHead,
)
from worker.observation.comparison import ComparisonSummary
from worker.observation.models import (
    ObservationResponse,
    ObservationResult,
    ObservationRun,
    ObservationStatus,
    ProviderType,
)
from worker.questions.universal import QuestionCategory, QuestionDifficulty
from worker.reports.assembler import (
    ReportAssembler,
    ReportAssemblerConfig,
    assemble_report,
)
from worker.reports.contract import (
    DivergenceLevel,
    FullReport,
    ReportVersion,
)
from worker.scoring.calculator import (
    CategoryBreakdown,
    CriterionScore,
    ScoreBreakdown,
)
from worker.scoring.rubric import RubricCriterion, ScoreLevel
from worker.simulation.runner import (
    Answerability,
    ConfidenceLevel,
    QuestionResult,
    RetrievedContext,
    SimulationResult,
)


def make_simulation_result() -> SimulationResult:
    """Create a test SimulationResult."""
    return SimulationResult(
        site_id=uuid4(),
        run_id=uuid4(),
        company_name="Test Company",
        question_results=[
            QuestionResult(
                question_id="q1",
                question_text="What does Test Company do?",
                category=QuestionCategory.IDENTITY,
                difficulty=QuestionDifficulty.EASY,
                source="universal",
                weight=1.0,
                context=RetrievedContext(
                    chunks=[],
                    total_chunks=3,
                    avg_relevance_score=0.7,
                    max_relevance_score=0.9,
                    source_pages=["https://test.com/about"],
                    content_preview="Test preview",
                ),
                answerability=Answerability.FULLY_ANSWERABLE,
                confidence=ConfidenceLevel.HIGH,
                score=0.8,
                signals_found=3,
                signals_total=4,
                signal_matches=[],
                retrieval_time_ms=50.0,
                evaluation_time_ms=10.0,
            ),
        ],
        total_questions=1,
        questions_answered=1,
        questions_partial=0,
        questions_unanswered=0,
        category_scores={"identity": 80.0},
        difficulty_scores={"easy": 80.0},
        overall_score=80.0,
        coverage_score=100.0,
        confidence_score=90.0,
        total_time_ms=100.0,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        metadata={},
    )


def make_score_breakdown() -> ScoreBreakdown:
    """Create a test ScoreBreakdown."""
    criterion = RubricCriterion(
        id="content_relevance",
        name="Content Relevance",
        description="Test",
        weight=0.35,
        max_points=35,
        excellent_threshold=0.9,
        good_threshold=0.7,
        fair_threshold=0.5,
        needs_work_threshold=0.3,
    )

    return ScoreBreakdown(
        total_score=75.0,
        grade="B",
        grade_description="Good performance",
        criterion_scores=[
            CriterionScore(
                criterion=criterion,
                raw_score=0.75,
                weighted_score=0.26,
                points_earned=26.25,
                max_points=35,
                level=ScoreLevel.GOOD,
                explanation="Good content relevance",
            )
        ],
        category_breakdowns={
            "identity": CategoryBreakdown(
                category=QuestionCategory.IDENTITY,
                weight=0.25,
                question_count=3,
                questions_answered=2,
                questions_partial=1,
                questions_unanswered=0,
                raw_score=80.0,
                weighted_score=20.0,
                contribution=20.0,
                question_scores=[],
                explanation="Good identity coverage",
                recommendations=[],
            )
        },
        question_scores=[],
        total_questions=10,
        questions_answered=7,
        questions_partial=2,
        questions_unanswered=1,
        coverage_percentage=80.0,
        calculation_summary=["Step 1: Calculate criteria"],
        formula_used="Score = ...",
        rubric_version="1.0",
    )


def make_fix_plan() -> FixPlan:
    """Create a test FixPlan."""
    reason_code = ReasonCode.MISSING_PRICING
    reason_info = get_reason_info(reason_code)
    template = get_template(reason_code)

    fix = Fix(
        id=uuid4(),
        reason_code=reason_code,
        reason_info=reason_info,
        template=template,
        affected_question_ids=["q1", "q2"],
        affected_categories=[QuestionCategory.OFFERINGS],
        scaffold="# Pricing\n[ADD CONTENT]",
        extracted_content=[],
        priority=1,
        estimated_impact=0.15,
        effort_level="medium",
        target_url="/pricing",
    )

    return FixPlan(
        id=uuid4(),
        site_id=uuid4(),
        run_id=uuid4(),
        company_name="Test Company",
        fixes=[fix],
        total_fixes=1,
        critical_fixes=0,
        high_priority_fixes=1,
        estimated_total_impact=0.15,
        categories_addressed=[QuestionCategory.OFFERINGS],
        questions_addressed=2,
    )


def make_observation_run() -> ObservationRun:
    """Create a test ObservationRun."""
    run = ObservationRun(
        site_id=uuid4(),
        company_name="Test Company",
        domain="test.com",
        provider=ProviderType.MOCK,
        model="gpt-4o-mini",
        total_questions=2,
        status=ObservationStatus.COMPLETED,
    )

    # Add results
    for i in range(2):
        result = ObservationResult(
            question_id=f"q{i+1}",
            question_text=f"Question {i+1}",
            company_name="Test Company",
            domain="test.com",
            response=ObservationResponse(
                request_id=uuid4(),
                provider=ProviderType.MOCK,
                model="mock",
                content="Test response mentioning Test Company",
                success=True,
            ),
            mentions_company=i == 0,  # First one mentions
            mentions_domain=False,
            mentions_url=i == 0,
            cited_urls=["https://test.com"] if i == 0 else [],
            confidence_expressed="medium",
        )
        run.add_result(result)

    return run


def make_comparison_summary() -> ComparisonSummary:
    """Create a test ComparisonSummary."""
    return ComparisonSummary(
        total_questions=10,
        correct_predictions=7,
        optimistic_predictions=2,
        pessimistic_predictions=1,
        unknown_predictions=0,
        prediction_accuracy=0.7,
        mention_rate_sim=0.6,
        mention_rate_obs=0.5,
        citation_rate_obs=0.2,
        mention_rate_delta=-0.1,
        comparisons=[],
        insights=["Simulation is slightly optimistic"],
        recommendations=["Improve citation signals"],
    )


def make_benchmark_result() -> BenchmarkResult:
    """Create a test BenchmarkResult."""
    competitor = CompetitorInfo(name="Rival Inc", domain="rival.com")

    return BenchmarkResult(
        company_name="Test Company",
        domain="test.com",
        competitor_results=[
            CompetitorResult(
                competitor=competitor,
                mention_rate=0.5,
                citation_rate=0.2,
                questions_mentioned=5,
                questions_cited=2,
                total_questions=10,
            )
        ],
        question_benchmarks=[],
        head_to_heads=[
            HeadToHead(
                competitor_name="Rival Inc",
                wins=6,
                losses=3,
                ties=1,
                win_rate=0.6,
                mention_advantage=0.1,
                citation_advantage=0.1,
            )
        ],
        total_questions=10,
        total_competitors=1,
        your_mention_rate=0.6,
        your_citation_rate=0.3,
        avg_competitor_mention_rate=0.5,
        avg_competitor_citation_rate=0.2,
        overall_wins=6,
        overall_losses=3,
        overall_ties=1,
        overall_win_rate=0.6,
        unique_wins=["q1"],
        unique_losses=["q10"],
        insights=["Competitive advantage"],
        recommendations=["Expand coverage"],
    )


class TestReportAssemblerConfig:
    """Tests for ReportAssemblerConfig."""

    def test_default_config(self) -> None:
        """Default config has expected values."""
        config = ReportAssemblerConfig()

        assert config.include_observation is True
        assert config.include_benchmark is True
        assert config.divergence_high_threshold == 0.35

    def test_custom_config(self) -> None:
        """Can customize config."""
        config = ReportAssemblerConfig(
            include_observation=False,
            divergence_high_threshold=0.5,
        )

        assert config.include_observation is False
        assert config.divergence_high_threshold == 0.5


class TestReportAssembler:
    """Tests for ReportAssembler class."""

    def test_create_assembler(self) -> None:
        """Can create assembler."""
        assembler = ReportAssembler()
        assert assembler is not None

    def test_assemble_minimal_report(self) -> None:
        """Assembles report with minimal required data."""
        assembler = ReportAssembler()

        report = assembler.assemble(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test Company",
            domain="test.com",
            simulation=make_simulation_result(),
            score_breakdown=make_score_breakdown(),
            fix_plan=make_fix_plan(),
        )

        assert isinstance(report, FullReport)
        assert report.metadata.company_name == "Test Company"
        assert report.score.total_score == 75.0
        assert report.fixes.total_fixes == 1

    def test_assemble_includes_metadata(self) -> None:
        """Report includes proper metadata."""
        assembler = ReportAssembler()
        site_id = uuid4()
        run_id = uuid4()

        report = assembler.assemble(
            site_id=site_id,
            run_id=run_id,
            company_name="Test Company",
            domain="test.com",
            simulation=make_simulation_result(),
            score_breakdown=make_score_breakdown(),
            fix_plan=make_fix_plan(),
        )

        assert report.metadata.site_id == site_id
        assert report.metadata.run_id == run_id
        assert report.metadata.version == ReportVersion.V1_1
        assert report.metadata.domain == "test.com"

    def test_assemble_calculates_run_duration(self) -> None:
        """Calculates run duration when times provided."""
        assembler = ReportAssembler()
        started = datetime(2024, 1, 1, 10, 0, 0)
        completed = datetime(2024, 1, 1, 10, 5, 30)

        report = assembler.assemble(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test",
            domain="test.com",
            simulation=make_simulation_result(),
            score_breakdown=make_score_breakdown(),
            fix_plan=make_fix_plan(),
            run_started_at=started,
            run_completed_at=completed,
        )

        assert report.metadata.run_duration_seconds == 330.0

    def test_assemble_with_observation(self) -> None:
        """Includes observation section when provided."""
        assembler = ReportAssembler()

        report = assembler.assemble(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test",
            domain="test.com",
            simulation=make_simulation_result(),
            score_breakdown=make_score_breakdown(),
            fix_plan=make_fix_plan(),
            observation=make_observation_run(),
        )

        assert report.observation is not None
        assert report.observation.total_questions == 2

    def test_assemble_with_comparison(self) -> None:
        """Includes comparison data in observation section."""
        assembler = ReportAssembler()

        report = assembler.assemble(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test",
            domain="test.com",
            simulation=make_simulation_result(),
            score_breakdown=make_score_breakdown(),
            fix_plan=make_fix_plan(),
            observation=make_observation_run(),
            comparison=make_comparison_summary(),
        )

        assert report.observation is not None
        assert report.observation.prediction_accuracy == 0.7
        assert len(report.observation.insights) > 0

    def test_assemble_with_benchmark(self) -> None:
        """Includes benchmark section when provided."""
        assembler = ReportAssembler()

        report = assembler.assemble(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test",
            domain="test.com",
            simulation=make_simulation_result(),
            score_breakdown=make_score_breakdown(),
            fix_plan=make_fix_plan(),
            benchmark=make_benchmark_result(),
        )

        assert report.benchmark is not None
        assert report.benchmark.total_competitors == 1
        assert report.benchmark.overall_win_rate == 0.6

    def test_assemble_builds_divergence(self) -> None:
        """Builds divergence section when comparison provided."""
        assembler = ReportAssembler()

        report = assembler.assemble(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test",
            domain="test.com",
            simulation=make_simulation_result(),
            score_breakdown=make_score_breakdown(),
            fix_plan=make_fix_plan(),
            observation=make_observation_run(),
            comparison=make_comparison_summary(),
        )

        assert report.divergence is not None
        assert report.divergence.prediction_accuracy == 0.7

    def test_divergence_level_none(self) -> None:
        """Sets divergence level to NONE for small delta."""
        assembler = ReportAssembler()
        comparison = make_comparison_summary()
        comparison.mention_rate_delta = 0.05  # 5% delta

        report = assembler.assemble(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test",
            domain="test.com",
            simulation=make_simulation_result(),
            score_breakdown=make_score_breakdown(),
            fix_plan=make_fix_plan(),
            comparison=comparison,
        )

        assert report.divergence.level == DivergenceLevel.NONE

    def test_divergence_level_high(self) -> None:
        """Sets divergence level to HIGH for large delta."""
        assembler = ReportAssembler()
        comparison = make_comparison_summary()
        comparison.mention_rate_delta = 0.4  # 40% delta

        report = assembler.assemble(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test",
            domain="test.com",
            simulation=make_simulation_result(),
            score_breakdown=make_score_breakdown(),
            fix_plan=make_fix_plan(),
            comparison=comparison,
        )

        assert report.divergence.level == DivergenceLevel.HIGH
        assert report.divergence.should_refresh is True

    def test_divergence_refresh_on_low_accuracy(self) -> None:
        """Triggers refresh on low prediction accuracy."""
        assembler = ReportAssembler()
        comparison = make_comparison_summary()
        comparison.prediction_accuracy = 0.4  # Below 50%

        report = assembler.assemble(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test",
            domain="test.com",
            simulation=make_simulation_result(),
            score_breakdown=make_score_breakdown(),
            fix_plan=make_fix_plan(),
            comparison=comparison,
        )

        assert report.divergence.should_refresh is True
        assert len(report.divergence.refresh_reasons) > 0

    def test_config_excludes_observation(self) -> None:
        """Config can exclude observation section."""
        config = ReportAssemblerConfig(include_observation=False)
        assembler = ReportAssembler(config)

        report = assembler.assemble(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test",
            domain="test.com",
            simulation=make_simulation_result(),
            score_breakdown=make_score_breakdown(),
            fix_plan=make_fix_plan(),
            observation=make_observation_run(),  # Provided but should be excluded
        )

        assert report.observation is None
        assert "Observation was not run" in report.metadata.limitations[0]

    def test_config_excludes_benchmark(self) -> None:
        """Config can exclude benchmark section."""
        config = ReportAssemblerConfig(include_benchmark=False)
        assembler = ReportAssembler(config)

        report = assembler.assemble(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test",
            domain="test.com",
            simulation=make_simulation_result(),
            score_breakdown=make_score_breakdown(),
            fix_plan=make_fix_plan(),
            benchmark=make_benchmark_result(),  # Provided but should be excluded
        )

        assert report.benchmark is None

    def test_report_to_dict(self) -> None:
        """Assembled report converts to dict."""
        assembler = ReportAssembler()

        report = assembler.assemble(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test Company",
            domain="test.com",
            simulation=make_simulation_result(),
            score_breakdown=make_score_breakdown(),
            fix_plan=make_fix_plan(),
            observation=make_observation_run(),
            comparison=make_comparison_summary(),
            benchmark=make_benchmark_result(),
        )

        d = report.to_dict()

        assert "metadata" in d
        assert "score" in d
        assert "fixes" in d
        assert "observation" in d
        assert "benchmark" in d
        assert "divergence" in d


class TestConvenienceFunction:
    """Tests for assemble_report convenience function."""

    def test_assemble_report_function(self) -> None:
        """Convenience function works."""
        report = assemble_report(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test",
            domain="test.com",
            simulation=make_simulation_result(),
            score_breakdown=make_score_breakdown(),
            fix_plan=make_fix_plan(),
        )

        assert isinstance(report, FullReport)
        assert report.metadata.company_name == "Test"

    def test_assemble_report_with_config(self) -> None:
        """Convenience function accepts config."""
        config = ReportAssemblerConfig(include_observation=False)

        report = assemble_report(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test",
            domain="test.com",
            simulation=make_simulation_result(),
            score_breakdown=make_score_breakdown(),
            fix_plan=make_fix_plan(),
            observation=make_observation_run(),
            config=config,
        )

        assert report.observation is None


class TestFullReportIntegration:
    """Integration tests for full report workflow."""

    def test_full_report_with_all_sections(self) -> None:
        """Creates complete report with all sections."""
        assembler = ReportAssembler()

        report = assembler.assemble(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test Company",
            domain="test.com",
            simulation=make_simulation_result(),
            score_breakdown=make_score_breakdown(),
            fix_plan=make_fix_plan(),
            observation=make_observation_run(),
            comparison=make_comparison_summary(),
            benchmark=make_benchmark_result(),
            run_started_at=datetime.utcnow(),
            run_completed_at=datetime.utcnow(),
        )

        # Verify all sections present
        assert report.metadata is not None
        assert report.score is not None
        assert report.fixes is not None
        assert report.observation is not None
        assert report.benchmark is not None
        assert report.divergence is not None

        # Verify can serialize
        d = report.to_dict()
        assert isinstance(d, dict)

        # Verify quick access fields
        fields = report.get_quick_access_fields()
        assert "score_typical" in fields
        assert "mention_rate" in fields

        # Verify summary
        summary = report.get_summary()
        assert "score" in summary
        assert "grade" in summary

    def test_report_score_section_complete(self) -> None:
        """Score section contains all required fields."""
        assembler = ReportAssembler()

        report = assembler.assemble(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test",
            domain="test.com",
            simulation=make_simulation_result(),
            score_breakdown=make_score_breakdown(),
            fix_plan=make_fix_plan(),
        )

        score = report.score
        assert score.total_score == 75.0
        assert score.grade == "B"
        assert score.total_questions == 10
        assert score.rubric_version == "1.0"
        assert len(score.show_the_math) > 0

    def test_report_fix_section_complete(self) -> None:
        """Fix section contains all required fields."""
        assembler = ReportAssembler()

        report = assembler.assemble(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Test",
            domain="test.com",
            simulation=make_simulation_result(),
            score_breakdown=make_score_breakdown(),
            fix_plan=make_fix_plan(),
        )

        fixes = report.fixes
        assert fixes.total_fixes == 1
        assert len(fixes.fixes) == 1
        assert fixes.fixes[0].reason_code == "missing_pricing"
