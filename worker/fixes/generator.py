"""Fix generator for AI sourceability improvements.

Analyzes simulation results to identify issues and generate
actionable fixes with content scaffolds.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from worker.fixes.reason_codes import (
    ReasonCode,
    ReasonCodeInfo,
    get_reason_info,
)
from worker.fixes.templates import FixTemplate, get_template
from worker.questions.universal import QuestionCategory
from worker.simulation.runner import (
    Answerability,
    ConfidenceLevel,
    QuestionResult,
    SimulationResult,
)


@dataclass
class ExtractedContent:
    """Content extracted from existing site pages."""

    text: str
    source_url: str
    relevance_score: float
    context: str  # Surrounding context


@dataclass
class Fix:
    """A single actionable fix recommendation."""

    id: UUID
    reason_code: ReasonCode
    reason_info: ReasonCodeInfo
    template: FixTemplate

    # Links to questions
    affected_question_ids: list[str]
    affected_categories: list[QuestionCategory]

    # Content scaffold
    scaffold: str  # Filled template with placeholders or extracted content
    extracted_content: list[ExtractedContent]  # Content pulled from site

    # Metadata
    priority: int  # 1 = highest
    estimated_impact: float  # 0-1, expected score improvement
    effort_level: str  # low, medium, high
    target_url: str | None  # Suggested URL for the fix

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "reason_code": self.reason_code.value,
            "reason_info": self.reason_info.to_dict(),
            "template": self.template.to_dict(),
            "affected_question_ids": self.affected_question_ids,
            "affected_categories": [c.value for c in self.affected_categories],
            "scaffold": self.scaffold,
            "extracted_content": [
                {
                    "text": ec.text,
                    "source_url": ec.source_url,
                    "relevance_score": ec.relevance_score,
                    "context": ec.context,
                }
                for ec in self.extracted_content
            ],
            "priority": self.priority,
            "estimated_impact": round(self.estimated_impact, 3),
            "effort_level": self.effort_level,
            "target_url": self.target_url,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class FixPlan:
    """Complete fix plan for a site."""

    id: UUID
    site_id: UUID
    run_id: UUID
    company_name: str

    # Fixes
    fixes: list[Fix]
    total_fixes: int

    # Summary
    critical_fixes: int
    high_priority_fixes: int
    estimated_total_impact: float  # Expected score improvement

    # Coverage
    categories_addressed: list[QuestionCategory]
    questions_addressed: int

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "site_id": str(self.site_id),
            "run_id": str(self.run_id),
            "company_name": self.company_name,
            "fixes": [f.to_dict() for f in self.fixes],
            "total_fixes": self.total_fixes,
            "critical_fixes": self.critical_fixes,
            "high_priority_fixes": self.high_priority_fixes,
            "estimated_total_impact": round(self.estimated_total_impact, 3),
            "categories_addressed": [c.value for c in self.categories_addressed],
            "questions_addressed": self.questions_addressed,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    def get_top_fixes(self, n: int = 5) -> list[Fix]:
        """Get top N fixes by priority and impact."""
        sorted_fixes = sorted(
            self.fixes,
            key=lambda f: (f.priority, -f.estimated_impact),
        )
        return sorted_fixes[:n]


@dataclass
class FixGeneratorConfig:
    """Configuration for fix generation."""

    # Thresholds for identifying issues
    low_score_threshold: float = 0.5  # Score below this triggers analysis
    partial_threshold: float = 0.7  # Partial answers below this need fixes

    # Limits
    max_fixes: int = 10  # Maximum fixes to generate
    max_fixes_per_category: int = 3  # Max fixes per question category

    # Scaffold generation
    include_examples: bool = True
    extract_site_content: bool = True
    max_extracted_snippets: int = 3


class FixGenerator:
    """Generates actionable fixes from simulation results."""

    def __init__(self, config: FixGeneratorConfig | None = None):
        self.config = config or FixGeneratorConfig()

    def generate(
        self,
        simulation: SimulationResult,
        site_content: dict[str, str] | None = None,
    ) -> FixPlan:
        """
        Generate a fix plan from simulation results.

        Args:
            simulation: Simulation result to analyze
            site_content: Optional dict of URL -> content for extraction

        Returns:
            FixPlan with prioritized fixes
        """
        # Identify problematic questions
        problem_questions = self._identify_problems(simulation.question_results)

        # Diagnose reason codes for each problem
        diagnosed: list[tuple[QuestionResult, list[ReasonCode]]] = []
        for question in problem_questions:
            reasons = self._diagnose_reasons(question, simulation)
            diagnosed.append((question, reasons))

        # Group by reason code to avoid duplicate fixes
        by_reason: dict[ReasonCode, list[QuestionResult]] = {}
        for question, reasons in diagnosed:
            for reason in reasons:
                if reason not in by_reason:
                    by_reason[reason] = []
                by_reason[reason].append(question)

        # Generate fixes for each reason code
        fixes: list[Fix] = []
        for reason_code, questions in by_reason.items():
            fix = self._generate_fix(
                reason_code=reason_code,
                questions=questions,
                site_content=site_content,
                company_name=simulation.company_name,
            )
            fixes.append(fix)

        # Sort by priority and impact
        fixes.sort(key=lambda f: (f.priority, -f.estimated_impact))

        # Limit fixes
        fixes = fixes[: self.config.max_fixes]

        # Calculate summary stats
        critical = sum(1 for f in fixes if f.reason_info.severity == "critical")
        high = sum(1 for f in fixes if f.reason_info.severity == "high")
        total_impact = min(1.0, sum(f.estimated_impact for f in fixes))

        categories = list({cat for f in fixes for cat in f.affected_categories})
        questions_addressed = len({qid for f in fixes for qid in f.affected_question_ids})

        return FixPlan(
            id=uuid4(),
            site_id=simulation.site_id,
            run_id=simulation.run_id,
            company_name=simulation.company_name,
            fixes=fixes,
            total_fixes=len(fixes),
            critical_fixes=critical,
            high_priority_fixes=high,
            estimated_total_impact=total_impact,
            categories_addressed=categories,
            questions_addressed=questions_addressed,
        )

    def _identify_problems(
        self,
        results: list[QuestionResult],
    ) -> list[QuestionResult]:
        """Identify questions with problems to fix."""
        problems: list[QuestionResult] = []

        for result in results:
            is_problem = (
                result.answerability == Answerability.NOT_ANSWERABLE
                or result.answerability == Answerability.CONTRADICTORY
                or (
                    result.answerability == Answerability.PARTIALLY_ANSWERABLE
                    and result.score < self.config.partial_threshold
                )
                or (
                    result.answerability == Answerability.FULLY_ANSWERABLE
                    and result.score < self.config.low_score_threshold
                )
            )
            if is_problem:
                problems.append(result)

        return problems

    def _diagnose_reasons(
        self,
        question: QuestionResult,
        _simulation: SimulationResult,
    ) -> list[ReasonCode]:
        """Diagnose reason codes for a problematic question."""
        reasons: list[ReasonCode] = []

        # Check for contradictory info
        if question.answerability == Answerability.CONTRADICTORY:
            reasons.append(ReasonCode.INCONSISTENT)

        # Check for no content retrieved
        if question.context.total_chunks == 0:
            # Could be missing content or blocked
            if question.category == QuestionCategory.OFFERINGS:
                reasons.append(ReasonCode.MISSING_FEATURES)
            elif question.category == QuestionCategory.CONTACT:
                reasons.append(ReasonCode.MISSING_CONTACT)
            elif question.category == QuestionCategory.TRUST:
                reasons.append(ReasonCode.MISSING_SOCIAL_PROOF)
            elif question.category == QuestionCategory.IDENTITY:
                reasons.append(ReasonCode.MISSING_DEFINITION)
            else:
                reasons.append(ReasonCode.NO_DEDICATED_PAGE)

        # Check for low relevance (content exists but doesn't match)
        elif question.context.avg_relevance_score < 0.4:
            reasons.append(ReasonCode.BURIED_ANSWER)

        # Check signal coverage
        signal_coverage = (
            question.signals_found / question.signals_total if question.signals_total > 0 else 0
        )
        if signal_coverage < 0.3:
            # Most signals missing - content gap
            if "pricing" in question.question_text.lower():
                reasons.append(ReasonCode.MISSING_PRICING)
            elif "contact" in question.question_text.lower():
                reasons.append(ReasonCode.MISSING_CONTACT)
            elif "location" in question.question_text.lower():
                reasons.append(ReasonCode.MISSING_LOCATION)
            elif question.category == QuestionCategory.TRUST:
                reasons.append(ReasonCode.TRUST_GAP)
            else:
                reasons.append(ReasonCode.MISSING_DEFINITION)
        elif signal_coverage < 0.6:
            # Some signals found but incomplete
            reasons.append(ReasonCode.FRAGMENTED_INFO)

        # Check confidence
        if question.confidence == ConfidenceLevel.LOW and not reasons:
            reasons.append(ReasonCode.VAGUE_LANGUAGE)

        # Default if no specific reason found
        if not reasons:
            reasons.append(ReasonCode.BURIED_ANSWER)

        return reasons[:2]  # Limit to top 2 reasons per question

    def _generate_fix(
        self,
        reason_code: ReasonCode,
        questions: list[QuestionResult],
        site_content: dict[str, str] | None,
        company_name: str,
    ) -> Fix:
        """Generate a fix for a reason code."""
        reason_info = get_reason_info(reason_code)
        template = get_template(reason_code)

        # Get affected categories
        categories = list({q.category for q in questions})

        # Get question IDs
        question_ids = [q.question_id for q in questions]

        # Extract relevant content from site
        extracted = self._extract_content(questions, site_content)

        # Build scaffold
        scaffold = self._build_scaffold(
            template=template,
            company_name=company_name,
            extracted=extracted,
        )

        # Calculate estimated impact
        impact = self._estimate_impact(reason_info, questions)

        # Determine effort level
        effort = self._determine_effort(reason_code, len(questions))

        # Suggest target URL
        target_url = self._suggest_target_url(reason_code, categories)

        return Fix(
            id=uuid4(),
            reason_code=reason_code,
            reason_info=reason_info,
            template=template,
            affected_question_ids=question_ids,
            affected_categories=categories,
            scaffold=scaffold,
            extracted_content=extracted,
            priority=template.priority,
            estimated_impact=impact,
            effort_level=effort,
            target_url=target_url,
        )

    def _extract_content(
        self,
        questions: list[QuestionResult],
        site_content: dict[str, str] | None,
    ) -> list[ExtractedContent]:
        """Extract relevant content from site for scaffold."""
        if not self.config.extract_site_content or not site_content:
            return []

        extracted: list[ExtractedContent] = []

        # Get high-relevance chunks from question results
        for question in questions:
            for chunk in question.context.chunks[: self.config.max_extracted_snippets]:
                if chunk.score >= 0.5:
                    source_url = chunk.metadata.get("source_url", "")
                    extracted.append(
                        ExtractedContent(
                            text=chunk.content[:500],
                            source_url=source_url,
                            relevance_score=chunk.score,
                            context=question.question_text,
                        )
                    )

        # Deduplicate and sort by relevance
        seen_texts: set[str] = set()
        unique: list[ExtractedContent] = []
        for ec in sorted(extracted, key=lambda x: -x.relevance_score):
            text_key = ec.text[:100]
            if text_key not in seen_texts:
                seen_texts.add(text_key)
                unique.append(ec)

        return unique[: self.config.max_extracted_snippets]

    def _build_scaffold(
        self,
        template: FixTemplate,
        company_name: str,
        extracted: list[ExtractedContent],
    ) -> str:
        """Build the fix scaffold with placeholders filled where possible."""
        scaffold = template.scaffold_template

        # Fill in company name
        scaffold = scaffold.replace("[COMPANY_NAME]", company_name)

        # Add extracted content as suggestions if available
        if extracted and self.config.include_examples:
            scaffold += "\n\n---\n\n## Existing Content You Can Reference\n\n"
            for _i, ec in enumerate(extracted, 1):
                scaffold += f"### From {ec.source_url or 'your site'}\n"
                scaffold += f"(Relevance: {ec.relevance_score:.0%})\n\n"
                scaffold += f'> "{ec.text}"\n\n'

        # Add examples if configured
        if self.config.include_examples and template.examples:
            scaffold += "\n\n---\n\n## Examples\n\n"
            for example in template.examples[:3]:
                scaffold += f"- {example}\n"

        return scaffold

    def _estimate_impact(
        self,
        reason_info: ReasonCodeInfo,
        questions: list[QuestionResult],
    ) -> float:
        """Estimate score impact of implementing this fix."""
        # Base impact from reason code
        base_impact = reason_info.typical_impact

        # Scale by number of affected questions
        question_factor = min(1.5, 1.0 + (len(questions) - 1) * 0.1)

        # Scale by average question weight
        avg_weight = sum(q.weight for q in questions) / len(questions)

        return min(0.5, base_impact * question_factor * avg_weight)

    def _determine_effort(
        self,
        reason_code: ReasonCode,
        affected_count: int,
    ) -> str:
        """Determine effort level for implementing fix."""
        # Technical fixes are higher effort
        technical_codes = {
            ReasonCode.RENDER_REQUIRED,
            ReasonCode.BLOCKED_BY_ROBOTS,
        }
        if reason_code in technical_codes:
            return "high"

        # Content creation is medium effort
        creation_codes = {
            ReasonCode.NO_DEDICATED_PAGE,
            ReasonCode.MISSING_SOCIAL_PROOF,
            ReasonCode.NO_AUTHORITY,
        }
        if reason_code in creation_codes:
            return "medium"

        # Multiple affected questions increases effort
        if affected_count > 3:
            return "medium"

        return "low"

    def _suggest_target_url(
        self,
        reason_code: ReasonCode,
        categories: list[QuestionCategory],
    ) -> str | None:
        """Suggest a URL path for the fix."""
        url_suggestions = {
            ReasonCode.MISSING_PRICING: "/pricing",
            ReasonCode.MISSING_CONTACT: "/contact",
            ReasonCode.MISSING_FEATURES: "/features",
            ReasonCode.MISSING_SOCIAL_PROOF: "/testimonials",
            ReasonCode.NO_AUTHORITY: "/about",
            ReasonCode.MISSING_DEFINITION: "/about",
            ReasonCode.MISSING_LOCATION: "/locations",
        }

        if reason_code in url_suggestions:
            return url_suggestions[reason_code]

        # Suggest based on category
        category_urls = {
            QuestionCategory.IDENTITY: "/about",
            QuestionCategory.OFFERINGS: "/services",
            QuestionCategory.CONTACT: "/contact",
            QuestionCategory.TRUST: "/testimonials",
            QuestionCategory.DIFFERENTIATION: "/why-us",
        }

        for category in categories:
            if category in category_urls:
                return category_urls[category]

        return None


def generate_fix_plan(
    simulation: SimulationResult,
    site_content: dict[str, str] | None = None,
    config: FixGeneratorConfig | None = None,
) -> FixPlan:
    """
    Convenience function to generate a fix plan.

    Args:
        simulation: Simulation result to analyze
        site_content: Optional dict of URL -> content
        config: Optional configuration

    Returns:
        FixPlan with prioritized fixes
    """
    generator = FixGenerator(config)
    return generator.generate(simulation, site_content)
