"""Report assembler for combining analysis results.

Assembles simulation, scoring, observation, and benchmark results
into a complete, versioned report.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from worker.fixes.generator_v2 import FixPlanV2

from worker.extraction.entity_recognition import EntityRecognitionResult
from worker.fixes.generator import FixPlan
from worker.fixes.impact import FixPlanImpact
from worker.observation.benchmark import BenchmarkResult
from worker.observation.comparison import ComparisonSummary
from worker.observation.models import ObservationRun
from worker.reports.contract import (
    CURRENT_VERSION,
    ActionCenterSection,
    ActionItemSummary,
    AuthorityComponent,
    AuthoritySection,
    BenchmarkSection,
    CitableIndexSection,
    CompetitorSummary,
    CrawledPageInfo,
    CrawlSection,
    DivergenceLevel,
    DivergenceSection,
    FixItem,
    FixSection,
    FullReport,
    ObservationSection,
    PillarSummary,
    ReportMetadata,
    SchemaComponent,
    SchemaSection,
    ScoreSection,
    ScoreSectionV2,
    StructureComponent,
    StructureSection,
    TechnicalComponent,
    TechnicalSection,
)
from worker.scoring.authority import AuthoritySignalsScore
from worker.scoring.calculator import ScoreBreakdown
from worker.scoring.calculator_v2 import FindableScoreV2, calculate_findable_score_v2
from worker.scoring.schema import SchemaRichnessScore
from worker.scoring.structure import StructureQualityScore
from worker.scoring.technical import TechnicalReadinessScore
from worker.simulation.runner import SimulationResult

# Lazy import to avoid circular dependency
# from worker.fixes.generator_v2 import FixPlanV2, generate_fix_plan_v2
# Import in methods that need it instead


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
        crawl_data: dict | None = None,
        technical_score: TechnicalReadinessScore | None = None,
        structure_score: StructureQualityScore | None = None,
        schema_score: SchemaRichnessScore | None = None,
        authority_score: AuthoritySignalsScore | None = None,
        entity_recognition_result: EntityRecognitionResult | None = None,
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
            entity_recognition_result: Optional entity recognition analysis

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

        # Build citable index section if observation has citation depth data
        citable_index_section = None
        if (
            observation
            and hasattr(observation, "avg_citation_depth")
            and observation.avg_citation_depth is not None
        ):
            citable_index_section = self._build_citable_index_section(observation)

        # Build crawl section if we have crawl data
        crawl_section = None
        if crawl_data:
            crawl_section = self._build_crawl_section(crawl_data)

        # Build technical section if we have technical score (v2)
        technical_section = None
        if technical_score:
            technical_section = self._build_technical_section(technical_score)

        # Build structure section if we have structure score (v2)
        structure_section = None
        if structure_score:
            structure_section = self._build_structure_section(structure_score)

        # Build schema section if we have schema score (v2)
        schema_section = None
        if schema_score:
            schema_section = self._build_schema_section(schema_score)

        # Build authority section if we have authority score (v2)
        authority_section = None
        if authority_score:
            authority_section = self._build_authority_section(authority_score)

        # Build v2 score section if we have any v2 pillar scores
        score_v2_section = None
        action_center_section = None
        if (
            technical_score
            or structure_score
            or schema_score
            or authority_score
            or entity_recognition_result
        ):
            # Lazy import to avoid circular dependency
            from worker.fixes.generator_v2 import generate_fix_plan_v2

            # Calculate v2 score
            findable_v2 = calculate_findable_score_v2(
                technical_score=technical_score,
                structure_score=structure_score,
                schema_score=schema_score,
                authority_score=authority_score,
                entity_recognition_result=entity_recognition_result,
                simulation_breakdown=score_breakdown,
            )
            score_v2_section = self._build_score_v2_section(findable_v2)

            # Generate v2 fix plan
            fix_plan_v2 = generate_fix_plan_v2(
                site_id=site_id,
                run_id=run_id,
                company_name=company_name,
                technical_score=technical_score,
                structure_score=structure_score,
                schema_score=schema_score,
                authority_score=authority_score,
                content_fix_plan=fix_plan,
            )
            action_center_section = self._build_action_center_section(fix_plan_v2)

        return FullReport(
            metadata=metadata,
            score=score_section,
            fixes=fix_section,
            crawl=crawl_section,
            technical=technical_section,
            structure=structure_section,
            schema=schema_section,
            authority=authority_section,
            score_v2=score_v2_section,
            action_center=action_center_section,
            observation=observation_section,
            benchmark=benchmark_section,
            divergence=divergence_section,
            citable_index=citable_index_section,
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

    def _build_crawl_section(self, crawl_data: dict) -> CrawlSection:
        """Build crawl section from crawl data."""
        pages = []
        for page in crawl_data.get("pages", []):
            pages.append(
                CrawledPageInfo(
                    url=page["url"],
                    title=page.get("title"),
                    status_code=page.get("status_code", 200),
                    depth=page.get("depth", 0),
                    word_count=page.get("word_count", 0),
                    chunk_count=page.get("chunk_count", 0),
                    surface=page.get("surface", "marketing"),
                )
            )

        return CrawlSection(
            total_pages=crawl_data.get("total_pages", len(pages)),
            total_words=crawl_data.get("total_words", 0),
            total_chunks=crawl_data.get("total_chunks", 0),
            urls_discovered=crawl_data.get("urls_discovered", 0),
            urls_failed=crawl_data.get("urls_failed", 0),
            max_depth_reached=crawl_data.get("max_depth_reached", 0),
            duration_seconds=crawl_data.get("duration_seconds", 0),
            pages=pages,
            docs_pages_crawled=crawl_data.get("docs_pages_crawled", 0),
            marketing_pages_crawled=crawl_data.get("marketing_pages_crawled", 0),
            docs_surface_detected=crawl_data.get("docs_surface_detected", False),
        )

    def _build_technical_section(
        self,
        technical_score: TechnicalReadinessScore,
    ) -> TechnicalSection:
        """Build technical readiness section from TechnicalReadinessScore."""
        # Convert components
        components = []
        for comp in technical_score.components:
            components.append(
                TechnicalComponent(
                    name=comp.name,
                    score=comp.raw_score,
                    weight=comp.weight,
                    level=comp.level,
                    explanation=comp.explanation,
                )
            )

        # Extract crawler access data
        crawlers_allowed = {}
        if technical_score.robots_result:
            for name, result in technical_score.robots_result.crawlers.items():
                crawlers_allowed[name] = result.allowed

        # Extract TTFB data
        ttfb_ms = None
        ttfb_level = None
        if technical_score.ttfb_result:
            if hasattr(technical_score.ttfb_result, "ttfb_ms"):
                ttfb_ms = technical_score.ttfb_result.ttfb_ms
            elif hasattr(technical_score.ttfb_result, "avg_ttfb_ms"):
                ttfb_ms = technical_score.ttfb_result.avg_ttfb_ms
            ttfb_level = technical_score.ttfb_result.level

        # Extract llms.txt data
        llms_txt_exists = False
        llms_txt_quality = 0.0
        if technical_score.llms_txt_result:
            llms_txt_exists = technical_score.llms_txt_result.exists
            llms_txt_quality = technical_score.llms_txt_result.quality_score

        # Extract JS data
        js_dependent = False
        js_framework = None
        if technical_score.js_result:
            js_dependent = technical_score.js_result.likely_js_dependent
            js_framework = technical_score.js_result.framework_detected

        return TechnicalSection(
            total_score=technical_score.total_score,
            level=technical_score.level,
            components=components,
            robots_txt_exists=(
                technical_score.robots_result.robots_txt_exists
                if technical_score.robots_result
                else False
            ),
            crawlers_allowed=crawlers_allowed,
            critical_crawlers_blocked=technical_score.critical_issues[:],
            ttfb_ms=ttfb_ms,
            ttfb_level=ttfb_level,
            llms_txt_exists=llms_txt_exists,
            llms_txt_quality=llms_txt_quality,
            js_dependent=js_dependent,
            js_framework=js_framework,
            is_https=technical_score.is_https,
            critical_issues=technical_score.critical_issues[:],
            all_issues=technical_score.all_issues[:],
            show_the_math=technical_score.show_the_math(),
        )

    def _build_structure_section(
        self,
        structure_score: StructureQualityScore,
    ) -> StructureSection:
        """Build structure quality section from StructureQualityScore."""
        # Convert components
        components = []
        for comp in structure_score.components:
            components.append(
                StructureComponent(
                    name=comp.name,
                    score=comp.raw_score,
                    weight=comp.weight,
                    level=comp.level,
                    explanation=comp.explanation,
                )
            )

        # Extract data from structure analysis
        analysis = structure_score.structure_analysis

        return StructureSection(
            total_score=structure_score.total_score,
            level=structure_score.level,
            components=components,
            h1_count=analysis.headings.h1_count if analysis else 0,
            heading_hierarchy_valid=analysis.headings.hierarchy_valid if analysis else True,
            heading_issues=[i.details for i in analysis.headings.issues[:3]] if analysis else [],
            answer_in_first_paragraph=(
                analysis.answer_first.answer_in_first_paragraph if analysis else False
            ),
            has_definition=analysis.answer_first.has_definition if analysis else False,
            has_faq_section=analysis.faq.has_faq_section if analysis else False,
            faq_count=analysis.faq.faq_count if analysis else 0,
            has_faq_schema=analysis.faq.has_faq_schema if analysis else False,
            internal_links=analysis.links.internal_links if analysis else 0,
            link_density_level=analysis.links.density_level if analysis else "unknown",
            table_count=analysis.formats.table_count if analysis else 0,
            list_item_count=analysis.formats.total_list_items if analysis else 0,
            critical_issues=structure_score.critical_issues[:],
            all_issues=structure_score.all_issues[:],
            recommendations=structure_score.recommendations[:5],
            show_the_math=structure_score.show_the_math(),
        )

    def _build_schema_section(
        self,
        schema_score: SchemaRichnessScore,
    ) -> SchemaSection:
        """Build schema richness section from SchemaRichnessScore."""
        # Convert components
        components = []
        for comp in schema_score.components:
            components.append(
                SchemaComponent(
                    name=comp.name,
                    score=comp.raw_score,
                    weight=comp.weight,
                    level=comp.level,
                    explanation=comp.explanation,
                )
            )

        # Extract data from schema analysis
        analysis = schema_score.schema_analysis

        return SchemaSection(
            total_score=schema_score.total_score,
            level=schema_score.level,
            components=components,
            has_json_ld=analysis.has_json_ld if analysis else False,
            has_microdata=analysis.has_microdata if analysis else False,
            total_schemas=analysis.total_schemas if analysis else 0,
            schema_types=analysis.schema_types_found[:10] if analysis else [],
            has_faq_page=analysis.has_faq_page if analysis else False,
            has_article=analysis.has_article if analysis else False,
            has_how_to=analysis.has_how_to if analysis else False,
            has_organization=analysis.has_organization if analysis else False,
            faq_count=analysis.faq_count if analysis else 0,
            has_author=analysis.has_author if analysis else False,
            author_name=analysis.author_name if analysis else None,
            has_date_modified=analysis.has_date_modified if analysis else False,
            date_modified=analysis.date_modified if analysis else None,
            days_since_modified=analysis.days_since_modified if analysis else None,
            freshness_level=analysis.freshness_level if analysis else "unknown",
            validation_errors=analysis.error_count if analysis else 0,
            critical_issues=schema_score.critical_issues[:],
            all_issues=schema_score.all_issues[:],
            recommendations=schema_score.recommendations[:5],
            show_the_math=schema_score.show_the_math(),
        )

    def _build_authority_section(
        self,
        authority_score: AuthoritySignalsScore,
    ) -> AuthoritySection:
        """Build authority signals section from AuthoritySignalsScore."""
        # Convert components
        components = []
        for comp in authority_score.components:
            components.append(
                AuthorityComponent(
                    name=comp.name,
                    score=comp.raw_score,
                    weight=comp.weight,
                    level=comp.level,
                    explanation=comp.explanation,
                )
            )

        # Extract data from authority analysis
        analysis = authority_score.authority_analysis

        return AuthoritySection(
            total_score=authority_score.total_score,
            level=authority_score.level,
            components=components,
            has_author=analysis.has_author if analysis else False,
            author_name=(
                analysis.primary_author.name if analysis and analysis.primary_author else None
            ),
            author_is_linked=(
                analysis.primary_author.is_linked if analysis and analysis.primary_author else False
            ),
            has_author_photo=analysis.has_author_photo if analysis else False,
            has_credentials=analysis.has_credentials if analysis else False,
            has_author_bio=analysis.has_author_bio if analysis else False,
            credentials_found=analysis.credentials_found[:5] if analysis else [],
            total_citations=analysis.total_citations if analysis else 0,
            authoritative_citations=analysis.authoritative_citations if analysis else 0,
            has_original_data=analysis.has_original_data if analysis else False,
            original_data_count=analysis.original_data_count if analysis else 0,
            has_visible_date=analysis.has_visible_date if analysis else False,
            days_since_published=analysis.days_since_published if analysis else None,
            freshness_level=analysis.freshness_level if analysis else "unknown",
            critical_issues=authority_score.critical_issues[:],
            all_issues=authority_score.all_issues[:],
            recommendations=authority_score.recommendations[:5],
            show_the_math=authority_score.show_the_math(),
        )

    def _build_score_v2_section(
        self,
        findable_v2: FindableScoreV2,
    ) -> ScoreSectionV2:
        """Build v2 score section from FindableScoreV2."""
        # Convert pillars to summaries
        pillar_summaries = []
        for pillar in findable_v2.pillars:
            pillar_summaries.append(
                PillarSummary(
                    name=pillar.name,
                    display_name=pillar.display_name,
                    raw_score=pillar.raw_score,
                    max_points=pillar.max_points,
                    points_earned=pillar.points_earned,
                    level=pillar.level,
                )
            )

        return ScoreSectionV2(
            total_score=findable_v2.total_score,
            version=findable_v2.version,
            level=findable_v2.level,
            level_label=findable_v2.level_label,
            level_summary=findable_v2.level_summary,
            level_focus=findable_v2.level_focus,
            next_milestone=(
                findable_v2.next_milestone.to_dict() if findable_v2.next_milestone else None
            ),
            points_to_milestone=findable_v2.points_to_milestone,
            path_forward=[p.to_dict() for p in findable_v2.path_forward],
            pillars=pillar_summaries,
            pillars_good=findable_v2.pillars_good,
            pillars_warning=findable_v2.pillars_warning,
            pillars_critical=findable_v2.pillars_critical,
            critical_issues=findable_v2.all_critical_issues[:5],
            top_recommendations=findable_v2.top_recommendations[:5],
            strengths=findable_v2.strengths[:5],
            calculation_summary=findable_v2.calculation_summary,
            show_the_math=findable_v2.show_the_math(),
        )

    def _build_action_center_section(
        self,
        fix_plan_v2: FixPlanV2,
    ) -> ActionCenterSection:
        """Build action center section from FixPlanV2."""
        action_center = fix_plan_v2.action_center

        # Convert quick wins
        quick_wins = []
        for item in action_center.quick_wins:
            quick_wins.append(
                ActionItemSummary(
                    id=item.fix.id,
                    category=item.fix.category.value,
                    title=item.fix.title,
                    description=item.fix.description,
                    priority=item.fix.priority,
                    impact_level=item.fix.impact_level.value,
                    effort_level=item.fix.effort_level.value,
                    estimated_points=item.fix.estimated_points,
                    affected_pillar=item.fix.affected_pillar,
                    scaffold=item.fix.scaffold,
                )
            )

        # Convert high priority
        high_priority = []
        for item in action_center.high_priority:
            high_priority.append(
                ActionItemSummary(
                    id=item.fix.id,
                    category=item.fix.category.value,
                    title=item.fix.title,
                    description=item.fix.description,
                    priority=item.fix.priority,
                    impact_level=item.fix.impact_level.value,
                    effort_level=item.fix.effort_level.value,
                    estimated_points=item.fix.estimated_points,
                    affected_pillar=item.fix.affected_pillar,
                    scaffold=item.fix.scaffold,
                )
            )

        # Convert all fixes
        all_fixes = []
        for item in action_center.all_fixes:
            all_fixes.append(
                ActionItemSummary(
                    id=item.fix.id,
                    category=item.fix.category.value,
                    title=item.fix.title,
                    description=item.fix.description,
                    priority=item.fix.priority,
                    impact_level=item.fix.impact_level.value,
                    effort_level=item.fix.effort_level.value,
                    estimated_points=item.fix.estimated_points,
                    affected_pillar=item.fix.affected_pillar,
                    scaffold=item.fix.scaffold,
                )
            )

        return ActionCenterSection(
            quick_wins=quick_wins,
            high_priority=high_priority,
            all_fixes=all_fixes,
            total_fixes=action_center.total_fixes,
            estimated_total_points=action_center.estimated_total_points,
            critical_count=action_center.critical_count,
            high_count=action_center.high_count,
            medium_count=action_center.medium_count,
            low_count=action_center.low_count,
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

    def _build_citable_index_section(
        self,
        observation: ObservationRun,
    ) -> CitableIndexSection:
        """Build citable index section from observation citation depth data."""
        # Extract per-result depth data
        depths = []
        heuristic_depths = []
        for result in observation.results:
            depth = getattr(result, "citation_depth", None)
            if depth is not None:
                depths.append(depth)
                h_depth = getattr(result, "heuristic_depth", depth)
                heuristic_depths.append(h_depth)

        if not depths:
            return CitableIndexSection(
                avg_depth=observation.avg_citation_depth or 0.0,
                pct_citable=0.0,
                pct_strongly_sourced=0.0,
                depth_histogram={},
                confidence="low",
                depth_divergence=0.0,
                avg_competitors=0.0,
                framing_distribution={},
            )

        n = len(depths)

        # Build histogram
        histogram: dict[int, int] = {}
        for d in depths:
            histogram[d] = histogram.get(d, 0) + 1
        histogram = dict(sorted(histogram.items()))

        # Citable thresholds
        pct_citable = sum(1 for d in depths if d >= 3) / n * 100
        pct_strongly_sourced = sum(1 for d in depths if d >= 4) / n * 100

        # Divergence and confidence
        divergence = sum(abs(d - h) for d, h in zip(depths, heuristic_depths, strict=False)) / n
        if divergence >= 2.0:
            confidence = "low"
        elif divergence >= 1.0:
            confidence = "medium"
        else:
            confidence = "high"

        # Free-signal aggregates
        avg_competitors = 0.0
        framing_dist: dict[str, int] = {}
        for result in observation.results:
            comp = getattr(result, "competitors_mentioned", 0)
            avg_competitors += comp
            framing = getattr(result, "source_framing", None)
            if framing:
                framing_dist[framing] = framing_dist.get(framing, 0) + 1
        avg_competitors = avg_competitors / len(observation.results) if observation.results else 0.0

        return CitableIndexSection(
            avg_depth=observation.avg_citation_depth or 0.0,
            pct_citable=pct_citable,
            pct_strongly_sourced=pct_strongly_sourced,
            depth_histogram=histogram,
            confidence=confidence,
            depth_divergence=divergence,
            avg_competitors=avg_competitors,
            framing_distribution=dict(sorted(framing_dist.items(), key=lambda x: -x[1])),
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
    crawl_data: dict | None = None,
    technical_score: TechnicalReadinessScore | None = None,
    structure_score: StructureQualityScore | None = None,
    schema_score: SchemaRichnessScore | None = None,
    authority_score: AuthoritySignalsScore | None = None,
    entity_recognition_result: EntityRecognitionResult | None = None,
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
        crawl_data: Optional crawl data with pages info
        technical_score: Optional technical readiness score (v2)
        structure_score: Optional structure quality score (v2)
        schema_score: Optional schema richness score (v2)
        authority_score: Optional authority signals score (v2)
        entity_recognition_result: Optional entity recognition analysis (v2)

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
        crawl_data=crawl_data,
        technical_score=technical_score,
        structure_score=structure_score,
        schema_score=schema_score,
        authority_score=authority_score,
        entity_recognition_result=entity_recognition_result,
    )
