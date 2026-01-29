"""Tests for universal questions."""

from worker.questions.universal import (
    QUESTION_STATS,
    UNIVERSAL_QUESTIONS,
    QuestionCategory,
    QuestionDifficulty,
    UniversalQuestion,
    format_question,
    get_category_weights,
    get_question_by_id,
    get_questions_by_category,
    get_questions_by_difficulty,
    get_total_weight,
    get_universal_questions,
)


class TestUniversalQuestion:
    """Tests for UniversalQuestion dataclass."""

    def test_create_question(self) -> None:
        """Can create a question."""
        q = UniversalQuestion(
            id="TEST-01",
            question="What does {company} do?",
            category=QuestionCategory.IDENTITY,
            difficulty=QuestionDifficulty.EASY,
            description="Test description",
            expected_signals=["signal1", "signal2"],
            weight=1.5,
        )

        assert q.id == "TEST-01"
        assert q.category == QuestionCategory.IDENTITY
        assert q.weight == 1.5

    def test_to_dict(self) -> None:
        """Question converts to dict."""
        q = UniversalQuestion(
            id="TEST-01",
            question="Test question?",
            category=QuestionCategory.OFFERINGS,
            difficulty=QuestionDifficulty.MEDIUM,
            description="Desc",
            expected_signals=["signal"],
        )

        d = q.to_dict()
        assert d["id"] == "TEST-01"
        assert d["category"] == "offerings"
        assert d["difficulty"] == "medium"


class TestQuestionCategory:
    """Tests for QuestionCategory enum."""

    def test_all_categories(self) -> None:
        """All expected categories exist."""
        assert QuestionCategory.IDENTITY == "identity"
        assert QuestionCategory.OFFERINGS == "offerings"
        assert QuestionCategory.CONTACT == "contact"
        assert QuestionCategory.TRUST == "trust"
        assert QuestionCategory.DIFFERENTIATION == "differentiation"


class TestQuestionDifficulty:
    """Tests for QuestionDifficulty enum."""

    def test_all_difficulties(self) -> None:
        """All expected difficulties exist."""
        assert QuestionDifficulty.EASY == "easy"
        assert QuestionDifficulty.MEDIUM == "medium"
        assert QuestionDifficulty.HARD == "hard"


class TestUniversalQuestions:
    """Tests for the universal questions set."""

    def test_has_15_questions(self) -> None:
        """Exactly 15 universal questions."""
        assert len(UNIVERSAL_QUESTIONS) == 15

    def test_all_have_required_fields(self) -> None:
        """All questions have required fields."""
        for q in UNIVERSAL_QUESTIONS:
            assert q.id
            assert q.question
            assert q.category
            assert q.difficulty
            assert q.description
            assert q.expected_signals
            assert q.weight > 0

    def test_all_have_company_placeholder(self) -> None:
        """All questions have {company} placeholder."""
        for q in UNIVERSAL_QUESTIONS:
            assert "{company}" in q.question

    def test_unique_ids(self) -> None:
        """All question IDs are unique."""
        ids = [q.id for q in UNIVERSAL_QUESTIONS]
        assert len(ids) == len(set(ids))

    def test_id_format(self) -> None:
        """IDs follow UQ-XX format."""
        for q in UNIVERSAL_QUESTIONS:
            assert q.id.startswith("UQ-")
            assert len(q.id) == 5

    def test_all_categories_represented(self) -> None:
        """All categories have at least one question."""
        categories = {q.category for q in UNIVERSAL_QUESTIONS}
        assert QuestionCategory.IDENTITY in categories
        assert QuestionCategory.OFFERINGS in categories
        assert QuestionCategory.CONTACT in categories
        assert QuestionCategory.TRUST in categories
        assert QuestionCategory.DIFFERENTIATION in categories

    def test_category_distribution(self) -> None:
        """Categories have reasonable distribution."""
        # Identity: 3, Offerings: 4, Contact: 2, Trust: 3, Differentiation: 3
        identity = get_questions_by_category(QuestionCategory.IDENTITY)
        offerings = get_questions_by_category(QuestionCategory.OFFERINGS)
        contact = get_questions_by_category(QuestionCategory.CONTACT)
        trust = get_questions_by_category(QuestionCategory.TRUST)
        diff = get_questions_by_category(QuestionCategory.DIFFERENTIATION)

        assert len(identity) == 3
        assert len(offerings) == 4
        assert len(contact) == 2
        assert len(trust) == 3
        assert len(diff) == 3


class TestGetUniversalQuestions:
    """Tests for get_universal_questions function."""

    def test_returns_copy(self) -> None:
        """Returns a copy, not the original."""
        q1 = get_universal_questions()
        q2 = get_universal_questions()

        assert q1 is not q2
        assert q1 == q2

    def test_returns_all_15(self) -> None:
        """Returns all 15 questions."""
        questions = get_universal_questions()
        assert len(questions) == 15


class TestGetQuestionsByCategory:
    """Tests for get_questions_by_category function."""

    def test_filter_by_identity(self) -> None:
        """Filter by IDENTITY category."""
        questions = get_questions_by_category(QuestionCategory.IDENTITY)

        assert len(questions) >= 1
        for q in questions:
            assert q.category == QuestionCategory.IDENTITY

    def test_filter_by_offerings(self) -> None:
        """Filter by OFFERINGS category."""
        questions = get_questions_by_category(QuestionCategory.OFFERINGS)

        assert len(questions) >= 1
        for q in questions:
            assert q.category == QuestionCategory.OFFERINGS


class TestGetQuestionsByDifficulty:
    """Tests for get_questions_by_difficulty function."""

    def test_filter_by_easy(self) -> None:
        """Filter by EASY difficulty."""
        questions = get_questions_by_difficulty(QuestionDifficulty.EASY)

        assert len(questions) >= 1
        for q in questions:
            assert q.difficulty == QuestionDifficulty.EASY

    def test_filter_by_hard(self) -> None:
        """Filter by HARD difficulty."""
        questions = get_questions_by_difficulty(QuestionDifficulty.HARD)

        assert len(questions) >= 1
        for q in questions:
            assert q.difficulty == QuestionDifficulty.HARD


class TestGetQuestionById:
    """Tests for get_question_by_id function."""

    def test_find_existing(self) -> None:
        """Find an existing question."""
        q = get_question_by_id("UQ-01")

        assert q is not None
        assert q.id == "UQ-01"

    def test_not_found(self) -> None:
        """Returns None for nonexistent ID."""
        q = get_question_by_id("NONEXISTENT")

        assert q is None


class TestFormatQuestion:
    """Tests for format_question function."""

    def test_formats_company_name(self) -> None:
        """Formats {company} placeholder."""
        q = UNIVERSAL_QUESTIONS[0]
        formatted = format_question(q, "Acme Corp")

        assert "{company}" not in formatted
        assert "Acme Corp" in formatted

    def test_handles_special_chars(self) -> None:
        """Handles company names with special chars."""
        q = UNIVERSAL_QUESTIONS[0]
        formatted = format_question(q, "O'Reilly & Associates")

        assert "O'Reilly & Associates" in formatted


class TestGetCategoryWeights:
    """Tests for get_category_weights function."""

    def test_returns_all_categories(self) -> None:
        """Returns weights for all categories."""
        weights = get_category_weights()

        assert QuestionCategory.IDENTITY in weights
        assert QuestionCategory.OFFERINGS in weights
        assert QuestionCategory.CONTACT in weights
        assert QuestionCategory.TRUST in weights
        assert QuestionCategory.DIFFERENTIATION in weights

    def test_weights_positive(self) -> None:
        """All weights are positive."""
        weights = get_category_weights()

        for weight in weights.values():
            assert weight > 0


class TestGetTotalWeight:
    """Tests for get_total_weight function."""

    def test_returns_positive(self) -> None:
        """Total weight is positive."""
        total = get_total_weight()
        assert total > 0

    def test_equals_sum(self) -> None:
        """Total equals sum of all weights."""
        total = get_total_weight()
        expected = sum(q.weight for q in UNIVERSAL_QUESTIONS)

        assert total == expected


class TestQuestionStats:
    """Tests for QUESTION_STATS constant."""

    def test_has_total_questions(self) -> None:
        """Stats include total questions."""
        assert QUESTION_STATS["total_questions"] == 15

    def test_has_total_weight(self) -> None:
        """Stats include total weight."""
        assert QUESTION_STATS["total_weight"] > 0

    def test_has_categories(self) -> None:
        """Stats include category counts."""
        assert "categories" in QUESTION_STATS
        assert len(QUESTION_STATS["categories"]) == 5

    def test_has_difficulties(self) -> None:
        """Stats include difficulty counts."""
        assert "difficulties" in QUESTION_STATS
        assert len(QUESTION_STATS["difficulties"]) == 3
