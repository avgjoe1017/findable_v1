"""Competitor benchmark for comparing sourceability across companies."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from worker.observation.models import ObservationRun
from worker.observation.parser import ParsedObservation


class BenchmarkOutcome(StrEnum):
    """Outcome of a single question benchmark."""

    WIN = "win"  # You were mentioned/cited, competitor was not
    LOSS = "loss"  # Competitor was mentioned/cited, you were not
    TIE = "tie"  # Both mentioned or both not mentioned
    MUTUAL_WIN = "mutual_win"  # Both were mentioned/cited
    MUTUAL_LOSS = "mutual_loss"  # Neither was mentioned


class MentionLevel(StrEnum):
    """Level of mention in AI response."""

    CITED = "cited"  # URL explicitly cited
    MENTIONED = "mentioned"  # Name mentioned but not cited
    OMITTED = "omitted"  # Not mentioned at all


@dataclass
class CompetitorInfo:
    """Information about a competitor."""

    name: str
    domain: str
    branded_terms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "domain": self.domain,
            "branded_terms": self.branded_terms,
        }


@dataclass
class QuestionBenchmark:
    """Benchmark result for a single question across companies."""

    question_id: str
    question_text: str

    # Your company's result
    you_mentioned: bool = False
    you_cited: bool = False
    you_mention_level: MentionLevel = MentionLevel.OMITTED

    # Competitor results by name
    competitor_mentioned: dict[str, bool] = field(default_factory=dict)
    competitor_cited: dict[str, bool] = field(default_factory=dict)
    competitor_mention_level: dict[str, MentionLevel] = field(default_factory=dict)

    # Outcomes per competitor
    outcomes: dict[str, BenchmarkOutcome] = field(default_factory=dict)

    # Aggregate
    total_wins: int = 0
    total_losses: int = 0
    total_ties: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "you_mentioned": self.you_mentioned,
            "you_cited": self.you_cited,
            "you_mention_level": self.you_mention_level.value,
            "competitor_mentioned": self.competitor_mentioned,
            "competitor_cited": self.competitor_cited,
            "outcomes": {k: v.value for k, v in self.outcomes.items()},
            "total_wins": self.total_wins,
            "total_losses": self.total_losses,
            "total_ties": self.total_ties,
        }


@dataclass
class CompetitorResult:
    """Observation results for a single competitor."""

    competitor: CompetitorInfo
    observation_run: ObservationRun | None = None
    parsed_results: dict[str, ParsedObservation] = field(default_factory=dict)

    # Aggregates
    mention_rate: float = 0.0
    citation_rate: float = 0.0
    questions_mentioned: int = 0
    questions_cited: int = 0
    total_questions: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "competitor": self.competitor.to_dict(),
            "mention_rate": round(self.mention_rate, 3),
            "citation_rate": round(self.citation_rate, 3),
            "questions_mentioned": self.questions_mentioned,
            "questions_cited": self.questions_cited,
            "total_questions": self.total_questions,
        }


@dataclass
class HeadToHead:
    """Head-to-head comparison with a single competitor."""

    competitor_name: str
    wins: int = 0
    losses: int = 0
    ties: int = 0
    win_rate: float = 0.0
    mention_advantage: float = 0.0  # Your mention rate - their mention rate
    citation_advantage: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "competitor_name": self.competitor_name,
            "wins": self.wins,
            "losses": self.losses,
            "ties": self.ties,
            "win_rate": round(self.win_rate, 3),
            "mention_advantage": round(self.mention_advantage, 3),
            "citation_advantage": round(self.citation_advantage, 3),
        }


@dataclass
class BenchmarkResult:
    """Complete benchmark result comparing you vs all competitors."""

    # Your company info
    company_name: str
    domain: str
    site_id: UUID | None = None

    # Your observation results
    your_observation: ObservationRun | None = None
    your_parsed: dict[str, ParsedObservation] = field(default_factory=dict)

    # Competitor results
    competitor_results: list[CompetitorResult] = field(default_factory=list)

    # Per-question benchmarks
    question_benchmarks: list[QuestionBenchmark] = field(default_factory=list)

    # Head-to-head summaries
    head_to_heads: list[HeadToHead] = field(default_factory=list)

    # Aggregate metrics
    total_questions: int = 0
    total_competitors: int = 0

    your_mention_rate: float = 0.0
    your_citation_rate: float = 0.0
    avg_competitor_mention_rate: float = 0.0
    avg_competitor_citation_rate: float = 0.0

    overall_wins: int = 0
    overall_losses: int = 0
    overall_ties: int = 0
    overall_win_rate: float = 0.0

    # Questions where you uniquely win/lose
    unique_wins: list[str] = field(default_factory=list)  # question_ids
    unique_losses: list[str] = field(default_factory=list)

    # Timing
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Insights
    insights: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "company_name": self.company_name,
            "domain": self.domain,
            "site_id": str(self.site_id) if self.site_id else None,
            "total_questions": self.total_questions,
            "total_competitors": self.total_competitors,
            "your_mention_rate": round(self.your_mention_rate, 3),
            "your_citation_rate": round(self.your_citation_rate, 3),
            "avg_competitor_mention_rate": round(self.avg_competitor_mention_rate, 3),
            "avg_competitor_citation_rate": round(self.avg_competitor_citation_rate, 3),
            "overall_wins": self.overall_wins,
            "overall_losses": self.overall_losses,
            "overall_ties": self.overall_ties,
            "overall_win_rate": round(self.overall_win_rate, 3),
            "unique_wins": self.unique_wins,
            "unique_losses": self.unique_losses,
            "head_to_heads": [h.to_dict() for h in self.head_to_heads],
            "question_benchmarks": [q.to_dict() for q in self.question_benchmarks],
            "competitor_results": [c.to_dict() for c in self.competitor_results],
            "insights": self.insights,
            "recommendations": self.recommendations,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class CompetitorBenchmarker:
    """Benchmarks a company against its competitors."""

    def benchmark(
        self,
        company_name: str,
        domain: str,
        your_observation: ObservationRun,
        competitor_observations: list[tuple[CompetitorInfo, ObservationRun]],
        your_parsed: dict[str, ParsedObservation] | None = None,
        competitor_parsed: dict[str, dict[str, ParsedObservation]] | None = None,
    ) -> BenchmarkResult:
        """
        Run benchmark comparison between your company and competitors.

        Args:
            company_name: Your company name
            domain: Your domain
            your_observation: Your observation run results
            competitor_observations: List of (CompetitorInfo, ObservationRun) tuples
            your_parsed: Optional parsed observations for your company
            competitor_parsed: Optional dict of competitor_name -> {q_id: ParsedObservation}

        Returns:
            BenchmarkResult with full comparison
        """
        result = BenchmarkResult(
            company_name=company_name,
            domain=domain,
            your_observation=your_observation,
            your_parsed=your_parsed or {},
            started_at=datetime.utcnow(),
        )

        # Process competitor observations
        for competitor_info, obs_run in competitor_observations:
            comp_parsed = (
                competitor_parsed.get(competitor_info.name, {}) if competitor_parsed else {}
            )
            comp_result = self._process_competitor(competitor_info, obs_run, comp_parsed)
            result.competitor_results.append(comp_result)

        result.total_competitors = len(result.competitor_results)

        # Build question benchmarks
        result.question_benchmarks = self._build_question_benchmarks(
            your_observation,
            your_parsed or {},
            result.competitor_results,
        )
        result.total_questions = len(result.question_benchmarks)

        # Calculate head-to-head summaries
        result.head_to_heads = self._calculate_head_to_heads(
            result.question_benchmarks,
            result.competitor_results,
        )

        # Calculate aggregate metrics
        self._calculate_aggregates(result)

        # Find unique wins/losses
        self._find_unique_outcomes(result)

        # Generate insights and recommendations
        result.insights = self._generate_insights(result)
        result.recommendations = self._generate_recommendations(result)

        result.completed_at = datetime.utcnow()
        return result

    def _process_competitor(
        self,
        competitor: CompetitorInfo,
        observation: ObservationRun,
        parsed: dict[str, ParsedObservation],
    ) -> CompetitorResult:
        """Process a competitor's observation results."""
        comp_result = CompetitorResult(
            competitor=competitor,
            observation_run=observation,
            parsed_results=parsed,
            total_questions=len(observation.results),
        )

        # Count mentions and citations
        for obs_result in observation.results:
            q_id = obs_result.question_id
            if q_id in parsed:
                mentioned = parsed[q_id].has_company_mention
                cited = parsed[q_id].has_url_citation
            else:
                mentioned = obs_result.mentions_company
                cited = obs_result.mentions_url

            if mentioned:
                comp_result.questions_mentioned += 1
            if cited:
                comp_result.questions_cited += 1

        # Calculate rates
        if comp_result.total_questions > 0:
            comp_result.mention_rate = comp_result.questions_mentioned / comp_result.total_questions
            comp_result.citation_rate = comp_result.questions_cited / comp_result.total_questions

        return comp_result

    def _build_question_benchmarks(
        self,
        your_observation: ObservationRun,
        your_parsed: dict[str, ParsedObservation],
        competitor_results: list[CompetitorResult],
    ) -> list[QuestionBenchmark]:
        """Build per-question benchmark comparisons."""
        benchmarks = []

        for your_result in your_observation.results:
            q_id = your_result.question_id

            # Get your mention level
            if q_id in your_parsed:
                you_mentioned = your_parsed[q_id].has_company_mention
                you_cited = your_parsed[q_id].has_url_citation
            else:
                you_mentioned = your_result.mentions_company
                you_cited = your_result.mentions_url

            you_level = self._get_mention_level(you_mentioned, you_cited)

            benchmark = QuestionBenchmark(
                question_id=q_id,
                question_text=your_result.question_text,
                you_mentioned=you_mentioned,
                you_cited=you_cited,
                you_mention_level=you_level,
            )

            # Check each competitor
            for comp_result in competitor_results:
                comp_name = comp_result.competitor.name

                # Find matching question result
                comp_obs = None
                for r in comp_result.observation_run.results if comp_result.observation_run else []:
                    if r.question_id == q_id:
                        comp_obs = r
                        break

                if comp_obs is None:
                    # No result for this question
                    benchmark.competitor_mentioned[comp_name] = False
                    benchmark.competitor_cited[comp_name] = False
                    benchmark.competitor_mention_level[comp_name] = MentionLevel.OMITTED
                    benchmark.outcomes[comp_name] = self._determine_outcome(
                        you_mentioned, you_cited, False, False
                    )
                    continue

                # Get competitor mention level
                if q_id in comp_result.parsed_results:
                    comp_mentioned = comp_result.parsed_results[q_id].has_company_mention
                    comp_cited = comp_result.parsed_results[q_id].has_url_citation
                else:
                    comp_mentioned = comp_obs.mentions_company
                    comp_cited = comp_obs.mentions_url

                comp_level = self._get_mention_level(comp_mentioned, comp_cited)

                benchmark.competitor_mentioned[comp_name] = comp_mentioned
                benchmark.competitor_cited[comp_name] = comp_cited
                benchmark.competitor_mention_level[comp_name] = comp_level

                # Determine outcome
                outcome = self._determine_outcome(
                    you_mentioned, you_cited, comp_mentioned, comp_cited
                )
                benchmark.outcomes[comp_name] = outcome

                # Update counts
                if outcome == BenchmarkOutcome.WIN:
                    benchmark.total_wins += 1
                elif outcome == BenchmarkOutcome.LOSS:
                    benchmark.total_losses += 1
                else:
                    benchmark.total_ties += 1

            benchmarks.append(benchmark)

        return benchmarks

    def _get_mention_level(self, mentioned: bool, cited: bool) -> MentionLevel:
        """Determine mention level from flags."""
        if cited:
            return MentionLevel.CITED
        elif mentioned:
            return MentionLevel.MENTIONED
        return MentionLevel.OMITTED

    def _determine_outcome(
        self,
        you_mentioned: bool,
        you_cited: bool,
        comp_mentioned: bool,
        comp_cited: bool,
    ) -> BenchmarkOutcome:
        """Determine benchmark outcome for a question."""
        you_visible = you_mentioned or you_cited
        comp_visible = comp_mentioned or comp_cited

        if you_visible and comp_visible:
            # Both visible - compare citation level
            if you_cited and not comp_cited:
                return BenchmarkOutcome.WIN
            elif comp_cited and not you_cited:
                return BenchmarkOutcome.LOSS
            return BenchmarkOutcome.MUTUAL_WIN
        elif you_visible and not comp_visible:
            return BenchmarkOutcome.WIN
        elif comp_visible and not you_visible:
            return BenchmarkOutcome.LOSS
        else:
            return BenchmarkOutcome.MUTUAL_LOSS

    def _calculate_head_to_heads(
        self,
        benchmarks: list[QuestionBenchmark],
        competitor_results: list[CompetitorResult],
    ) -> list[HeadToHead]:
        """Calculate head-to-head summaries for each competitor."""
        head_to_heads = []

        for comp_result in competitor_results:
            comp_name = comp_result.competitor.name
            h2h = HeadToHead(competitor_name=comp_name)

            for benchmark in benchmarks:
                outcome = benchmark.outcomes.get(comp_name)
                if outcome == BenchmarkOutcome.WIN:
                    h2h.wins += 1
                elif outcome == BenchmarkOutcome.LOSS:
                    h2h.losses += 1
                else:
                    h2h.ties += 1

            # Calculate rates
            total = h2h.wins + h2h.losses + h2h.ties
            if total > 0:
                h2h.win_rate = h2h.wins / total

            # Calculate advantages (will be set in _calculate_aggregates)
            h2h.mention_advantage = 0.0
            h2h.citation_advantage = 0.0

            head_to_heads.append(h2h)

        return head_to_heads

    def _calculate_aggregates(self, result: BenchmarkResult) -> None:
        """Calculate aggregate metrics."""
        # Your rates from observation
        if result.your_observation:
            result.your_mention_rate = result.your_observation.company_mention_rate
            result.your_citation_rate = result.your_observation.citation_rate

        # Average competitor rates
        if result.competitor_results:
            total_mention = sum(c.mention_rate for c in result.competitor_results)
            total_citation = sum(c.citation_rate for c in result.competitor_results)
            result.avg_competitor_mention_rate = total_mention / len(result.competitor_results)
            result.avg_competitor_citation_rate = total_citation / len(result.competitor_results)

        # Update head-to-head advantages
        for h2h in result.head_to_heads:
            comp_result = next(
                (c for c in result.competitor_results if c.competitor.name == h2h.competitor_name),
                None,
            )
            if comp_result:
                h2h.mention_advantage = result.your_mention_rate - comp_result.mention_rate
                h2h.citation_advantage = result.your_citation_rate - comp_result.citation_rate

        # Overall wins/losses
        for benchmark in result.question_benchmarks:
            result.overall_wins += benchmark.total_wins
            result.overall_losses += benchmark.total_losses
            result.overall_ties += benchmark.total_ties

        # Overall win rate
        total_matchups = result.overall_wins + result.overall_losses + result.overall_ties
        if total_matchups > 0:
            result.overall_win_rate = result.overall_wins / total_matchups

    def _find_unique_outcomes(self, result: BenchmarkResult) -> None:
        """Find questions where you uniquely win or lose against all competitors."""
        for benchmark in result.question_benchmarks:
            if not benchmark.outcomes:
                continue

            outcomes = list(benchmark.outcomes.values())

            # Unique win: you win against all competitors
            if all(o == BenchmarkOutcome.WIN for o in outcomes):
                result.unique_wins.append(benchmark.question_id)

            # Unique loss: you lose against all competitors
            elif all(o == BenchmarkOutcome.LOSS for o in outcomes):
                result.unique_losses.append(benchmark.question_id)

    def _generate_insights(self, result: BenchmarkResult) -> list[str]:
        """Generate insights from benchmark results."""
        insights = []

        # Overall position
        if result.overall_win_rate > 0.6:
            insights.append(
                f"Strong competitive position: {result.overall_win_rate:.0%} win rate "
                "across all competitor matchups."
            )
        elif result.overall_win_rate < 0.4:
            insights.append(
                f"Competitive disadvantage: only {result.overall_win_rate:.0%} win rate. "
                "Competitors are being mentioned more frequently."
            )

        # Mention rate comparison
        mention_diff = result.your_mention_rate - result.avg_competitor_mention_rate
        if mention_diff > 0.15:
            insights.append(
                f"Mention advantage: you're mentioned {mention_diff:.0%} more often "
                "than average competitor."
            )
        elif mention_diff < -0.15:
            insights.append(
                f"Mention gap: competitors are mentioned {-mention_diff:.0%} more often. "
                "Focus on increasing AI visibility."
            )

        # Citation advantage
        citation_diff = result.your_citation_rate - result.avg_competitor_citation_rate
        if citation_diff > 0.1:
            insights.append(
                f"Citation leader: your site is cited {citation_diff:.0%} more often "
                "than competitors."
            )
        elif citation_diff < -0.1:
            insights.append(
                "Citation gap: competitors get more direct citations. "
                "Improve structured data and authoritative content."
            )

        # Unique wins/losses
        if len(result.unique_wins) > 3:
            insights.append(
                f"Dominating {len(result.unique_wins)} topics where no competitor "
                "gets mentioned."
            )
        if len(result.unique_losses) > 3:
            insights.append(
                f"Missing from {len(result.unique_losses)} topics where all competitors "
                "get mentioned."
            )

        # Per-competitor insights
        for h2h in result.head_to_heads:
            if h2h.win_rate > 0.7:
                insights.append(
                    f"Significantly outperforming {h2h.competitor_name} "
                    f"({h2h.win_rate:.0%} win rate)."
                )
            elif h2h.win_rate < 0.3:
                insights.append(
                    f"Trailing {h2h.competitor_name} significantly "
                    f"({1 - h2h.win_rate:.0%} loss rate)."
                )

        return insights

    def _generate_recommendations(self, result: BenchmarkResult) -> list[str]:
        """Generate recommendations from benchmark results."""
        recommendations = []

        # Based on unique losses
        if result.unique_losses:
            recommendations.append(
                f"Priority content gap: create/improve content for "
                f"{len(result.unique_losses)} topics where competitors dominate."
            )

        # Based on citation gap
        if result.your_citation_rate < result.avg_competitor_citation_rate:
            recommendations.append(
                "Improve citation likelihood: add schema markup, authoritative "
                "sources, and canonical URLs to match competitors."
            )

        # Based on specific competitor advantages
        for h2h in result.head_to_heads:
            if h2h.mention_advantage < -0.2:
                recommendations.append(
                    f"Analyze {h2h.competitor_name}'s content strategy: "
                    f"they have {-h2h.mention_advantage:.0%} mention advantage."
                )

        # Based on overall position
        if result.overall_win_rate < 0.5:
            recommendations.append(
                "Competitive content audit: review what topics competitors " "cover that you don't."
            )

        return recommendations


def run_benchmark(
    company_name: str,
    domain: str,
    your_observation: ObservationRun,
    competitor_observations: list[tuple[CompetitorInfo, ObservationRun]],
    your_parsed: dict[str, ParsedObservation] | None = None,
    competitor_parsed: dict[str, dict[str, ParsedObservation]] | None = None,
) -> BenchmarkResult:
    """
    Convenience function to run competitor benchmark.

    Args:
        company_name: Your company name
        domain: Your domain
        your_observation: Your observation run
        competitor_observations: List of (CompetitorInfo, ObservationRun)
        your_parsed: Optional parsed results for your company
        competitor_parsed: Optional parsed results by competitor name

    Returns:
        BenchmarkResult with full comparison
    """
    benchmarker = CompetitorBenchmarker()
    return benchmarker.benchmark(
        company_name=company_name,
        domain=domain,
        your_observation=your_observation,
        competitor_observations=competitor_observations,
        your_parsed=your_parsed,
        competitor_parsed=competitor_parsed,
    )
