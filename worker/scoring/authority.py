"""Authority Signals score calculator.

Calculates the Authority Signals pillar score (15 points in v2)
based on E-E-A-T signals: author attribution, credentials,
citations, original data, and content freshness.
"""

from dataclasses import dataclass, field

import structlog

from worker.extraction.authority import AuthorityAnalysis

logger = structlog.get_logger(__name__)


# Component weights within Authority Signals (total = 100 for internal scoring)
AUTHORITY_WEIGHTS = {
    "author_attribution": 27,  # 4 points in v2
    "author_credentials": 20,  # 3 points in v2
    "primary_citations": 20,  # 3 points in v2
    "content_freshness": 20,  # 3 points in v2
    "original_data": 13,  # 2 points in v2
}


@dataclass
class AuthorityComponent:
    """Score for a single authority component."""

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
class AuthoritySignalsScore:
    """Complete Authority Signals score with breakdown."""

    total_score: float  # 0-100
    level: str  # full, partial, limited (progress-based)
    max_points: float = 15.0  # Points this contributes to v2 score

    # Component scores
    components: list[AuthorityComponent] = field(default_factory=list)

    # Issues that should be fixed
    critical_issues: list[str] = field(default_factory=list)
    all_issues: list[str] = field(default_factory=list)

    # Recommendations
    recommendations: list[str] = field(default_factory=list)

    # Raw analysis for detailed inspection
    authority_analysis: AuthorityAnalysis | None = None

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
            "AUTHORITY SIGNALS SCORE",
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
            icon = "+" if comp.level == "full" else "!" if comp.level == "partial" else "X"
            lines.append(
                f"[{icon}] {comp.name}: {comp.raw_score:.0f}/100 x {comp.weight:.0%} = "
                f"{comp.weighted_score:.1f}"
            )
            lines.append(f"    {comp.explanation}")

        if self.critical_issues:
            lines.extend(
                [
                    "",
                    "-" * 50,
                    "CRITICAL ISSUES",
                    "-" * 50,
                ]
            )
            for issue in self.critical_issues:
                lines.append(f"  * {issue}")

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
                lines.append(f"  * {rec}")

        lines.append("")
        lines.append("=" * 50)

        return "\n".join(lines)


class AuthorityScoreCalculator:
    """Calculates Authority Signals score from authority analysis."""

    def calculate(
        self,
        authority_analysis: AuthorityAnalysis,
    ) -> AuthoritySignalsScore:
        """
        Calculate Authority Signals score from authority analysis.

        Args:
            authority_analysis: Complete authority analysis result

        Returns:
            AuthoritySignalsScore with full breakdown
        """
        components = []
        critical_issues = []
        all_issues = []
        recommendations = []
        total_weighted = 0.0

        # 1. Author Attribution (27%)
        _, author_comp = self._score_author_attribution(authority_analysis)
        components.append(author_comp)
        total_weighted += author_comp.weighted_score
        if not authority_analysis.has_author:
            critical_issues.append("No author attribution found")
            recommendations.append("Add author byline to content")

        # 2. Author Credentials (20%)
        _, cred_comp = self._score_author_credentials(authority_analysis)
        components.append(cred_comp)
        total_weighted += cred_comp.weighted_score
        if authority_analysis.has_author and not authority_analysis.has_credentials:
            all_issues.append("Author lacks visible credentials")
            recommendations.append("Add author bio with credentials and expertise")

        # 3. Primary Source Citations (20%)
        _, cite_comp = self._score_citations(authority_analysis)
        components.append(cite_comp)
        total_weighted += cite_comp.weighted_score
        if authority_analysis.authoritative_citations == 0:
            if authority_analysis.total_citations > 0:
                # Has citations but none are authoritative - this is a missed opportunity
                all_issues.append(
                    f"{authority_analysis.total_citations} citations found but none are authoritative sources. "
                    "AI models prioritize content backed by primary sources (.gov, .edu, research papers)."
                )
            else:
                # No citations at all - more critical
                critical_issues.append(
                    "No citations to authoritative sources. AI models strongly prefer content "
                    "backed by primary sources (research papers, .gov, .edu, official docs)."
                )
            recommendations.append(
                "Add 3-5 links to authoritative sources: research papers, .gov/.edu sites, "
                "official documentation, or industry reports"
            )

        # 4. Content Freshness (20%)
        _, fresh_comp = self._score_freshness(authority_analysis)
        components.append(fresh_comp)
        total_weighted += fresh_comp.weighted_score
        if not authority_analysis.has_visible_date:
            all_issues.append("No visible publication/update date")
            recommendations.append("Add visible publication and update dates")
        elif authority_analysis.freshness_level in ["stale", "very_stale"]:
            all_issues.append(
                f"Content is {authority_analysis.freshness_level} "
                f"({authority_analysis.days_since_published} days old)"
            )
            recommendations.append("Review and update content, then update dates")

        # 5. Original Data Markers (13%)
        _, data_comp = self._score_original_data(authority_analysis)
        components.append(data_comp)
        total_weighted += data_comp.weighted_score
        if not authority_analysis.has_original_data:
            recommendations.append("Add original research, data, or unique insights")

        # Calculate total
        total_score = total_weighted

        # Determine level
        if total_score >= 70:
            level = "full"
        elif total_score >= 40:
            level = "partial"
        else:
            level = "limited"

        result = AuthoritySignalsScore(
            total_score=total_score,
            level=level,
            components=components,
            critical_issues=critical_issues,
            all_issues=all_issues,
            recommendations=recommendations,
            authority_analysis=authority_analysis,
        )

        logger.info(
            "authority_score_calculated",
            total_score=total_score,
            level=level,
            has_author=authority_analysis.has_author,
            authoritative_citations=authority_analysis.authoritative_citations,
        )

        return result

    def _score_author_attribution(
        self, analysis: AuthorityAnalysis
    ) -> tuple[float, AuthorityComponent]:
        """Score author attribution."""
        weight = AUTHORITY_WEIGHTS["author_attribution"] / 100

        if not analysis.has_author:
            return 0.0, AuthorityComponent(
                name="Author Attribution",
                raw_score=0.0,
                weight=weight,
                weighted_score=0.0,
                level="limited",
                explanation="No author byline found",
            )

        score = 50.0  # Base score for having an author
        details = {"author_name": analysis.primary_author.name if analysis.primary_author else None}

        if analysis.primary_author:
            if analysis.primary_author.is_linked:
                score += 20
                details["is_linked"] = True
            if analysis.primary_author.has_photo:
                score += 15
                details["has_photo"] = True
            if analysis.primary_author.has_social_links:
                score += 15
                details["has_social"] = True

        score = min(100, score)
        level = "full" if score >= 70 else "partial" if score >= 40 else "limited"

        author_name = analysis.primary_author.name if analysis.primary_author else "Unknown"
        explanation = f"Author: {author_name}"
        if analysis.primary_author and analysis.primary_author.is_linked:
            explanation += " (linked)"

        return score, AuthorityComponent(
            name="Author Attribution",
            raw_score=score,
            weight=weight,
            weighted_score=score * weight,
            level=level,
            explanation=explanation,
            details=details,
        )

    def _score_author_credentials(
        self, analysis: AuthorityAnalysis
    ) -> tuple[float, AuthorityComponent]:
        """Score author credentials and expertise."""
        weight = AUTHORITY_WEIGHTS["author_credentials"] / 100

        if not analysis.has_author:
            return 0.0, AuthorityComponent(
                name="Author Credentials",
                raw_score=0.0,
                weight=weight,
                weighted_score=0.0,
                level="partial",
                explanation="No author to evaluate credentials",
            )

        score = 0.0
        details = {}

        # Check for credentials
        if analysis.has_credentials:
            score += 40
            details["credentials"] = analysis.credentials_found[:3]

        # Check for bio
        if analysis.has_author_bio:
            score += 30
            details["has_bio"] = True

        # Check for photo (indicates real person)
        if analysis.has_author_photo:
            score += 20
            details["has_photo"] = True

        # Bonus for multiple credentials
        if len(analysis.credentials_found) >= 3:
            score += 10

        score = min(100, score)
        level = "full" if score >= 70 else "partial" if score >= 40 else "limited"

        if analysis.has_credentials:
            creds = ", ".join(analysis.credentials_found[:2])
            explanation = f"Credentials found: {creds}"
        elif analysis.has_author_bio:
            explanation = "Author bio present, no formal credentials"
        else:
            explanation = "No credentials or bio found"

        return score, AuthorityComponent(
            name="Author Credentials",
            raw_score=score,
            weight=weight,
            weighted_score=score * weight,
            level=level,
            explanation=explanation,
            details=details,
        )

    def _score_citations(self, analysis: AuthorityAnalysis) -> tuple[float, AuthorityComponent]:
        """Score primary source citations."""
        weight = AUTHORITY_WEIGHTS["primary_citations"] / 100

        if analysis.total_citations == 0:
            return 0.0, AuthorityComponent(
                name="Primary Citations",
                raw_score=0.0,
                weight=weight,
                weighted_score=0.0,
                level="limited",
                explanation="No external citations - AI models prefer sourced content",
            )

        # Score based on authoritative citations
        auth_count = analysis.authoritative_citations

        if auth_count >= 5:
            score = 100.0
            level = "full"
            explanation = f"{auth_count} authoritative citations (excellent)"
        elif auth_count >= 3:
            score = 80.0
            level = "full"
            explanation = f"{auth_count} authoritative citations"
        elif auth_count >= 1:
            score = 50.0
            level = "partial"
            explanation = f"{auth_count} authoritative citation(s), add more primary sources"
        else:
            score = 15.0
            level = "limited"
            explanation = (
                f"{analysis.total_citations} citations but 0 authoritative - "
                "add .gov, .edu, or research sources"
            )

        details = {
            "total_citations": analysis.total_citations,
            "authoritative_citations": auth_count,
        }

        return score, AuthorityComponent(
            name="Primary Citations",
            raw_score=score,
            weight=weight,
            weighted_score=score * weight,
            level=level,
            explanation=explanation,
            details=details,
        )

    def _score_freshness(self, analysis: AuthorityAnalysis) -> tuple[float, AuthorityComponent]:
        """Score content freshness from visible dates."""
        weight = AUTHORITY_WEIGHTS["content_freshness"] / 100

        if not analysis.has_visible_date:
            return 0.0, AuthorityComponent(
                name="Content Freshness",
                raw_score=0.0,
                weight=weight,
                weighted_score=0.0,
                level="partial",
                explanation="No visible date found",
            )

        freshness = analysis.freshness_level
        days = analysis.days_since_published

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
        else:  # very_stale or unknown
            score = 15.0
            level = "limited"
            explanation = (
                f"Content updated {days} days ago (very stale)" if days else "Date unclear"
            )

        details = {
            "days_since_published": days,
            "freshness_level": freshness,
        }

        return score, AuthorityComponent(
            name="Content Freshness",
            raw_score=score,
            weight=weight,
            weighted_score=score * weight,
            level=level,
            explanation=explanation,
            details=details,
        )

    def _score_original_data(self, analysis: AuthorityAnalysis) -> tuple[float, AuthorityComponent]:
        """Score original data and research markers."""
        weight = AUTHORITY_WEIGHTS["original_data"] / 100

        if not analysis.has_original_data:
            # Original data is a bonus, not having it isn't critical
            return 40.0, AuthorityComponent(
                name="Original Data",
                raw_score=40.0,
                weight=weight,
                weighted_score=40.0 * weight,
                level="partial",
                explanation="No original research markers found (optional)",
            )

        count = analysis.original_data_count

        if count >= 5:
            score = 100.0
            level = "full"
            explanation = f"{count} original data markers (excellent)"
        elif count >= 3:
            score = 85.0
            level = "full"
            explanation = f"{count} original data markers"
        elif count >= 1:
            score = 70.0
            level = "full"
            explanation = f"{count} original data marker(s)"
        else:
            score = 40.0
            level = "partial"
            explanation = "Minimal original data"

        details = {
            "marker_count": count,
        }

        return score, AuthorityComponent(
            name="Original Data",
            raw_score=score,
            weight=weight,
            weighted_score=score * weight,
            level=level,
            explanation=explanation,
            details=details,
        )


def calculate_authority_score(
    authority_analysis: AuthorityAnalysis,
) -> AuthoritySignalsScore:
    """
    Convenience function to calculate Authority Signals score.

    Args:
        authority_analysis: Complete authority analysis result

    Returns:
        AuthoritySignalsScore with full breakdown
    """
    calculator = AuthorityScoreCalculator()
    return calculator.calculate(authority_analysis)
