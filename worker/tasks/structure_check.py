"""Structure quality check task runner.

Runs all structure quality checks (heading hierarchy, answer-first,
FAQ sections, internal links, extractable formats) and generates
fixes for identified issues.
"""

import structlog

from worker.extraction.structure import analyze_structure
from worker.scoring.structure import StructureQualityScore, calculate_structure_score

logger = structlog.get_logger(__name__)


async def run_structure_checks(
    html: str,
    url: str,
    main_content: str = "",
    word_count: int = 0,
) -> StructureQualityScore:
    """
    Run all structure quality checks for a page.

    Args:
        html: Full HTML content
        url: Page URL
        main_content: Extracted main content text
        word_count: Word count of content

    Returns:
        StructureQualityScore with all component scores
    """
    logger.info("structure_check_starting", url=url)

    # Analyze structure
    structure_analysis = analyze_structure(
        html=html,
        url=url,
        main_content=main_content,
        word_count=word_count,
    )

    # Calculate score
    structure_score = calculate_structure_score(structure_analysis)

    logger.info(
        "structure_check_completed",
        url=url,
        total_score=structure_score.total_score,
        level=structure_score.level,
        critical_issues=len(structure_score.critical_issues),
    )

    return structure_score


def run_structure_checks_sync(
    html: str,
    url: str,
    main_content: str = "",
    word_count: int = 0,
) -> StructureQualityScore:
    """
    Synchronous version of structure checks.

    Args:
        html: Full HTML content
        url: Page URL
        main_content: Extracted main content text
        word_count: Word count of content

    Returns:
        StructureQualityScore with all component scores
    """
    structure_analysis = analyze_structure(
        html=html,
        url=url,
        main_content=main_content,
        word_count=word_count,
    )
    return calculate_structure_score(structure_analysis)


def aggregate_structure_scores(
    page_scores: list[StructureQualityScore],
) -> StructureQualityScore:
    """
    Aggregate structure scores from multiple pages into site-level score.

    Args:
        page_scores: List of per-page structure scores

    Returns:
        Aggregated StructureQualityScore for the site
    """
    if not page_scores:
        return StructureQualityScore(
            total_score=0.0,
            level="limited",
            critical_issues=["No pages analyzed"],
        )

    # Weight pages: homepage (first) counts more
    weights = [2.0] + [1.0] * (len(page_scores) - 1)
    total_weight = sum(weights)

    # Calculate weighted average
    weighted_sum = sum(s.total_score * w for s, w in zip(page_scores, weights, strict=False))
    avg_score = weighted_sum / total_weight

    # Aggregate issues
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

            from worker.scoring.structure import StructureComponent

            aggregated_components.append(
                StructureComponent(
                    name=comp.name,
                    raw_score=avg_raw,
                    weight=comp.weight,
                    weighted_score=avg_raw * comp.weight,
                    level="full" if avg_raw >= 80 else "partial" if avg_raw >= 50 else "limited",
                    explanation=comp.explanation,
                    details=comp.details,
                )
            )

    # Determine level
    if avg_score >= 80:
        level = "full"
    elif avg_score >= 50:
        level = "partial"
    else:
        level = "limited"

    # Compute H1 sub-metrics across all pages
    pages_missing_h1 = 0
    pages_multiple_h1 = 0
    total_heading_issues = 0
    total_heading_score = 0.0

    for ps in page_scores:
        for comp in ps.components:
            if comp.name == "Heading Hierarchy":
                h1_count = comp.details.get("h1_count", 1)
                if h1_count == 0:
                    pages_missing_h1 += 1
                elif h1_count > 1:
                    pages_multiple_h1 += 1
                total_heading_issues += comp.details.get("issues", 0)
                total_heading_score += comp.raw_score
                break

    n = len(page_scores)

    return StructureQualityScore(
        total_score=avg_score,
        level=level,
        components=aggregated_components,
        critical_issues=all_critical[:5],
        all_issues=all_issues[:10],
        recommendations=all_recommendations[:5],
        structure_analysis=page_scores[0].structure_analysis if page_scores else None,
        pages_analyzed=n,
        pages_missing_h1=pages_missing_h1,
        pages_multiple_h1=pages_multiple_h1,
        avg_heading_issues=total_heading_issues / n if n else 0.0,
        avg_heading_score=total_heading_score / n if n else 0.0,
    )


def generate_structure_fixes(score: StructureQualityScore) -> list[dict]:
    """
    Generate fix recommendations from structure score.

    Args:
        score: Structure quality score with analysis

    Returns:
        List of fix dictionaries
    """
    fixes: list[dict[str, object]] = []
    analysis = score.structure_analysis

    if not analysis:
        return fixes

    # Fix 1: Missing or multiple H1
    if analysis.headings.h1_count == 0:
        fixes.append(
            {
                "id": "structure_missing_h1",
                "category": "structure",
                "priority": 1,
                "title": "Add H1 heading to page",
                "description": (
                    "Page is missing an H1 heading. Add a single H1 that clearly "
                    "describes the page content. H1 is critical for AI to understand "
                    "the page topic."
                ),
                "estimated_impact": 5.0,
                "effort": "low",
            }
        )
    elif analysis.headings.h1_count > 1:
        fixes.append(
            {
                "id": "structure_multiple_h1",
                "category": "structure",
                "priority": 2,
                "title": "Use only one H1 heading per page",
                "description": (
                    f"Page has {analysis.headings.h1_count} H1 headings. Consolidate "
                    "into a single H1 that represents the main topic."
                ),
                "estimated_impact": 3.0,
                "effort": "low",
            }
        )

    # Fix 2: Heading hierarchy issues
    if analysis.headings.skip_count > 0:
        fixes.append(
            {
                "id": "structure_heading_hierarchy",
                "category": "structure",
                "priority": 2,
                "title": "Fix heading hierarchy",
                "description": (
                    f"Headings skip levels {analysis.headings.skip_count} times "
                    "(e.g., H1 to H3 without H2). Fix the hierarchy for better "
                    "AI content parsing."
                ),
                "estimated_impact": 3.0,
                "effort": "medium",
            }
        )

    # Fix 3: Answer not first
    if not analysis.answer_first.answer_in_first_paragraph:
        fixes.append(
            {
                "id": "structure_answer_first",
                "category": "structure",
                "priority": 1,
                "title": "Move answer to first paragraph",
                "description": (
                    "Content doesn't lead with the answer. Move the main point, "
                    "definition, or key information to the first paragraph. "
                    "AI systems prioritize early content."
                ),
                "estimated_impact": 5.0,
                "effort": "medium",
            }
        )

    # Fix 4: No FAQ section
    if not analysis.faq.has_faq_section:
        fixes.append(
            {
                "id": "structure_add_faq",
                "category": "structure",
                "priority": 2,
                "title": "Add FAQ section",
                "description": (
                    "Add an FAQ section with 3-5 common questions about your topic. "
                    "FAQ content is highly favored by AI answer engines."
                ),
                "estimated_impact": 4.0,
                "effort": "medium",
            }
        )
    elif not analysis.faq.has_faq_schema:
        fixes.append(
            {
                "id": "structure_faq_schema",
                "category": "structure",
                "priority": 1,
                "title": "Add FAQPage schema to FAQ section",
                "description": (
                    "Your FAQ section lacks FAQPage schema markup. Adding schema "
                    "can increase AI citations by 35-40%."
                ),
                "estimated_impact": 8.0,
                "effort": "low",
            }
        )

    # Fix 5: Low internal links
    if analysis.links.density_level == "low":
        fixes.append(
            {
                "id": "structure_internal_links",
                "category": "structure",
                "priority": 3,
                "title": "Add more internal links",
                "description": (
                    f"Only {analysis.links.internal_links} internal links found. "
                    "Target 5-15 internal links per page to help AI understand "
                    "your site structure."
                ),
                "estimated_impact": 3.0,
                "effort": "medium",
            }
        )

    # Fix 6: Generic anchor text
    if analysis.links.generic_anchors > 5:
        fixes.append(
            {
                "id": "structure_anchor_text",
                "category": "structure",
                "priority": 3,
                "title": "Use descriptive anchor text",
                "description": (
                    f"{analysis.links.generic_anchors} links use generic text like "
                    "'click here'. Replace with descriptive anchor text that tells "
                    "AI what the linked page is about."
                ),
                "estimated_impact": 2.0,
                "effort": "medium",
            }
        )

    # Fix 7: Tables without headers
    if analysis.formats.table_count > 0 and analysis.formats.tables_with_headers == 0:
        fixes.append(
            {
                "id": "structure_table_headers",
                "category": "structure",
                "priority": 3,
                "title": "Add header rows to tables",
                "description": (
                    f"{analysis.formats.table_count} tables lack header rows. "
                    "Add <th> elements to help AI extract structured data."
                ),
                "estimated_impact": 2.0,
                "effort": "low",
            }
        )

    # Sort by priority
    fixes.sort(key=lambda x: x["priority"])  # type: ignore[arg-type, return-value]

    return fixes
