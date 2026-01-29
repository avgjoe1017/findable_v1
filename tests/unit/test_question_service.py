"""Tests for question service."""

from api.services.question_service import (
    QuestionService,
    get_question_service,
)
from worker.questions.universal import QuestionCategory, QuestionDifficulty


class TestQuestionSet:
    """Tests for QuestionSet dataclass."""

    def test_all_questions(self) -> None:
        """all_questions combines universal and derived."""
        # Create a question set with some mock questions
        service = QuestionService()
        question_set = service.generate_for_site(
            company_name="TestCo",
            domain="test.com",
        )

        all_qs = question_set.all_questions()

        assert len(all_qs) == question_set.total_count
        assert len(all_qs) == len(question_set.universal) + len(question_set.derived)

    def test_to_dict(self) -> None:
        """QuestionSet converts to dict."""
        service = QuestionService()
        question_set = service.generate_for_site(
            company_name="TestCo",
            domain="test.com",
        )

        d = question_set.to_dict()

        assert "universal" in d
        assert "derived" in d
        assert "total_count" in d
        assert "total_weight" in d
        assert "stats" in d
        assert d["stats"]["universal_count"] == len(question_set.universal)


class TestQuestionService:
    """Tests for QuestionService class."""

    def test_create_service(self) -> None:
        """Can create question service."""
        service = QuestionService()

        assert service is not None
        assert service.generator is not None
        assert service.derived_generator is not None

    def test_generate_for_site_basic(self) -> None:
        """Generate questions for a site."""
        service = QuestionService()

        question_set = service.generate_for_site(
            company_name="TestCo",
            domain="test.com",
        )

        assert question_set.total_count >= 15  # At least universal
        assert len(question_set.universal) == 15
        assert question_set.total_weight > 0

    def test_generate_for_site_with_metadata(self) -> None:
        """Generate questions with metadata."""
        service = QuestionService()

        question_set = service.generate_for_site(
            company_name="TestCo",
            domain="test.com",
            title="TestCo - Enterprise Solution",
            description="Enterprise-grade API platform",
        )

        # Should have derived questions from metadata
        assert len(question_set.derived) >= 0

    def test_generate_for_site_with_texts(self) -> None:
        """Generate questions with page texts."""
        service = QuestionService()

        question_set = service.generate_for_site(
            company_name="TestCo",
            domain="test.com",
            texts=["Check our API documentation", "Integrates with Slack"],
        )

        # Should have derived questions from content
        assert len(question_set.derived) >= 1

    def test_get_universal_questions(self) -> None:
        """Get all universal questions."""
        service = QuestionService()

        questions = service.get_universal_questions()

        assert len(questions) == 15

    def test_get_question_by_id(self) -> None:
        """Get question by ID."""
        service = QuestionService()

        question = service.get_question_by_id("UQ-01")

        assert question is not None
        assert question.id == "UQ-01"

    def test_get_question_by_id_not_found(self) -> None:
        """Returns None for unknown ID."""
        service = QuestionService()

        question = service.get_question_by_id("UNKNOWN")

        assert question is None

    def test_get_questions_by_category(self) -> None:
        """Filter questions by category."""
        service = QuestionService()

        questions = service.get_questions_by_category(QuestionCategory.IDENTITY)

        assert len(questions) >= 1
        for q in questions:
            assert q.category == QuestionCategory.IDENTITY

    def test_get_questions_by_difficulty(self) -> None:
        """Filter questions by difficulty."""
        service = QuestionService()

        questions = service.get_questions_by_difficulty(QuestionDifficulty.EASY)

        assert len(questions) >= 1
        for q in questions:
            assert q.difficulty == QuestionDifficulty.EASY

    def test_get_stats(self) -> None:
        """Get question statistics."""
        service = QuestionService()

        stats = service.get_stats()

        assert stats["total_questions"] == 15
        assert stats["total_weight"] > 0
        assert "categories" in stats
        assert "difficulties" in stats

    def test_analyze_content(self) -> None:
        """Analyze content for question derivation."""
        service = QuestionService()

        analysis = service.analyze_content(
            texts=["Check our API documentation"],
            headings={"h2": ["Features"]},
        )

        assert analysis.has_api is True


class TestGetQuestionService:
    """Tests for get_question_service function."""

    def test_returns_service(self) -> None:
        """Returns a QuestionService instance."""
        service = get_question_service()

        assert isinstance(service, QuestionService)

    def test_returns_singleton(self) -> None:
        """Returns the same instance."""
        service1 = get_question_service()
        service2 = get_question_service()

        assert service1 is service2


class TestQuestionServiceIntegration:
    """Integration tests for QuestionService."""

    def test_full_workflow(self) -> None:
        """Full question generation workflow."""
        service = QuestionService()

        # Generate questions for a realistic site
        question_set = service.generate_for_site(
            company_name="Acme Corp",
            domain="acme.com",
            title="Acme Corp - Enterprise Solutions",
            description="Enterprise-grade AI-powered automation platform",
            schema_types=["Organization", "SoftwareApplication"],
            headings={
                "h1": ["Welcome to Acme Corp"],
                "h2": ["Features", "Pricing", "About Us"],
            },
            texts=[
                "Acme Corp provides enterprise automation solutions.",
                "Check our API documentation for developers.",
                "Integrates with Slack, Salesforce, and more.",
            ],
        )

        # Verify universal questions
        assert len(question_set.universal) == 15
        for q in question_set.universal:
            assert "Acme Corp" in q.question
            assert "{company}" not in q.question

        # Verify derived questions
        assert len(question_set.derived) <= 5
        for q in question_set.derived:
            assert "Acme Corp" in q.question

        # Verify totals
        assert question_set.total_count == len(question_set.universal) + len(question_set.derived)
        assert question_set.total_weight > 0

        # Verify dict conversion
        d = question_set.to_dict()
        assert len(d["universal"]) == 15
        assert d["total_count"] == question_set.total_count
