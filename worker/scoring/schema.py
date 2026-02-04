"""Schema Richness score calculator.

Calculates the Schema Richness pillar score (15 points in v2)
based on structured data quality, completeness, and validation.
"""

from dataclasses import dataclass, field

import structlog

from worker.extraction.schema import SchemaAnalysis

logger = structlog.get_logger(__name__)


# Component weights within Schema Richness (total = 100 for internal scoring)
SCHEMA_WEIGHTS = {
    "faq_page": 27,  # 4 points in v2 - highest impact
    "article_author": 20,  # 3 points in v2
    "date_modified": 20,  # 3 points in v2
    "organization": 13,  # 2 points in v2
    "how_to": 13,  # 2 points in v2
    "validation": 7,  # 1 point in v2
}


@dataclass
class SchemaComponent:
    """Score for a single schema component."""

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
class SchemaRichnessScore:
    """Complete Schema Richness score with breakdown."""

    total_score: float  # 0-100
    level: str  # full, partial, limited (progress-based)
    max_points: float = 15.0  # Points this contributes to v2 score

    # Component scores
    components: list[SchemaComponent] = field(default_factory=list)

    # Issues that should be fixed
    critical_issues: list[str] = field(default_factory=list)
    all_issues: list[str] = field(default_factory=list)

    # Recommendations
    recommendations: list[str] = field(default_factory=list)

    # Raw analysis for detailed inspection
    schema_analysis: SchemaAnalysis | None = None

    def to_dict(self) -> dict:
        return {
            "total_score": round(self.total_score, 2),
            "level": self.level,
            "max_points": self.max_points,
            "points_earned": round(self.total_score / 100 * self.max_points, 2),
            "components": [c.to_dict() for c in self.components],
            "critical_issues": self.critical_issues,
            "all_issues": self.all_issues,
            "recommendations": self.recommendations,
        }

    def show_the_math(self) -> str:
        """Generate human-readable calculation breakdown."""
        lines = [
            "=" * 50,
            "SCHEMA RICHNESS SCORE",
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


class SchemaScoreCalculator:
    """Calculates Schema Richness score from schema analysis."""

    def calculate(
        self,
        schema_analysis: SchemaAnalysis,
    ) -> SchemaRichnessScore:
        """
        Calculate Schema Richness score from schema analysis.

        Args:
            schema_analysis: Complete schema analysis result

        Returns:
            SchemaRichnessScore with full breakdown
        """
        components = []
        critical_issues = []
        all_issues = []
        recommendations = []
        total_weighted = 0.0

        # 1. FAQPage Schema (27%)
        faq_score, faq_comp = self._score_faq_page(schema_analysis)
        components.append(faq_comp)
        total_weighted += faq_comp.weighted_score
        if not schema_analysis.has_faq_page:
            recommendations.append("Add FAQPage schema to your FAQ content (35-40% citation lift)")

        # 2. Article with Author (20%)
        article_score, article_comp = self._score_article_author(schema_analysis)
        components.append(article_comp)
        total_weighted += article_comp.weighted_score
        if schema_analysis.has_article and not schema_analysis.has_author:
            all_issues.append("Article schema missing author")
            recommendations.append("Add author information to Article schema")

        # 3. dateModified (20%)
        date_score, date_comp = self._score_date_modified(schema_analysis)
        components.append(date_comp)
        total_weighted += date_comp.weighted_score
        if not schema_analysis.has_date_modified:
            recommendations.append("Add dateModified to schema for freshness signals")
        elif schema_analysis.freshness_level in ["stale", "very_stale"]:
            all_issues.append(
                f"Content is {schema_analysis.freshness_level} "
                f"({schema_analysis.days_since_modified} days since update)"
            )

        # 4. Organization Schema (13%)
        org_score, org_comp = self._score_organization(schema_analysis)
        components.append(org_comp)
        total_weighted += org_comp.weighted_score
        if not schema_analysis.has_organization:
            recommendations.append("Add Organization schema for entity recognition")

        # 5. HowTo Schema (13%)
        howto_score, howto_comp = self._score_how_to(schema_analysis)
        components.append(howto_comp)
        total_weighted += howto_comp.weighted_score

        # 6. Validation (7%)
        validation_score, validation_comp = self._score_validation(schema_analysis)
        components.append(validation_comp)
        total_weighted += validation_comp.weighted_score
        if schema_analysis.error_count > 0:
            critical_issues.append(f"{schema_analysis.error_count} schema validation errors found")
            for error in schema_analysis.validation_errors[:3]:
                all_issues.append(error.message)

        # Calculate total
        total_score = total_weighted

        # Determine level
        if total_score >= 70:
            level = "full"
        elif total_score >= 40:
            level = "partial"
        else:
            level = "limited"

        result = SchemaRichnessScore(
            total_score=total_score,
            level=level,
            components=components,
            critical_issues=critical_issues,
            all_issues=all_issues,
            recommendations=recommendations,
            schema_analysis=schema_analysis,
        )

        logger.info(
            "schema_score_calculated",
            total_score=total_score,
            level=level,
            total_schemas=schema_analysis.total_schemas,
        )

        return result

    def _score_faq_page(self, analysis: SchemaAnalysis) -> tuple[float, SchemaComponent]:
        """Score FAQPage schema."""
        weight = SCHEMA_WEIGHTS["faq_page"] / 100

        if not analysis.has_faq_page:
            return 0.0, SchemaComponent(
                name="FAQPage Schema",
                raw_score=0.0,
                weight=weight,
                weighted_score=0.0,
                level="partial",
                explanation="No FAQPage schema found",
            )

        # Score based on number of FAQ items
        if analysis.faq_count >= 5:
            score = 100.0
            level = "full"
            explanation = f"FAQPage with {analysis.faq_count} Q&A pairs"
        elif analysis.faq_count >= 3:
            score = 80.0
            level = "full"
            explanation = (
                f"FAQPage with {analysis.faq_count} Q&A pairs (add more for better coverage)"
            )
        elif analysis.faq_count >= 1:
            score = 50.0
            level = "partial"
            explanation = f"FAQPage with only {analysis.faq_count} Q&A pair(s)"
        else:
            score = 25.0
            level = "partial"
            explanation = "FAQPage schema exists but no Q&A pairs found"

        return score, SchemaComponent(
            name="FAQPage Schema",
            raw_score=score,
            weight=weight,
            weighted_score=score * weight,
            level=level,
            explanation=explanation,
            details={"faq_count": analysis.faq_count},
        )

    def _score_article_author(self, analysis: SchemaAnalysis) -> tuple[float, SchemaComponent]:
        """Score Article schema with author."""
        weight = SCHEMA_WEIGHTS["article_author"] / 100

        if not analysis.has_article:
            return 0.0, SchemaComponent(
                name="Article + Author",
                raw_score=0.0,
                weight=weight,
                weighted_score=0.0,
                level="partial",
                explanation="No Article schema found",
            )

        if analysis.has_author and analysis.has_author_credentials:
            score = 100.0
            level = "full"
            explanation = f"Article with author: {analysis.author_name} (with credentials)"
        elif analysis.has_author:
            score = 70.0
            level = "full"
            explanation = f"Article with author: {analysis.author_name}"
        else:
            score = 30.0
            level = "partial"
            explanation = "Article schema missing author"

        return score, SchemaComponent(
            name="Article + Author",
            raw_score=score,
            weight=weight,
            weighted_score=score * weight,
            level=level,
            explanation=explanation,
            details={
                "has_author": analysis.has_author,
                "author_name": analysis.author_name,
            },
        )

    def _score_date_modified(self, analysis: SchemaAnalysis) -> tuple[float, SchemaComponent]:
        """Score dateModified freshness."""
        weight = SCHEMA_WEIGHTS["date_modified"] / 100

        if not analysis.has_date_modified:
            # Check if at least datePublished exists
            if analysis.has_date_published:
                return 30.0, SchemaComponent(
                    name="Content Freshness",
                    raw_score=30.0,
                    weight=weight,
                    weighted_score=30.0 * weight,
                    level="partial",
                    explanation="Has datePublished but no dateModified",
                )
            return 0.0, SchemaComponent(
                name="Content Freshness",
                raw_score=0.0,
                weight=weight,
                weighted_score=0.0,
                level="partial",
                explanation="No date information in schema",
            )

        # Score based on freshness
        freshness = analysis.freshness_level
        days = analysis.days_since_modified

        if freshness == "fresh":
            score = 100.0
            level = "full"
            explanation = f"Content updated {days} days ago (fresh)"
        elif freshness == "recent":
            score = 80.0
            level = "full"
            explanation = f"Content updated {days} days ago (recent)"
        elif freshness == "stale":
            score = 40.0
            level = "partial"
            explanation = f"Content updated {days} days ago (stale)"
        else:  # very_stale
            score = 20.0
            level = "limited"
            explanation = f"Content updated {days} days ago (very stale)"

        return score, SchemaComponent(
            name="Content Freshness",
            raw_score=score,
            weight=weight,
            weighted_score=score * weight,
            level=level,
            explanation=explanation,
            details={
                "date_modified": analysis.date_modified,
                "days_since": days,
                "freshness_level": freshness,
            },
        )

    def _score_organization(self, analysis: SchemaAnalysis) -> tuple[float, SchemaComponent]:
        """Score Organization schema."""
        weight = SCHEMA_WEIGHTS["organization"] / 100

        if analysis.has_organization:
            return 100.0, SchemaComponent(
                name="Organization Schema",
                raw_score=100.0,
                weight=weight,
                weighted_score=100.0 * weight,
                level="full",
                explanation="Organization schema present for entity recognition",
            )

        return 0.0, SchemaComponent(
            name="Organization Schema",
            raw_score=0.0,
            weight=weight,
            weighted_score=0.0,
            level="partial",
            explanation="No Organization schema found",
        )

    def _score_how_to(self, analysis: SchemaAnalysis) -> tuple[float, SchemaComponent]:
        """Score HowTo schema."""
        weight = SCHEMA_WEIGHTS["how_to"] / 100

        if analysis.has_how_to:
            return 100.0, SchemaComponent(
                name="HowTo Schema",
                raw_score=100.0,
                weight=weight,
                weighted_score=100.0 * weight,
                level="full",
                explanation="HowTo schema present for procedural content",
            )

        # HowTo is optional, so no penalty
        return 50.0, SchemaComponent(
            name="HowTo Schema",
            raw_score=50.0,
            weight=weight,
            weighted_score=50.0 * weight,
            level="partial",
            explanation="No HowTo schema (optional for non-procedural content)",
        )

    def _score_validation(self, analysis: SchemaAnalysis) -> tuple[float, SchemaComponent]:
        """Score schema validation."""
        weight = SCHEMA_WEIGHTS["validation"] / 100

        if analysis.total_schemas == 0:
            return 0.0, SchemaComponent(
                name="Schema Validation",
                raw_score=0.0,
                weight=weight,
                weighted_score=0.0,
                level="partial",
                explanation="No schemas to validate",
            )

        if analysis.error_count == 0:
            return 100.0, SchemaComponent(
                name="Schema Validation",
                raw_score=100.0,
                weight=weight,
                weighted_score=100.0 * weight,
                level="full",
                explanation="All schemas valid (0 errors)",
            )

        # Penalize based on error count
        score = max(0, 100 - analysis.error_count * 20)
        level = "partial" if score >= 50 else "limited"

        return score, SchemaComponent(
            name="Schema Validation",
            raw_score=score,
            weight=weight,
            weighted_score=score * weight,
            level=level,
            explanation=f"{analysis.error_count} validation errors found",
            details={"error_count": analysis.error_count},
        )


def calculate_schema_score(
    schema_analysis: SchemaAnalysis,
) -> SchemaRichnessScore:
    """
    Convenience function to calculate Schema Richness score.

    Args:
        schema_analysis: Complete schema analysis result

    Returns:
        SchemaRichnessScore with full breakdown
    """
    calculator = SchemaScoreCalculator()
    return calculator.calculate(schema_analysis)
