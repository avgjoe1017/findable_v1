"""Tests for site-derived question generation."""

from worker.questions.derived import (
    CONTENT_PATTERNS,
    ContentAnalysis,
    ContentAnalyzer,
    DerivedConfig,
    DerivedQuestionGenerator,
    derive_questions,
)
from worker.questions.generator import QuestionSource, SiteContext
from worker.questions.universal import QuestionCategory


class TestContentPatterns:
    """Tests for content detection patterns."""

    def test_pricing_pattern(self) -> None:
        """Detects pricing-related content."""
        pattern = CONTENT_PATTERNS["pricing"]
        assert pattern.search("Check our pricing plans")
        assert pattern.search("Free trial available")
        assert pattern.search("See the cost breakdown")
        assert not pattern.search("Hello world")

    def test_blog_pattern(self) -> None:
        """Detects blog-related content."""
        pattern = CONTENT_PATTERNS["blog"]
        assert pattern.search("Read our blog")
        assert pattern.search("Latest articles")
        assert pattern.search("Industry news")
        assert not pattern.search("Hello world")

    def test_api_pattern(self) -> None:
        """Detects API-related content."""
        pattern = CONTENT_PATTERNS["api"]
        assert pattern.search("Check our API docs")
        assert pattern.search("Developer tools")
        assert pattern.search("SDK available")
        assert not pattern.search("Hello world")

    def test_integrations_pattern(self) -> None:
        """Detects integrations-related content."""
        pattern = CONTENT_PATTERNS["integrations"]
        assert pattern.search("Integrates with Slack")
        assert pattern.search("Connect your tools")
        assert pattern.search("Partner apps")
        assert not pattern.search("Hello world")


class TestContentAnalysis:
    """Tests for ContentAnalysis dataclass."""

    def test_default_values(self) -> None:
        """Default values are empty/false."""
        analysis = ContentAnalysis()

        assert analysis.products == []
        assert analysis.services == []
        assert analysis.keywords == []
        assert analysis.has_pricing is False
        assert analysis.has_blog is False
        assert analysis.has_api is False

    def test_custom_values(self) -> None:
        """Can set custom values."""
        analysis = ContentAnalysis(
            products=["Product A"],
            has_pricing=True,
            has_api=True,
        )

        assert analysis.products == ["Product A"]
        assert analysis.has_pricing is True
        assert analysis.has_api is True


class TestDerivedConfig:
    """Tests for DerivedConfig dataclass."""

    def test_default_config(self) -> None:
        """Default config has expected values."""
        config = DerivedConfig()

        assert config.max_questions == 5
        assert config.min_keyword_frequency == 3
        assert config.max_keywords == 10

    def test_custom_config(self) -> None:
        """Can set custom config values."""
        config = DerivedConfig(max_questions=3, min_keyword_frequency=5)

        assert config.max_questions == 3
        assert config.min_keyword_frequency == 5


class TestContentAnalyzer:
    """Tests for ContentAnalyzer class."""

    def test_analyze_empty(self) -> None:
        """Handles empty input."""
        analyzer = ContentAnalyzer()
        analysis = analyzer.analyze([])

        assert analysis.products == []
        assert analysis.has_pricing is False

    def test_detect_pricing(self) -> None:
        """Detects pricing content."""
        analyzer = ContentAnalyzer()
        analysis = analyzer.analyze(["Check our pricing plans today"])

        assert analysis.has_pricing is True

    def test_detect_blog(self) -> None:
        """Detects blog content."""
        analyzer = ContentAnalyzer()
        analysis = analyzer.analyze(["Read our latest blog posts"])

        assert analysis.has_blog is True

    def test_detect_api(self) -> None:
        """Detects API content."""
        analyzer = ContentAnalyzer()
        analysis = analyzer.analyze(["Explore our API documentation"])

        assert analysis.has_api is True

    def test_detect_integrations(self) -> None:
        """Detects integrations content."""
        analyzer = ContentAnalyzer()
        analysis = analyzer.analyze(["Integrates with your favorite tools"])

        assert analysis.has_integrations is True

    def test_detect_careers(self) -> None:
        """Detects careers content."""
        analyzer = ContentAnalyzer()
        analysis = analyzer.analyze(["Join our team - we are hiring!"])

        assert analysis.has_careers is True

    def test_extract_keywords(self) -> None:
        """Extracts significant keywords."""
        analyzer = ContentAnalyzer(DerivedConfig(min_keyword_frequency=2))
        text = "automation automation automation analytics analytics"
        analysis = analyzer.analyze([text])

        assert "automation" in analysis.keywords
        assert "analytics" in analysis.keywords

    def test_filter_stop_words(self) -> None:
        """Filters stop words from keywords."""
        analyzer = ContentAnalyzer(DerivedConfig(min_keyword_frequency=1))
        text = "the the the and and and"
        analysis = analyzer.analyze([text])

        assert "the" not in analysis.keywords
        assert "and" not in analysis.keywords

    def test_analyze_headings_for_industry(self) -> None:
        """Extracts industry from headings."""
        analyzer = ContentAnalyzer()
        analysis = analyzer.analyze(
            texts=["Content here"],
            headings={"h2": ["Healthcare Solutions"]},
        )

        assert "Healthcare" in analysis.industries

    def test_analyze_metadata(self) -> None:
        """Extracts from metadata."""
        analyzer = ContentAnalyzer(DerivedConfig(min_keyword_frequency=1))
        analysis = analyzer.analyze(
            texts=[""],
            metadata={"description": "Leading automation platform"},
        )

        assert "automation" in analysis.keywords or "platform" in analysis.keywords


class TestDerivedQuestionGenerator:
    """Tests for DerivedQuestionGenerator class."""

    def test_generate_empty_context(self) -> None:
        """Handles empty context."""
        generator = DerivedQuestionGenerator()
        context = SiteContext(company_name="TestCo", domain="test.com")

        questions = generator.generate(context)

        # Should return empty or minimal questions
        assert len(questions) <= 5

    def test_generate_with_api_content(self) -> None:
        """Generates API question when API content detected."""
        generator = DerivedQuestionGenerator()
        context = SiteContext(company_name="TestCo", domain="test.com")
        texts = ["Check our API documentation for developers"]

        questions = generator.generate(context, texts)

        api_questions = [q for q in questions if "api" in q.question.lower().replace("'", "")]
        assert len(api_questions) >= 1

    def test_generate_with_integrations(self) -> None:
        """Generates integrations question."""
        generator = DerivedQuestionGenerator()
        context = SiteContext(company_name="TestCo", domain="test.com")
        texts = ["Integrates with Slack, Salesforce, and more"]

        questions = generator.generate(context, texts)

        integration_questions = [q for q in questions if "integrat" in q.question.lower()]
        assert len(integration_questions) >= 1

    def test_generate_with_careers(self) -> None:
        """Generates careers question."""
        generator = DerivedQuestionGenerator()
        context = SiteContext(company_name="TestCo", domain="test.com")
        texts = ["We are hiring! Check our open positions"]

        questions = generator.generate(context, texts)

        career_questions = [q for q in questions if "hiring" in q.question.lower()]
        assert len(career_questions) >= 1

    def test_respects_max_questions(self) -> None:
        """Respects max questions limit."""
        config = DerivedConfig(max_questions=2)
        generator = DerivedQuestionGenerator(config)
        context = SiteContext(company_name="TestCo", domain="test.com")
        texts = [
            "API documentation",
            "Integrations available",
            "We are hiring",
            "Read our blog",
        ]

        questions = generator.generate(context, texts)

        assert len(questions) <= 2

    def test_questions_have_correct_source(self) -> None:
        """Generated questions have correct source."""
        generator = DerivedQuestionGenerator()
        context = SiteContext(company_name="TestCo", domain="test.com")
        texts = ["Check our API documentation"]

        questions = generator.generate(context, texts)

        for q in questions:
            assert q.source in [QuestionSource.CONTENT, QuestionSource.METADATA]

    def test_questions_include_company_name(self) -> None:
        """Questions include the company name."""
        generator = DerivedQuestionGenerator()
        context = SiteContext(company_name="Acme Corp", domain="acme.com")
        texts = ["Check our API documentation"]

        questions = generator.generate(context, texts)

        for q in questions:
            assert "Acme Corp" in q.question

    def test_generate_from_metadata_enterprise(self) -> None:
        """Generates enterprise question from metadata."""
        generator = DerivedQuestionGenerator()
        context = SiteContext(
            company_name="TestCo",
            domain="test.com",
            description="Enterprise-grade security solution",
        )

        questions = generator.generate(context)

        enterprise_questions = [q for q in questions if "enterprise" in q.question.lower()]
        assert len(enterprise_questions) >= 1

    def test_generate_from_metadata_ai(self) -> None:
        """Generates AI question from metadata."""
        generator = DerivedQuestionGenerator()
        context = SiteContext(
            company_name="TestCo",
            domain="test.com",
            description="AI-powered automation platform",
        )

        questions = generator.generate(context)

        ai_questions = [q for q in questions if "ai" in q.question.lower()]
        assert len(ai_questions) >= 1

    def test_deduplicates_questions(self) -> None:
        """Removes duplicate questions."""
        generator = DerivedQuestionGenerator()
        context = SiteContext(company_name="TestCo", domain="test.com")
        # Content that might trigger the same question multiple times
        texts = ["API API API documentation", "Developer API tools"]

        questions = generator.generate(context, texts)

        # Check for duplicates
        question_texts = [q.question.lower() for q in questions]
        assert len(question_texts) == len(set(question_texts))


class TestDeriveQuestionsFunction:
    """Tests for derive_questions convenience function."""

    def test_basic_derivation(self) -> None:
        """Basic derivation works."""
        context = SiteContext(company_name="TestCo", domain="test.com")

        questions = derive_questions(context)

        assert isinstance(questions, list)
        assert len(questions) <= 5

    def test_with_texts(self) -> None:
        """Derivation with texts."""
        context = SiteContext(company_name="TestCo", domain="test.com")
        texts = ["API documentation available"]

        questions = derive_questions(context, texts)

        assert len(questions) >= 1

    def test_with_config(self) -> None:
        """Derivation with custom config."""
        context = SiteContext(company_name="TestCo", domain="test.com")
        config = DerivedConfig(max_questions=1)
        texts = ["API and integrations"]

        questions = derive_questions(context, texts, config)

        assert len(questions) <= 1


class TestQuestionCategories:
    """Tests for question category assignment."""

    def test_api_question_is_offerings(self) -> None:
        """API questions are categorized as offerings."""
        generator = DerivedQuestionGenerator()
        context = SiteContext(company_name="TestCo", domain="test.com")
        texts = ["Check our API documentation"]

        questions = generator.generate(context, texts)

        api_questions = [q for q in questions if "api" in q.question.lower()]
        for q in api_questions:
            assert q.category == QuestionCategory.OFFERINGS

    def test_careers_question_is_identity(self) -> None:
        """Careers questions are categorized as identity."""
        generator = DerivedQuestionGenerator()
        context = SiteContext(company_name="TestCo", domain="test.com")
        texts = ["We are hiring new team members"]

        questions = generator.generate(context, texts)

        career_questions = [q for q in questions if "hiring" in q.question.lower()]
        for q in career_questions:
            assert q.category == QuestionCategory.IDENTITY

    def test_blog_question_is_trust(self) -> None:
        """Blog questions are categorized as trust."""
        generator = DerivedQuestionGenerator()
        context = SiteContext(company_name="TestCo", domain="test.com")
        texts = ["Read our blog for industry insights"]

        questions = generator.generate(context, texts)

        blog_questions = [q for q in questions if "blog" in q.question.lower()]
        for q in blog_questions:
            assert q.category == QuestionCategory.TRUST


class TestKeywordQuestions:
    """Tests for keyword-based question generation."""

    def test_automation_keyword(self) -> None:
        """Generates automation question from keyword."""
        generator = DerivedQuestionGenerator(DerivedConfig(min_keyword_frequency=1))
        context = SiteContext(company_name="TestCo", domain="test.com")
        texts = ["automation automation automation platform"]

        questions = generator.generate(context, texts)

        automation_questions = [q for q in questions if "automat" in q.question.lower()]
        assert len(automation_questions) >= 1

    def test_security_keyword(self) -> None:
        """Generates security question from keyword."""
        generator = DerivedQuestionGenerator(DerivedConfig(min_keyword_frequency=1))
        context = SiteContext(company_name="TestCo", domain="test.com")
        texts = ["security security security certifications"]

        questions = generator.generate(context, texts)

        security_questions = [q for q in questions if "security" in q.question.lower()]
        assert len(security_questions) >= 1
