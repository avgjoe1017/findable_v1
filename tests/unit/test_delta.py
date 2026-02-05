"""Tests for score delta comparison."""

from datetime import datetime, timedelta
from uuid import uuid4

from worker.scoring.calculator_v2 import (
    FINDABILITY_LEVELS,
    FindableScoreV2,
    MilestoneInfo,
    PillarScore,
)
from worker.scoring.delta import (
    ChangeDirection,
    ChangeSignificance,
    PillarDelta,
    ScoreDelta,
    ScoreDeltaCalculator,
    build_trend_data,
    compare_scores,
)


def create_pillar(
    name: str, raw_score: float, max_points: float, evaluated: bool = True
) -> PillarScore:
    """Helper to create a pillar score."""
    level = "full" if raw_score >= 70 else "partial" if raw_score >= 40 else "limited"
    return PillarScore(
        name=name,
        display_name=name.title().replace("_", " "),
        raw_score=raw_score,
        max_points=max_points,
        points_earned=raw_score / 100 * max_points,
        weight_pct=max_points,
        level=level,
        description=f"{name} description",
        evaluated=evaluated,
    )


def get_findability_level(score: float) -> tuple[str, str, str, str]:
    """Get findability level info for a score."""
    for level_id, level_data in FINDABILITY_LEVELS.items():
        if level_data["min_score"] <= score <= level_data["max_score"]:
            return level_id, level_data["label"], level_data["summary"], level_data["focus"]
    return "not_yet_findable", "Not Yet Findable", "", ""


def create_score_v2(
    technical: float = 70,
    structure: float = 70,
    schema: float = 70,
    authority: float = 70,
    retrieval: float = 70,
    coverage: float = 70,
) -> FindableScoreV2:
    """Helper to create a FindableScoreV2 with specified pillar scores."""
    pillars = [
        create_pillar("technical", technical, 15),
        create_pillar("structure", structure, 20),
        create_pillar("schema", schema, 15),
        create_pillar("authority", authority, 15),
        create_pillar("retrieval", retrieval, 25),
        create_pillar("coverage", coverage, 10),
    ]

    total = sum(p.points_earned for p in pillars)

    # Determine findability level
    level_id, level_label, level_summary, level_focus = get_findability_level(total)

    # Determine next milestone
    next_milestone = None
    points_to_milestone = 0.0
    milestones = [40, 55, 70, 85]
    for m_score in milestones:
        if total < m_score:
            next_milestone = MilestoneInfo(
                score=m_score,
                name=f"Milestone {m_score}",
                description="Test milestone",
                points_needed=m_score - total,
            )
            points_to_milestone = m_score - total
            break

    return FindableScoreV2(
        total_score=total,
        level=level_id,
        level_label=level_label,
        level_summary=level_summary,
        level_focus=level_focus,
        next_milestone=next_milestone,
        points_to_milestone=points_to_milestone,
        pillars=pillars,
        pillar_breakdown={p.name: p for p in pillars},
        pillars_good=sum(1 for p in pillars if p.level == "full"),
        pillars_warning=sum(1 for p in pillars if p.level == "partial"),
        pillars_critical=sum(1 for p in pillars if p.level == "limited"),
        all_critical_issues=[],
        top_recommendations=[],
    )


class TestScoreDeltaCalculator:
    """Tests for ScoreDeltaCalculator."""

    def test_calculate_improvement(self):
        """Test delta calculation when score improved."""
        prev = create_score_v2(
            technical=50, structure=50, schema=50, authority=50, retrieval=50, coverage=50
        )
        curr = create_score_v2(
            technical=70, structure=70, schema=70, authority=70, retrieval=70, coverage=70
        )

        calculator = ScoreDeltaCalculator()
        delta = calculator.calculate(prev, curr)

        assert delta.total_delta > 0
        assert delta.total_direction == ChangeDirection.IMPROVED
        assert delta.pillars_improved == 6
        assert delta.pillars_declined == 0

    def test_calculate_decline(self):
        """Test delta calculation when score declined."""
        prev = create_score_v2(
            technical=80, structure=80, schema=80, authority=80, retrieval=80, coverage=80
        )
        curr = create_score_v2(
            technical=60, structure=60, schema=60, authority=60, retrieval=60, coverage=60
        )

        calculator = ScoreDeltaCalculator()
        delta = calculator.calculate(prev, curr)

        assert delta.total_delta < 0
        assert delta.total_direction == ChangeDirection.DECLINED
        assert delta.pillars_improved == 0
        assert delta.pillars_declined == 6

    def test_calculate_unchanged(self):
        """Test delta calculation when score unchanged."""
        prev = create_score_v2(technical=70, structure=70)
        curr = create_score_v2(technical=70, structure=70)

        calculator = ScoreDeltaCalculator()
        delta = calculator.calculate(prev, curr)

        assert abs(delta.total_delta) < 1
        assert delta.total_direction == ChangeDirection.UNCHANGED
        assert delta.pillars_unchanged == 6

    def test_pillar_deltas(self):
        """Test individual pillar delta calculations."""
        prev = create_score_v2(technical=50, structure=80)
        curr = create_score_v2(technical=70, structure=60)

        calculator = ScoreDeltaCalculator()
        delta = calculator.calculate(prev, curr)

        # Find technical pillar delta
        tech_delta = next(d for d in delta.pillar_deltas if d.pillar_name == "technical")
        assert tech_delta.score_delta == 20
        assert tech_delta.direction == ChangeDirection.IMPROVED

        # Find structure pillar delta
        struct_delta = next(d for d in delta.pillar_deltas if d.pillar_name == "structure")
        assert struct_delta.score_delta == -20
        assert struct_delta.direction == ChangeDirection.DECLINED

    def test_biggest_gain_and_loss(self):
        """Test identification of biggest gain and loss."""
        prev = create_score_v2(technical=40, structure=90, schema=70)
        curr = create_score_v2(technical=80, structure=50, schema=70)

        calculator = ScoreDeltaCalculator()
        delta = calculator.calculate(prev, curr)

        assert delta.biggest_gain is not None
        assert delta.biggest_gain.pillar_name == "technical"
        assert delta.biggest_gain.score_delta == 40

        assert delta.biggest_loss is not None
        assert delta.biggest_loss.pillar_name == "structure"
        assert delta.biggest_loss.score_delta == -40

    def test_level_change(self):
        """Test findability level change detection."""
        prev = create_score_v2(
            technical=50, structure=50, schema=50, authority=50, retrieval=50, coverage=50
        )
        curr = create_score_v2(
            technical=85, structure=85, schema=85, authority=85, retrieval=85, coverage=85
        )

        calculator = ScoreDeltaCalculator()
        delta = calculator.calculate(prev, curr)

        # Level should improve from lower to higher
        assert delta.grade_improved is True
        assert delta.grade_declined is False

    def test_level_changes(self):
        """Test pillar level change tracking."""
        prev = create_score_v2(technical=35, structure=75)  # limited, full
        curr = create_score_v2(technical=75, structure=35)  # full, limited

        calculator = ScoreDeltaCalculator()
        delta = calculator.calculate(prev, curr)

        tech_delta = next(d for d in delta.pillar_deltas if d.pillar_name == "technical")
        assert tech_delta.level_improved is True
        assert tech_delta.previous_level == "limited"
        assert tech_delta.current_level == "full"

        struct_delta = next(d for d in delta.pillar_deltas if d.pillar_name == "structure")
        assert struct_delta.level_declined is True
        assert struct_delta.previous_level == "full"
        assert struct_delta.current_level == "limited"

    def test_significance_levels(self):
        """Test change significance classification."""
        calculator = ScoreDeltaCalculator()

        assert calculator._get_significance(15) == ChangeSignificance.MAJOR
        assert calculator._get_significance(-12) == ChangeSignificance.MAJOR
        assert calculator._get_significance(7) == ChangeSignificance.MODERATE
        assert calculator._get_significance(-6) == ChangeSignificance.MODERATE
        assert calculator._get_significance(3) == ChangeSignificance.MINOR
        assert calculator._get_significance(-2) == ChangeSignificance.MINOR
        assert calculator._get_significance(0.3) == ChangeSignificance.NEGLIGIBLE

    def test_days_between_runs(self):
        """Test days between runs calculation."""
        prev = create_score_v2()
        curr = create_score_v2()

        prev_date = datetime(2024, 1, 1)
        curr_date = datetime(2024, 1, 15)

        calculator = ScoreDeltaCalculator()
        delta = calculator.calculate(
            prev,
            curr,
            previous_run_date=prev_date,
            current_run_date=curr_date,
        )

        assert delta.days_between_runs == 14

    def test_insights_generation(self):
        """Test insight generation for improvements."""
        prev = create_score_v2(
            technical=40, structure=40, schema=40, authority=40, retrieval=40, coverage=40
        )
        curr = create_score_v2(
            technical=70, structure=70, schema=70, authority=70, retrieval=70, coverage=70
        )

        calculator = ScoreDeltaCalculator()
        delta = calculator.calculate(prev, curr)

        assert len(delta.insights) > 0
        # Should have improvement-related insights
        assert any("improvement" in i.lower() or "improved" in i.lower() for i in delta.insights)

    def test_warnings_generation(self):
        """Test warning generation for declines."""
        prev = create_score_v2(
            technical=90, structure=90, schema=90, authority=90, retrieval=90, coverage=90
        )
        curr = create_score_v2(
            technical=50, structure=50, schema=50, authority=50, retrieval=50, coverage=50
        )

        calculator = ScoreDeltaCalculator()
        delta = calculator.calculate(prev, curr)

        assert len(delta.warnings) > 0
        # Should have regression warning
        assert any(
            "regression" in w.lower() or "declined" in w.lower() or "drop" in w.lower()
            for w in delta.warnings
        )


class TestScoreDelta:
    """Tests for ScoreDelta dataclass."""

    def test_to_dict(self):
        """Test serialization to dict."""
        prev = create_score_v2()
        curr = create_score_v2()

        delta = compare_scores(prev, curr)
        data = delta.to_dict()

        assert "previous_total" in data
        assert "current_total" in data
        assert "total_delta" in data
        assert "pillar_deltas" in data
        assert isinstance(data["pillar_deltas"], list)

    def test_show_the_delta(self):
        """Test human-readable output."""
        prev = create_score_v2(technical=50)
        curr = create_score_v2(technical=70)

        delta = compare_scores(prev, curr)
        output = delta.show_the_delta()

        assert "SCORE COMPARISON" in output
        assert "PILLAR CHANGES" in output
        assert "Technical" in output


class TestPillarDelta:
    """Tests for PillarDelta dataclass."""

    def test_delta_display_positive(self):
        """Test positive delta display."""
        delta = PillarDelta(
            pillar_name="technical",
            display_name="Technical Readiness",
            previous_score=50,
            previous_points=7.5,
            previous_level="partial",
            current_score=70,
            current_points=10.5,
            current_level="full",
            score_delta=20,
            points_delta=3,
            direction=ChangeDirection.IMPROVED,
            significance=ChangeSignificance.MAJOR,
            level_improved=True,
            level_declined=False,
            max_points=15,
        )

        assert delta.delta_display == "+20"

    def test_delta_display_negative(self):
        """Test negative delta display."""
        delta = PillarDelta(
            pillar_name="structure",
            display_name="Structure Quality",
            previous_score=80,
            previous_points=16,
            previous_level="full",
            current_score=60,
            current_points=12,
            current_level="partial",
            score_delta=-20,
            points_delta=-4,
            direction=ChangeDirection.DECLINED,
            significance=ChangeSignificance.MAJOR,
            level_improved=False,
            level_declined=True,
            max_points=20,
        )

        assert delta.delta_display == "-20"

    def test_delta_display_unchanged(self):
        """Test unchanged delta display."""
        delta = PillarDelta(
            pillar_name="schema",
            display_name="Schema Richness",
            previous_score=70,
            previous_points=10.5,
            previous_level="full",
            current_score=70.3,
            current_points=10.545,
            current_level="full",
            score_delta=0.3,
            points_delta=0.045,
            direction=ChangeDirection.UNCHANGED,
            significance=ChangeSignificance.NEGLIGIBLE,
            level_improved=False,
            level_declined=False,
            max_points=15,
        )

        assert delta.delta_display == "—"


class TestBuildTrendData:
    """Tests for trend data building."""

    def test_empty_scores(self):
        """Test with no scores."""
        summary = build_trend_data([])

        assert summary.total_runs == 0
        assert len(summary.data_points) == 0

    def test_single_score(self):
        """Test with single score."""
        score = create_score_v2()
        run_date = datetime.now()

        summary = build_trend_data([(score, uuid4(), run_date)])

        assert summary.total_runs == 1
        assert len(summary.data_points) == 1
        assert summary.latest_score == score.total_score

    def test_improving_trend(self):
        """Test improving trend detection."""
        base_date = datetime.now()
        # Need changes that result in >= 5 point total score change
        # All pillars at 50 vs all at 70 = significant improvement
        scores = [
            (
                create_score_v2(
                    technical=50, structure=50, schema=50, authority=50, retrieval=50, coverage=50
                ),
                uuid4(),
                base_date,
            ),
            (
                create_score_v2(
                    technical=60, structure=60, schema=60, authority=60, retrieval=60, coverage=60
                ),
                uuid4(),
                base_date + timedelta(days=7),
            ),
            (
                create_score_v2(
                    technical=70, structure=70, schema=70, authority=70, retrieval=70, coverage=70
                ),
                uuid4(),
                base_date + timedelta(days=14),
            ),
        ]

        summary = build_trend_data(scores)

        assert summary.total_runs == 3
        assert summary.score_trend == "improving"
        assert summary.days_tracked == 14

    def test_declining_trend(self):
        """Test declining trend detection."""
        base_date = datetime.now()
        # Need changes that result in >= 5 point total score decline
        scores = [
            (
                create_score_v2(
                    technical=80, structure=80, schema=80, authority=80, retrieval=80, coverage=80
                ),
                uuid4(),
                base_date,
            ),
            (
                create_score_v2(
                    technical=70, structure=70, schema=70, authority=70, retrieval=70, coverage=70
                ),
                uuid4(),
                base_date + timedelta(days=7),
            ),
            (
                create_score_v2(
                    technical=50, structure=50, schema=50, authority=50, retrieval=50, coverage=50
                ),
                uuid4(),
                base_date + timedelta(days=14),
            ),
        ]

        summary = build_trend_data(scores)

        assert summary.score_trend == "declining"

    def test_stable_trend(self):
        """Test stable trend detection."""
        base_date = datetime.now()
        scores = [
            (create_score_v2(technical=70), uuid4(), base_date),
            (create_score_v2(technical=71), uuid4(), base_date + timedelta(days=7)),
            (create_score_v2(technical=69), uuid4(), base_date + timedelta(days=14)),
        ]

        summary = build_trend_data(scores)

        assert summary.score_trend == "stable"

    def test_pillar_trends(self):
        """Test per-pillar trend tracking."""
        base_date = datetime.now()
        scores = [
            (create_score_v2(technical=50, structure=80), uuid4(), base_date),
            (create_score_v2(technical=80, structure=50), uuid4(), base_date + timedelta(days=14)),
        ]

        summary = build_trend_data(scores)

        assert summary.pillar_trends.get("technical") == "improving"
        assert summary.pillar_trends.get("structure") == "declining"

    def test_trend_summary_to_dict(self):
        """Test trend summary serialization."""
        score = create_score_v2()
        summary = build_trend_data([(score, uuid4(), datetime.now())])

        data = summary.to_dict()

        assert "total_runs" in data
        assert "score_trend" in data
        assert "data_points" in data
        assert "pillar_trends" in data


class TestConvenienceFunction:
    """Tests for compare_scores convenience function."""

    def test_compare_scores(self):
        """Test compare_scores function."""
        prev = create_score_v2(technical=50)
        curr = create_score_v2(technical=70)

        delta = compare_scores(prev, curr)

        assert isinstance(delta, ScoreDelta)
        assert delta.total_delta != 0
        assert len(delta.pillar_deltas) == 6
