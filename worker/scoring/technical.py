"""Technical Readiness score calculator.

Combines robots.txt, TTFB, llms.txt, and JS dependency checks
into a single Technical Readiness score (0-100).

This is the first pillar of the Findable Score v2.
If technical access fails, nothing else matters.
"""

from dataclasses import dataclass, field

import structlog

from worker.crawler.llms_txt import LlmsTxtResult
from worker.crawler.performance import SitePerformanceResult, TTFBResult
from worker.crawler.robots_ai import RobotsTxtAIResult
from worker.extraction.js_detection import JSDetectionResult

logger = structlog.get_logger(__name__)


# Component weights within Technical Readiness (total = 100)
TECHNICAL_WEIGHTS = {
    "robots_txt": 35,  # Most critical - binary gate
    "ttfb": 30,  # Performance critical for AI crawlers
    "llms_txt": 15,  # New standard, not yet required
    "js_accessible": 10,  # Important for content visibility
    "https": 10,  # Trust signal
}


@dataclass
class TechnicalComponent:
    """Score for a single technical component."""

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
class TechnicalReadinessScore:
    """Complete Technical Readiness score with breakdown."""

    total_score: float  # 0-100
    level: str  # full, partial, limited (progress-based)
    max_points: float = 15.0  # Points this contributes to v2 score

    # Component scores
    components: list[TechnicalComponent] = field(default_factory=list)

    # Critical issues that should be fixed immediately
    critical_issues: list[str] = field(default_factory=list)

    # All issues found
    all_issues: list[str] = field(default_factory=list)

    # Raw results for detailed inspection
    robots_result: RobotsTxtAIResult | None = None
    ttfb_result: TTFBResult | SitePerformanceResult | None = None
    llms_txt_result: LlmsTxtResult | None = None
    js_result: JSDetectionResult | None = None
    is_https: bool = True

    def to_dict(self) -> dict:
        return {
            "total_score": round(self.total_score, 2),
            "level": self.level,
            "max_points": self.max_points,
            "points_earned": round(self.total_score / 100 * self.max_points, 2),
            "components": [c.to_dict() for c in self.components],
            "critical_issues": self.critical_issues,
            "all_issues": self.all_issues,
            "robots": self.robots_result.to_dict() if self.robots_result else None,
            "ttfb": self.ttfb_result.to_dict() if self.ttfb_result else None,
            "llms_txt": self.llms_txt_result.to_dict() if self.llms_txt_result else None,
            "js_detection": self.js_result.to_dict() if self.js_result else None,
            "is_https": self.is_https,
        }

    def show_the_math(self) -> str:
        """Generate human-readable calculation breakdown."""
        lines = [
            "=" * 50,
            "TECHNICAL READINESS SCORE",
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
                    "🔴 CRITICAL ISSUES (Fix Immediately)",
                    "-" * 50,
                ]
            )
            for issue in self.critical_issues:
                lines.append(f"  • {issue}")

        if self.all_issues:
            lines.extend(
                [
                    "",
                    "-" * 50,
                    "ALL ISSUES",
                    "-" * 50,
                ]
            )
            for issue in self.all_issues:
                lines.append(f"  • {issue}")

        lines.append("")
        lines.append("=" * 50)

        return "\n".join(lines)


class TechnicalScoreCalculator:
    """Calculates Technical Readiness score from component results."""

    def calculate(
        self,
        robots_result: RobotsTxtAIResult | None = None,
        ttfb_result: TTFBResult | SitePerformanceResult | None = None,
        llms_txt_result: LlmsTxtResult | None = None,
        js_result: JSDetectionResult | None = None,
        is_https: bool = True,
    ) -> TechnicalReadinessScore:
        """
        Calculate Technical Readiness score from component results.

        Args:
            robots_result: AI crawler access check result
            ttfb_result: TTFB measurement result
            llms_txt_result: llms.txt detection result
            js_result: JavaScript dependency detection result
            is_https: Whether site uses HTTPS

        Returns:
            TechnicalReadinessScore with full breakdown
        """
        components = []
        critical_issues = []
        all_issues = []
        total_weighted = 0.0

        # 1. robots.txt (35%)
        robots_score, robots_comp = self._score_robots(robots_result)
        components.append(robots_comp)
        total_weighted += robots_comp.weighted_score
        if robots_result:
            # Search engine blocks are CRITICAL (AI can't find you via indexes)
            if robots_result.critical_blocked:
                critical_issues.append(
                    f"Search engines blocked in robots.txt: {', '.join(robots_result.critical_blocked)}. "
                    "Most AI systems source content from search indexes - blocking these prevents AI visibility entirely."
                )
                all_issues.append(
                    f"Search engines blocked: {', '.join(robots_result.critical_blocked)}"
                )
            # AI crawler blocks are WARNINGS (limits direct access, not search-indexed)
            if robots_result.warning_blocked:
                all_issues.append(
                    f"AI crawlers blocked: {', '.join(robots_result.warning_blocked)} "
                    f"(direct-crawl limited, but search-indexed visibility: {robots_result.search_indexed_score:.0f}%)"
                )

        # 2. TTFB (30%)
        ttfb_score, ttfb_comp = self._score_ttfb(ttfb_result)
        components.append(ttfb_comp)
        total_weighted += ttfb_comp.weighted_score
        if ttfb_result:
            ttfb_ms = (
                ttfb_result.ttfb_ms
                if isinstance(ttfb_result, TTFBResult)
                else ttfb_result.avg_ttfb_ms
            )
            if ttfb_ms > 1500:
                critical_issues.append(f"TTFB critically slow: {ttfb_ms}ms (target: <500ms)")
            elif ttfb_ms > 500:
                all_issues.append(f"TTFB slow: {ttfb_ms}ms (target: <500ms)")

        # 3. llms.txt (15%)
        llms_score, llms_comp = self._score_llms_txt(llms_txt_result)
        components.append(llms_comp)
        total_weighted += llms_comp.weighted_score
        if llms_txt_result and not llms_txt_result.exists:
            all_issues.append("llms.txt not found (recommend creating)")
        elif llms_txt_result and llms_txt_result.issues:
            all_issues.extend(llms_txt_result.issues)

        # 4. JS Accessibility (10%)
        js_score, js_comp = self._score_js(js_result)
        components.append(js_comp)
        total_weighted += js_comp.weighted_score
        if js_result:
            # Check for empty shell (most critical - AI sees nothing)
            if js_result.is_empty_shell:
                critical_issues.append(
                    "CRITICAL: Page appears empty to AI crawlers. "
                    f"Only {js_result.main_content_length} chars of content detected. "
                    "Implement server-side rendering (SSR) or static site generation (SSG) immediately."
                )
            elif js_result.likely_js_dependent:
                if js_result.confidence == "high":
                    framework_info = (
                        f" ({js_result.framework_detected})" if js_result.framework_detected else ""
                    )
                    critical_issues.append(
                        f"Site requires JavaScript to render content{framework_info}. "
                        "AI crawlers like GPTBot and ClaudeBot cannot execute JS. "
                        "Enable SSR/prerendering for AI visibility."
                    )
                else:
                    all_issues.append(
                        f"Site may require JavaScript ({js_result.confidence} confidence). "
                        "Verify content is visible without JS."
                    )

        # 5. HTTPS (10%)
        https_score, https_comp = self._score_https(is_https)
        components.append(https_comp)
        total_weighted += https_comp.weighted_score
        if not is_https:
            all_issues.append("Site not using HTTPS")

        # Calculate total
        total_score = total_weighted

        # Determine level (progress-based, not severity-based)
        # Indicates how far along technical readiness is
        if total_score >= 80:
            level = "full"
        elif total_score >= 50:
            level = "partial"
        else:
            level = "limited"

        result = TechnicalReadinessScore(
            total_score=total_score,
            level=level,
            components=components,
            critical_issues=critical_issues,
            all_issues=all_issues,
            robots_result=robots_result,
            ttfb_result=ttfb_result,
            llms_txt_result=llms_txt_result,
            js_result=js_result,
            is_https=is_https,
        )

        logger.info(
            "technical_score_calculated",
            total_score=total_score,
            level=level,
            critical_issues_count=len(critical_issues),
        )

        return result

    def _score_robots(self, result: RobotsTxtAIResult | None) -> tuple[float, TechnicalComponent]:
        """
        Score robots.txt access using the two-pipeline model.

        Two AI visibility pipelines:
        1. Search-indexed (60% weight): Googlebot/Bingbot → AI finds via search
        2. Direct-crawl (40% weight): GPTBot/ClaudeBot → AI crawls directly

        Blocking search engines = CRITICAL (AI can't find you at all)
        Blocking AI crawlers = WARNING (limits direct access, not search-indexed)
        """
        weight = TECHNICAL_WEIGHTS["robots_txt"] / 100

        if result is None:
            return 100.0, TechnicalComponent(
                name="Crawler Access",
                raw_score=100.0,
                weight=weight,
                weighted_score=100.0 * weight,
                level="full",
                explanation="Not checked (assumed allowed)",
            )

        score = result.score

        # Determine level based on visibility progress (not severity)
        if result.critical_blocked:
            # Search engines blocked = limited visibility
            level = "limited"
            explanation = f"Search engines blocked: {', '.join(result.critical_blocked)}. AI systems cannot find your content via search indexes."
        elif result.warning_blocked:
            # Only AI crawlers blocked = partial visibility
            level = "partial"
            explanation = (
                f"AI crawlers blocked: {', '.join(result.warning_blocked)}. "
                f"Your content is still visible via search indexes (search: {result.search_indexed_score:.0f}/100)."
            )
        elif score >= 80:
            level = "full"
            explanation = "All crawlers allowed. Full visibility via both search indexes and direct AI access."
        else:
            level = "partial"
            explanation = "Partial crawler access"

        return score, TechnicalComponent(
            name="Crawler Access",
            raw_score=score,
            weight=weight,
            weighted_score=score * weight,
            level=level,
            explanation=explanation,
            details={
                "crawlers": {k: v.allowed for k, v in result.crawlers.items()},
                "search_indexed_score": result.search_indexed_score,
                "direct_crawl_score": result.direct_crawl_score,
                "critical_blocked": result.critical_blocked,
                "warning_blocked": result.warning_blocked,
                "pipeline_summary": result.pipeline_summary,
            },
        )

    def _score_ttfb(
        self, result: TTFBResult | SitePerformanceResult | None
    ) -> tuple[float, TechnicalComponent]:
        """Score TTFB performance."""
        weight = TECHNICAL_WEIGHTS["ttfb"] / 100

        if result is None:
            return 50.0, TechnicalComponent(
                name="TTFB Performance",
                raw_score=50.0,
                weight=weight,
                weighted_score=50.0 * weight,
                level="partial",
                explanation="Not measured",
            )

        score = result.score
        ttfb_ms = result.ttfb_ms if isinstance(result, TTFBResult) else result.avg_ttfb_ms

        if score >= 80:
            level = "full"
            explanation = f"TTFB excellent: {ttfb_ms}ms"
        elif score >= 50:
            level = "partial"
            explanation = f"TTFB acceptable: {ttfb_ms}ms (target: <500ms)"
        else:
            level = "limited"
            explanation = f"TTFB too slow: {ttfb_ms}ms (AI crawlers may timeout)"

        return score, TechnicalComponent(
            name="TTFB Performance",
            raw_score=score,
            weight=weight,
            weighted_score=score * weight,
            level=level,
            explanation=explanation,
            details={"ttfb_ms": ttfb_ms},
        )

    def _score_llms_txt(self, result: LlmsTxtResult | None) -> tuple[float, TechnicalComponent]:
        """Score llms.txt presence and quality."""
        weight = TECHNICAL_WEIGHTS["llms_txt"] / 100

        if result is None:
            return 0.0, TechnicalComponent(
                name="llms.txt",
                raw_score=0.0,
                weight=weight,
                weighted_score=0.0,
                level="limited",
                explanation="Not checked",
            )

        if not result.exists:
            return 0.0, TechnicalComponent(
                name="llms.txt",
                raw_score=0.0,
                weight=weight,
                weighted_score=0.0,
                level="limited",
                explanation="Not found (recommend creating for AI visibility)",
            )

        score = result.quality_score
        if score >= 80:
            level = "full"
            explanation = f"Well-structured with {result.link_count} links"
        elif score >= 50:
            level = "partial"
            explanation = "Exists but could be improved"
        else:
            level = "partial"
            explanation = "Exists but poorly structured"

        return score, TechnicalComponent(
            name="llms.txt",
            raw_score=score,
            weight=weight,
            weighted_score=score * weight,
            level=level,
            explanation=explanation,
            details={
                "link_count": result.link_count,
                "has_title": result.has_title,
                "has_description": result.has_description,
            },
        )

    def _score_js(self, result: JSDetectionResult | None) -> tuple[float, TechnicalComponent]:
        """Score JavaScript accessibility."""
        weight = TECHNICAL_WEIGHTS["js_accessible"] / 100

        if result is None:
            return 100.0, TechnicalComponent(
                name="JS Accessibility",
                raw_score=100.0,
                weight=weight,
                weighted_score=100.0 * weight,
                level="full",
                explanation="Not checked (assumed accessible)",
            )

        score = result.score

        # Check for empty shell first (most severe)
        if result.is_empty_shell:
            level = "limited"
            explanation = (
                f"Page is a JS shell ({result.main_content_length} chars visible). "
                "AI crawlers see empty content. SSR required."
            )
        elif score >= 80:
            level = "full"
            explanation = "Content accessible without JavaScript"
        elif score >= 50:
            level = "partial"
            explanation = f"May require JS ({result.confidence} confidence)"
        else:
            level = "limited"
            framework = result.framework_detected or "SPA"
            explanation = f"Likely requires JS to render ({framework})"

        return score, TechnicalComponent(
            name="JS Accessibility",
            raw_score=score,
            weight=weight,
            weighted_score=score * weight,
            level=level,
            explanation=explanation,
            details={
                "framework": result.framework_detected,
                "main_content_length": result.main_content_length,
                "is_empty_shell": result.is_empty_shell,
                "severity": result.severity,
            },
        )

    def _score_https(self, is_https: bool) -> tuple[float, TechnicalComponent]:
        """Score HTTPS usage."""
        weight = TECHNICAL_WEIGHTS["https"] / 100

        if is_https:
            return 100.0, TechnicalComponent(
                name="HTTPS",
                raw_score=100.0,
                weight=weight,
                weighted_score=100.0 * weight,
                level="full",
                explanation="Site uses HTTPS",
            )
        else:
            return 0.0, TechnicalComponent(
                name="HTTPS",
                raw_score=0.0,
                weight=weight,
                weighted_score=0.0,
                level="limited",
                explanation="Site not using HTTPS (trust signal missing)",
            )


def calculate_technical_score(
    robots_result: RobotsTxtAIResult | None = None,
    ttfb_result: TTFBResult | SitePerformanceResult | None = None,
    llms_txt_result: LlmsTxtResult | None = None,
    js_result: JSDetectionResult | None = None,
    is_https: bool = True,
) -> TechnicalReadinessScore:
    """
    Convenience function to calculate Technical Readiness score.

    Args:
        robots_result: AI crawler access check result
        ttfb_result: TTFB measurement result
        llms_txt_result: llms.txt detection result
        js_result: JavaScript dependency detection result
        is_https: Whether site uses HTTPS

    Returns:
        TechnicalReadinessScore with full breakdown
    """
    calculator = TechnicalScoreCalculator()
    return calculator.calculate(
        robots_result=robots_result,
        ttfb_result=ttfb_result,
        llms_txt_result=llms_txt_result,
        js_result=js_result,
        is_https=is_https,
    )
