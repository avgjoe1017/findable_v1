"""Schema richness check task runner.

Runs schema.org analysis and generates fixes for
missing or incomplete structured data.
"""

import structlog

from worker.extraction.schema import analyze_schema
from worker.scoring.schema import SchemaRichnessScore, calculate_schema_score

logger = structlog.get_logger(__name__)


async def run_schema_checks(
    html: str,
    url: str,
) -> SchemaRichnessScore:
    """
    Run schema richness checks for a page.

    Args:
        html: Full HTML content
        url: Page URL

    Returns:
        SchemaRichnessScore with all component scores
    """
    logger.info("schema_check_starting", url=url)

    # Analyze schema
    schema_analysis = analyze_schema(html, url)

    # Calculate score
    schema_score = calculate_schema_score(schema_analysis)

    logger.info(
        "schema_check_completed",
        url=url,
        total_score=schema_score.total_score,
        level=schema_score.level,
        total_schemas=schema_analysis.total_schemas,
    )

    return schema_score


def run_schema_checks_sync(
    html: str,
    url: str,
) -> SchemaRichnessScore:
    """
    Synchronous version of schema checks.

    Args:
        html: Full HTML content
        url: Page URL

    Returns:
        SchemaRichnessScore with all component scores
    """
    schema_analysis = analyze_schema(html, url)
    return calculate_schema_score(schema_analysis)


def aggregate_schema_scores(
    page_scores: list[SchemaRichnessScore],
) -> SchemaRichnessScore:
    """
    Aggregate schema scores from multiple pages into site-level score.

    Args:
        page_scores: List of per-page schema scores

    Returns:
        Aggregated SchemaRichnessScore for the site
    """
    if not page_scores:
        return SchemaRichnessScore(
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

            from worker.scoring.schema import SchemaComponent

            aggregated_components.append(
                SchemaComponent(
                    name=comp.name,
                    raw_score=avg_raw,
                    weight=comp.weight,
                    weighted_score=avg_raw * comp.weight,
                    level="full" if avg_raw >= 70 else "partial" if avg_raw >= 40 else "limited",
                    explanation=comp.explanation,
                    details=comp.details,
                )
            )

    # Determine level
    if avg_score >= 70:
        level = "full"
    elif avg_score >= 40:
        level = "partial"
    else:
        level = "limited"

    return SchemaRichnessScore(
        total_score=avg_score,
        level=level,
        components=aggregated_components,
        critical_issues=all_critical[:5],
        all_issues=all_issues[:10],
        recommendations=all_recommendations[:5],
        schema_analysis=page_scores[0].schema_analysis if page_scores else None,
    )


def generate_schema_fixes(score: SchemaRichnessScore) -> list[dict]:
    """
    Generate fix recommendations from schema score.

    Args:
        score: Schema richness score with analysis

    Returns:
        List of fix dictionaries
    """
    fixes = []
    analysis = score.schema_analysis

    if not analysis:
        return fixes

    # Fix 1: Add FAQPage schema (highest impact)
    if not analysis.has_faq_page:
        fixes.append(
            {
                "id": "schema_add_faq_page",
                "category": "schema",
                "priority": 1,
                "title": "Add FAQPage schema markup",
                "description": (
                    "Add FAQPage structured data to your FAQ content. "
                    "Research shows FAQPage schema can increase AI citations by 35-40%. "
                    "Include 3-5 question-answer pairs for best results."
                ),
                "estimated_impact": 8.0,
                "effort": "medium",
                "scaffold": _generate_faq_schema_template(),
            }
        )
    elif analysis.faq_count < 3:
        fixes.append(
            {
                "id": "schema_expand_faq",
                "category": "schema",
                "priority": 2,
                "title": "Expand FAQPage with more Q&A pairs",
                "description": (
                    f"Your FAQPage only has {analysis.faq_count} Q&A pair(s). "
                    "Add at least 3-5 questions for better AI visibility."
                ),
                "estimated_impact": 3.0,
                "effort": "low",
            }
        )

    # Fix 2: Add Article schema with author
    if not analysis.has_article:
        fixes.append(
            {
                "id": "schema_add_article",
                "category": "schema",
                "priority": 2,
                "title": "Add Article schema with author",
                "description": (
                    "Add Article (or BlogPosting/NewsArticle) structured data "
                    "with author information. This helps AI attribute content to "
                    "your organization and authors."
                ),
                "estimated_impact": 5.0,
                "effort": "medium",
                "scaffold": _generate_article_schema_template(),
            }
        )
    elif not analysis.has_author:
        fixes.append(
            {
                "id": "schema_add_author",
                "category": "schema",
                "priority": 2,
                "title": "Add author to Article schema",
                "description": (
                    "Your Article schema is missing author information. "
                    "Add author name, credentials, and optionally a link to their bio."
                ),
                "estimated_impact": 3.0,
                "effort": "low",
            }
        )

    # Fix 3: Add dateModified
    if not analysis.has_date_modified:
        fixes.append(
            {
                "id": "schema_add_date_modified",
                "category": "schema",
                "priority": 2,
                "title": "Add dateModified to schema",
                "description": (
                    "Add dateModified field to your schema markup. "
                    "Content freshness is a key signal for AI answer engines."
                ),
                "estimated_impact": 4.0,
                "effort": "low",
            }
        )
    elif analysis.freshness_level in ["stale", "very_stale"]:
        fixes.append(
            {
                "id": "schema_update_content",
                "category": "schema",
                "priority": 1,
                "title": "Update stale content",
                "description": (
                    f"Content was last modified {analysis.days_since_modified} days ago. "
                    "Review and update content, then update the dateModified field."
                ),
                "estimated_impact": 5.0,
                "effort": "high",
            }
        )

    # Fix 4: Add Organization schema
    if not analysis.has_organization:
        fixes.append(
            {
                "id": "schema_add_organization",
                "category": "schema",
                "priority": 3,
                "title": "Add Organization schema",
                "description": (
                    "Add Organization structured data to help AI recognize your "
                    "business entity. Include name, URL, logo, and contact information."
                ),
                "estimated_impact": 3.0,
                "effort": "low",
                "scaffold": _generate_organization_schema_template(),
            }
        )

    # Fix 5: Fix validation errors
    if analysis.error_count > 0:
        error_summary = ", ".join(e.message for e in analysis.validation_errors[:3])
        fixes.append(
            {
                "id": "schema_fix_validation",
                "category": "schema",
                "priority": 1,
                "title": f"Fix {analysis.error_count} schema validation errors",
                "description": (
                    f"Schema validation errors found: {error_summary}. "
                    "Fix these errors to ensure AI can properly parse your structured data."
                ),
                "estimated_impact": 2.0,
                "effort": "low",
            }
        )

    # Sort by priority
    fixes.sort(key=lambda x: x["priority"])

    return fixes


def _generate_faq_schema_template() -> str:
    """Generate FAQPage schema template."""
    return """<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "Your question here?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Your answer here."
      }
    },
    {
      "@type": "Question",
      "name": "Another question?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Another answer."
      }
    }
  ]
}
</script>"""


def _generate_article_schema_template() -> str:
    """Generate Article schema template."""
    return """<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "Your Article Title",
  "author": {
    "@type": "Person",
    "name": "Author Name",
    "jobTitle": "Job Title",
    "url": "https://example.com/author"
  },
  "datePublished": "2024-01-15",
  "dateModified": "2024-06-01",
  "publisher": {
    "@type": "Organization",
    "name": "Your Company",
    "logo": {
      "@type": "ImageObject",
      "url": "https://example.com/logo.png"
    }
  },
  "description": "Article description",
  "image": "https://example.com/article-image.jpg"
}
</script>"""


def _generate_organization_schema_template() -> str:
    """Generate Organization schema template."""
    return """<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Your Company Name",
  "url": "https://example.com",
  "logo": "https://example.com/logo.png",
  "description": "Brief company description",
  "contactPoint": {
    "@type": "ContactPoint",
    "contactType": "customer service",
    "email": "support@example.com"
  },
  "sameAs": [
    "https://twitter.com/yourcompany",
    "https://linkedin.com/company/yourcompany"
  ]
}
</script>"""
