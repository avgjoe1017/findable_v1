"""Tests for question generator."""

from worker.questions.generator import (
    GeneratedQuestion,
    GeneratorConfig,
    QuestionGenerator,
    QuestionSource,
    SiteContext,
    generate_questions,
)
from worker.questions.universal import QuestionCategory, QuestionDifficulty


class TestQuestionSource:
    """Tests for QuestionSource enum."""

    def test_all_sources(self) -> None:
        """All expected sources exist."""
        assert QuestionSource.UNIVERSAL == "universal"
        assert QuestionSource.SCHEMA == "schema"
        assert QuestionSource.METADATA == "metadata"
        assert QuestionSource.CONTENT == "content"
        assert QuestionSource.HEADING == "heading"


class TestGeneratedQuestion:
    """Tests for GeneratedQuestion dataclass."""

    def test_create_question(self) -> None:
        """Can create a generated question."""
        q = GeneratedQuestion(
            question="What does Acme do?",
            source=QuestionSource.UNIVERSAL,
            category=QuestionCategory.IDENTITY,
            difficulty=QuestionDifficulty.EASY,
            weight=1.5,
            context="Universal question UQ-01",
        )

        assert q.question == "What does Acme do?"
        assert q.source == QuestionSource.UNIVERSAL
        assert q.weight == 1.5

    def test_default_values(self) -> None:
        """Default values are set correctly."""
        q = GeneratedQuestion(
            question="Test?",
            source=QuestionSource.SCHEMA,
            category=QuestionCategory.OFFERINGS,
            difficulty=QuestionDifficulty.MEDIUM,
        )

        assert q.weight == 1.0
        assert q.context is None
        assert q.expected_signals == []
        assert q.metadata == {}

    def test_to_dict(self) -> None:
        """Question converts to dict."""
        q = GeneratedQuestion(
            question="Test question?",
            source=QuestionSource.HEADING,
            category=QuestionCategory.TRUST,
            difficulty=QuestionDifficulty.HARD,
            weight=0.8,
            context="From heading",
            expected_signals=["signal1"],
            metadata={"key": "value"},
        )

        d = q.to_dict()
        assert d["question"] == "Test question?"
        assert d["source"] == "heading"
        assert d["category"] == "trust"
        assert d["difficulty"] == "hard"
        assert d["weight"] == 0.8
        assert d["context"] == "From heading"
        assert d["expected_signals"] == ["signal1"]
        assert d["metadata"] == {"key": "value"}


class TestGeneratorConfig:
    """Tests for GeneratorConfig dataclass."""

    def test_default_config(self) -> None:
        """Default config has expected values."""
        config = GeneratorConfig()

        assert config.include_universal is True
        assert config.max_schema_questions == 3
        assert config.max_heading_questions == 2
        assert config.max_content_questions == 0
        assert config.total_question_limit == 20

    def test_custom_config(self) -> None:
        """Can create custom config."""
        config = GeneratorConfig(
            include_universal=False,
            max_schema_questions=5,
            total_question_limit=10,
        )

        assert config.include_universal is False
        assert config.max_schema_questions == 5
        assert config.total_question_limit == 10


class TestSiteContext:
    """Tests for SiteContext dataclass."""

    def test_minimal_context(self) -> None:
        """Can create context with required fields only."""
        ctx = SiteContext(
            company_name="Acme Corp",
            domain="acme.com",
        )

        assert ctx.company_name == "Acme Corp"
        assert ctx.domain == "acme.com"
        assert ctx.title is None
        assert ctx.schema_types == []
        assert ctx.headings == {}

    def test_full_context(self) -> None:
        """Can create context with all fields."""
        ctx = SiteContext(
            company_name="Acme Corp",
            domain="acme.com",
            title="Acme - Homepage",
            description="We make everything",
            schema_types=["Organization", "Product"],
            headings={"h1": ["Welcome"], "h2": ["Features", "Pricing"]},
            keywords=["acme", "products"],
            metadata={"key": "value"},
        )

        assert ctx.title == "Acme - Homepage"
        assert len(ctx.schema_types) == 2
        assert len(ctx.headings["h2"]) == 2


class TestQuestionGenerator:
    """Tests for QuestionGenerator class."""

    def test_generate_universal_only(self) -> None:
        """Generates universal questions by default."""
        generator = QuestionGenerator()
        context = SiteContext(company_name="TestCo", domain="test.com")

        questions = generator.generate(context)

        # Should have 15 universal questions
        universal = [q for q in questions if q.source == QuestionSource.UNIVERSAL]
        assert len(universal) == 15

    def test_generate_excludes_universal(self) -> None:
        """Can exclude universal questions."""
        config = GeneratorConfig(include_universal=False)
        generator = QuestionGenerator(config)
        context = SiteContext(company_name="TestCo", domain="test.com")

        questions = generator.generate(context)

        universal = [q for q in questions if q.source == QuestionSource.UNIVERSAL]
        assert len(universal) == 0

    def test_generate_from_schema(self) -> None:
        """Generates questions from schema.org types."""
        generator = QuestionGenerator()
        context = SiteContext(
            company_name="TestCo",
            domain="test.com",
            schema_types=["Product", "LocalBusiness"],
        )

        questions = generator.generate(context)

        schema_qs = [q for q in questions if q.source == QuestionSource.SCHEMA]
        assert len(schema_qs) > 0
        assert len(schema_qs) <= 3  # Default max_schema_questions

    def test_generate_from_headings(self) -> None:
        """Generates questions from page headings."""
        generator = QuestionGenerator()
        context = SiteContext(
            company_name="TestCo",
            domain="test.com",
            headings={
                "h1": ["Welcome to TestCo"],
                "h2": ["Our Pricing Plans", "Customer Testimonials"],
            },
        )

        questions = generator.generate(context)

        heading_qs = [q for q in questions if q.source == QuestionSource.HEADING]
        assert len(heading_qs) > 0
        assert len(heading_qs) <= 2  # Default max_heading_questions

    def test_respects_total_limit(self) -> None:
        """Respects total question limit."""
        config = GeneratorConfig(total_question_limit=10)
        generator = QuestionGenerator(config)
        context = SiteContext(
            company_name="TestCo",
            domain="test.com",
            schema_types=["Product", "LocalBusiness", "Organization"],
            headings={"h2": ["Pricing", "Features", "Team", "Support"]},
        )

        questions = generator.generate(context)

        assert len(questions) <= 10

    def test_deduplicates_questions(self) -> None:
        """Removes duplicate questions."""
        generator = QuestionGenerator()
        context = SiteContext(
            company_name="TestCo",
            domain="test.com",
            headings={
                "h1": ["Our Features"],
                "h2": ["Features Overview"],  # Both match features pattern
            },
        )

        questions = generator.generate(context)

        # Check for duplicates
        question_texts = [q.question.lower() for q in questions]
        unique_texts = set(question_texts)
        assert len(question_texts) == len(unique_texts)

    def test_formats_company_name(self) -> None:
        """Company name is formatted into questions."""
        generator = QuestionGenerator()
        context = SiteContext(company_name="Acme Corp", domain="acme.com")

        questions = generator.generate(context)

        for q in questions:
            assert "{company}" not in q.question
            # At least some questions should contain the company name
        company_mentions = sum(1 for q in questions if "Acme Corp" in q.question)
        assert company_mentions > 0

    def test_generate_for_site_method(self) -> None:
        """Convenience method works correctly."""
        generator = QuestionGenerator()

        questions = generator.generate_for_site(
            company_name="TestCo",
            domain="test.com",
            schema_types=["Product"],
        )

        assert len(questions) > 0


class TestGenerateQuestions:
    """Tests for generate_questions convenience function."""

    def test_basic_generation(self) -> None:
        """Basic question generation works."""
        questions = generate_questions(
            company_name="TestCo",
            domain="test.com",
        )

        assert len(questions) == 15  # Just universal questions

    def test_with_schema(self) -> None:
        """Generation with schema types."""
        questions = generate_questions(
            company_name="TestCo",
            domain="test.com",
            schema_types=["Product"],
        )

        assert len(questions) > 15  # Universal + schema questions

    def test_with_headings(self) -> None:
        """Generation with headings."""
        questions = generate_questions(
            company_name="TestCo",
            domain="test.com",
            headings={"h2": ["Pricing Plans"]},
        )

        assert len(questions) > 15  # Universal + heading questions

    def test_with_custom_config(self) -> None:
        """Generation with custom config."""
        config = GeneratorConfig(include_universal=False)
        questions = generate_questions(
            company_name="TestCo",
            domain="test.com",
            schema_types=["Product"],
            config=config,
        )

        # No universal questions, just schema
        assert all(q.source != QuestionSource.UNIVERSAL for q in questions)


class TestSchemaQuestions:
    """Tests for schema-based question generation."""

    def test_product_schema(self) -> None:
        """Product schema generates relevant questions."""
        generator = QuestionGenerator(
            GeneratorConfig(include_universal=False, max_schema_questions=10)
        )
        context = SiteContext(
            company_name="TestCo",
            domain="test.com",
            schema_types=["Product"],
        )

        questions = generator.generate(context)

        # Should have product-related questions
        assert any("features" in q.question.lower() for q in questions)

    def test_local_business_schema(self) -> None:
        """LocalBusiness schema generates relevant questions."""
        generator = QuestionGenerator(
            GeneratorConfig(include_universal=False, max_schema_questions=10)
        )
        context = SiteContext(
            company_name="TestCo",
            domain="test.com",
            schema_types=["LocalBusiness"],
        )

        questions = generator.generate(context)

        # Should have location-related questions
        assert any(
            "hours" in q.question.lower() or "address" in q.question.lower() for q in questions
        )

    def test_unknown_schema_ignored(self) -> None:
        """Unknown schema types are ignored."""
        generator = QuestionGenerator(
            GeneratorConfig(include_universal=False, max_schema_questions=10)
        )
        context = SiteContext(
            company_name="TestCo",
            domain="test.com",
            schema_types=["UnknownType", "AnotherUnknown"],
        )

        questions = generator.generate(context)

        assert len(questions) == 0


class TestHeadingQuestions:
    """Tests for heading-based question generation."""

    def test_pricing_heading(self) -> None:
        """Pricing heading generates pricing question."""
        generator = QuestionGenerator(
            GeneratorConfig(include_universal=False, max_heading_questions=10)
        )
        context = SiteContext(
            company_name="TestCo",
            domain="test.com",
            headings={"h2": ["Pricing Plans"]},
        )

        questions = generator.generate(context)

        assert any("pricing" in q.question.lower() for q in questions)

    def test_about_heading(self) -> None:
        """About heading generates identity question."""
        generator = QuestionGenerator(
            GeneratorConfig(include_universal=False, max_heading_questions=10)
        )
        context = SiteContext(
            company_name="TestCo",
            domain="test.com",
            headings={"h2": ["About Us"]},
        )

        questions = generator.generate(context)

        assert any("background" in q.question.lower() for q in questions)

    def test_support_heading(self) -> None:
        """Support heading generates contact question."""
        generator = QuestionGenerator(
            GeneratorConfig(include_universal=False, max_heading_questions=10)
        )
        context = SiteContext(
            company_name="TestCo",
            domain="test.com",
            headings={"h2": ["Customer Support"]},
        )

        questions = generator.generate(context)

        assert any("support" in q.question.lower() for q in questions)

    def test_no_matching_headings(self) -> None:
        """Non-matching headings produce no questions."""
        generator = QuestionGenerator(
            GeneratorConfig(include_universal=False, max_heading_questions=10)
        )
        context = SiteContext(
            company_name="TestCo",
            domain="test.com",
            headings={"h2": ["Random Title", "Another Random"]},
        )

        questions = generator.generate(context)

        assert len(questions) == 0
