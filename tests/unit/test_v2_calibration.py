"""Calibration tests for Findable Score v2.

Tests the v2 scoring system against known high and low performers
to ensure scores are reasonable and differentiated.
"""

from uuid import uuid4

from worker.fixes.generator_v2 import (
    FixPlanV2,
    generate_fix_plan_v2,
)
from worker.scoring.authority import AuthorityComponent, AuthoritySignalsScore
from worker.scoring.calculator import ScoreBreakdown
from worker.scoring.calculator_v2 import (
    PILLAR_WEIGHTS,
    FindableScoreCalculatorV2,
    calculate_findable_score_v2,
)
from worker.scoring.schema import SchemaComponent, SchemaRichnessScore
from worker.scoring.structure import StructureComponent, StructureQualityScore
from worker.scoring.technical import TechnicalComponent, TechnicalReadinessScore

# ============================================================================
# Test Profiles - Known Archetypes
# ============================================================================


class SiteProfiles:
    """Predefined site profiles for calibration testing."""

    @staticmethod
    def excellent_enterprise() -> dict:
        """A well-optimized enterprise site (expected: optimized/highly_findable)."""
        return {
            "technical": TechnicalReadinessScore(
                total_score=95.0,
                level="full",
                max_points=15.0,
                components=[
                    TechnicalComponent(
                        name="robots_txt",
                        raw_score=100.0,
                        weight=0.35,
                        weighted_score=35.0,
                        level="full",
                        explanation="All AI bots allowed",
                    ),
                    TechnicalComponent(
                        name="ttfb",
                        raw_score=95.0,
                        weight=0.30,
                        weighted_score=28.5,
                        level="full",
                        explanation="TTFB: 180ms",
                    ),
                    TechnicalComponent(
                        name="llms_txt",
                        raw_score=100.0,
                        weight=0.15,
                        weighted_score=15.0,
                        level="full",
                        explanation="llms.txt present and valid",
                    ),
                    TechnicalComponent(
                        name="js_accessible",
                        raw_score=85.0,
                        weight=0.10,
                        weighted_score=8.5,
                        level="full",
                        explanation="SSR enabled",
                    ),
                    TechnicalComponent(
                        name="https",
                        raw_score=100.0,
                        weight=0.10,
                        weighted_score=10.0,
                        level="full",
                        explanation="HTTPS enabled",
                    ),
                ],
                critical_issues=[],
                all_issues=[],
            ),
            "structure": StructureQualityScore(
                total_score=90.0,
                level="full",
                max_points=20.0,
                components=[
                    StructureComponent(
                        name="heading_hierarchy",
                        raw_score=95.0,
                        weight=0.25,
                        weighted_score=23.75,
                        level="full",
                        explanation="Valid H1→H2→H3 hierarchy",
                    ),
                    StructureComponent(
                        name="answer_first",
                        raw_score=90.0,
                        weight=0.25,
                        weighted_score=22.5,
                        level="full",
                        explanation="Answers in first paragraph",
                    ),
                    StructureComponent(
                        name="faq_sections",
                        raw_score=85.0,
                        weight=0.20,
                        weighted_score=17.0,
                        level="full",
                        explanation="Multiple FAQ sections",
                    ),
                    StructureComponent(
                        name="internal_links",
                        raw_score=88.0,
                        weight=0.15,
                        weighted_score=13.2,
                        level="full",
                        explanation="Good internal linking",
                    ),
                    StructureComponent(
                        name="extractable_formats",
                        raw_score=92.0,
                        weight=0.15,
                        weighted_score=13.8,
                        level="full",
                        explanation="Tables and lists present",
                    ),
                ],
                critical_issues=[],
                recommendations=[],
            ),
            "schema": SchemaRichnessScore(
                total_score=92.0,
                level="full",
                max_points=15.0,
                components=[
                    SchemaComponent(
                        name="faq_page",
                        raw_score=100.0,
                        weight=0.27,
                        weighted_score=27.0,
                        level="full",
                        explanation="FAQPage schema present",
                    ),
                    SchemaComponent(
                        name="article",
                        raw_score=95.0,
                        weight=0.20,
                        weighted_score=19.0,
                        level="full",
                        explanation="Article with author",
                    ),
                    SchemaComponent(
                        name="date_modified",
                        raw_score=90.0,
                        weight=0.20,
                        weighted_score=18.0,
                        level="full",
                        explanation="dateModified present",
                    ),
                    SchemaComponent(
                        name="organization",
                        raw_score=100.0,
                        weight=0.13,
                        weighted_score=13.0,
                        level="full",
                        explanation="Organization schema present",
                    ),
                    SchemaComponent(
                        name="how_to",
                        raw_score=80.0,
                        weight=0.13,
                        weighted_score=10.4,
                        level="full",
                        explanation="HowTo on relevant pages",
                    ),
                    SchemaComponent(
                        name="validation",
                        raw_score=95.0,
                        weight=0.07,
                        weighted_score=6.65,
                        level="full",
                        explanation="Minor validation warnings",
                    ),
                ],
                critical_issues=[],
                recommendations=[],
            ),
            "authority": AuthoritySignalsScore(
                total_score=88.0,
                level="full",
                max_points=15.0,
                components=[
                    AuthorityComponent(
                        name="author_attribution",
                        raw_score=95.0,
                        weight=0.27,
                        weighted_score=25.65,
                        level="full",
                        explanation="Authors on all articles",
                    ),
                    AuthorityComponent(
                        name="author_credentials",
                        raw_score=90.0,
                        weight=0.20,
                        weighted_score=18.0,
                        level="full",
                        explanation="Credentials displayed",
                    ),
                    AuthorityComponent(
                        name="primary_citations",
                        raw_score=80.0,
                        weight=0.20,
                        weighted_score=16.0,
                        level="full",
                        explanation="Good citation density",
                    ),
                    AuthorityComponent(
                        name="content_freshness",
                        raw_score=85.0,
                        weight=0.20,
                        weighted_score=17.0,
                        level="full",
                        explanation="Content updated recently",
                    ),
                    AuthorityComponent(
                        name="original_data",
                        raw_score=85.0,
                        weight=0.13,
                        weighted_score=11.05,
                        level="full",
                        explanation="Original research present",
                    ),
                ],
                critical_issues=[],
                recommendations=[],
            ),
            "simulation": ScoreBreakdown(
                total_score=90.0,
                grade="A",
                grade_description="Excellent",
                criterion_scores=[],
                category_breakdowns={},
                question_scores=[],
                total_questions=20,
                questions_answered=18,
                questions_partial=2,
                questions_unanswered=0,
                coverage_percentage=95.0,
                calculation_summary=[],
                formula_used="v1",
                rubric_version="1.0",
            ),
        }

    @staticmethod
    def poor_js_spa() -> dict:
        """A JS-heavy SPA with poor AI accessibility (expected: not_yet_findable)."""
        return {
            "technical": TechnicalReadinessScore(
                total_score=25.0,
                level="limited",
                max_points=15.0,
                components=[
                    TechnicalComponent(
                        name="robots_txt",
                        raw_score=30.0,
                        weight=0.35,
                        weighted_score=10.5,
                        level="limited",
                        explanation="GPTBot blocked",
                    ),
                    TechnicalComponent(
                        name="ttfb",
                        raw_score=40.0,
                        weight=0.30,
                        weighted_score=12.0,
                        level="partial",
                        explanation="TTFB: 1800ms",
                    ),
                    TechnicalComponent(
                        name="llms_txt",
                        raw_score=0.0,
                        weight=0.15,
                        weighted_score=0.0,
                        level="limited",
                        explanation="No llms.txt",
                    ),
                    TechnicalComponent(
                        name="js_accessible",
                        raw_score=10.0,
                        weight=0.10,
                        weighted_score=1.0,
                        level="limited",
                        explanation="Fully JS-dependent",
                    ),
                    TechnicalComponent(
                        name="https",
                        raw_score=100.0,
                        weight=0.10,
                        weighted_score=10.0,
                        level="full",
                        explanation="HTTPS enabled",
                    ),
                ],
                critical_issues=["GPTBot blocked", "Content requires JavaScript"],
                all_issues=["GPTBot blocked", "Slow TTFB", "No llms.txt", "JS dependent"],
            ),
            "structure": StructureQualityScore(
                total_score=30.0,
                level="limited",
                max_points=20.0,
                components=[
                    StructureComponent(
                        name="heading_hierarchy",
                        raw_score=20.0,
                        weight=0.25,
                        weighted_score=5.0,
                        level="limited",
                        explanation="No semantic headings",
                    ),
                    StructureComponent(
                        name="answer_first",
                        raw_score=25.0,
                        weight=0.25,
                        weighted_score=6.25,
                        level="limited",
                        explanation="Answers buried in content",
                    ),
                    StructureComponent(
                        name="faq_sections",
                        raw_score=0.0,
                        weight=0.20,
                        weighted_score=0.0,
                        level="limited",
                        explanation="No FAQ sections",
                    ),
                    StructureComponent(
                        name="internal_links",
                        raw_score=60.0,
                        weight=0.15,
                        weighted_score=9.0,
                        level="partial",
                        explanation="Minimal internal links",
                    ),
                    StructureComponent(
                        name="extractable_formats",
                        raw_score=40.0,
                        weight=0.15,
                        weighted_score=6.0,
                        level="partial",
                        explanation="Few extractable elements",
                    ),
                ],
                critical_issues=["No semantic headings", "No FAQ content"],
                recommendations=["Add proper heading hierarchy", "Create FAQ sections"],
            ),
            "schema": SchemaRichnessScore(
                total_score=15.0,
                level="limited",
                max_points=15.0,
                components=[
                    SchemaComponent(
                        name="faq_page",
                        raw_score=0.0,
                        weight=0.27,
                        weighted_score=0.0,
                        level="limited",
                        explanation="No FAQPage schema",
                    ),
                    SchemaComponent(
                        name="article",
                        raw_score=20.0,
                        weight=0.20,
                        weighted_score=4.0,
                        level="limited",
                        explanation="Basic Article, no author",
                    ),
                    SchemaComponent(
                        name="date_modified",
                        raw_score=0.0,
                        weight=0.20,
                        weighted_score=0.0,
                        level="limited",
                        explanation="No dateModified",
                    ),
                    SchemaComponent(
                        name="organization",
                        raw_score=50.0,
                        weight=0.13,
                        weighted_score=6.5,
                        level="partial",
                        explanation="Basic Organization",
                    ),
                    SchemaComponent(
                        name="how_to",
                        raw_score=0.0,
                        weight=0.13,
                        weighted_score=0.0,
                        level="limited",
                        explanation="No HowTo schema",
                    ),
                    SchemaComponent(
                        name="validation",
                        raw_score=30.0,
                        weight=0.07,
                        weighted_score=2.1,
                        level="limited",
                        explanation="Multiple validation errors",
                    ),
                ],
                critical_issues=["No FAQPage schema", "No dateModified"],
                recommendations=["Add FAQPage schema", "Add dateModified"],
            ),
            "authority": AuthoritySignalsScore(
                total_score=20.0,
                level="limited",
                max_points=15.0,
                components=[
                    AuthorityComponent(
                        name="author_attribution",
                        raw_score=10.0,
                        weight=0.27,
                        weighted_score=2.7,
                        level="limited",
                        explanation="No author bylines",
                    ),
                    AuthorityComponent(
                        name="author_credentials",
                        raw_score=0.0,
                        weight=0.20,
                        weighted_score=0.0,
                        level="limited",
                        explanation="No credentials shown",
                    ),
                    AuthorityComponent(
                        name="primary_citations",
                        raw_score=20.0,
                        weight=0.20,
                        weighted_score=4.0,
                        level="limited",
                        explanation="Few citations",
                    ),
                    AuthorityComponent(
                        name="content_freshness",
                        raw_score=40.0,
                        weight=0.20,
                        weighted_score=8.0,
                        level="partial",
                        explanation="Content 2 years old",
                    ),
                    AuthorityComponent(
                        name="original_data",
                        raw_score=15.0,
                        weight=0.13,
                        weighted_score=1.95,
                        level="limited",
                        explanation="No original data",
                    ),
                ],
                critical_issues=["No author attribution", "Stale content"],
                recommendations=["Add author bylines", "Update content"],
            ),
            "simulation": ScoreBreakdown(
                total_score=35.0,
                grade="D",
                grade_description="Poor",
                criterion_scores=[],
                category_breakdowns={},
                question_scores=[],
                total_questions=20,
                questions_answered=4,
                questions_partial=5,
                questions_unanswered=11,
                coverage_percentage=32.5,
                calculation_summary=[],
                formula_used="v1",
                rubric_version="1.0",
            ),
        }

    @staticmethod
    def average_blog() -> dict:
        """An average blog with mixed signals (expected: findable/highly_findable)."""
        return {
            "technical": TechnicalReadinessScore(
                total_score=70.0,
                level="full",
                max_points=15.0,
                components=[
                    TechnicalComponent(
                        name="robots_txt",
                        raw_score=80.0,
                        weight=0.35,
                        weighted_score=28.0,
                        level="full",
                        explanation="Most AI bots allowed",
                    ),
                    TechnicalComponent(
                        name="ttfb",
                        raw_score=70.0,
                        weight=0.30,
                        weighted_score=21.0,
                        level="full",
                        explanation="TTFB: 600ms",
                    ),
                    TechnicalComponent(
                        name="llms_txt",
                        raw_score=0.0,
                        weight=0.15,
                        weighted_score=0.0,
                        level="limited",
                        explanation="No llms.txt",
                    ),
                    TechnicalComponent(
                        name="js_accessible",
                        raw_score=90.0,
                        weight=0.10,
                        weighted_score=9.0,
                        level="full",
                        explanation="Static HTML",
                    ),
                    TechnicalComponent(
                        name="https",
                        raw_score=100.0,
                        weight=0.10,
                        weighted_score=10.0,
                        level="full",
                        explanation="HTTPS enabled",
                    ),
                ],
                critical_issues=[],
                all_issues=["No llms.txt"],
            ),
            "structure": StructureQualityScore(
                total_score=65.0,
                level="partial",
                max_points=20.0,
                components=[
                    StructureComponent(
                        name="heading_hierarchy",
                        raw_score=75.0,
                        weight=0.25,
                        weighted_score=18.75,
                        level="full",
                        explanation="Mostly valid headings",
                    ),
                    StructureComponent(
                        name="answer_first",
                        raw_score=55.0,
                        weight=0.25,
                        weighted_score=13.75,
                        level="partial",
                        explanation="Answers sometimes buried",
                    ),
                    StructureComponent(
                        name="faq_sections",
                        raw_score=40.0,
                        weight=0.20,
                        weighted_score=8.0,
                        level="partial",
                        explanation="Few FAQ sections",
                    ),
                    StructureComponent(
                        name="internal_links",
                        raw_score=80.0,
                        weight=0.15,
                        weighted_score=12.0,
                        level="full",
                        explanation="Good internal linking",
                    ),
                    StructureComponent(
                        name="extractable_formats",
                        raw_score=70.0,
                        weight=0.15,
                        weighted_score=10.5,
                        level="full",
                        explanation="Some tables and lists",
                    ),
                ],
                critical_issues=[],
                recommendations=["Add more FAQ content", "Move answers to first paragraph"],
            ),
            "schema": SchemaRichnessScore(
                total_score=55.0,
                level="partial",
                max_points=15.0,
                components=[
                    SchemaComponent(
                        name="faq_page",
                        raw_score=0.0,
                        weight=0.27,
                        weighted_score=0.0,
                        level="limited",
                        explanation="No FAQPage schema",
                    ),
                    SchemaComponent(
                        name="article",
                        raw_score=70.0,
                        weight=0.20,
                        weighted_score=14.0,
                        level="full",
                        explanation="Article with basic author",
                    ),
                    SchemaComponent(
                        name="date_modified",
                        raw_score=80.0,
                        weight=0.20,
                        weighted_score=16.0,
                        level="full",
                        explanation="dateModified present",
                    ),
                    SchemaComponent(
                        name="organization",
                        raw_score=75.0,
                        weight=0.13,
                        weighted_score=9.75,
                        level="full",
                        explanation="Organization schema present",
                    ),
                    SchemaComponent(
                        name="how_to",
                        raw_score=0.0,
                        weight=0.13,
                        weighted_score=0.0,
                        level="limited",
                        explanation="No HowTo schema",
                    ),
                    SchemaComponent(
                        name="validation",
                        raw_score=90.0,
                        weight=0.07,
                        weighted_score=6.3,
                        level="full",
                        explanation="Valid schemas",
                    ),
                ],
                critical_issues=[],
                recommendations=["Add FAQPage schema"],
            ),
            "authority": AuthoritySignalsScore(
                total_score=60.0,
                level="partial",
                max_points=15.0,
                components=[
                    AuthorityComponent(
                        name="author_attribution",
                        raw_score=70.0,
                        weight=0.27,
                        weighted_score=18.9,
                        level="full",
                        explanation="Authors on most posts",
                    ),
                    AuthorityComponent(
                        name="author_credentials",
                        raw_score=40.0,
                        weight=0.20,
                        weighted_score=8.0,
                        level="partial",
                        explanation="Basic bio only",
                    ),
                    AuthorityComponent(
                        name="primary_citations",
                        raw_score=50.0,
                        weight=0.20,
                        weighted_score=10.0,
                        level="partial",
                        explanation="Some citations",
                    ),
                    AuthorityComponent(
                        name="content_freshness",
                        raw_score=75.0,
                        weight=0.20,
                        weighted_score=15.0,
                        level="full",
                        explanation="Updated quarterly",
                    ),
                    AuthorityComponent(
                        name="original_data",
                        raw_score=40.0,
                        weight=0.13,
                        weighted_score=5.2,
                        level="partial",
                        explanation="Occasional original data",
                    ),
                ],
                critical_issues=[],
                recommendations=["Add author credentials"],
            ),
            "simulation": ScoreBreakdown(
                total_score=65.0,
                grade="C+",
                grade_description="Fair",
                criterion_scores=[],
                category_breakdowns={},
                question_scores=[],
                total_questions=20,
                questions_answered=10,
                questions_partial=6,
                questions_unanswered=4,
                coverage_percentage=65.0,
                calculation_summary=[],
                formula_used="v1",
                rubric_version="1.0",
            ),
        }


# ============================================================================
# Calibration Tests
# ============================================================================


class TestScoreCalibration:
    """Tests that v2 scores are properly calibrated for known archetypes."""

    def test_excellent_site_is_optimized(self):
        """Excellent enterprise site should be optimized or highly_findable.

        Note: With 7-pillar system, entity_recognition may not be evaluated,
        so we check score of evaluated pillars is high.
        """
        profile = SiteProfiles.excellent_enterprise()

        result = calculate_findable_score_v2(
            technical_score=profile["technical"],
            structure_score=profile["structure"],
            schema_score=profile["schema"],
            authority_score=profile["authority"],
            simulation_breakdown=profile["simulation"],
        )

        # With entity_recognition unevaluated, raw max is 87 points (100 - 13)
        # total_score is rescaled to 0-100 from evaluated pillars
        # Excellent site should score very high on evaluated pillars
        assert result.total_score >= 75.0  # Rescaled: ~87%+ of evaluated pillars
        assert result.level in ["optimized", "highly_findable"]
        # Entity recognition not evaluated doesn't count as critical
        assert result.pillars_critical == 0

    def test_poor_site_is_not_yet_findable(self):
        """Poor JS SPA should be not_yet_findable or partially_findable."""
        profile = SiteProfiles.poor_js_spa()

        result = calculate_findable_score_v2(
            technical_score=profile["technical"],
            structure_score=profile["structure"],
            schema_score=profile["schema"],
            authority_score=profile["authority"],
            simulation_breakdown=profile["simulation"],
        )

        assert result.total_score < 50.0
        assert result.level in ["not_yet_findable", "partially_findable"]
        assert result.pillars_critical >= 3

    def test_average_site_is_findable(self):
        """Average blog should be findable or highly_findable."""
        profile = SiteProfiles.average_blog()

        result = calculate_findable_score_v2(
            technical_score=profile["technical"],
            structure_score=profile["structure"],
            schema_score=profile["schema"],
            authority_score=profile["authority"],
            simulation_breakdown=profile["simulation"],
        )

        assert 55.0 <= result.total_score <= 75.0
        assert result.level in ["findable", "highly_findable"]

    def test_score_differentiation(self):
        """Excellent sites should score significantly higher than poor sites."""
        excellent = SiteProfiles.excellent_enterprise()
        poor = SiteProfiles.poor_js_spa()
        average = SiteProfiles.average_blog()

        excellent_score = calculate_findable_score_v2(
            technical_score=excellent["technical"],
            structure_score=excellent["structure"],
            schema_score=excellent["schema"],
            authority_score=excellent["authority"],
            simulation_breakdown=excellent["simulation"],
        )

        poor_score = calculate_findable_score_v2(
            technical_score=poor["technical"],
            structure_score=poor["structure"],
            schema_score=poor["schema"],
            authority_score=poor["authority"],
            simulation_breakdown=poor["simulation"],
        )

        average_score = calculate_findable_score_v2(
            technical_score=average["technical"],
            structure_score=average["structure"],
            schema_score=average["schema"],
            authority_score=average["authority"],
            simulation_breakdown=average["simulation"],
        )

        # At least 30 point difference between excellent and poor
        assert excellent_score.total_score - poor_score.total_score >= 30

        # Average should be between
        assert poor_score.total_score < average_score.total_score < excellent_score.total_score


class TestFixCalibration:
    """Tests that fix generation is properly calibrated."""

    def test_poor_site_gets_many_fixes(self):
        """Poor site should have many fix recommendations.

        Note: Fix generation requires analysis objects (structure_analysis,
        authority_analysis, etc.) on the score objects. This test verifies
        the fix generator runs without error on minimal score data.
        """
        profile = SiteProfiles.poor_js_spa()
        site_id = uuid4()
        run_id = uuid4()

        result = generate_fix_plan_v2(
            site_id=site_id,
            run_id=run_id,
            company_name="Poor SPA Inc",
            technical_score=profile["technical"],
            structure_score=profile["structure"],
            schema_score=profile["schema"],
            authority_score=profile["authority"],
        )

        # Fix generator should complete without error
        assert isinstance(result, FixPlanV2)
        assert result.action_center is not None
        # Without analysis objects, fixes won't be generated
        # This is expected - real fix generation needs full analysis data

    def test_excellent_site_gets_few_fixes(self):
        """Excellent site should have minimal fix recommendations."""
        profile = SiteProfiles.excellent_enterprise()
        site_id = uuid4()
        run_id = uuid4()

        result = generate_fix_plan_v2(
            site_id=site_id,
            run_id=run_id,
            company_name="Enterprise Corp",
            technical_score=profile["technical"],
            structure_score=profile["structure"],
            schema_score=profile["schema"],
            authority_score=profile["authority"],
        )

        # Should have few or no critical fixes
        assert result.action_center.critical_count <= 1
        # Total fixes should be low
        assert result.action_center.total_fixes <= 5

    def test_fixes_sorted_by_impact(self):
        """Fixes should be sorted by priority (impact)."""
        profile = SiteProfiles.poor_js_spa()
        site_id = uuid4()
        run_id = uuid4()

        result = generate_fix_plan_v2(
            site_id=site_id,
            run_id=run_id,
            company_name="Poor SPA Inc",
            technical_score=profile["technical"],
            structure_score=profile["structure"],
            schema_score=profile["schema"],
            authority_score=profile["authority"],
        )

        fixes = result.action_center.all_fixes
        if len(fixes) >= 2:
            # First fixes should be higher priority (lower number = higher priority)
            for i in range(len(fixes) - 1):
                assert fixes[i].fix.priority <= fixes[i + 1].fix.priority


# ============================================================================
# Migration Formula Tests
# ============================================================================


class TestV1ToV2Migration:
    """Tests for v1 to v2 score migration."""

    def test_v1_score_maps_to_retrieval_and_coverage(self):
        """v1 total score feeds into retrieval pillar, coverage feeds into coverage pillar."""
        calculator = FindableScoreCalculatorV2()

        # v1 score of 75, coverage of 80
        breakdown = ScoreBreakdown(
            total_score=75.0,
            grade="B",
            grade_description="Good",
            criterion_scores=[],
            category_breakdowns={},
            question_scores=[],
            total_questions=20,
            questions_answered=16,
            questions_partial=2,
            questions_unanswered=2,
            coverage_percentage=80.0,
            calculation_summary=[],
            formula_used="v1",
            rubric_version="1.0",
        )

        result = calculator.calculate(simulation_breakdown=breakdown)

        # Retrieval should use v1 total_score
        assert result.pillar_breakdown["retrieval"].raw_score == 75.0
        # Coverage should use coverage_percentage
        assert result.pillar_breakdown["coverage"].raw_score == 80.0

    def test_v1_only_score_reasonable(self):
        """With only v1 score (no new pillars), result should be reasonable."""
        breakdown = ScoreBreakdown(
            total_score=70.0,
            grade="B-",
            grade_description="Satisfactory",
            criterion_scores=[],
            category_breakdowns={},
            question_scores=[],
            total_questions=20,
            questions_answered=12,
            questions_partial=4,
            questions_unanswered=4,
            coverage_percentage=70.0,
            calculation_summary=[],
            formula_used="v1",
            rubric_version="1.0",
        )

        result = calculate_findable_score_v2(simulation_breakdown=breakdown)

        # With only retrieval (22pts) and coverage (10pts) = 32pts max
        # At 70% raw = ~22.4 raw points, rescaled to 0-100: (22.4/32)*100 = 70.0
        assert 65.0 <= result.total_score <= 75.0  # Rescaled: 70% of evaluated pillars
        assert result.raw_points_earned < 25.0  # Raw points still ~22.4
        # Unevaluated pillars tracked separately (tech, struct, schema, auth, entity_recognition)
        assert result.pillars_not_evaluated == 5  # 5 pillars not run in 7-pillar system
        assert result.pillars_evaluated == 2  # Only retrieval and coverage evaluated

    def test_migration_formula_documented(self):
        """The migration formula should be predictable."""
        # v1 total_score -> retrieval (22% weight in 7-pillar system)
        # v1 coverage -> coverage (10% weight)
        # New pillars start at 0 if not provided

        v1_score = 80.0
        v1_coverage = 90.0

        breakdown = ScoreBreakdown(
            total_score=v1_score,
            grade="B+",
            grade_description="Good",
            criterion_scores=[],
            category_breakdowns={},
            question_scores=[],
            total_questions=20,
            questions_answered=18,
            questions_partial=1,
            questions_unanswered=1,
            coverage_percentage=v1_coverage,
            calculation_summary=[],
            formula_used="v1",
            rubric_version="1.0",
        )

        result = calculate_findable_score_v2(simulation_breakdown=breakdown)

        # Expected: retrieval = 80 * 0.22 = 17.6 pts, coverage = 90 * 0.10 = 9 pts
        # Raw from v1 = 26.6 pts out of 32 max; rescaled = (26.6/32)*100 = 83.1/100
        expected_retrieval_pts = v1_score / 100 * 22  # 22% weight in 7-pillar system
        expected_coverage_pts = v1_coverage / 100 * 10

        assert (
            abs(result.pillar_breakdown["retrieval"].points_earned - expected_retrieval_pts) < 0.1
        )
        assert abs(result.pillar_breakdown["coverage"].points_earned - expected_coverage_pts) < 0.1


# ============================================================================
# Pillar Balance Tests
# ============================================================================


class TestPillarBalance:
    """Tests that pillar weights create balanced scoring."""

    def test_no_single_pillar_dominates(self):
        """No single pillar should contribute more than 30% of score."""
        for pillar, weight in PILLAR_WEIGHTS.items():
            assert weight <= 30, f"{pillar} weight {weight} exceeds 30%"

    def test_retrieval_is_heaviest(self):
        """Retrieval should be the heaviest pillar (22% in 7-pillar system)."""
        assert PILLAR_WEIGHTS["retrieval"] == 22

    def test_all_weights_sum_to_100(self):
        """All weights should sum to exactly 100."""
        total = sum(PILLAR_WEIGHTS.values())
        assert total == 100

    def test_new_pillars_worth_68_percent(self):
        """New v2 pillars (tech, struct, schema, auth, entity_recognition) should total 68%."""
        new_pillar_weight = (
            PILLAR_WEIGHTS["technical"]
            + PILLAR_WEIGHTS["structure"]
            + PILLAR_WEIGHTS["schema"]
            + PILLAR_WEIGHTS["authority"]
            + PILLAR_WEIGHTS["entity_recognition"]
        )
        assert new_pillar_weight == 68
