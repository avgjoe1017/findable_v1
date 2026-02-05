"""Structure Quality score calculator.

Calculates the Structure Quality pillar score (20 points in v2)
based on heading hierarchy, answer-first content, FAQ sections,
internal linking, and extractable formats.
"""

from dataclasses import dataclass, field

import structlog

from worker.extraction.structure import StructureAnalysis

logger = structlog.get_logger(__name__)


# Component weights within Structure Quality (total = 100 for internal scoring)
STRUCTURE_WEIGHTS = {
    "heading_hierarchy": 25,  # 5 points in v2
    "answer_first": 25,  # 5 points in v2
    "faq_sections": 20,  # 4 points in v2
    "internal_links": 15,  # 3 points in v2
    "extractable_formats": 15,  # 3 points in v2
}


@dataclass
class StructureComponent:
    """Score for a single structure component."""

    name: str
    raw_score: float  # 0-100
    weight: float
    weighted_score: float
    level: str  # full, partial, limited (progress-based)
    explanation: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "raw_score": round(self.raw_score, 2),
            "weight": self.weight,
            "weighted_score": round(self.weighted_score, 2),
            "level": self.level,
            "explanation": self.explanation,
            "details": self.details,
        }


@dataclass
class StructureQualityScore:
    """Complete Semantic Structure score with breakdown.

    Measures H1 uniqueness, heading hierarchy, and semantic nesting.
    Pages can look well-organized to humans while scoring low here
    if the underlying HTML markup is poorly structured for machines.
    """

    total_score: float  # 0-100
    level: str  # full, partial, limited (progress-based)
    max_points: float = 20.0  # Points this contributes to v2 score

    # Component scores
    components: list[StructureComponent] = field(default_factory=list)

    # Issues that should be fixed
    critical_issues: list[str] = field(default_factory=list)
    all_issues: list[str] = field(default_factory=list)

    # Recommendations
    recommendations: list[str] = field(default_factory=list)

    # Raw analysis for detailed inspection
    structure_analysis: StructureAnalysis | None = None

    # Aggregate H1 sub-metrics (filled by aggregate_structure_scores)
    pages_analyzed: int = 0
    pages_missing_h1: int = 0  # H1 count == 0
    pages_multiple_h1: int = 0  # H1 count > 1
    avg_heading_issues: float = 0.0  # Average issues per page
    avg_heading_score: float = 0.0  # Average raw heading score

    def to_dict(self) -> dict:
        result = {
            "total_score": round(self.total_score, 2),
            "level": self.level,
            "max_points": self.max_points,
            "points_earned": round(self.total_score / 100 * self.max_points, 2),
            "components": [c.to_dict() for c in self.components],
            "critical_issues": self.critical_issues,
            "all_issues": self.all_issues,
            "recommendations": self.recommendations,
        }
        # Include H1 sub-metrics when available (aggregated scores)
        if self.pages_analyzed > 0:
            result["h1_sub_metrics"] = {
                "pages_analyzed": self.pages_analyzed,
                "pages_missing_h1": self.pages_missing_h1,
                "pct_missing_h1": round(self.pages_missing_h1 / self.pages_analyzed * 100, 1),
                "pages_multiple_h1": self.pages_multiple_h1,
                "pct_multiple_h1": round(self.pages_multiple_h1 / self.pages_analyzed * 100, 1),
                "avg_heading_issues": round(self.avg_heading_issues, 1),
                "avg_heading_score": round(self.avg_heading_score, 1),
            }
        return result

    def show_the_math(self) -> str:
        """Generate human-readable calculation breakdown."""
        lines = [
            "=" * 50,
            "SEMANTIC STRUCTURE SCORE",
            "=" * 50,
            "",
            f"Total Score: {self.total_score:.1f}/100 ({self.level.upper()})",
            f"Points Earned: {self.total_score / 100 * self.max_points:.1f}/{self.max_points}",
            "",
            "-" * 50,
            "COMPONENT BREAKDOWN",
            "-" * 50,
        ]

        for comp in self.components:
            icon = "✅" if comp.level == "full" else "⚠️" if comp.level == "partial" else "❌"
            lines.append(
                f"{icon} {comp.name}: {comp.raw_score:.0f}/100 × {comp.weight:.0%} = "
                f"{comp.weighted_score:.1f}"
            )
            lines.append(f"   → {comp.explanation}")

        if self.critical_issues:
            lines.extend(
                [
                    "",
                    "-" * 50,
                    "🔴 CRITICAL ISSUES",
                    "-" * 50,
                ]
            )
            for issue in self.critical_issues:
                lines.append(f"  • {issue}")

        if self.recommendations:
            lines.extend(
                [
                    "",
                    "-" * 50,
                    "RECOMMENDATIONS",
                    "-" * 50,
                ]
            )
            for rec in self.recommendations[:5]:
                lines.append(f"  • {rec}")

        lines.append("")
        lines.append("=" * 50)

        return "\n".join(lines)


class StructureScoreCalculator:
    """Calculates Structure Quality score from structure analysis."""

    def calculate(
        self,
        structure_analysis: StructureAnalysis,
    ) -> StructureQualityScore:
        """
        Calculate Structure Quality score from structure analysis.

        Args:
            structure_analysis: Complete structure analysis result

        Returns:
            StructureQualityScore with full breakdown
        """
        components = []
        critical_issues = []
        all_issues = []
        total_weighted = 0.0

        # 1. Heading Hierarchy (25%)
        heading_score, heading_comp = self._score_headings(structure_analysis)
        components.append(heading_comp)
        total_weighted += heading_comp.weighted_score
        if not structure_analysis.headings.hierarchy_valid:
            for issue in structure_analysis.headings.issues[:3]:
                all_issues.append(f"Heading: {issue.details}")
        if structure_analysis.headings.h1_count == 0:
            critical_issues.append("Missing H1 heading")

        # 2. Answer-First (25%)
        answer_score, answer_comp = self._score_answer_first(structure_analysis)
        components.append(answer_comp)
        total_weighted += answer_comp.weighted_score
        if not structure_analysis.answer_first.answer_in_first_paragraph:
            all_issues.append("Answer not in first paragraph")

        # 3. FAQ Sections (20%)
        faq_score, faq_comp = self._score_faq(structure_analysis)
        components.append(faq_comp)
        total_weighted += faq_comp.weighted_score
        if not structure_analysis.faq.has_faq_section:
            all_issues.append("No FAQ section found")

        # 4. Internal Links (15%)
        links_score, links_comp = self._score_links(structure_analysis)
        components.append(links_comp)
        total_weighted += links_comp.weighted_score
        all_issues.extend(structure_analysis.links.issues[:2])

        # 5. Extractable Formats (15%)
        formats_score, formats_comp = self._score_formats(structure_analysis)
        components.append(formats_comp)
        total_weighted += formats_comp.weighted_score

        # Calculate total
        total_score = total_weighted

        # Determine level
        if total_score >= 80:
            level = "full"
        elif total_score >= 50:
            level = "partial"
        else:
            level = "limited"

        # Compile recommendations
        recommendations = structure_analysis.recommendations[:]

        result = StructureQualityScore(
            total_score=total_score,
            level=level,
            components=components,
            critical_issues=critical_issues,
            all_issues=all_issues,
            recommendations=recommendations,
            structure_analysis=structure_analysis,
        )

        logger.info(
            "structure_score_calculated",
            total_score=total_score,
            level=level,
            critical_issues_count=len(critical_issues),
        )

        return result

    def _score_headings(self, analysis: StructureAnalysis) -> tuple[float, StructureComponent]:
        """Score heading hierarchy."""
        weight = STRUCTURE_WEIGHTS["heading_hierarchy"] / 100
        score = analysis.headings.score

        if score >= 80:
            level = "full"
            explanation = f"Valid heading hierarchy ({analysis.headings.h1_count} H1, {analysis.headings.h2_count} H2)"
        elif score >= 50:
            level = "partial"
            explanation = f"Heading issues found ({len(analysis.headings.issues)} issues)"
        else:
            level = "limited"
            if analysis.headings.h1_count == 0:
                explanation = "Missing H1 heading"
            else:
                explanation = "Multiple heading hierarchy issues"

        return score, StructureComponent(
            name="Heading Hierarchy",
            raw_score=score,
            weight=weight,
            weighted_score=score * weight,
            level=level,
            explanation=explanation,
            details={
                "h1_count": analysis.headings.h1_count,
                "h2_count": analysis.headings.h2_count,
                "total_headings": analysis.headings.total_headings,
                "hierarchy_valid": analysis.headings.hierarchy_valid,
                "skip_count": analysis.headings.skip_count,
                "duplicate_count": analysis.headings.duplicate_count,
                "issues": len(analysis.headings.issues),
            },
        )

    def _score_answer_first(self, analysis: StructureAnalysis) -> tuple[float, StructureComponent]:
        """Score answer-first content structure."""
        weight = STRUCTURE_WEIGHTS["answer_first"] / 100
        score = analysis.answer_first.score

        if score >= 80:
            level = "full"
            explanation = "Content leads with answer/definition"
        elif score >= 50:
            level = "partial"
            explanation = "Answer not immediately apparent"
        else:
            level = "limited"
            explanation = "Answer buried in content"

        return score, StructureComponent(
            name="Answer-First Content",
            raw_score=score,
            weight=weight,
            weighted_score=score * weight,
            level=level,
            explanation=explanation,
            details={
                "answer_in_first_paragraph": analysis.answer_first.answer_in_first_paragraph,
                "has_definition": analysis.answer_first.has_definition,
                "has_number": analysis.answer_first.has_number,
            },
        )

    def _score_faq(self, analysis: StructureAnalysis) -> tuple[float, StructureComponent]:
        """Score FAQ sections."""
        weight = STRUCTURE_WEIGHTS["faq_sections"] / 100
        score = analysis.faq.score

        if score >= 80:
            level = "full"
            if analysis.faq.has_faq_schema:
                explanation = f"FAQ section with schema ({analysis.faq.faq_count} Q&As)"
            else:
                explanation = f"FAQ section found ({analysis.faq.faq_count} Q&As)"
        elif score >= 50:
            level = "partial"
            explanation = f"Basic FAQ section ({analysis.faq.faq_count} Q&As, no schema)"
        else:
            level = "partial"  # FAQ is optional, so not critical
            explanation = "No FAQ section found"

        return score, StructureComponent(
            name="FAQ Sections",
            raw_score=score,
            weight=weight,
            weighted_score=score * weight,
            level=level,
            explanation=explanation,
            details={
                "has_faq": analysis.faq.has_faq_section,
                "faq_count": analysis.faq.faq_count,
                "has_schema": analysis.faq.has_faq_schema,
            },
        )

    def _score_links(self, analysis: StructureAnalysis) -> tuple[float, StructureComponent]:
        """Score internal linking."""
        weight = STRUCTURE_WEIGHTS["internal_links"] / 100
        score = analysis.links.score

        if score >= 80:
            level = "full"
            explanation = f"Good internal linking ({analysis.links.internal_links} links)"
        elif score >= 50:
            level = "partial"
            explanation = f"Internal linking could improve ({analysis.links.density_level})"
        else:
            level = "limited"
            explanation = f"Poor internal linking ({analysis.links.internal_links} links)"

        return score, StructureComponent(
            name="Internal Linking",
            raw_score=score,
            weight=weight,
            weighted_score=score * weight,
            level=level,
            explanation=explanation,
            details={
                "internal_links": analysis.links.internal_links,
                "density_level": analysis.links.density_level,
                "good_anchors": analysis.links.good_anchor_count,
            },
        )

    def _score_formats(self, analysis: StructureAnalysis) -> tuple[float, StructureComponent]:
        """Score extractable formats."""
        weight = STRUCTURE_WEIGHTS["extractable_formats"] / 100
        score = analysis.formats.score

        formats_found = []
        if analysis.formats.table_count > 0:
            formats_found.append(f"{analysis.formats.table_count} tables")
        if analysis.formats.total_list_items > 0:
            formats_found.append(f"{analysis.formats.total_list_items} list items")
        if analysis.formats.code_block_count > 0:
            formats_found.append(f"{analysis.formats.code_block_count} code blocks")

        if score >= 80:
            level = "full"
            explanation = f"Rich extractable formats: {', '.join(formats_found) or 'various'}"
        elif score >= 50:
            level = "partial"
            explanation = f"Some extractable formats: {', '.join(formats_found) or 'limited'}"
        else:
            level = "partial"  # Not critical, just suboptimal
            explanation = "Few extractable formats (tables, lists)"

        return score, StructureComponent(
            name="Extractable Formats",
            raw_score=score,
            weight=weight,
            weighted_score=score * weight,
            level=level,
            explanation=explanation,
            details={
                "tables": analysis.formats.table_count,
                "lists": analysis.formats.ordered_list_count
                + analysis.formats.unordered_list_count,
                "code_blocks": analysis.formats.code_block_count,
            },
        )


def calculate_structure_score(
    structure_analysis: StructureAnalysis,
) -> StructureQualityScore:
    """
    Convenience function to calculate Structure Quality score.

    Args:
        structure_analysis: Complete structure analysis result

    Returns:
        StructureQualityScore with full breakdown
    """
    calculator = StructureScoreCalculator()
    return calculator.calculate(structure_analysis)
