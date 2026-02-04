"""Authority signals check task runner.

Runs E-E-A-T authority analysis and generates fixes for
missing or weak authority signals.
"""

import structlog

from worker.extraction.authority import analyze_authority
from worker.scoring.authority import AuthoritySignalsScore, calculate_authority_score

logger = structlog.get_logger(__name__)


async def run_authority_checks(
    html: str,
    url: str,
    main_content: str = "",
) -> AuthoritySignalsScore:
    """
    Run authority signal checks for a page.

    Args:
        html: Full HTML content
        url: Page URL
        main_content: Extracted main content text

    Returns:
        AuthoritySignalsScore with all component scores
    """
    logger.info("authority_check_starting", url=url)

    # Analyze authority signals
    authority_analysis = analyze_authority(html, url, main_content)

    # Calculate score
    authority_score = calculate_authority_score(authority_analysis)

    logger.info(
        "authority_check_completed",
        url=url,
        total_score=authority_score.total_score,
        level=authority_score.level,
        has_author=authority_analysis.has_author,
        authoritative_citations=authority_analysis.authoritative_citations,
    )

    return authority_score


def run_authority_checks_sync(
    html: str,
    url: str,
    main_content: str = "",
) -> AuthoritySignalsScore:
    """
    Synchronous version of authority checks.

    Args:
        html: Full HTML content
        url: Page URL
        main_content: Extracted main content text

    Returns:
        AuthoritySignalsScore with all component scores
    """
    authority_analysis = analyze_authority(html, url, main_content)
    return calculate_authority_score(authority_analysis)


def aggregate_authority_scores(
    page_scores: list[AuthoritySignalsScore],
) -> AuthoritySignalsScore:
    """
    Aggregate authority scores from multiple pages into site-level score.

    Args:
        page_scores: List of per-page authority scores

    Returns:
        Aggregated AuthoritySignalsScore for the site
    """
    if not page_scores:
        return AuthoritySignalsScore(
            total_score=0.0,
            level="critical",
            critical_issues=["No pages analyzed"],
        )

    # Weight pages: homepage (first) counts more
    weights = [2.0] + [1.0] * (len(page_scores) - 1)
    total_weight = sum(weights)

    # Calculate weighted average
    weighted_sum = sum(s.total_score * w for s, w in zip(page_scores, weights, strict=False))
    avg_score = weighted_sum / total_weight

    # Aggregate issues and recommendations
    all_critical = []
    all_issues = []
    all_recommendations = []
    seen_issues = set()
    seen_recs = set()

    for score in page_scores:
        for issue in score.critical_issues:
            if issue not in seen_issues:
                all_critical.append(issue)
                seen_issues.add(issue)
        for issue in score.all_issues:
            if issue not in seen_issues:
                all_issues.append(issue)
                seen_issues.add(issue)
        for rec in score.recommendations:
            if rec not in seen_recs:
                all_recommendations.append(rec)
                seen_recs.add(rec)

    # Aggregate components (use first page as template, average scores)
    aggregated_components = []
    if page_scores and page_scores[0].components:
        for i, comp in enumerate(page_scores[0].components):
            # Average the raw scores across pages
            raw_scores = [s.components[i].raw_score for s in page_scores if i < len(s.components)]
            avg_raw = sum(raw_scores) / len(raw_scores) if raw_scores else 0

            from worker.scoring.authority import AuthorityComponent

            aggregated_components.append(
                AuthorityComponent(
                    name=comp.name,
                    raw_score=avg_raw,
                    weight=comp.weight,
                    weighted_score=avg_raw * comp.weight,
                    level="good" if avg_raw >= 70 else "warning" if avg_raw >= 40 else "critical",
                    explanation=comp.explanation,
                    details=comp.details,
                )
            )

    # Determine level
    if avg_score >= 70:
        level = "good"
    elif avg_score >= 40:
        level = "warning"
    else:
        level = "critical"

    return AuthoritySignalsScore(
        total_score=avg_score,
        level=level,
        components=aggregated_components,
        critical_issues=all_critical[:5],
        all_issues=all_issues[:10],
        recommendations=all_recommendations[:5],
        authority_analysis=page_scores[0].authority_analysis if page_scores else None,
    )


def generate_authority_fixes(score: AuthoritySignalsScore) -> list[dict]:
    """
    Generate fix recommendations from authority score.

    Args:
        score: Authority signals score with analysis

    Returns:
        List of fix dictionaries
    """
    fixes = []
    analysis = score.authority_analysis

    if not analysis:
        return fixes

    # Fix 1: Add author attribution (highest priority for authority)
    if not analysis.has_author:
        fixes.append(
            {
                "id": "authority_add_author",
                "category": "authority",
                "priority": 1,
                "title": "Add author byline to content",
                "description": (
                    "Add a visible author byline to your content. "
                    "AI systems trust content more when they can attribute it to a real person. "
                    "Include the author's name prominently near the title or at the end."
                ),
                "estimated_impact": 7.0,
                "effort": "low",
            }
        )
    elif analysis.primary_author and not analysis.primary_author.is_linked:
        fixes.append(
            {
                "id": "authority_link_author",
                "category": "authority",
                "priority": 2,
                "title": "Link author name to bio page",
                "description": (
                    "Link the author's name to their bio page or profile. "
                    "This helps AI verify the author's identity and expertise."
                ),
                "estimated_impact": 3.0,
                "effort": "low",
            }
        )

    # Fix 2: Add author credentials
    if analysis.has_author and not analysis.has_credentials:
        fixes.append(
            {
                "id": "authority_add_credentials",
                "category": "authority",
                "priority": 1,
                "title": "Add author credentials and bio",
                "description": (
                    "Add author credentials (titles, certifications, experience) "
                    "and a brief bio. Include job title, relevant expertise, "
                    "and years of experience in the field."
                ),
                "estimated_impact": 6.0,
                "effort": "medium",
            }
        )

    # Fix 3: Add author photo
    if analysis.has_author and not analysis.has_author_photo:
        fixes.append(
            {
                "id": "authority_add_photo",
                "category": "authority",
                "priority": 3,
                "title": "Add author photo",
                "description": (
                    "Add a professional photo of the author. "
                    "This signals that the content is from a real person "
                    "and increases trust signals for AI systems."
                ),
                "estimated_impact": 2.0,
                "effort": "low",
            }
        )

    # Fix 4: Add authoritative citations
    if analysis.authoritative_citations < 2:
        fixes.append(
            {
                "id": "authority_add_citations",
                "category": "authority",
                "priority": 1,
                "title": "Add links to primary sources",
                "description": (
                    f"Your content has only {analysis.authoritative_citations} authoritative citation(s). "
                    "Add links to primary sources like academic research (.edu), "
                    "government sources (.gov), or reputable industry publications. "
                    "Aim for at least 3-5 authoritative citations per article."
                ),
                "estimated_impact": 6.0,
                "effort": "medium",
            }
        )

    # Fix 5: Add visible dates
    if not analysis.has_visible_date:
        fixes.append(
            {
                "id": "authority_add_dates",
                "category": "authority",
                "priority": 1,
                "title": "Add visible publication and update dates",
                "description": (
                    "Add visible publication and last-updated dates to your content. "
                    "Place them prominently near the title or author byline. "
                    "AI systems use freshness as a key trust signal."
                ),
                "estimated_impact": 5.0,
                "effort": "low",
            }
        )
    elif analysis.freshness_level in ["stale", "very_stale"]:
        fixes.append(
            {
                "id": "authority_update_content",
                "category": "authority",
                "priority": 1,
                "title": f"Update stale content ({analysis.days_since_published} days old)",
                "description": (
                    f"Your content was last updated {analysis.days_since_published} days ago. "
                    "Review the content for accuracy, update any outdated information, "
                    "and update the modification date. AI systems prefer fresh content."
                ),
                "estimated_impact": 5.0,
                "effort": "high",
            }
        )

    # Fix 6: Add original research/data
    if not analysis.has_original_data:
        fixes.append(
            {
                "id": "authority_add_original_data",
                "category": "authority",
                "priority": 2,
                "title": "Add original research or unique insights",
                "description": (
                    "Include original research, proprietary data, or unique insights. "
                    "Use phrases like 'our research shows', 'our data indicates', "
                    "or 'we found that' to signal first-party information. "
                    "This differentiates your content from aggregated sources."
                ),
                "estimated_impact": 4.0,
                "effort": "high",
            }
        )

    # Sort by priority
    fixes.sort(key=lambda x: x["priority"])

    return fixes
