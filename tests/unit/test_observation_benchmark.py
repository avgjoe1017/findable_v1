"""Tests for competitor benchmark."""

from uuid import uuid4

from worker.observation.benchmark import (
    BenchmarkOutcome,
    BenchmarkResult,
    CompetitorBenchmarker,
    CompetitorInfo,
    CompetitorResult,
    HeadToHead,
    MentionLevel,
    QuestionBenchmark,
    run_benchmark,
)
from worker.observation.models import (
    ObservationResponse,
    ObservationResult,
    ObservationRun,
    ObservationStatus,
    ProviderType,
)
from worker.observation.parser import ParsedObservation


def make_observation_result(
    question_id: str = "q1",
    company_name: str = "Test Company",
    domain: str = "test.com",
    mentions_company: bool = True,
    mentions_url: bool = False,
) -> ObservationResult:
    """Create a test ObservationResult."""
    return ObservationResult(
        question_id=question_id,
        question_text=f"Question {question_id}",
        company_name=company_name,
        domain=domain,
        response=ObservationResponse(
            request_id=uuid4(),
            provider=ProviderType.MOCK,
            model="mock",
            content=f"Test response about {company_name}",
            success=True,
        ),
        mentions_company=mentions_company,
        mentions_domain=mentions_company,
        mentions_url=mentions_url,
        cited_urls=[f"https://{domain}"] if mentions_url else [],
    )


def make_observation_run(
    company_name: str = "Test Company",
    domain: str = "test.com",
    results: list[ObservationResult] | None = None,
) -> ObservationRun:
    """Create a test ObservationRun."""
    if results is None:
        results = [make_observation_result(company_name=company_name, domain=domain)]

    run = ObservationRun(
        site_id=uuid4(),
        company_name=company_name,
        domain=domain,
        total_questions=len(results),
        status=ObservationStatus.COMPLETED,
    )

    for result in results:
        run.add_result(result)

    return run


class TestCompetitorInfo:
    """Tests for CompetitorInfo dataclass."""

    def test_create_competitor_info(self) -> None:
        """Can create competitor info."""
        info = CompetitorInfo(
            name="Competitor Corp",
            domain="competitor.com",
            branded_terms=["CompProd"],
        )

        assert info.name == "Competitor Corp"
        assert info.domain == "competitor.com"
        assert "CompProd" in info.branded_terms

    def test_to_dict(self) -> None:
        """Converts to dict."""
        info = CompetitorInfo(name="Test", domain="test.com")

        d = info.to_dict()

        assert d["name"] == "Test"
        assert d["domain"] == "test.com"


class TestMentionLevel:
    """Tests for MentionLevel enum."""

    def test_mention_levels(self) -> None:
        """Has expected values."""
        assert MentionLevel.CITED.value == "cited"
        assert MentionLevel.MENTIONED.value == "mentioned"
        assert MentionLevel.OMITTED.value == "omitted"


class TestBenchmarkOutcome:
    """Tests for BenchmarkOutcome enum."""

    def test_outcomes(self) -> None:
        """Has expected values."""
        assert BenchmarkOutcome.WIN.value == "win"
        assert BenchmarkOutcome.LOSS.value == "loss"
        assert BenchmarkOutcome.TIE.value == "tie"
        assert BenchmarkOutcome.MUTUAL_WIN.value == "mutual_win"
        assert BenchmarkOutcome.MUTUAL_LOSS.value == "mutual_loss"


class TestQuestionBenchmark:
    """Tests for QuestionBenchmark dataclass."""

    def test_create_benchmark(self) -> None:
        """Can create a question benchmark."""
        benchmark = QuestionBenchmark(
            question_id="q1",
            question_text="Test question",
            you_mentioned=True,
            you_cited=False,
        )

        assert benchmark.question_id == "q1"
        assert benchmark.you_mentioned is True

    def test_to_dict(self) -> None:
        """Converts to dict."""
        benchmark = QuestionBenchmark(
            question_id="q1",
            question_text="Test",
            you_mention_level=MentionLevel.MENTIONED,
            outcomes={"Competitor": BenchmarkOutcome.WIN},
        )

        d = benchmark.to_dict()

        assert d["question_id"] == "q1"
        assert d["you_mention_level"] == "mentioned"
        assert d["outcomes"]["Competitor"] == "win"


class TestCompetitorResult:
    """Tests for CompetitorResult dataclass."""

    def test_create_result(self) -> None:
        """Can create a competitor result."""
        competitor = CompetitorInfo(name="Comp", domain="comp.com")
        result = CompetitorResult(
            competitor=competitor,
            mention_rate=0.75,
            citation_rate=0.25,
        )

        assert result.competitor.name == "Comp"
        assert result.mention_rate == 0.75

    def test_to_dict(self) -> None:
        """Converts to dict."""
        competitor = CompetitorInfo(name="Test", domain="test.com")
        result = CompetitorResult(
            competitor=competitor,
            questions_mentioned=3,
            total_questions=4,
        )

        d = result.to_dict()

        assert d["questions_mentioned"] == 3
        assert d["competitor"]["name"] == "Test"


class TestHeadToHead:
    """Tests for HeadToHead dataclass."""

    def test_create_head_to_head(self) -> None:
        """Can create head to head."""
        h2h = HeadToHead(
            competitor_name="Rival Inc",
            wins=5,
            losses=3,
            ties=2,
        )

        assert h2h.wins == 5
        assert h2h.losses == 3

    def test_to_dict(self) -> None:
        """Converts to dict."""
        h2h = HeadToHead(
            competitor_name="Test",
            win_rate=0.6,
            mention_advantage=0.15,
        )

        d = h2h.to_dict()

        assert d["win_rate"] == 0.6
        assert d["mention_advantage"] == 0.15


class TestBenchmarkResult:
    """Tests for BenchmarkResult dataclass."""

    def test_create_result(self) -> None:
        """Can create benchmark result."""
        result = BenchmarkResult(
            company_name="My Company",
            domain="mycompany.com",
            total_questions=10,
            total_competitors=2,
        )

        assert result.company_name == "My Company"
        assert result.total_competitors == 2

    def test_to_dict(self) -> None:
        """Converts to dict."""
        result = BenchmarkResult(
            company_name="Test",
            domain="test.com",
            overall_win_rate=0.65,
        )

        d = result.to_dict()

        assert d["company_name"] == "Test"
        assert d["overall_win_rate"] == 0.65


class TestCompetitorBenchmarker:
    """Tests for CompetitorBenchmarker class."""

    def test_create_benchmarker(self) -> None:
        """Can create a benchmarker."""
        benchmarker = CompetitorBenchmarker()
        assert benchmarker is not None

    def test_benchmark_single_competitor_win(self) -> None:
        """Detects win when you are mentioned but competitor is not."""
        benchmarker = CompetitorBenchmarker()

        # You are mentioned
        your_results = [
            make_observation_result("q1", "My Company", "mycompany.com", True, False),
        ]
        your_obs = make_observation_run("My Company", "mycompany.com", your_results)

        # Competitor is not mentioned
        comp_results = [
            make_observation_result("q1", "Competitor", "competitor.com", False, False),
        ]
        comp_obs = make_observation_run("Competitor", "competitor.com", comp_results)

        competitor = CompetitorInfo(name="Competitor", domain="competitor.com")

        result = benchmarker.benchmark(
            company_name="My Company",
            domain="mycompany.com",
            your_observation=your_obs,
            competitor_observations=[(competitor, comp_obs)],
        )

        assert result.overall_wins >= 1
        assert result.question_benchmarks[0].outcomes["Competitor"] == BenchmarkOutcome.WIN

    def test_benchmark_single_competitor_loss(self) -> None:
        """Detects loss when competitor is mentioned but you are not."""
        benchmarker = CompetitorBenchmarker()

        # You are not mentioned
        your_results = [
            make_observation_result("q1", "My Company", "mycompany.com", False, False),
        ]
        your_obs = make_observation_run("My Company", "mycompany.com", your_results)

        # Competitor is mentioned
        comp_results = [
            make_observation_result("q1", "Competitor", "competitor.com", True, False),
        ]
        comp_obs = make_observation_run("Competitor", "competitor.com", comp_results)

        competitor = CompetitorInfo(name="Competitor", domain="competitor.com")

        result = benchmarker.benchmark(
            company_name="My Company",
            domain="mycompany.com",
            your_observation=your_obs,
            competitor_observations=[(competitor, comp_obs)],
        )

        assert result.overall_losses >= 1
        assert result.question_benchmarks[0].outcomes["Competitor"] == BenchmarkOutcome.LOSS

    def test_benchmark_mutual_win(self) -> None:
        """Detects mutual win when both are mentioned."""
        benchmarker = CompetitorBenchmarker()

        your_results = [
            make_observation_result("q1", "My Company", "mycompany.com", True, False),
        ]
        your_obs = make_observation_run("My Company", "mycompany.com", your_results)

        comp_results = [
            make_observation_result("q1", "Competitor", "competitor.com", True, False),
        ]
        comp_obs = make_observation_run("Competitor", "competitor.com", comp_results)

        competitor = CompetitorInfo(name="Competitor", domain="competitor.com")

        result = benchmarker.benchmark(
            company_name="My Company",
            domain="mycompany.com",
            your_observation=your_obs,
            competitor_observations=[(competitor, comp_obs)],
        )

        assert result.question_benchmarks[0].outcomes["Competitor"] == BenchmarkOutcome.MUTUAL_WIN

    def test_benchmark_mutual_loss(self) -> None:
        """Detects mutual loss when neither is mentioned."""
        benchmarker = CompetitorBenchmarker()

        your_results = [
            make_observation_result("q1", "My Company", "mycompany.com", False, False),
        ]
        your_obs = make_observation_run("My Company", "mycompany.com", your_results)

        comp_results = [
            make_observation_result("q1", "Competitor", "competitor.com", False, False),
        ]
        comp_obs = make_observation_run("Competitor", "competitor.com", comp_results)

        competitor = CompetitorInfo(name="Competitor", domain="competitor.com")

        result = benchmarker.benchmark(
            company_name="My Company",
            domain="mycompany.com",
            your_observation=your_obs,
            competitor_observations=[(competitor, comp_obs)],
        )

        assert result.question_benchmarks[0].outcomes["Competitor"] == BenchmarkOutcome.MUTUAL_LOSS

    def test_benchmark_citation_advantage(self) -> None:
        """Citation beats mention in head-to-head."""
        benchmarker = CompetitorBenchmarker()

        # You are cited
        your_results = [
            make_observation_result("q1", "My Company", "mycompany.com", True, True),
        ]
        your_obs = make_observation_run("My Company", "mycompany.com", your_results)

        # Competitor is only mentioned
        comp_results = [
            make_observation_result("q1", "Competitor", "competitor.com", True, False),
        ]
        comp_obs = make_observation_run("Competitor", "competitor.com", comp_results)

        competitor = CompetitorInfo(name="Competitor", domain="competitor.com")

        result = benchmarker.benchmark(
            company_name="My Company",
            domain="mycompany.com",
            your_observation=your_obs,
            competitor_observations=[(competitor, comp_obs)],
        )

        # Citation beats mention
        assert result.question_benchmarks[0].outcomes["Competitor"] == BenchmarkOutcome.WIN

    def test_benchmark_multiple_questions(self) -> None:
        """Handles multiple questions."""
        benchmarker = CompetitorBenchmarker()

        your_results = [
            make_observation_result("q1", "My Company", "mycompany.com", True, False),
            make_observation_result("q2", "My Company", "mycompany.com", False, False),
            make_observation_result("q3", "My Company", "mycompany.com", True, True),
        ]
        your_obs = make_observation_run("My Company", "mycompany.com", your_results)

        comp_results = [
            make_observation_result("q1", "Competitor", "competitor.com", False, False),
            make_observation_result("q2", "Competitor", "competitor.com", True, False),
            make_observation_result("q3", "Competitor", "competitor.com", True, False),
        ]
        comp_obs = make_observation_run("Competitor", "competitor.com", comp_results)

        competitor = CompetitorInfo(name="Competitor", domain="competitor.com")

        result = benchmarker.benchmark(
            company_name="My Company",
            domain="mycompany.com",
            your_observation=your_obs,
            competitor_observations=[(competitor, comp_obs)],
        )

        assert result.total_questions == 3
        assert len(result.question_benchmarks) == 3

    def test_benchmark_multiple_competitors(self) -> None:
        """Handles multiple competitors."""
        benchmarker = CompetitorBenchmarker()

        your_results = [
            make_observation_result("q1", "My Company", "mycompany.com", True, False),
        ]
        your_obs = make_observation_run("My Company", "mycompany.com", your_results)

        comp1_results = [
            make_observation_result("q1", "Competitor1", "comp1.com", False, False),
        ]
        comp1_obs = make_observation_run("Competitor1", "comp1.com", comp1_results)

        comp2_results = [
            make_observation_result("q1", "Competitor2", "comp2.com", True, False),
        ]
        comp2_obs = make_observation_run("Competitor2", "comp2.com", comp2_results)

        competitors = [
            (CompetitorInfo(name="Competitor1", domain="comp1.com"), comp1_obs),
            (CompetitorInfo(name="Competitor2", domain="comp2.com"), comp2_obs),
        ]

        result = benchmarker.benchmark(
            company_name="My Company",
            domain="mycompany.com",
            your_observation=your_obs,
            competitor_observations=competitors,
        )

        assert result.total_competitors == 2
        assert len(result.head_to_heads) == 2

    def test_calculates_head_to_head(self) -> None:
        """Calculates head-to-head stats."""
        benchmarker = CompetitorBenchmarker()

        your_results = [
            make_observation_result("q1", "My", "my.com", True, False),
            make_observation_result("q2", "My", "my.com", True, False),
            make_observation_result("q3", "My", "my.com", False, False),
        ]
        your_obs = make_observation_run("My", "my.com", your_results)

        comp_results = [
            make_observation_result("q1", "Comp", "comp.com", False, False),  # Win
            make_observation_result("q2", "Comp", "comp.com", True, False),  # Tie
            make_observation_result("q3", "Comp", "comp.com", True, False),  # Loss
        ]
        comp_obs = make_observation_run("Comp", "comp.com", comp_results)

        competitor = CompetitorInfo(name="Comp", domain="comp.com")

        result = benchmarker.benchmark(
            company_name="My",
            domain="my.com",
            your_observation=your_obs,
            competitor_observations=[(competitor, comp_obs)],
        )

        h2h = result.head_to_heads[0]
        assert h2h.wins == 1
        assert h2h.losses == 1
        assert h2h.ties == 1

    def test_calculates_win_rate(self) -> None:
        """Calculates overall win rate."""
        benchmarker = CompetitorBenchmarker()

        # 2 wins, 1 loss
        your_results = [
            make_observation_result("q1", "My", "my.com", True, False),
            make_observation_result("q2", "My", "my.com", True, False),
            make_observation_result("q3", "My", "my.com", False, False),
        ]
        your_obs = make_observation_run("My", "my.com", your_results)

        comp_results = [
            make_observation_result("q1", "Comp", "comp.com", False, False),
            make_observation_result("q2", "Comp", "comp.com", False, False),
            make_observation_result("q3", "Comp", "comp.com", True, False),
        ]
        comp_obs = make_observation_run("Comp", "comp.com", comp_results)

        competitor = CompetitorInfo(name="Comp", domain="comp.com")

        result = benchmarker.benchmark(
            company_name="My",
            domain="my.com",
            your_observation=your_obs,
            competitor_observations=[(competitor, comp_obs)],
        )

        assert result.overall_wins == 2
        assert result.overall_losses == 1
        # Win rate: 2/3 = 0.666...
        assert 0.66 < result.overall_win_rate < 0.67

    def test_finds_unique_wins(self) -> None:
        """Identifies questions where you win against all competitors."""
        benchmarker = CompetitorBenchmarker()

        your_results = [
            make_observation_result("q1", "My", "my.com", True, False),
        ]
        your_obs = make_observation_run("My", "my.com", your_results)

        comp1_results = [make_observation_result("q1", "C1", "c1.com", False, False)]
        comp2_results = [make_observation_result("q1", "C2", "c2.com", False, False)]

        competitors = [
            (
                CompetitorInfo(name="C1", domain="c1.com"),
                make_observation_run("C1", "c1.com", comp1_results),
            ),
            (
                CompetitorInfo(name="C2", domain="c2.com"),
                make_observation_run("C2", "c2.com", comp2_results),
            ),
        ]

        result = benchmarker.benchmark(
            company_name="My",
            domain="my.com",
            your_observation=your_obs,
            competitor_observations=competitors,
        )

        assert "q1" in result.unique_wins

    def test_finds_unique_losses(self) -> None:
        """Identifies questions where you lose against all competitors."""
        benchmarker = CompetitorBenchmarker()

        your_results = [
            make_observation_result("q1", "My", "my.com", False, False),
        ]
        your_obs = make_observation_run("My", "my.com", your_results)

        comp1_results = [make_observation_result("q1", "C1", "c1.com", True, False)]
        comp2_results = [make_observation_result("q1", "C2", "c2.com", True, False)]

        competitors = [
            (
                CompetitorInfo(name="C1", domain="c1.com"),
                make_observation_run("C1", "c1.com", comp1_results),
            ),
            (
                CompetitorInfo(name="C2", domain="c2.com"),
                make_observation_run("C2", "c2.com", comp2_results),
            ),
        ]

        result = benchmarker.benchmark(
            company_name="My",
            domain="my.com",
            your_observation=your_obs,
            competitor_observations=competitors,
        )

        assert "q1" in result.unique_losses

    def test_uses_parsed_observations(self) -> None:
        """Uses parsed observations when provided."""
        benchmarker = CompetitorBenchmarker()

        your_results = [
            make_observation_result("q1", "My", "my.com", False, False),  # Raw says no
        ]
        your_obs = make_observation_run("My", "my.com", your_results)

        # But parsed says yes
        your_parsed = {"q1": ParsedObservation(has_company_mention=True, has_url_citation=True)}

        comp_results = [make_observation_result("q1", "Comp", "comp.com", False, False)]
        comp_obs = make_observation_run("Comp", "comp.com", comp_results)

        competitor = CompetitorInfo(name="Comp", domain="comp.com")

        result = benchmarker.benchmark(
            company_name="My",
            domain="my.com",
            your_observation=your_obs,
            competitor_observations=[(competitor, comp_obs)],
            your_parsed=your_parsed,
        )

        # Should use parsed (you cited) vs raw (competitor not mentioned) = WIN
        assert result.question_benchmarks[0].you_cited is True
        assert result.question_benchmarks[0].outcomes["Comp"] == BenchmarkOutcome.WIN

    def test_generates_insights(self) -> None:
        """Generates insights from results."""
        benchmarker = CompetitorBenchmarker()

        # Create scenario with clear competitive advantage
        your_results = [
            make_observation_result(f"q{i}", "My", "my.com", True, False) for i in range(5)
        ]
        your_obs = make_observation_run("My", "my.com", your_results)

        comp_results = [
            make_observation_result(f"q{i}", "Comp", "comp.com", False, False) for i in range(5)
        ]
        comp_obs = make_observation_run("Comp", "comp.com", comp_results)

        competitor = CompetitorInfo(name="Comp", domain="comp.com")

        result = benchmarker.benchmark(
            company_name="My",
            domain="my.com",
            your_observation=your_obs,
            competitor_observations=[(competitor, comp_obs)],
        )

        assert len(result.insights) > 0

    def test_generates_recommendations(self) -> None:
        """Generates recommendations from results."""
        benchmarker = CompetitorBenchmarker()

        # Create scenario with competitive disadvantage
        your_results = [
            make_observation_result(f"q{i}", "My", "my.com", False, False) for i in range(5)
        ]
        your_obs = make_observation_run("My", "my.com", your_results)

        comp_results = [
            make_observation_result(f"q{i}", "Comp", "comp.com", True, True) for i in range(5)
        ]
        comp_obs = make_observation_run("Comp", "comp.com", comp_results)

        competitor = CompetitorInfo(name="Comp", domain="comp.com")

        result = benchmarker.benchmark(
            company_name="My",
            domain="my.com",
            your_observation=your_obs,
            competitor_observations=[(competitor, comp_obs)],
        )

        assert len(result.recommendations) > 0

    def test_calculates_mention_rates(self) -> None:
        """Calculates mention and citation rates."""
        benchmarker = CompetitorBenchmarker()

        your_results = [
            make_observation_result("q1", "My", "my.com", True, True),
            make_observation_result("q2", "My", "my.com", True, False),
        ]
        your_obs = make_observation_run("My", "my.com", your_results)

        comp_results = [
            make_observation_result("q1", "Comp", "comp.com", True, False),
            make_observation_result("q2", "Comp", "comp.com", False, False),
        ]
        comp_obs = make_observation_run("Comp", "comp.com", comp_results)

        competitor = CompetitorInfo(name="Comp", domain="comp.com")

        result = benchmarker.benchmark(
            company_name="My",
            domain="my.com",
            your_observation=your_obs,
            competitor_observations=[(competitor, comp_obs)],
        )

        # Your rates come from observation run
        assert result.your_mention_rate == 1.0  # Both mentioned
        assert result.your_citation_rate == 0.5  # 1 of 2 cited

        # Competitor average
        assert result.avg_competitor_mention_rate == 0.5  # 1 of 2 mentioned


class TestConvenienceFunction:
    """Tests for run_benchmark convenience function."""

    def test_run_benchmark_function(self) -> None:
        """Convenience function works."""
        your_results = [
            make_observation_result("q1", "My", "my.com", True, False),
        ]
        your_obs = make_observation_run("My", "my.com", your_results)

        comp_results = [
            make_observation_result("q1", "Comp", "comp.com", False, False),
        ]
        comp_obs = make_observation_run("Comp", "comp.com", comp_results)

        competitor = CompetitorInfo(name="Comp", domain="comp.com")

        result = run_benchmark(
            company_name="My",
            domain="my.com",
            your_observation=your_obs,
            competitor_observations=[(competitor, comp_obs)],
        )

        assert isinstance(result, BenchmarkResult)
        assert result.total_questions == 1
        assert result.total_competitors == 1


class TestEdgeCases:
    """Tests for edge cases."""

    def test_no_competitors(self) -> None:
        """Handles no competitors."""
        benchmarker = CompetitorBenchmarker()

        your_results = [
            make_observation_result("q1", "My", "my.com", True, False),
        ]
        your_obs = make_observation_run("My", "my.com", your_results)

        result = benchmarker.benchmark(
            company_name="My",
            domain="my.com",
            your_observation=your_obs,
            competitor_observations=[],
        )

        assert result.total_competitors == 0
        assert len(result.head_to_heads) == 0

    def test_missing_competitor_question(self) -> None:
        """Handles missing question in competitor results."""
        benchmarker = CompetitorBenchmarker()

        your_results = [
            make_observation_result("q1", "My", "my.com", True, False),
            make_observation_result("q2", "My", "my.com", True, False),
        ]
        your_obs = make_observation_run("My", "my.com", your_results)

        # Competitor only has q1
        comp_results = [
            make_observation_result("q1", "Comp", "comp.com", True, False),
        ]
        comp_obs = make_observation_run("Comp", "comp.com", comp_results)

        competitor = CompetitorInfo(name="Comp", domain="comp.com")

        result = benchmarker.benchmark(
            company_name="My",
            domain="my.com",
            your_observation=your_obs,
            competitor_observations=[(competitor, comp_obs)],
        )

        # q2 should be a win since competitor has no result
        q2_benchmark = next(b for b in result.question_benchmarks if b.question_id == "q2")
        assert q2_benchmark.outcomes["Comp"] == BenchmarkOutcome.WIN

    def test_empty_observations(self) -> None:
        """Handles empty observation runs."""
        benchmarker = CompetitorBenchmarker()

        your_obs = make_observation_run("My", "my.com", [])
        comp_obs = make_observation_run("Comp", "comp.com", [])

        competitor = CompetitorInfo(name="Comp", domain="comp.com")

        result = benchmarker.benchmark(
            company_name="My",
            domain="my.com",
            your_observation=your_obs,
            competitor_observations=[(competitor, comp_obs)],
        )

        assert result.total_questions == 0
        assert len(result.question_benchmarks) == 0
