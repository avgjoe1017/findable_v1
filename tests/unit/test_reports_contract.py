"""Tests for report contract data structures."""

from datetime import datetime
from uuid import uuid4

from worker.reports.contract import (
    CURRENT_VERSION,
    BenchmarkSection,
    CompetitorSummary,
    DivergenceLevel,
    DivergenceSection,
    FixItem,
    FixSection,
    FullReport,
    ObservationSection,
    ReportMetadata,
    ReportVersion,
    ScoreSection,
)


class TestReportVersion:
    """Tests for ReportVersion enum."""

    def test_versions(self) -> None:
        """Has expected versions."""
        assert ReportVersion.V1_0.value == "1.0"
        assert ReportVersion.V1_1.value == "1.1"

    def test_current_version(self) -> None:
        """Current version is set."""
        assert CURRENT_VERSION == ReportVersion.V1_0


class TestReportMetadata:
    """Tests for ReportMetadata dataclass."""

    def test_create_metadata(self) -> None:
        """Can create metadata."""
        metadata = ReportMetadata(
            report_id=uuid4(),
            site_id=uuid4(),
            run_id=uuid4(),
            version=ReportVersion.V1_0,
            company_name="Test Company",
            domain="test.com",
            created_at=datetime.utcnow(),
        )

        assert metadata.company_name == "Test Company"
        assert metadata.version == ReportVersion.V1_0

    def test_to_dict(self) -> None:
        """Converts to dict."""
        report_id = uuid4()
        now = datetime.utcnow()

        metadata = ReportMetadata(
            report_id=report_id,
            site_id=uuid4(),
            run_id=uuid4(),
            version=ReportVersion.V1_0,
            company_name="Test",
            domain="test.com",
            created_at=now,
            limitations=["Test limitation"],
        )

        d = metadata.to_dict()

        assert d["report_id"] == str(report_id)
        assert d["version"] == "1.0"
        assert d["company_name"] == "Test"
        assert d["limitations"] == ["Test limitation"]


class TestScoreSection:
    """Tests for ScoreSection dataclass."""

    def test_create_score_section(self) -> None:
        """Can create score section."""
        section = ScoreSection(
            total_score=75.5,
            grade="B",
            grade_description="Good performance",
            category_scores={"identity": 80.0, "offerings": 70.0},
            category_breakdown={},
            criterion_scores=[],
            total_questions=20,
            questions_answered=15,
            questions_partial=3,
            questions_unanswered=2,
            coverage_percentage=85.0,
            calculation_summary=["Step 1", "Step 2"],
            formula_used="Score = ...",
            rubric_version="1.0",
            show_the_math="Full calculation...",
        )

        assert section.total_score == 75.5
        assert section.grade == "B"

    def test_to_dict(self) -> None:
        """Converts to dict."""
        section = ScoreSection(
            total_score=80.123,
            grade="B+",
            grade_description="Very good",
            category_scores={"identity": 85.0},
            category_breakdown={},
            criterion_scores=[],
            total_questions=10,
            questions_answered=8,
            questions_partial=1,
            questions_unanswered=1,
            coverage_percentage=85.0,
            calculation_summary=[],
            formula_used="",
            rubric_version="1.0",
            show_the_math="",
        )

        d = section.to_dict()

        assert d["total_score"] == 80.12
        assert d["grade"] == "B+"
        assert d["category_scores"]["identity"] == 85.0


class TestFixItem:
    """Tests for FixItem dataclass."""

    def test_create_fix_item(self) -> None:
        """Can create fix item."""
        item = FixItem(
            id="fix-1",
            reason_code="missing_pricing",
            title="Add pricing page",
            description="Create a dedicated pricing page",
            scaffold="# Pricing\n[ADD CONTENT]",
            priority=1,
            estimated_impact_min=5.0,
            estimated_impact_max=15.0,
            estimated_impact_expected=10.0,
            effort_level="medium",
            target_url="/pricing",
            affected_questions=["q1", "q2"],
            affected_categories=["offerings"],
        )

        assert item.title == "Add pricing page"
        assert item.priority == 1

    def test_to_dict(self) -> None:
        """Converts to dict."""
        item = FixItem(
            id="fix-1",
            reason_code="missing_contact",
            title="Add contact",
            description="Add contact info",
            scaffold="",
            priority=2,
            estimated_impact_min=2.0,
            estimated_impact_max=8.0,
            estimated_impact_expected=5.0,
            effort_level="low",
            target_url="/contact",
            affected_questions=["q1"],
            affected_categories=["contact"],
        )

        d = item.to_dict()

        assert d["id"] == "fix-1"
        assert d["estimated_impact"]["expected"] == 5.0
        assert d["estimated_impact"]["min"] == 2.0


class TestFixSection:
    """Tests for FixSection dataclass."""

    def test_create_fix_section(self) -> None:
        """Can create fix section."""
        section = FixSection(
            total_fixes=5,
            critical_fixes=1,
            high_priority_fixes=2,
            estimated_total_impact=25.0,
            fixes=[],
            categories_addressed=["identity", "offerings"],
            questions_addressed=8,
        )

        assert section.total_fixes == 5
        assert section.critical_fixes == 1

    def test_to_dict(self) -> None:
        """Converts to dict."""
        fix = FixItem(
            id="fix-1",
            reason_code="test",
            title="Test",
            description="Test",
            scaffold="",
            priority=1,
            estimated_impact_min=1.0,
            estimated_impact_max=3.0,
            estimated_impact_expected=2.0,
            effort_level="low",
            target_url=None,
            affected_questions=[],
            affected_categories=[],
        )

        section = FixSection(
            total_fixes=1,
            critical_fixes=0,
            high_priority_fixes=1,
            estimated_total_impact=10.0,
            fixes=[fix],
            categories_addressed=["identity"],
            questions_addressed=2,
        )

        d = section.to_dict()

        assert d["total_fixes"] == 1
        assert len(d["fixes"]) == 1


class TestObservationSection:
    """Tests for ObservationSection dataclass."""

    def test_create_observation_section(self) -> None:
        """Can create observation section."""
        section = ObservationSection(
            company_mention_rate=0.75,
            domain_mention_rate=0.5,
            citation_rate=0.25,
            total_questions=20,
            questions_with_mention=15,
            questions_with_citation=5,
            provider="openrouter",
            model="gpt-4o-mini",
            question_results=[],
            prediction_accuracy=0.8,
            optimistic_predictions=2,
            pessimistic_predictions=1,
            correct_predictions=17,
            insights=["Insight 1"],
            recommendations=["Rec 1"],
        )

        assert section.company_mention_rate == 0.75
        assert section.prediction_accuracy == 0.8

    def test_to_dict(self) -> None:
        """Converts to dict."""
        section = ObservationSection(
            company_mention_rate=0.6,
            domain_mention_rate=0.4,
            citation_rate=0.2,
            total_questions=10,
            questions_with_mention=6,
            questions_with_citation=2,
            provider="mock",
            model="test",
            question_results=[{"question_id": "q1"}],
            prediction_accuracy=0.7,
            optimistic_predictions=1,
            pessimistic_predictions=2,
            correct_predictions=7,
            insights=[],
            recommendations=[],
        )

        d = section.to_dict()

        assert d["company_mention_rate"] == 0.6
        assert len(d["question_results"]) == 1


class TestCompetitorSummary:
    """Tests for CompetitorSummary dataclass."""

    def test_create_summary(self) -> None:
        """Can create competitor summary."""
        summary = CompetitorSummary(
            name="Competitor Inc",
            domain="competitor.com",
            mention_rate=0.6,
            citation_rate=0.3,
            wins_against_you=5,
            losses_against_you=10,
            ties=5,
        )

        assert summary.name == "Competitor Inc"
        assert summary.wins_against_you == 5

    def test_to_dict(self) -> None:
        """Converts to dict."""
        summary = CompetitorSummary(
            name="Test",
            domain="test.com",
            mention_rate=0.5,
            citation_rate=0.25,
            wins_against_you=3,
            losses_against_you=7,
            ties=0,
        )

        d = summary.to_dict()

        assert d["name"] == "Test"
        assert d["mention_rate"] == 0.5


class TestBenchmarkSection:
    """Tests for BenchmarkSection dataclass."""

    def test_create_benchmark_section(self) -> None:
        """Can create benchmark section."""
        section = BenchmarkSection(
            total_competitors=2,
            total_questions=20,
            your_mention_rate=0.7,
            your_citation_rate=0.3,
            avg_competitor_mention_rate=0.5,
            avg_competitor_citation_rate=0.2,
            overall_wins=12,
            overall_losses=5,
            overall_ties=3,
            overall_win_rate=0.6,
            unique_wins=["q1", "q2"],
            unique_losses=["q10"],
            competitors=[],
            question_benchmarks=[],
            insights=["Insight"],
            recommendations=["Rec"],
        )

        assert section.overall_win_rate == 0.6
        assert section.unique_wins == ["q1", "q2"]

    def test_to_dict(self) -> None:
        """Converts to dict."""
        section = BenchmarkSection(
            total_competitors=1,
            total_questions=10,
            your_mention_rate=0.8,
            your_citation_rate=0.4,
            avg_competitor_mention_rate=0.6,
            avg_competitor_citation_rate=0.3,
            overall_wins=6,
            overall_losses=3,
            overall_ties=1,
            overall_win_rate=0.6,
            unique_wins=[],
            unique_losses=[],
            competitors=[],
            question_benchmarks=[],
            insights=[],
            recommendations=[],
        )

        d = section.to_dict()

        assert d["total_competitors"] == 1
        assert d["overall_win_rate"] == 0.6


class TestDivergenceSection:
    """Tests for DivergenceSection dataclass."""

    def test_create_divergence_section(self) -> None:
        """Can create divergence section."""
        section = DivergenceSection(
            level=DivergenceLevel.LOW,
            mention_rate_delta=0.15,
            prediction_accuracy=0.75,
            should_refresh=False,
            refresh_reasons=[],
            optimism_bias=0.1,
            pessimism_bias=0.05,
            calibration_notes=["Well calibrated"],
        )

        assert section.level == DivergenceLevel.LOW
        assert section.prediction_accuracy == 0.75

    def test_to_dict(self) -> None:
        """Converts to dict."""
        section = DivergenceSection(
            level=DivergenceLevel.HIGH,
            mention_rate_delta=-0.3,
            prediction_accuracy=0.4,
            should_refresh=True,
            refresh_reasons=["High divergence"],
            optimism_bias=0.4,
            pessimism_bias=0.1,
            calibration_notes=["Needs adjustment"],
        )

        d = section.to_dict()

        assert d["level"] == "high"
        assert d["should_refresh"] is True


class TestFullReport:
    """Tests for FullReport dataclass."""

    def make_minimal_report(self) -> FullReport:
        """Create a minimal report for testing."""
        metadata = ReportMetadata(
            report_id=uuid4(),
            site_id=uuid4(),
            run_id=uuid4(),
            version=ReportVersion.V1_0,
            company_name="Test Company",
            domain="test.com",
            created_at=datetime.utcnow(),
        )

        score = ScoreSection(
            total_score=75.0,
            grade="B",
            grade_description="Good",
            category_scores={"identity": 80.0},
            category_breakdown={},
            criterion_scores=[],
            total_questions=10,
            questions_answered=7,
            questions_partial=2,
            questions_unanswered=1,
            coverage_percentage=80.0,
            calculation_summary=[],
            formula_used="",
            rubric_version="1.0",
            show_the_math="",
        )

        fixes = FixSection(
            total_fixes=3,
            critical_fixes=1,
            high_priority_fixes=1,
            estimated_total_impact=15.0,
            fixes=[],
            categories_addressed=["identity"],
            questions_addressed=5,
        )

        return FullReport(metadata=metadata, score=score, fixes=fixes)

    def test_create_full_report(self) -> None:
        """Can create full report."""
        report = self.make_minimal_report()

        assert report.metadata.company_name == "Test Company"
        assert report.score.total_score == 75.0

    def test_to_dict(self) -> None:
        """Converts to dict."""
        report = self.make_minimal_report()

        d = report.to_dict()

        assert "metadata" in d
        assert "score" in d
        assert "fixes" in d
        assert d["metadata"]["company_name"] == "Test Company"

    def test_to_dict_with_optional_sections(self) -> None:
        """Includes optional sections when present."""
        report = self.make_minimal_report()

        report.observation = ObservationSection(
            company_mention_rate=0.7,
            domain_mention_rate=0.5,
            citation_rate=0.3,
            total_questions=10,
            questions_with_mention=7,
            questions_with_citation=3,
            provider="mock",
            model="test",
            question_results=[],
            prediction_accuracy=0.8,
            optimistic_predictions=1,
            pessimistic_predictions=1,
            correct_predictions=8,
            insights=[],
            recommendations=[],
        )

        d = report.to_dict()

        assert "observation" in d
        assert d["observation"]["company_mention_rate"] == 0.7

    def test_get_quick_access_fields(self) -> None:
        """Gets denormalized fields for database."""
        report = self.make_minimal_report()

        fields = report.get_quick_access_fields()

        assert "score_conservative" in fields
        assert "score_typical" in fields
        assert "score_generous" in fields
        assert fields["score_typical"] == 75

    def test_get_top_fixes(self) -> None:
        """Gets top priority fixes."""
        report = self.make_minimal_report()

        fix1 = FixItem(
            id="fix-1",
            reason_code="a",
            title="High priority",
            description="",
            scaffold="",
            priority=1,
            estimated_impact_min=5,
            estimated_impact_max=15,
            estimated_impact_expected=10,
            effort_level="low",
            target_url=None,
            affected_questions=[],
            affected_categories=[],
        )
        fix2 = FixItem(
            id="fix-2",
            reason_code="b",
            title="Low priority",
            description="",
            scaffold="",
            priority=3,
            estimated_impact_min=1,
            estimated_impact_max=5,
            estimated_impact_expected=3,
            effort_level="low",
            target_url=None,
            affected_questions=[],
            affected_categories=[],
        )

        report.fixes.fixes = [fix2, fix1]  # Out of order

        top = report.get_top_fixes(1)

        assert len(top) == 1
        assert top[0].id == "fix-1"

    def test_get_summary(self) -> None:
        """Gets summary for list views."""
        report = self.make_minimal_report()

        summary = report.get_summary()

        assert summary["score"] == 75.0
        assert summary["grade"] == "B"
        assert summary["total_fixes"] == 3
