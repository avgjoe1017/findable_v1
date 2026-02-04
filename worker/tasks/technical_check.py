"""Technical readiness check runner.

Runs all Phase 1 technical checks:
- robots.txt AI crawler access
- TTFB performance
- llms.txt presence
- JavaScript dependency detection

Returns a complete TechnicalReadinessScore.
"""

from urllib.parse import urlparse

import structlog

from worker.crawler.llms_txt import LlmsTxtResult, check_llms_txt
from worker.crawler.performance import TTFBResult, measure_ttfb
from worker.crawler.robots_ai import RobotsTxtAIResult, check_ai_crawler_access
from worker.extraction.js_detection import JSDetectionResult, detect_js_dependency
from worker.scoring.technical import TechnicalReadinessScore, calculate_technical_score

logger = structlog.get_logger(__name__)


async def run_technical_checks(
    url: str,
    html: str | None = None,
    timeout: float = 10.0,
) -> TechnicalReadinessScore:
    """
    Run all technical readiness checks for a URL.

    This is the main entry point for Phase 1 technical analysis.

    Args:
        url: The URL to check (will use domain for robots/llms.txt)
        html: Optional HTML content for JS detection
        timeout: Request timeout for network checks

    Returns:
        TechnicalReadinessScore with complete breakdown

    Example:
        score = await run_technical_checks("https://example.com")
        print(score.show_the_math())
    """
    parsed = urlparse(url)
    is_https = parsed.scheme == "https"

    logger.info("technical_checks_starting", url=url)

    # Run checks (could parallelize with asyncio.gather)
    robots_result: RobotsTxtAIResult | None = None
    ttfb_result: TTFBResult | None = None
    llms_txt_result: LlmsTxtResult | None = None
    js_result: JSDetectionResult | None = None

    try:
        robots_result = await check_ai_crawler_access(url, timeout=timeout)
    except Exception as e:
        logger.warning("robots_check_failed", url=url, error=str(e))

    try:
        ttfb_result = await measure_ttfb(url, timeout=timeout)
    except Exception as e:
        logger.warning("ttfb_check_failed", url=url, error=str(e))

    try:
        llms_txt_result = await check_llms_txt(url, timeout=timeout)
    except Exception as e:
        logger.warning("llms_txt_check_failed", url=url, error=str(e))

    if html:
        try:
            js_result = detect_js_dependency(html, url)
        except Exception as e:
            logger.warning("js_detection_failed", url=url, error=str(e))

    # Calculate combined score
    score = calculate_technical_score(
        robots_result=robots_result,
        ttfb_result=ttfb_result,
        llms_txt_result=llms_txt_result,
        js_result=js_result,
        is_https=is_https,
    )

    logger.info(
        "technical_checks_complete",
        url=url,
        total_score=score.total_score,
        level=score.level,
        critical_issues=len(score.critical_issues),
    )

    return score


async def run_technical_checks_parallel(
    url: str,
    html: str | None = None,
    timeout: float = 10.0,
) -> TechnicalReadinessScore:
    """
    Run all technical checks in parallel for faster execution.

    Same as run_technical_checks but uses asyncio.gather for parallel execution.

    Args:
        url: The URL to check
        html: Optional HTML content for JS detection
        timeout: Request timeout

    Returns:
        TechnicalReadinessScore
    """
    import asyncio

    parsed = urlparse(url)
    is_https = parsed.scheme == "https"

    logger.info("technical_checks_parallel_starting", url=url)

    # Run network checks in parallel
    results = await asyncio.gather(
        _safe_check(check_ai_crawler_access(url, timeout=timeout)),
        _safe_check(measure_ttfb(url, timeout=timeout)),
        _safe_check(check_llms_txt(url, timeout=timeout)),
        return_exceptions=True,
    )

    robots_result = results[0] if not isinstance(results[0], Exception) else None
    ttfb_result = results[1] if not isinstance(results[1], Exception) else None
    llms_txt_result = results[2] if not isinstance(results[2], Exception) else None

    # JS detection is sync, run separately
    js_result = None
    if html:
        try:
            js_result = detect_js_dependency(html, url)
        except Exception as e:
            logger.warning("js_detection_failed", url=url, error=str(e))

    # Calculate combined score
    score = calculate_technical_score(
        robots_result=robots_result,
        ttfb_result=ttfb_result,
        llms_txt_result=llms_txt_result,
        js_result=js_result,
        is_https=is_https,
    )

    logger.info(
        "technical_checks_parallel_complete",
        url=url,
        total_score=score.total_score,
        level=score.level,
    )

    return score


async def _safe_check(coro):
    """Wrap a coroutine to return None on exception instead of raising."""
    try:
        return await coro
    except Exception as e:
        logger.warning("check_failed", error=str(e))
        return None


def generate_technical_fixes(score: TechnicalReadinessScore) -> list[dict]:
    """
    Generate fix recommendations from technical score.

    Args:
        score: Technical readiness score result

    Returns:
        List of fix dictionaries with impact estimates
    """
    fixes = []

    # robots.txt fixes
    if score.robots_result and score.robots_result.critical_blocked:
        blocked = score.robots_result.critical_blocked
        fixes.append(
            {
                "category": "technical",
                "priority": "critical",
                "title": "Unblock AI crawlers in robots.txt",
                "description": (
                    "Add the following to your robots.txt:\n\n"
                    + "\n".join([f"User-agent: {crawler}\nAllow: /" for crawler in blocked])
                ),
                "impact_points": 15,
                "effort": "5 minutes",
                "blocked_crawlers": blocked,
            }
        )

    # TTFB fixes
    if score.ttfb_result:
        ttfb_ms = (
            score.ttfb_result.ttfb_ms
            if hasattr(score.ttfb_result, "ttfb_ms")
            else score.ttfb_result.avg_ttfb_ms
        )
        if ttfb_ms > 1000:
            fixes.append(
                {
                    "category": "technical",
                    "priority": "high" if ttfb_ms > 1500 else "medium",
                    "title": f"Reduce TTFB from {ttfb_ms}ms to <500ms",
                    "description": (
                        "AI crawlers have strict timeout limits. Improve TTFB by:\n"
                        "- Enabling a CDN\n"
                        "- Adding server-side caching\n"
                        "- Optimizing database queries\n"
                        "- Using HTTP/2 or HTTP/3"
                    ),
                    "impact_points": 10,
                    "effort": "2-8 hours",
                    "current_ttfb_ms": ttfb_ms,
                }
            )

    # llms.txt fixes
    if score.llms_txt_result and not score.llms_txt_result.exists:
        fixes.append(
            {
                "category": "technical",
                "priority": "medium",
                "title": "Create llms.txt file",
                "description": (
                    "Add /llms.txt to help AI systems discover your key content.\n"
                    "Include: title, description, and links to important pages.\n"
                    "See https://llmstxt.org for specification."
                ),
                "impact_points": 5,
                "effort": "30 minutes",
            }
        )

    # JS rendering fixes
    if score.js_result and score.js_result.likely_js_dependent:
        fixes.append(
            {
                "category": "technical",
                "priority": "high" if score.js_result.confidence == "high" else "medium",
                "title": "Enable server-side rendering",
                "description": (
                    f"Your site appears to use {score.js_result.framework_detected or 'client-side rendering'}. "
                    "AI crawlers cannot execute JavaScript.\n\n"
                    "Options:\n"
                    "- Enable SSR in your framework\n"
                    "- Use static site generation\n"
                    "- Implement dynamic rendering for bots"
                ),
                "impact_points": 15,
                "effort": "4-40 hours",
                "framework": score.js_result.framework_detected,
            }
        )

    # HTTPS fix
    if not score.is_https:
        fixes.append(
            {
                "category": "technical",
                "priority": "medium",
                "title": "Enable HTTPS",
                "description": "HTTPS is a trust signal for both users and AI systems.",
                "impact_points": 3,
                "effort": "1-2 hours",
            }
        )

    return fixes
