"""Comparison between simulation predictions and observation results."""

from dataclasses import dataclass, field
from enum import Enum

from worker.observation.models import ObservationResult, ObservationRun
from worker.observation.parser import ParsedObservation
from worker.simulation.runner import Answerability, QuestionResult, SimulationResult


class OutcomeMatch(str, Enum):
    """How well simulation matched observation."""

    CORRECT = "correct"  # Simulation prediction matched reality
    OPTIMISTIC = "optimistic"  # Simulation was more positive than reality
    PESSIMISTIC = "pessimistic"  # Simulation was more negative than reality
    UNKNOWN = "unknown"  # Can't determine


class SourceabilityOutcome(str, Enum):
    """Actual sourceability outcome from observation."""

    CITED = "cited"  # Company was explicitly cited with URL
    MENTIONED = "mentioned"  # Company was mentioned but not cited
    OMITTED = "omitted"  # Company was not mentioned
    COMPETITOR_CITED = "competitor_cited"  # A competitor was cited instead
    REFUSED = "refused"  # Model refused to answer


@dataclass
class QuestionComparison:
    """Comparison of simulation vs observation for a single question."""

    question_id: str
    question_text: str

    # Simulation prediction
    sim_answerability: Answerability | None = None
    sim_score: float = 0.0
    sim_signals_found: int = 0
    sim_signals_total: int = 0

    # Observation result
    obs_mentioned: bool = False
    obs_cited: bool = False
    obs_sentiment: str = ""
    obs_confidence: str = ""

    # Comparison
    outcome_match: OutcomeMatch = OutcomeMatch.UNKNOWN
    sourceability_outcome: SourceabilityOutcome = SourceabilityOutcome.OMITTED

    # Delta analysis
    prediction_accurate: bool = False
    explanation: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "sim_answerability": self.sim_answerability.value if self.sim_answerability else None,
            "sim_score": round(self.sim_score, 2),
            "sim_signals_found": self.sim_signals_found,
            "sim_signals_total": self.sim_signals_total,
            "obs_mentioned": self.obs_mentioned,
            "obs_cited": self.obs_cited,
            "obs_sentiment": self.obs_sentiment,
            "obs_confidence": self.obs_confidence,
            "outcome_match": self.outcome_match.value,
            "sourceability_outcome": self.sourceability_outcome.value,
            "prediction_accurate": self.prediction_accurate,
            "explanation": self.explanation,
        }


@dataclass
class ComparisonSummary:
    """Summary of simulation vs observation comparison."""

    # Counts
    total_questions: int = 0
    correct_predictions: int = 0
    optimistic_predictions: int = 0
    pessimistic_predictions: int = 0
    unknown_predictions: int = 0

    # Rates
    prediction_accuracy: float = 0.0
    mention_rate_sim: float = 0.0  # What simulation predicted
    mention_rate_obs: float = 0.0  # What actually happened
    citation_rate_obs: float = 0.0

    # Deltas
    mention_rate_delta: float = 0.0
    score_correlation: float = 0.0

    # Per-question comparisons
    comparisons: list[QuestionComparison] = field(default_factory=list)

    # Insights
    insights: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_questions": self.total_questions,
            "correct_predictions": self.correct_predictions,
            "optimistic_predictions": self.optimistic_predictions,
            "pessimistic_predictions": self.pessimistic_predictions,
            "prediction_accuracy": round(self.prediction_accuracy, 3),
            "mention_rate_sim": round(self.mention_rate_sim, 3),
            "mention_rate_obs": round(self.mention_rate_obs, 3),
            "citation_rate_obs": round(self.citation_rate_obs, 3),
            "mention_rate_delta": round(self.mention_rate_delta, 3),
            "comparisons": [c.to_dict() for c in self.comparisons],
            "insights": self.insights,
            "recommendations": self.recommendations,
        }


class SimulationObservationComparator:
    """Compares simulation predictions with observation results."""

    # Thresholds for answerability mapping
    FULLY_ANSWERABLE_THRESHOLD = 0.7
    PARTIALLY_ANSWERABLE_THRESHOLD = 0.3

    def compare(
        self,
        simulation: SimulationResult,
        observation: ObservationRun,
        parsed_results: dict[str, ParsedObservation] | None = None,
    ) -> ComparisonSummary:
        """
        Compare simulation predictions with observation results.

        Args:
            simulation: The simulation result
            observation: The observation run result
            parsed_results: Optional dict of question_id -> ParsedObservation

        Returns:
            ComparisonSummary with detailed analysis
        """
        summary = ComparisonSummary()
        summary.total_questions = len(simulation.question_results)

        # Build lookup maps
        sim_map: dict[str, QuestionResult] = {r.question_id: r for r in simulation.question_results}
        obs_map: dict[str, ObservationResult] = {r.question_id: r for r in observation.results}

        # Compare each question
        for q_id, sim_result in sim_map.items():
            obs_result = obs_map.get(q_id)
            parsed = parsed_results.get(q_id) if parsed_results else None

            comparison = self._compare_question(sim_result, obs_result, parsed)
            summary.comparisons.append(comparison)

            # Update counts
            if comparison.outcome_match == OutcomeMatch.CORRECT:
                summary.correct_predictions += 1
            elif comparison.outcome_match == OutcomeMatch.OPTIMISTIC:
                summary.optimistic_predictions += 1
            elif comparison.outcome_match == OutcomeMatch.PESSIMISTIC:
                summary.pessimistic_predictions += 1
            else:
                summary.unknown_predictions += 1

        # Calculate rates
        if summary.total_questions > 0:
            summary.prediction_accuracy = summary.correct_predictions / summary.total_questions

            # Simulation prediction rate (based on answerability)
            answerable = sum(
                1
                for r in simulation.question_results
                if r.answerability
                in (
                    Answerability.FULLY_ANSWERABLE,
                    Answerability.PARTIALLY_ANSWERABLE,
                )
            )
            summary.mention_rate_sim = answerable / summary.total_questions

        # Observation rates
        summary.mention_rate_obs = observation.company_mention_rate
        summary.citation_rate_obs = observation.citation_rate
        summary.mention_rate_delta = summary.mention_rate_obs - summary.mention_rate_sim

        # Generate insights
        summary.insights = self._generate_insights(summary)
        summary.recommendations = self._generate_recommendations(summary)

        return summary

    def _compare_question(
        self,
        sim_result: QuestionResult,
        obs_result: ObservationResult | None,
        parsed: ParsedObservation | None,
    ) -> QuestionComparison:
        """Compare a single question's simulation vs observation."""
        comparison = QuestionComparison(
            question_id=sim_result.question_id,
            question_text=sim_result.question_text,
            sim_answerability=sim_result.answerability,
            sim_score=sim_result.score,
            sim_signals_found=sim_result.signals_found,
            sim_signals_total=sim_result.signals_total,
        )

        if obs_result is None:
            comparison.outcome_match = OutcomeMatch.UNKNOWN
            comparison.explanation = "No observation result for this question"
            return comparison

        # Get observation signals
        if parsed:
            comparison.obs_mentioned = parsed.has_company_mention
            comparison.obs_cited = parsed.has_url_citation
            comparison.obs_sentiment = parsed.overall_sentiment.value
            comparison.obs_confidence = parsed.confidence_level.value
        else:
            comparison.obs_mentioned = obs_result.mentions_company
            comparison.obs_cited = obs_result.mentions_url
            comparison.obs_confidence = obs_result.confidence_expressed

        # Determine sourceability outcome
        if parsed and parsed.is_refusal:
            comparison.sourceability_outcome = SourceabilityOutcome.REFUSED
        elif comparison.obs_cited:
            comparison.sourceability_outcome = SourceabilityOutcome.CITED
        elif comparison.obs_mentioned:
            comparison.sourceability_outcome = SourceabilityOutcome.MENTIONED
        else:
            comparison.sourceability_outcome = SourceabilityOutcome.OMITTED

        # Compare prediction to outcome
        comparison.outcome_match, comparison.prediction_accurate = self._evaluate_prediction(
            sim_result, comparison
        )

        # Generate explanation
        comparison.explanation = self._explain_comparison(sim_result, comparison)

        return comparison

    def _evaluate_prediction(
        self,
        sim_result: QuestionResult,
        comparison: QuestionComparison,
    ) -> tuple[OutcomeMatch, bool]:
        """Evaluate how well simulation predicted the outcome."""
        sim_positive = sim_result.answerability in (
            Answerability.FULLY_ANSWERABLE,
            Answerability.PARTIALLY_ANSWERABLE,
        )
        obs_positive = comparison.sourceability_outcome in (
            SourceabilityOutcome.CITED,
            SourceabilityOutcome.MENTIONED,
        )

        if comparison.sourceability_outcome == SourceabilityOutcome.REFUSED:
            return OutcomeMatch.UNKNOWN, False

        if sim_positive == obs_positive:
            return OutcomeMatch.CORRECT, True
        elif sim_positive and not obs_positive:
            return OutcomeMatch.OPTIMISTIC, False
        else:
            return OutcomeMatch.PESSIMISTIC, False

    def _explain_comparison(
        self,
        sim_result: QuestionResult,
        comparison: QuestionComparison,
    ) -> str:
        """Generate human-readable explanation of the comparison."""
        sim_desc = {
            Answerability.FULLY_ANSWERABLE: "fully answerable",
            Answerability.PARTIALLY_ANSWERABLE: "partially answerable",
            Answerability.NOT_ANSWERABLE: "not answerable",
            Answerability.CONTRADICTORY: "contradictory",
        }.get(sim_result.answerability, "unknown")

        obs_desc = {
            SourceabilityOutcome.CITED: "explicitly cited the company",
            SourceabilityOutcome.MENTIONED: "mentioned but didn't cite",
            SourceabilityOutcome.OMITTED: "did not mention the company",
            SourceabilityOutcome.REFUSED: "refused to answer",
            SourceabilityOutcome.COMPETITOR_CITED: "cited a competitor instead",
        }.get(comparison.sourceability_outcome, "unknown outcome")

        match_desc = {
            OutcomeMatch.CORRECT: "Prediction matched reality.",
            OutcomeMatch.OPTIMISTIC: "Simulation was overly optimistic.",
            OutcomeMatch.PESSIMISTIC: "Simulation underestimated sourceability.",
            OutcomeMatch.UNKNOWN: "Unable to compare.",
        }.get(comparison.outcome_match, "")

        return (
            f"Simulation predicted '{sim_desc}' (score: {sim_result.score:.2f}). "
            f"Observation: model {obs_desc}. {match_desc}"
        )

    def _generate_insights(self, summary: ComparisonSummary) -> list[str]:
        """Generate insights from the comparison."""
        insights = []

        # Accuracy insight
        if summary.prediction_accuracy >= 0.8:
            insights.append(
                f"High prediction accuracy ({summary.prediction_accuracy:.0%}): "
                "simulation closely matches real AI behavior."
            )
        elif summary.prediction_accuracy <= 0.5:
            insights.append(
                f"Low prediction accuracy ({summary.prediction_accuracy:.0%}): "
                "significant gap between simulation and real AI behavior."
            )

        # Optimism/pessimism bias
        if summary.optimistic_predictions > summary.pessimistic_predictions * 2:
            insights.append(
                "Simulation tends to be optimistic: real AI models mention "
                "your company less often than predicted."
            )
        elif summary.pessimistic_predictions > summary.optimistic_predictions * 2:
            insights.append(
                "Simulation tends to be pessimistic: real AI models mention "
                "your company more often than predicted."
            )

        # Citation vs mention gap
        if summary.mention_rate_obs > 0:
            citation_ratio = summary.citation_rate_obs / summary.mention_rate_obs
            if citation_ratio < 0.3:
                insights.append(
                    "Low citation rate: AI models mention your company but "
                    "rarely cite your website directly."
                )
            elif citation_ratio > 0.7:
                insights.append(
                    "High citation rate: when mentioned, AI models often "
                    "cite your website directly."
                )

        # Mention rate comparison
        if summary.mention_rate_delta > 0.2:
            insights.append(
                f"Observation shows {summary.mention_rate_delta:.0%} higher mention rate "
                "than simulation predicted."
            )
        elif summary.mention_rate_delta < -0.2:
            insights.append(
                f"Observation shows {-summary.mention_rate_delta:.0%} lower mention rate "
                "than simulation predicted."
            )

        return insights

    def _generate_recommendations(self, summary: ComparisonSummary) -> list[str]:
        """Generate recommendations based on comparison."""
        recommendations = []

        # Based on citation rate
        if summary.citation_rate_obs < 0.3 and summary.mention_rate_obs > 0.5:
            recommendations.append(
                "Improve citation likelihood: add structured data, canonical URLs, "
                "and explicit 'cite this' information."
            )

        # Based on prediction accuracy
        if summary.prediction_accuracy < 0.6:
            recommendations.append(
                "Simulation may need calibration: consider adjusting scoring "
                "thresholds based on observation data."
            )

        # Based on optimism bias
        if summary.optimistic_predictions > summary.total_questions * 0.4:
            recommendations.append(
                "Content may look comprehensive but lacks AI-recognizable signals. "
                "Focus on explicit, structured information."
            )

        # Based on pessimism bias
        if summary.pessimistic_predictions > summary.total_questions * 0.4:
            recommendations.append(
                "Your content performs better than expected. "
                "Consider expanding coverage to more topics."
            )

        return recommendations


def compare_simulation_observation(
    simulation: SimulationResult,
    observation: ObservationRun,
    parsed_results: dict[str, ParsedObservation] | None = None,
) -> ComparisonSummary:
    """
    Convenience function to compare simulation with observation.

    Args:
        simulation: Simulation result
        observation: Observation run result
        parsed_results: Optional parsed observations by question_id

    Returns:
        ComparisonSummary
    """
    comparator = SimulationObservationComparator()
    return comparator.compare(simulation, observation, parsed_results)
