"""Tests for scoring rubric."""

from worker.questions.universal import QuestionCategory, QuestionDifficulty
from worker.scoring.rubric import (
    CategoryWeight,
    DifficultyMultiplier,
    RubricCriterion,
    ScoreLevel,
    ScoringRubric,
    get_rubric,
)


class TestScoreLevel:
    """Tests for ScoreLevel enum."""

    def test_all_levels(self) -> None:
        """All expected levels exist."""
        assert ScoreLevel.EXCELLENT == "excellent"
        assert ScoreLevel.GOOD == "good"
        assert ScoreLevel.FAIR == "fair"
        assert ScoreLevel.NEEDS_WORK == "needs_work"
        assert ScoreLevel.POOR == "poor"


class TestRubricCriterion:
    """Tests for RubricCriterion."""

    def test_create_criterion(self) -> None:
        """Can create a criterion."""
        criterion = RubricCriterion(
            id="test",
            name="Test Criterion",
            description="Test description",
            weight=0.25,
            max_points=25,
        )

        assert criterion.id == "test"
        assert criterion.weight == 0.25
        assert criterion.max_points == 25

    def test_get_level_excellent(self) -> None:
        """Gets excellent level for high score."""
        criterion = RubricCriterion(
            id="test", name="Test", description="Test",
            weight=0.25, max_points=25,
        )

        assert criterion.get_level(0.95) == ScoreLevel.EXCELLENT
        assert criterion.get_level(0.90) == ScoreLevel.EXCELLENT

    def test_get_level_good(self) -> None:
        """Gets good level for good score."""
        criterion = RubricCriterion(
            id="test", name="Test", description="Test",
            weight=0.25, max_points=25,
        )

        assert criterion.get_level(0.85) == ScoreLevel.GOOD
        assert criterion.get_level(0.80) == ScoreLevel.GOOD

    def test_get_level_fair(self) -> None:
        """Gets fair level for fair score."""
        criterion = RubricCriterion(
            id="test", name="Test", description="Test",
            weight=0.25, max_points=25,
        )

        assert criterion.get_level(0.75) == ScoreLevel.FAIR
        assert criterion.get_level(0.70) == ScoreLevel.FAIR

    def test_get_level_poor(self) -> None:
        """Gets poor level for low score."""
        criterion = RubricCriterion(
            id="test", name="Test", description="Test",
            weight=0.25, max_points=25,
        )

        assert criterion.get_level(0.50) == ScoreLevel.POOR
        assert criterion.get_level(0.0) == ScoreLevel.POOR

    def test_to_dict(self) -> None:
        """Converts to dict."""
        criterion = RubricCriterion(
            id="test", name="Test", description="Test",
            weight=0.25, max_points=25,
        )

        d = criterion.to_dict()
        assert d["id"] == "test"
        assert d["weight"] == 0.25


class TestCategoryWeight:
    """Tests for CategoryWeight."""

    def test_create_weight(self) -> None:
        """Can create category weight."""
        weight = CategoryWeight(
            category=QuestionCategory.IDENTITY,
            weight=0.25,
            description="Who you are",
            importance="Foundation for AI",
        )

        assert weight.category == QuestionCategory.IDENTITY
        assert weight.weight == 0.25

    def test_to_dict(self) -> None:
        """Converts to dict."""
        weight = CategoryWeight(
            category=QuestionCategory.IDENTITY,
            weight=0.25,
            description="Who you are",
            importance="Foundation for AI",
        )

        d = weight.to_dict()
        assert d["category"] == "identity"
        assert d["weight"] == 0.25


class TestDifficultyMultiplier:
    """Tests for DifficultyMultiplier."""

    def test_create_multiplier(self) -> None:
        """Can create difficulty multiplier."""
        mult = DifficultyMultiplier(
            difficulty=QuestionDifficulty.HARD,
            multiplier=1.5,
            description="Complex questions",
        )

        assert mult.difficulty == QuestionDifficulty.HARD
        assert mult.multiplier == 1.5

    def test_to_dict(self) -> None:
        """Converts to dict."""
        mult = DifficultyMultiplier(
            difficulty=QuestionDifficulty.EASY,
            multiplier=1.0,
            description="Basic questions",
        )

        d = mult.to_dict()
        assert d["difficulty"] == "easy"
        assert d["multiplier"] == 1.0


class TestScoringRubric:
    """Tests for ScoringRubric."""

    def test_default_rubric(self) -> None:
        """Default rubric has expected structure."""
        rubric = ScoringRubric()

        assert rubric.name == "Findable Score Rubric v1"
        assert rubric.version == "1.0"
        assert len(rubric.criteria) == 4
        assert len(rubric.category_weights) == 5
        assert len(rubric.difficulty_multipliers) == 3

    def test_default_criteria(self) -> None:
        """Default criteria are present."""
        rubric = ScoringRubric()

        criterion_ids = [c.id for c in rubric.criteria]
        assert "content_relevance" in criterion_ids
        assert "signal_coverage" in criterion_ids
        assert "answer_confidence" in criterion_ids
        assert "source_quality" in criterion_ids

    def test_criteria_weights_sum_to_one(self) -> None:
        """Criteria weights sum to 1.0."""
        rubric = ScoringRubric()

        total_weight = sum(c.weight for c in rubric.criteria)
        assert abs(total_weight - 1.0) < 0.01

    def test_category_weights_sum_to_one(self) -> None:
        """Category weights sum to 1.0."""
        rubric = ScoringRubric()

        total_weight = sum(cw.weight for cw in rubric.category_weights.values())
        assert abs(total_weight - 1.0) < 0.01

    def test_get_grade_a(self) -> None:
        """Gets A grade for high score."""
        rubric = ScoringRubric()

        assert rubric.get_grade(95) == "A"
        assert rubric.get_grade(93) == "A"

    def test_get_grade_b(self) -> None:
        """Gets B grade for good score."""
        rubric = ScoringRubric()

        assert rubric.get_grade(85) == "B"
        assert rubric.get_grade(83) == "B"

    def test_get_grade_c(self) -> None:
        """Gets C grade for fair score."""
        rubric = ScoringRubric()

        assert rubric.get_grade(75) == "C"
        assert rubric.get_grade(73) == "C"

    def test_get_grade_f(self) -> None:
        """Gets F grade for low score."""
        rubric = ScoringRubric()

        assert rubric.get_grade(50) == "F"
        assert rubric.get_grade(0) == "F"

    def test_get_grade_description(self) -> None:
        """Gets grade descriptions."""
        rubric = ScoringRubric()

        desc = rubric.get_grade_description("A")
        assert "Excellent" in desc

        desc = rubric.get_grade_description("F")
        assert "Critical" in desc

    def test_get_category_weight(self) -> None:
        """Gets category weight."""
        rubric = ScoringRubric()

        weight = rubric.get_category_weight(QuestionCategory.IDENTITY)
        assert weight == 0.25

        weight = rubric.get_category_weight(QuestionCategory.OFFERINGS)
        assert weight == 0.30

    def test_get_difficulty_multiplier(self) -> None:
        """Gets difficulty multiplier."""
        rubric = ScoringRubric()

        mult = rubric.get_difficulty_multiplier(QuestionDifficulty.EASY)
        assert mult == 1.0

        mult = rubric.get_difficulty_multiplier(QuestionDifficulty.HARD)
        assert mult == 1.5

    def test_to_dict(self) -> None:
        """Converts to dict."""
        rubric = ScoringRubric()

        d = rubric.to_dict()
        assert "name" in d
        assert "version" in d
        assert "criteria" in d
        assert "category_weights" in d
        assert "difficulty_multipliers" in d
        assert "grade_thresholds" in d


class TestGetRubric:
    """Tests for get_rubric function."""

    def test_returns_rubric(self) -> None:
        """Returns a ScoringRubric."""
        rubric = get_rubric()

        assert isinstance(rubric, ScoringRubric)

    def test_returns_default(self) -> None:
        """Returns the default rubric."""
        rubric = get_rubric()

        assert rubric.name == "Findable Score Rubric v1"
