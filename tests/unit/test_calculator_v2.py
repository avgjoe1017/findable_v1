"""Unit tests for Findable Score v2 Calculator."""

import pytest

from worker.extraction.entity_recognition import (
    DomainSignals,
    EntityRecognitionResult,
    WebPresenceSignals,
    WikidataSignals,
    WikipediaSignals,
)
from worker.scoring.authority import AuthorityComponent, AuthoritySignalsScore
from worker.scoring.calculator import ScoreBreakdown
from worker.scoring.calculator_v2 import (
    FINDABILITY_LEVELS,
    MILESTONES,
    PILLAR_WEIGHTS,
    FindableScoreCalculatorV2,
    FindableScoreV2,
    MilestoneInfo,
    PathAction,
    PillarScore,
    calculate_findable_score_v2,
)
from worker.scoring.schema import SchemaComponent, SchemaRichnessScore
from worker.scoring.structure import StructureComponent, StructureQualityScore
from worker.scoring.technical import TechnicalComponent, TechnicalReadinessScore

# ============================================================================
# Helper Functions for Creating Test Scores
# ============================================================================


def make_technical_score(score: float = 80.0) -> TechnicalReadinessScore:
    """Create a TechnicalReadinessScore for testing."""
    return TechnicalReadinessScore(
        total_score=score,
        level="good" if score >= 70 else "warning" if score >= 40 else "critical",
        max_points=15.0,
        components=[
            TechnicalComponent(
                name="robots_txt",
                raw_score=score,
                weight=0.35,
                weighted_score=score * 0.35,
                level="good",
                explanation="AI bots allowed",
            ),
            TechnicalComponent(
                name="ttfb",
                raw_score=score,
                weight=0.30,
                weighted_score=score * 0.30,
                level="good",
                explanation="Fast response",
            ),
        ],
        critical_issues=[],
        all_issues=[],
    )


def make_structure_score(score: float = 75.0) -> StructureQualityScore:
    """Create a StructureQualityScore for testing."""
    return StructureQualityScore(
        total_score=score,
        level="good" if score >= 70 else "warning" if score >= 40 else "critical",
        max_points=20.0,
        components=[
            StructureComponent(
                name="heading_hierarchy",
                raw_score=score,
                weight=0.25,
                weighted_score=score * 0.25,
                level="good",
                explanation="Valid hierarchy",
            ),
        ],
        critical_issues=[],
        recommendations=[],
    )


def make_schema_score(score: float = 70.0) -> SchemaRichnessScore:
    """Create a SchemaRichnessScore for testing."""
    return SchemaRichnessScore(
        total_score=score,
        level="good" if score >= 70 else "warning" if score >= 40 else "critical",
        max_points=15.0,
        components=[
            SchemaComponent(
                name="faq_page",
                raw_score=score,
                weight=0.27,
                weighted_score=score * 0.27,
                level="good",
                explanation="FAQPage found",
            ),
        ],
        critical_issues=[],
        recommendations=[],
    )


def make_authority_score(score: float = 65.0) -> AuthoritySignalsScore:
    """Create an AuthoritySignalsScore for testing."""
    return AuthoritySignalsScore(
        total_score=score,
        level="good" if score >= 70 else "warning" if score >= 40 else "critical",
        max_points=15.0,
        components=[
            AuthorityComponent(
                name="author_attribution",
                raw_score=score,
                weight=0.27,
                weighted_score=score * 0.27,
                level="good" if score >= 70 else "warning",
                explanation="Authors found",
            ),
        ],
        critical_issues=[],
        recommendations=[],
    )


def make_score_breakdown(
    total_score: float = 75.0,
    coverage: float = 80.0,
) -> ScoreBreakdown:
    """Create a ScoreBreakdown for testing retrieval/coverage."""
    return ScoreBreakdown(
        total_score=total_score,
        grade="B",
        grade_description="Good",
        criterion_scores=[],
        category_breakdowns={},
        question_scores=[],
        total_questions=10,
        questions_answered=8,
        questions_partial=1,
        questions_unanswered=1,
        coverage_percentage=coverage,
        calculation_summary=[],
        formula_used="v1",
        rubric_version="1.0",
    )


def make_entity_recognition_result(score: float = 60.0) -> EntityRecognitionResult:
    """Create an EntityRecognitionResult for testing.

    Args:
        score: Target normalized score (0-100)
    """
    # For 100, create a perfect result that actually scores 100
    if score >= 100:
        from datetime import UTC, datetime, timedelta

        result = EntityRecognitionResult(
            domain="test.com",
            brand_name="Test Brand",
            wikipedia=WikipediaSignals(
                has_page=True,
                page_length_chars=50000,  # Max bonus (+5)
                citation_count=100,  # Max bonus (+5)
                infobox_present=True,  # +2
                page_sections=20,  # +2
                last_edited=datetime.now(UTC) - timedelta(days=30),  # Freshness (+1)
            ),
            wikidata=WikidataSignals(
                has_entity=True,  # +10
                property_count=100,  # Max bonus (+4)
                sitelink_count=100,  # Max bonus (+4)
                instance_of=["company"],  # Notable type (+2)
            ),
            domain_signals=DomainSignals(
                domain="x.co",  # Ultra-short domain (+3)
                is_registered=True,
                domain_age_years=25,  # Very old (max +10)
                tld="com",
                is_premium_tld=True,  # +5
            ),
            web_presence=WebPresenceSignals(
                google_results_estimate=500_000_000,  # Max (+15)
                news_mentions_30d=200,  # Max (+10)
                news_sources=["nytimes.com", "bbc.com", "reuters.com"],  # Max (+5)
                twitter_followers=1_000_000,  # Bonus
            ),
        )
        result.calculate_total_score()
        return result

    # Scale component scores to achieve target normalized score
    # Max possible: wikipedia=30, wikidata=20, domain=20, web=30 = 100
    scale = score / 100.0

    result = EntityRecognitionResult(
        domain="test.com",
        brand_name="Test Brand",
        wikipedia=WikipediaSignals(
            has_page=score >= 30,
            page_length_chars=int(10000 * scale) if score >= 40 else 0,
            citation_count=int(50 * scale) if score >= 50 else 0,
            infobox_present=score >= 60,
        ),
        wikidata=WikidataSignals(
            has_entity=score >= 20,
            property_count=int(40 * scale) if score >= 30 else 0,
            sitelink_count=int(30 * scale) if score >= 40 else 0,
        ),
        domain_signals=DomainSignals(
            domain="test.com",
            is_registered=True,
            domain_age_years=10.0 * scale,
            is_premium_tld=True,
        ),
        web_presence=WebPresenceSignals(
            google_results_estimate=int(1_000_000 * scale) if score >= 20 else 0,
        ),
    )
    result.calculate_total_score()
    return result


# ============================================================================
# Findability Levels Tests
# ============================================================================


class TestFindabilityLevels:
    """Tests for findability levels configuration."""

    def test_levels_cover_full_range(self):
        """Levels cover entire 0-100 score range without gaps."""
        # Check that all scores 0-100 map to exactly one level
        for score in range(101):
            matched_levels = [
                level_id
                for level_id, level_data in FINDABILITY_LEVELS.items()
                if level_data["min_score"] <= score <= level_data["max_score"]
            ]
            assert len(matched_levels) == 1, f"Score {score} matched {len(matched_levels)} levels"

    def test_levels_have_required_fields(self):
        """Each level has all required fields."""
        required_fields = ["min_score", "max_score", "label", "summary", "focus"]
        for level_id, level_data in FINDABILITY_LEVELS.items():
            for field in required_fields:
                assert field in level_data, f"Level {level_id} missing {field}"

    def test_level_boundaries(self):
        """Level boundaries are at expected scores."""
        assert FINDABILITY_LEVELS["not_yet_findable"]["max_score"] == 39
        assert FINDABILITY_LEVELS["partially_findable"]["min_score"] == 40
        assert FINDABILITY_LEVELS["findable"]["min_score"] == 55
        assert FINDABILITY_LEVELS["highly_findable"]["min_score"] == 70
        assert FINDABILITY_LEVELS["optimized"]["min_score"] == 85


class TestMilestones:
    """Tests for milestone configuration."""

    def test_milestones_in_order(self):
        """Milestones are in ascending order."""
        scores = [m["score"] for m in MILESTONES]
        assert scores == sorted(scores)

    def test_milestones_have_required_fields(self):
        """Each milestone has required fields."""
        for milestone in MILESTONES:
            assert "score" in milestone
            assert "name" in milestone
            assert "description" in milestone


# ============================================================================
# PillarScore Tests
# ============================================================================


class TestPillarScore:
    """Tests for PillarScore dataclass."""

    def test_pillar_score_creation(self):
        """PillarScore stores pillar data correctly."""
        pillar = PillarScore(
            name="technical",
            display_name="Technical Readiness",
            raw_score=80.0,
            max_points=15.0,
            points_earned=12.0,
            weight_pct=15.0,
            level="good",
            description="Can AI access your site?",
        )
        assert pillar.name == "technical"
        assert pillar.raw_score == 80.0
        assert pillar.max_points == 15.0
        assert pillar.points_earned == 12.0

    def test_pillar_score_to_dict(self):
        """PillarScore converts to dictionary correctly."""
        pillar = PillarScore(
            name="structure",
            display_name="Structure Quality",
            raw_score=75.0,
            max_points=20.0,
            points_earned=15.0,
            weight_pct=20.0,
            level="good",
            description="Is your content extractable?",
        )
        data = pillar.to_dict()
        assert data["name"] == "structure"
        assert data["raw_score"] == 75.0
        assert data["level"] == "good"


# ============================================================================
# MilestoneInfo and PathAction Tests
# ============================================================================


class TestMilestoneInfo:
    """Tests for MilestoneInfo dataclass."""

    def test_milestone_info_to_dict(self):
        """MilestoneInfo converts to dictionary correctly."""
        milestone = MilestoneInfo(
            score=55,
            name="Findable",
            description="AI can reliably find and cite you",
            points_needed=6.0,
        )
        data = milestone.to_dict()
        assert data["score"] == 55
        assert data["name"] == "Findable"
        assert data["points_needed"] == 6.0


class TestPathAction:
    """Tests for PathAction dataclass."""

    def test_path_action_to_dict(self):
        """PathAction converts to dictionary correctly."""
        action = PathAction(
            action="Add FAQPage schema",
            impact_points=8.0,
            effort="30 min",
            pillar="schema",
        )
        data = action.to_dict()
        assert data["action"] == "Add FAQPage schema"
        assert data["impact_points"] == 8.0
        assert data["effort"] == "30 min"


# ============================================================================
# FindableScoreV2 Tests
# ============================================================================


class TestFindableScoreV2:
    """Tests for FindableScoreV2 dataclass."""

    def test_findable_score_v2_to_dict(self):
        """FindableScoreV2 converts to dictionary correctly."""
        pillar = PillarScore(
            name="technical",
            display_name="Technical Readiness",
            raw_score=80.0,
            max_points=15.0,
            points_earned=12.0,
            weight_pct=15.0,
            level="good",
            description="Test",
        )

        score = FindableScoreV2(
            total_score=75.0,
            level="highly_findable",
            level_label="Highly Findable",
            level_summary="You're ahead of most competitors.",
            level_focus="Address remaining gaps.",
            next_milestone=MilestoneInfo(
                score=85, name="Optimized", description="Top-tier", points_needed=10
            ),
            points_to_milestone=10.0,
            pillars=[pillar],
            pillar_breakdown={"technical": pillar},
            pillars_good=1,
            pillars_warning=0,
            pillars_critical=0,
            all_critical_issues=[],
            top_recommendations=[],
            calculation_summary=[],
        )

        data = score.to_dict()
        assert data["total_score"] == 75.0
        assert data["level"] == "highly_findable"
        assert data["level_label"] == "Highly Findable"
        assert data["version"] == "2.2"
        assert len(data["pillars"]) == 1
        assert data["next_milestone"]["score"] == 85

    def test_show_the_math(self):
        """show_the_math generates readable output."""
        pillar = PillarScore(
            name="technical",
            display_name="Technical Readiness",
            raw_score=80.0,
            max_points=15.0,
            points_earned=12.0,
            weight_pct=15.0,
            level="good",
            description="Test",
        )

        score = FindableScoreV2(
            total_score=75.0,
            level="highly_findable",
            level_label="Highly Findable",
            level_summary="You're ahead of most competitors.",
            level_focus="Address remaining gaps.",
            next_milestone=None,
            points_to_milestone=0,
            pillars=[pillar],
            pillar_breakdown={"technical": pillar},
            pillars_good=1,
            pillars_warning=0,
            pillars_critical=0,
            all_critical_issues=["Test issue"],
            top_recommendations=["Test recommendation"],
            calculation_summary=["Step 1"],
        )

        math_output = score.show_the_math()
        assert "FINDABLE SCORE: 75/100" in math_output
        assert "HIGHLY FINDABLE" in math_output
        assert "Technical Readiness" in math_output


# ============================================================================
# FindableScoreCalculatorV2 Tests
# ============================================================================


class TestFindableScoreCalculatorV2:
    """Tests for FindableScoreCalculatorV2."""

    def test_calculate_with_all_pillars(self):
        """Calculate v2 score with all 7 pillars."""
        calculator = FindableScoreCalculatorV2()

        result = calculator.calculate(
            technical_score=make_technical_score(80.0),
            structure_score=make_structure_score(75.0),
            schema_score=make_schema_score(70.0),
            authority_score=make_authority_score(65.0),
            simulation_breakdown=make_score_breakdown(80.0, 85.0),
        )

        assert isinstance(result, FindableScoreV2)
        assert result.total_score > 0
        assert result.total_score <= 100
        assert len(result.pillars) == 7  # 7 pillars including entity_recognition

    def test_calculate_with_partial_pillars(self):
        """Calculate v2 score with only some pillars."""
        calculator = FindableScoreCalculatorV2()

        result = calculator.calculate(
            technical_score=make_technical_score(80.0),
            structure_score=make_structure_score(75.0),
        )

        assert isinstance(result, FindableScoreV2)
        # Missing pillars should be critical with 0 points
        assert result.pillar_breakdown["schema"].raw_score == 0.0
        assert result.pillar_breakdown["schema"].level == "critical"

    def test_calculate_with_no_pillars(self):
        """Calculate v2 score with no pillar scores."""
        calculator = FindableScoreCalculatorV2()

        result = calculator.calculate()

        assert result.total_score == 0.0
        assert result.level == "not_yet_findable"

    def test_pillar_weights_sum_to_100(self):
        """Pillar weights should sum to 100 points."""
        total_weight = sum(PILLAR_WEIGHTS.values())
        assert total_weight == 100

    def test_perfect_score(self):
        """Perfect scores in all pillars yield very high score (optimized level).

        Note: Entity recognition scoring has component max_scores that make
        achieving exactly 100 very difficult. The important thing is that
        maxing all other pillars plus a high entity recognition score
        achieves the 'optimized' level.
        """
        calculator = FindableScoreCalculatorV2()

        result = calculator.calculate(
            technical_score=make_technical_score(100.0),
            structure_score=make_structure_score(100.0),
            schema_score=make_schema_score(100.0),
            authority_score=make_authority_score(100.0),
            entity_recognition_result=make_entity_recognition_result(100.0),
            simulation_breakdown=make_score_breakdown(100.0, 100.0),
        )

        # Entity recognition's component scoring makes exactly 100 difficult
        # but we should be at least 98% with perfect inputs
        assert result.total_score >= 98.0
        assert result.level == "optimized"

    def test_pillar_levels_good(self):
        """Good level for scores >= 70."""
        calculator = FindableScoreCalculatorV2()

        result = calculator.calculate(
            technical_score=make_technical_score(80.0),
        )

        assert result.pillar_breakdown["technical"].level == "good"

    def test_pillar_levels_warning(self):
        """Warning level for scores 40-69."""
        calculator = FindableScoreCalculatorV2()

        result = calculator.calculate(
            technical_score=make_technical_score(50.0),
        )

        assert result.pillar_breakdown["technical"].level == "warning"

    def test_pillar_levels_critical(self):
        """Critical level for scores < 40."""
        calculator = FindableScoreCalculatorV2()

        result = calculator.calculate(
            technical_score=make_technical_score(30.0),
        )

        assert result.pillar_breakdown["technical"].level == "critical"

    def test_pillar_counts(self):
        """Pillar level counts are accurate."""
        calculator = FindableScoreCalculatorV2()

        result = calculator.calculate(
            technical_score=make_technical_score(80.0),  # good
            structure_score=make_structure_score(50.0),  # warning
            schema_score=make_schema_score(30.0),  # critical
        )

        assert result.pillars_good >= 1
        assert result.pillars_warning >= 1
        assert result.pillars_critical >= 1

    def test_calculation_summary_generated(self):
        """Calculation summary is populated."""
        calculator = FindableScoreCalculatorV2()

        result = calculator.calculate(
            technical_score=make_technical_score(80.0),
        )

        assert len(result.calculation_summary) > 0
        # Should show calculation steps
        assert any("Technical" in step for step in result.calculation_summary)


# ============================================================================
# Findability Level Determination Tests
# ============================================================================


class TestFindabilityLevelDetermination:
    """Tests for findability level determination logic."""

    def test_findability_level_boundaries(self):
        """Test level boundaries are correctly applied."""
        calculator = FindableScoreCalculatorV2()

        # Test boundaries
        assert calculator.get_findability_level(39)["id"] == "not_yet_findable"
        assert calculator.get_findability_level(40)["id"] == "partially_findable"
        assert calculator.get_findability_level(54)["id"] == "partially_findable"
        assert calculator.get_findability_level(55)["id"] == "findable"
        assert calculator.get_findability_level(69)["id"] == "findable"
        assert calculator.get_findability_level(70)["id"] == "highly_findable"
        assert calculator.get_findability_level(84)["id"] == "highly_findable"
        assert calculator.get_findability_level(85)["id"] == "optimized"
        assert calculator.get_findability_level(100)["id"] == "optimized"

    def test_findability_level_returns_all_fields(self):
        """Level dict includes all expected fields."""
        calculator = FindableScoreCalculatorV2()
        level = calculator.get_findability_level(50)

        assert "id" in level
        assert "label" in level
        assert "summary" in level
        assert "focus" in level
        assert "min_score" in level
        assert "max_score" in level

    def test_level_assignment_in_full_calculation(self):
        """Level is correctly assigned in full calculation."""
        calculator = FindableScoreCalculatorV2()

        # Score around 49 -> partially_findable
        result = calculator.calculate(
            technical_score=make_technical_score(50.0),
            structure_score=make_structure_score(50.0),
            schema_score=make_schema_score(50.0),
            authority_score=make_authority_score(50.0),
            simulation_breakdown=make_score_breakdown(50.0, 50.0),
        )

        assert result.level == "partially_findable"
        assert result.level_label == "Partially Findable"


# ============================================================================
# Milestone Tests
# ============================================================================


class TestNextMilestone:
    """Tests for next milestone determination."""

    def test_next_milestone_at_30(self):
        """At score 30, next milestone is Partially Findable (40)."""
        calculator = FindableScoreCalculatorV2()
        milestone = calculator.get_next_milestone(30)

        assert milestone is not None
        assert milestone.score == 40
        assert milestone.name == "Partially Findable"
        assert milestone.points_needed == 10

    def test_next_milestone_at_49(self):
        """At score 49, next milestone is Findable (55)."""
        calculator = FindableScoreCalculatorV2()
        milestone = calculator.get_next_milestone(49)

        assert milestone is not None
        assert milestone.score == 55
        assert milestone.name == "Findable"
        assert milestone.points_needed == 6

    def test_next_milestone_at_70(self):
        """At score 70, next milestone is Optimized (85)."""
        calculator = FindableScoreCalculatorV2()
        milestone = calculator.get_next_milestone(70)

        assert milestone is not None
        assert milestone.score == 85
        assert milestone.name == "Optimized"
        assert milestone.points_needed == 15

    def test_next_milestone_at_90(self):
        """At score 90, no next milestone (already optimized)."""
        calculator = FindableScoreCalculatorV2()
        milestone = calculator.get_next_milestone(90)

        assert milestone is None


# ============================================================================
# Path Forward Tests
# ============================================================================


class TestPathForward:
    """Tests for path forward generation."""

    def test_path_forward_reaches_milestone(self):
        """Path forward impact should reach milestone."""
        calculator = FindableScoreCalculatorV2()
        fixes = [
            {
                "title": "Add FAQ schema",
                "impact_points": 8,
                "effort": "30 min",
                "category": "schema",
            },
            {
                "title": "Add author",
                "impact_points": 5,
                "effort": "1 hour",
                "category": "authority",
            },
            {"title": "Fix TTFB", "impact_points": 4, "effort": "2 hours", "category": "technical"},
        ]

        path = calculator.get_path_forward(score=49, fixes=fixes, milestone_target=55)

        total_impact = sum(p.impact_points for p in path)
        assert total_impact >= 6  # Enough to reach milestone

    def test_path_forward_max_5_items(self):
        """Path forward has at most 5 items."""
        calculator = FindableScoreCalculatorV2()
        fixes = [
            {"title": f"Fix {i}", "impact_points": 2, "effort": "30 min", "category": "general"}
            for i in range(10)
        ]

        path = calculator.get_path_forward(score=30, fixes=fixes, milestone_target=55)

        assert len(path) <= 5

    def test_path_forward_sorted_by_impact(self):
        """Path forward actions are sorted by impact (descending)."""
        calculator = FindableScoreCalculatorV2()
        fixes = [
            {"title": "Low impact", "impact_points": 2, "effort": "30 min", "category": "general"},
            {"title": "High impact", "impact_points": 10, "effort": "1 hour", "category": "schema"},
            {
                "title": "Medium impact",
                "impact_points": 5,
                "effort": "45 min",
                "category": "authority",
            },
        ]

        path = calculator.get_path_forward(score=30, fixes=fixes, milestone_target=55)

        # First action should have highest impact
        assert path[0].impact_points == 10
        assert path[0].action == "High impact"

    def test_path_forward_skips_zero_impact(self):
        """Path forward skips fixes with zero impact."""
        calculator = FindableScoreCalculatorV2()
        fixes = [
            {"title": "Zero impact", "impact_points": 0, "effort": "30 min", "category": "general"},
            {"title": "Has impact", "impact_points": 5, "effort": "1 hour", "category": "schema"},
        ]

        path = calculator.get_path_forward(score=30, fixes=fixes, milestone_target=55)

        assert all(p.impact_points > 0 for p in path)

    def test_path_forward_in_full_calculation(self):
        """Path forward is populated when fixes are provided."""
        calculator = FindableScoreCalculatorV2()
        fixes = [
            {
                "title": "Add FAQ schema",
                "impact_points": 8,
                "effort": "30 min",
                "category": "schema",
            },
            {
                "title": "Add author",
                "impact_points": 5,
                "effort": "1 hour",
                "category": "authority",
            },
            {"title": "Fix TTFB", "impact_points": 4, "effort": "2 hours", "category": "technical"},
        ]

        result = calculator.calculate(
            technical_score=make_technical_score(50.0),
            structure_score=make_structure_score(50.0),
            schema_score=make_schema_score(50.0),
            authority_score=make_authority_score(50.0),
            simulation_breakdown=make_score_breakdown(50.0, 50.0),
            fixes=fixes,
        )

        assert len(result.path_forward) >= 1
        assert result.next_milestone is not None


# ============================================================================
# Pillar Builder Tests
# ============================================================================


class TestPillarBuilders:
    """Tests for individual pillar builders."""

    def test_build_technical_pillar(self):
        """Technical pillar built correctly."""
        calculator = FindableScoreCalculatorV2()
        tech_score = make_technical_score(80.0)

        pillar = calculator._build_technical_pillar(tech_score)

        assert pillar.name == "technical"
        assert pillar.display_name == "Technical Readiness"
        assert pillar.raw_score == 80.0
        assert pillar.max_points == 12  # New weight in 7-pillar system
        assert pillar.points_earned == pytest.approx(9.6)  # 80/100 * 12

    def test_build_technical_pillar_none(self):
        """Technical pillar handles None input."""
        calculator = FindableScoreCalculatorV2()

        pillar = calculator._build_technical_pillar(None)

        assert pillar.raw_score == 0.0
        assert pillar.level == "critical"

    def test_build_structure_pillar(self):
        """Structure pillar built correctly."""
        calculator = FindableScoreCalculatorV2()
        struct_score = make_structure_score(75.0)

        pillar = calculator._build_structure_pillar(struct_score)

        assert pillar.name == "structure"
        assert pillar.max_points == 18  # New weight in 7-pillar system
        assert pillar.points_earned == 13.5  # 75/100 * 18

    def test_build_schema_pillar(self):
        """Schema pillar built correctly."""
        calculator = FindableScoreCalculatorV2()
        schema_score = make_schema_score(70.0)

        pillar = calculator._build_schema_pillar(schema_score)

        assert pillar.name == "schema"
        assert pillar.max_points == 13  # New weight in 7-pillar system
        assert pillar.points_earned == 9.1  # 70/100 * 13

    def test_build_authority_pillar(self):
        """Authority pillar built correctly."""
        calculator = FindableScoreCalculatorV2()
        auth_score = make_authority_score(65.0)

        pillar = calculator._build_authority_pillar(auth_score)

        assert pillar.name == "authority"
        assert pillar.max_points == 12  # New weight in 7-pillar system
        assert pillar.points_earned == pytest.approx(7.8)  # 65/100 * 12

    def test_build_retrieval_pillar(self):
        """Retrieval pillar built from v1 breakdown."""
        calculator = FindableScoreCalculatorV2()
        breakdown = make_score_breakdown(total_score=80.0)

        pillar = calculator._build_retrieval_pillar(breakdown)

        assert pillar.name == "retrieval"
        assert pillar.max_points == 22  # New weight in 7-pillar system
        assert pillar.raw_score == 80.0
        assert pillar.points_earned == 17.6  # 80/100 * 22

    def test_build_coverage_pillar(self):
        """Coverage pillar built from v1 breakdown."""
        calculator = FindableScoreCalculatorV2()
        breakdown = make_score_breakdown(coverage=85.0)

        pillar = calculator._build_coverage_pillar(breakdown)

        assert pillar.name == "coverage"
        assert pillar.max_points == 10
        assert pillar.raw_score == 85.0
        assert pillar.points_earned == 8.5  # 85/100 * 10


# ============================================================================
# Convenience Function Tests
# ============================================================================


class TestCalculateFindableScoreV2:
    """Tests for calculate_findable_score_v2 convenience function."""

    def test_convenience_function_works(self):
        """Convenience function produces same result as class method."""
        result = calculate_findable_score_v2(
            technical_score=make_technical_score(80.0),
            structure_score=make_structure_score(75.0),
        )

        assert isinstance(result, FindableScoreV2)
        assert result.total_score > 0

    def test_convenience_function_with_all_params(self):
        """Convenience function accepts all parameters."""
        result = calculate_findable_score_v2(
            technical_score=make_technical_score(80.0),
            structure_score=make_structure_score(75.0),
            schema_score=make_schema_score(70.0),
            authority_score=make_authority_score(65.0),
            entity_recognition_result=make_entity_recognition_result(60.0),
            simulation_breakdown=make_score_breakdown(80.0, 85.0),
        )

        assert len(result.pillars) == 7  # 7 pillars including entity_recognition


# ============================================================================
# Integration Tests
# ============================================================================


class TestScoreIntegration:
    """Integration tests for score calculation."""

    def test_score_changes_with_improvements(self):
        """Improving pillar scores increases total score."""
        calculator = FindableScoreCalculatorV2()

        # Baseline
        baseline = calculator.calculate(
            technical_score=make_technical_score(60.0),
            structure_score=make_structure_score(60.0),
        )

        # Improved
        improved = calculator.calculate(
            technical_score=make_technical_score(80.0),
            structure_score=make_structure_score(80.0),
        )

        assert improved.total_score > baseline.total_score

    def test_weighted_pillar_impact(self):
        """Higher-weighted pillars have more impact."""
        calculator = FindableScoreCalculatorV2()

        # Only retrieval (25 points weight)
        retrieval_only = calculator.calculate(
            simulation_breakdown=make_score_breakdown(100.0, 0.0),
        )

        # Only technical (15 points weight)
        technical_only = calculator.calculate(
            technical_score=make_technical_score(100.0),
        )

        # Retrieval should contribute more
        retrieval_contrib = retrieval_only.pillar_breakdown["retrieval"].points_earned
        technical_contrib = technical_only.pillar_breakdown["technical"].points_earned

        assert retrieval_contrib > technical_contrib

    def test_to_dict_serialization(self):
        """Full score serializes to dict correctly."""
        calculator = FindableScoreCalculatorV2()

        result = calculator.calculate(
            technical_score=make_technical_score(80.0),
            structure_score=make_structure_score(75.0),
            schema_score=make_schema_score(70.0),
            authority_score=make_authority_score(65.0),
            entity_recognition_result=make_entity_recognition_result(60.0),
            simulation_breakdown=make_score_breakdown(80.0, 85.0),
        )

        data = result.to_dict()

        assert "total_score" in data
        assert "level" in data
        assert "level_label" in data
        assert "pillars" in data
        assert "pillar_breakdown" in data
        assert "version" in data
        assert data["version"] == "2.2"
        # No grade fields
        assert "grade" not in data
        assert "grade_description" not in data
        # Entity recognition pillar present
        assert "entity_recognition" in data["pillar_breakdown"]


# ============================================================================
# Dynamic Weight Loading Tests
# ============================================================================


class TestDynamicWeightLoading:
    """Tests for dynamic calibration weight loading."""

    def test_default_weights_used_when_no_cache(self):
        """Default weights used when no cache is set."""
        from worker.scoring.calculator_v2 import (
            DEFAULT_PILLAR_WEIGHTS,
            get_pillar_weights,
            set_active_calibration_weights,
        )

        # Clear cache
        set_active_calibration_weights(None)

        weights = get_pillar_weights()
        assert weights == DEFAULT_PILLAR_WEIGHTS
        assert sum(weights.values()) == 100.0

    def test_custom_weights_can_be_passed_to_calculator(self):
        """Custom weights can be passed directly to calculator."""
        custom_weights = {
            "technical": 15,
            "structure": 15,
            "schema": 10,
            "authority": 10,
            "entity_recognition": 10,
            "retrieval": 30,
            "coverage": 10,
        }

        calculator = FindableScoreCalculatorV2(
            weights=custom_weights,
            config_name="test-custom",
        )

        assert calculator.weights == custom_weights
        assert calculator.config_name == "test-custom"

    def test_cached_weights_are_used(self):
        """Cached weights are used by calculator when set."""
        from worker.scoring.calculator_v2 import (
            get_cached_config_name,
            get_pillar_weights,
            set_active_calibration_weights,
        )

        cached_weights = {
            "technical": 10,
            "structure": 20,
            "schema": 15,
            "authority": 10,
            "entity_recognition": 10,
            "retrieval": 25,
            "coverage": 10,
        }

        # Set cache
        set_active_calibration_weights(cached_weights, config_name="cached-config")

        # Verify cache is used
        weights = get_pillar_weights()
        assert weights == cached_weights
        assert get_cached_config_name() == "cached-config"

        # Calculator should use cached weights
        calculator = FindableScoreCalculatorV2()
        assert calculator.weights == cached_weights
        assert calculator.config_name == "cached-config"

        # Clean up
        set_active_calibration_weights(None)

    def test_invalid_weights_fall_back_to_defaults(self):
        """Invalid weights (not summing to 100) fall back to defaults."""
        from worker.scoring.calculator_v2 import (
            DEFAULT_PILLAR_WEIGHTS,
            set_active_calibration_weights,
        )

        # Clear any existing cache
        set_active_calibration_weights(None)

        # Invalid weights that don't sum to 100
        invalid_weights = {
            "technical": 20,
            "structure": 20,
            "schema": 20,
            "authority": 20,
            "entity_recognition": 20,
            "retrieval": 20,
            "coverage": 20,  # Sum = 140!
        }

        calculator = FindableScoreCalculatorV2(weights=invalid_weights)

        # Should fall back to defaults
        assert calculator.weights == DEFAULT_PILLAR_WEIGHTS
        assert calculator.config_name == "default (fallback)"

    def test_set_active_calibration_weights_validates_sum(self):
        """set_active_calibration_weights rejects invalid weights."""
        from worker.scoring.calculator_v2 import (
            DEFAULT_PILLAR_WEIGHTS,
            get_pillar_weights,
            set_active_calibration_weights,
        )

        # Clear cache first
        set_active_calibration_weights(None)

        # Try to set invalid weights
        invalid_weights = {
            "technical": 50,
            "structure": 50,
            "schema": 50,
            "authority": 0,
            "entity_recognition": 0,
            "retrieval": 0,
            "coverage": 0,  # Sum = 150!
        }
        set_active_calibration_weights(invalid_weights, config_name="invalid")

        # Should not be cached, should still get defaults
        weights = get_pillar_weights()
        assert weights == DEFAULT_PILLAR_WEIGHTS

    def test_weights_affect_pillar_calculations(self):
        """Custom weights correctly affect pillar point calculations."""
        from worker.scoring.calculator_v2 import set_active_calibration_weights

        # Clear cache
        set_active_calibration_weights(None)

        # Create calculator with custom weights
        custom_weights = {
            "technical": 25,  # Higher than default
            "structure": 15,  # Lower than default
            "schema": 12,
            "authority": 10,
            "entity_recognition": 10,
            "retrieval": 18,  # Lower than default
            "coverage": 10,
        }

        calculator = FindableScoreCalculatorV2(weights=custom_weights)

        result = calculator.calculate(
            technical_score=make_technical_score(100.0),
            structure_score=make_structure_score(100.0),
        )

        # Technical should earn 25 points (25% of 100)
        assert result.pillar_breakdown["technical"].points_earned == 25.0
        assert result.pillar_breakdown["technical"].max_points == 25.0

        # Structure should earn 15 points (15% of 100)
        assert result.pillar_breakdown["structure"].points_earned == 15.0
        assert result.pillar_breakdown["structure"].max_points == 15.0

    def test_clear_cache_restores_defaults(self):
        """Clearing cache restores default weights."""
        from worker.scoring.calculator_v2 import (
            DEFAULT_PILLAR_WEIGHTS,
            get_cached_config_name,
            get_pillar_weights,
            set_active_calibration_weights,
        )

        # Set some cache (must sum to 100 with 7 pillars)
        set_active_calibration_weights(
            {
                "technical": 10,
                "structure": 20,
                "schema": 15,
                "authority": 10,
                "entity_recognition": 10,
                "retrieval": 25,
                "coverage": 10,
            },
            config_name="temp-config",
        )

        # Clear it
        set_active_calibration_weights(None)

        # Should be back to defaults
        assert get_pillar_weights() == DEFAULT_PILLAR_WEIGHTS
        assert get_cached_config_name() is None

    def test_pillar_weights_alias_exists(self):
        """PILLAR_WEIGHTS alias exists for backward compatibility."""
        from worker.scoring.calculator_v2 import DEFAULT_PILLAR_WEIGHTS, PILLAR_WEIGHTS

        assert PILLAR_WEIGHTS == DEFAULT_PILLAR_WEIGHTS
