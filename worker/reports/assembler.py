"""Report assembler for combining analysis results.

Assembles simulation, scoring, observation, and benchmark results
into a complete, versioned report.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from worker.fixes.generator import FixPlan
from worker.fixes.impact import FixPlanImpact
from worker.observation.benchmark import BenchmarkResult
from worker.observation.comparison import ComparisonSummary
from worker.observation.models import ObservationRun
from worker.reports.contract import (
    CURRENT_VERSION,
    BenchmarkSection,
    CompetitorSummary,
    DivergenceLevel,
    DivergenceSection,
    FixItem,
    FixSection,
    FullReport,
    ObservationSection,
    ReportMetadata,
    ScoreSection,
)
from worker.scoring.calculator import ScoreBreakdown
from worker.simulation.runner import SimulationResult


@dataclass
class ReportAssemblerConfig:
    """Configuration for report assembly."""

    include_observation: bool = True
    include_benchmark: bool = True

    # Divergence thresholds
    divergence_low_threshold: float = 0.1  # 10%
    divergence_medium_threshold: float = 0.2  # 20%
    divergence_high_threshold: float = 0.35  # 35%

    # Refresh triggers
    refresh_on_high_divergence: bool = True
    refresh_on_low_accuracy: float = 0.5  # Accuracy below 50%


class ReportAssembler:
    """Assembles all analysis results into a complete report."""

    def __init__(self, config: ReportAssemblerConfig | None = None):
        self.config = config or ReportAssemblerConfig()

    def assemble(
        self,
        site_id: UUID,
        run_id: UUID,
        company_name: str,
        domain: str,
        simulation: SimulationResult,  # noqa: ARG002 - Reserved for future use
        score_breakdown: ScoreBreakdown,
        fix_plan: FixPlan,
        fix_impact: FixPlanImpact | None = None,
        observation: ObservationRun | None = None,
        comparison: ComparisonSummary | None = None,
        benchmark: BenchmarkResult | None = None,
        run_started_at: datetime | None = None,
        run_completed_at: datetime | None = None,
    ) -> FullReport:
        """
        Assemble a complete report from analysis results.

        Args:
            site_id: Site identifier
            run_id: Run identifier
            company_name: Company name
            domain: Company domain
            simulation: Simulation result
            score_breakdown: Score calculation breakdown
            fix_plan: Generated fix plan
            fix_impact: Optional impact estimates for fixes
            observation: Optional observation run results
            comparison: Optional simulation vs observation comparison
            benchmark: Optional competitor benchmark results
            run_started_at: Optional run start time
            run_completed_at: Optional run completion time

        Returns:
            FullReport with all sections assembled
        """
        now = datetime.utcnow()

        # Calculate run duration
        duration = None
        if run_started_at and run_completed_at:
            duration = (run_completed_at - run_started_at).total_seconds()

        # Build metadata
        metadata = self._build_metadata(
            site_id=site_id,
            run_id=run_id,
            company_name=company_name,
            domain=domain,
            run_started_at=run_started_at,
            run_completed_at=run_completed_at,
            duration=duration,
            now=now,
        )

        # Build score section
        score_section = self._build_score_section(score_breakdown)

        # Build fix section
        fix_section = self._build_fix_section(fix_plan, fix_impact)

        # Build optional sections
        observation_section = None
        if observation and self.config.include_observation:
            observation_section = self._build_observation_section(observation, comparison)

        benchmark_section = None
        if benchmark and self.config.include_benchmark:
            benchmark_section = self._build_benchmark_section(benchmark)

        # Build divergence section if we have both simulation and observation
        divergence_section = None
        if comparison:
            divergence_section = self._build_divergence_section(comparison)

        return FullReport(
            metadata=metadata,
            score=score_section,
            fixes=fix_section,
            observation=observation_section,
            benchmark=benchmark_section,
            divergence=divergence_section,
        )

    def _build_metadata(
        self,
        site_id: UUID,
        run_id: UUID,
        company_name: str,
        domain: str,
        run_started_at: datetime | None,
        run_completed_at: datetime | None,
        duration: float | None,
        now: datetime,
    ) -> ReportMetadata:
        """Build report metadata."""
        limitations: list[str] = []
        notes: list[str] = []

        # Add limitations based on config
        if not self.config.include_observation:
            limitations.append(
                "Observation was not run. Mention rates are simulated estimates only."
            )

        if not self.config.include_benchmark:
            limitations.append(
                "Competitor benchmark was not run. No competitive analysis available."
            )

        return ReportMetadata(
            report_id=uuid4(),
            site_id=site_id,
            run_id=run_id,
            version=CURRENT_VERSION,
            company_name=company_name,
            domain=domain,
            created_at=now,
            run_started_at=run_started_at,
            run_completed_at=run_completed_at,
            run_duration_seconds=duration,
            include_observation=self.config.include_observation,
            include_benchmark=self.config.include_benchmark,
            limitations=limitations,
            notes=notes,
        )

    def _build_score_section(
        self,
        breakdown: ScoreBreakdown,
    ) -> ScoreSection:
        """Build score section from ScoreBreakdown."""
        # Extract category scores
        category_scores = {cat: cb.raw_score for cat, cb in breakdown.category_breakdowns.items()}

        return ScoreSection(
            total_score=breakdown.total_score,
            grade=breakdown.grade,
            grade_description=breakdown.grade_description,
            category_scores=category_scores,
            category_breakdown={k: v.to_dict() for k, v in breakdown.category_breakdowns.items()},
            criterion_scores=[cs.to_dict() for cs in breakdown.criterion_scores],
            total_questions=breakdown.total_questions,
            questions_answered=breakdown.questions_answered,
            questions_partial=breakdown.questions_partial,
            questions_unanswered=breakdown.questions_unanswered,
            coverage_percentage=breakdown.coverage_percentage,
            calculation_summary=breakdown.calculation_summary,
            formula_used=breakdown.formula_used,
            rubric_version=breakdown.rubric_version,
            show_the_math=breakdown.show_the_math(),
        )

    def _build_fix_section(
        self,
        fix_plan: FixPlan,
        fix_impact: FixPlanImpact | None,
    ) -> FixSection:
        """Build fix section from FixPlan."""
        fix_items = []

        for fix in fix_plan.fixes:
            # Get impact estimates if available
            impact_min = fix.estimated_impact * 0.5
            impact_max = fix.estimated_impact * 1.5
            impact_expected = fix.estimated_impact

            if fix_impact:
                # Try to find matching impact estimate
                for estimate in fix_impact.estimates:
                    if str(estimate.fix_id) == str(fix.id):
                        impact_min = estimate.impact_range.min_points
                        impact_max = estimate.impact_range.max_points
                        impact_expected = estimate.impact_range.expected_points
                        break

            fix_items.append(
                FixItem(
                    id=str(fix.id),
                    reason_code=fix.reason_code.value,
                    title=fix.template.title,
                    description=fix.template.description,
                    scaffold=fix.scaffold,
                    priority=fix.priority,
                    estimated_impact_min=impact_min,
                    estimated_impact_max=impact_max,
                    estimated_impact_expected=impact_expected,
                    effort_level=fix.effort_level,
                    target_url=fix.target_url,
                    affected_questions=fix.affected_question_ids,
                    affected_categories=[c.value for c in fix.affected_categories],
                )
            )

        return FixSection(
            total_fixes=fix_plan.total_fixes,
            critical_fixes=fix_plan.critical_fixes,
            high_priority_fixes=fix_plan.high_priority_fixes,
            estimated_total_impact=fix_plan.estimated_total_impact,
            fixes=fix_items,
            categories_addressed=[c.value for c in fix_plan.categories_addressed],
            questions_addressed=fix_plan.questions_addressed,
        )

    def _build_observation_section(
        self,
        observation: ObservationRun,
        comparison: ComparisonSummary | None,
    ) -> ObservationSection:
        """Build observation section from ObservationRun."""
        # Count questions with mentions/citations
        questions_with_mention = sum(1 for r in observation.results if r.mentions_company)
        questions_with_citation = sum(1 for r in observation.results if r.mentions_url)

        # Build simplified question results
        question_results = []
        for result in observation.results:
            question_results.append(
                {
                    "question_id": result.question_id,
                    "question_text": result.question_text[:100],
                    "mentions_company": result.mentions_company,
                    "mentions_url": result.mentions_url,
                    "cited_urls": result.cited_urls[:3],  # Limit URLs
                    "confidence_expressed": result.confidence_expressed,
                }
            )

        # Get comparison data if available
        prediction_accuracy = comparison.prediction_accuracy if comparison else 0.0
        optimistic = comparison.optimistic_predictions if comparison else 0
        pessimistic = comparison.pessimistic_predictions if comparison else 0
        correct = comparison.correct_predictions if comparison else 0
        insights = comparison.insights if comparison else []
        recommendations = comparison.recommendations if comparison else []

        return ObservationSection(
            company_mention_rate=observation.company_mention_rate,
            domain_mention_rate=observation.domain_mention_rate,
            citation_rate=observation.citation_rate,
            total_questions=len(observation.results),
            questions_with_mention=questions_with_mention,
            questions_with_citation=questions_with_citation,
            provider=observation.provider.value,
            model=observation.model,
            question_results=question_results,
            prediction_accuracy=prediction_accuracy,
            optimistic_predictions=optimistic,
            pessimistic_predictions=pessimistic,
            correct_predictions=correct,
            insights=insights,
            recommendations=recommendations,
        )

    def _build_benchmark_section(
        self,
        benchmark: BenchmarkResult,
    ) -> BenchmarkSection:
        """Build benchmark section from BenchmarkResult."""
        # Build competitor summaries
        competitors = []
        for h2h in benchmark.head_to_heads:
            # Find the competitor result
            comp_result = next(
                (
                    c
                    for c in benchmark.competitor_results
                    if c.competitor.name == h2h.competitor_name
                ),
                None,
            )
            if comp_result:
                competitors.append(
                    CompetitorSummary(
                        name=h2h.competitor_name,
                        domain=comp_result.competitor.domain,
                        mention_rate=comp_result.mention_rate,
                        citation_rate=comp_result.citation_rate,
                        wins_against_you=h2h.losses,  # Their wins = your losses
                        losses_against_you=h2h.wins,  # Their losses = your wins
                        ties=h2h.ties,
                    )
                )

        # Build question benchmarks
        question_benchmarks = [qb.to_dict() for qb in benchmark.question_benchmarks]

        return BenchmarkSection(
            total_competitors=benchmark.total_competitors,
            total_questions=benchmark.total_questions,
            your_mention_rate=benchmark.your_mention_rate,
            your_citation_rate=benchmark.your_citation_rate,
            avg_competitor_mention_rate=benchmark.avg_competitor_mention_rate,
            avg_competitor_citation_rate=benchmark.avg_competitor_citation_rate,
            overall_wins=benchmark.overall_wins,
            overall_losses=benchmark.overall_losses,
            overall_ties=benchmark.overall_ties,
            overall_win_rate=benchmark.overall_win_rate,
            unique_wins=benchmark.unique_wins,
            unique_losses=benchmark.unique_losses,
            competitors=competitors,
            question_benchmarks=question_benchmarks,
            insights=benchmark.insights,
            recommendations=benchmark.recommendations,
        )

    def _build_divergence_section(
        self,
        comparison: ComparisonSummary,
    ) -> DivergenceSection:
        """Build divergence section from comparison."""
        # Calculate divergence level
        delta = abs(comparison.mention_rate_delta)
        if delta < self.config.divergence_low_threshold:
            level = DivergenceLevel.NONE
        elif delta < self.config.divergence_medium_threshold:
            level = DivergenceLevel.LOW
        elif delta < self.config.divergence_high_threshold:
            level = DivergenceLevel.MEDIUM
        else:
            level = DivergenceLevel.HIGH

        # Determine refresh triggers
        refresh_reasons = []
        should_refresh = False

        if self.config.refresh_on_high_divergence and level == DivergenceLevel.HIGH:
            should_refresh = True
            refresh_reasons.append(
                f"High divergence ({delta:.0%}) between simulation and observation."
            )

        if comparison.prediction_accuracy < self.config.refresh_on_low_accuracy:
            should_refresh = True
            refresh_reasons.append(
                f"Low prediction accuracy ({comparison.prediction_accuracy:.0%}). "
                "Consider recrawling or updating content."
            )

        # Calculate bias
        total = comparison.total_questions
        optimism = comparison.optimistic_predictions / total if total > 0 else 0
        pessimism = comparison.pessimistic_predictions / total if total > 0 else 0

        # Calibration notes
        calibration_notes = []
        if optimism > 0.3:
            calibration_notes.append(
                "Simulation tends to overestimate sourceability. "
                "Scoring thresholds may need adjustment."
            )
        if pessimism > 0.3:
            calibration_notes.append(
                "Simulation tends to underestimate sourceability. "
                "Content may perform better than expected."
            )
        if not calibration_notes:
            calibration_notes.append(
                "Simulation predictions are well-calibrated with observations."
            )

        return DivergenceSection(
            level=level,
            mention_rate_delta=comparison.mention_rate_delta,
            prediction_accuracy=comparison.prediction_accuracy,
            should_refresh=should_refresh,
            refresh_reasons=refresh_reasons,
            optimism_bias=optimism,
            pessimism_bias=pessimism,
            calibration_notes=calibration_notes,
        )


def assemble_report(
    site_id: UUID,
    run_id: UUID,
    company_name: str,
    domain: str,
    simulation: SimulationResult,
    score_breakdown: ScoreBreakdown,
    fix_plan: FixPlan,
    fix_impact: FixPlanImpact | None = None,
    observation: ObservationRun | None = None,
    comparison: ComparisonSummary | None = None,
    benchmark: BenchmarkResult | None = None,
    config: ReportAssemblerConfig | None = None,
) -> FullReport:
    """
    Convenience function to assemble a report.

    Args:
        site_id: Site identifier
        run_id: Run identifier
        company_name: Company name
        domain: Company domain
        simulation: Simulation result
        score_breakdown: Score calculation breakdown
        fix_plan: Generated fix plan
        fix_impact: Optional impact estimates
        observation: Optional observation results
        comparison: Optional comparison results
        benchmark: Optional benchmark results
        config: Optional assembler configuration

    Returns:
        FullReport with all sections
    """
    assembler = ReportAssembler(config)
    return assembler.assemble(
        site_id=site_id,
        run_id=run_id,
        company_name=company_name,
        domain=domain,
        simulation=simulation,
        score_breakdown=score_breakdown,
        fix_plan=fix_plan,
        fix_impact=fix_impact,
        observation=observation,
        comparison=comparison,
        benchmark=benchmark,
    )
