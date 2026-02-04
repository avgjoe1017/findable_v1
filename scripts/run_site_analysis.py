#!/usr/bin/env python
"""Run a full Findable Score v2 analysis on a real site.

This script demonstrates the complete v2 analysis pipeline:
1. Technical readiness check (robots.txt, TTFB, llms.txt, JS detection)
2. Crawl site pages
3. Extract content
4. Structure analysis (headings, FAQ, answer-first, links)
5. Schema analysis (JSON-LD, validation)
6. Authority analysis (author, credentials, citations, dates)
7. Calculate v2 score with all 6 pillars

Usage:
    python scripts/run_site_analysis.py https://example.com
"""

import asyncio
import json
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, ".")


async def analyze_site(url: str, max_pages: int = 10) -> dict:
    """Run full v2 analysis on a site."""
    from worker.crawler.crawler import crawl_site
    from worker.extraction.extractor import ContentExtractor
    from worker.scoring.calculator_v2 import FindableScoreCalculatorV2
    from worker.tasks.authority_check import aggregate_authority_scores, run_authority_checks_sync
    from worker.tasks.schema_check import aggregate_schema_scores, run_schema_checks_sync
    from worker.tasks.structure_check import aggregate_structure_scores, run_structure_checks_sync
    from worker.tasks.technical_check import run_technical_checks_parallel

    print(f"\n{'='*60}")
    print("Findable Score v2 Analysis")
    print(f"URL: {url}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    results = {
        "url": url,
        "started_at": datetime.now().isoformat(),
        "pillars": {},
    }

    # =========================================================
    # Step 1: Technical Readiness Check
    # =========================================================
    print("[1/6] Technical Readiness Check...")
    try:
        technical_score = await run_technical_checks_parallel(url=url, html=None, timeout=15.0)
        print(f"      Score: {technical_score.total_score:.1f}/100 ({technical_score.level})")
        robots_ok = technical_score.robots_result and technical_score.robots_result.all_allowed
        print(f"      - Robots.txt: {'AI-friendly' if robots_ok else 'Blocking some AI crawlers'}")
        print(
            f"      - TTFB: {technical_score.ttfb_result.ttfb_ms if technical_score.ttfb_result else 'N/A'}ms"
        )
        print(
            f"      - llms.txt: {'Found' if technical_score.llms_txt_result and technical_score.llms_txt_result.exists else 'Not found'}"
        )
        print(f"      - HTTPS: {'Yes' if technical_score.is_https else 'No'}")

        results["pillars"]["technical"] = {
            "score": technical_score.total_score,
            "level": technical_score.level,
            "critical_issues": technical_score.critical_issues,
        }
    except Exception as e:
        print(f"      Error: {e}")
        results["pillars"]["technical"] = {"error": str(e)}

    # =========================================================
    # Step 2: Crawl Site
    # =========================================================
    print(f"\n[2/6] Crawling site (max {max_pages} pages)...")
    try:
        crawl_result = await crawl_site(url=url, max_pages=max_pages, max_depth=3)
        print(f"      Pages crawled: {len(crawl_result.pages)}")
        print(f"      URLs discovered: {crawl_result.urls_discovered}")
        print(f"      Duration: {crawl_result.duration_seconds:.1f}s")

        results["crawl"] = {
            "pages_crawled": len(crawl_result.pages),
            "urls_discovered": crawl_result.urls_discovered,
            "duration_seconds": crawl_result.duration_seconds,
        }
    except Exception as e:
        print(f"      Error: {e}")
        return results

    # =========================================================
    # Step 3: Extract Content
    # =========================================================
    print("\n[3/6] Extracting content...")
    extractor = ContentExtractor()
    extraction_result = extractor.extract_crawl(crawl_result)
    print(f"      Pages extracted: {extraction_result.total_pages}")
    print(f"      Total words: {extraction_result.total_words:,}")

    results["extraction"] = {
        "pages": extraction_result.total_pages,
        "words": extraction_result.total_words,
    }

    # Update technical score with JS detection
    if crawl_result.pages and crawl_result.pages[0].html:
        from worker.extraction.js_detection import detect_js_dependency
        from worker.scoring.technical import calculate_technical_score

        js_result = detect_js_dependency(crawl_result.pages[0].html, url)
        if "technical" in results["pillars"] and "error" not in results["pillars"]["technical"]:
            technical_score = calculate_technical_score(
                robots_result=technical_score.robots_result,
                ttfb_result=technical_score.ttfb_result,
                llms_txt_result=technical_score.llms_txt_result,
                js_result=js_result,
                is_https=technical_score.is_https,
            )
            print(f"      JS-dependent: {'Yes' if js_result.likely_js_dependent else 'No'}")
            results["pillars"]["technical"]["js_dependent"] = js_result.likely_js_dependent
            results["pillars"]["technical"]["score"] = technical_score.total_score

    # =========================================================
    # Step 4: Structure Analysis
    # =========================================================
    print("\n[4/6] Structure analysis...")
    structure_scores = []
    for i, page in enumerate(crawl_result.pages):
        if page.html and i < len(extraction_result.pages):
            extracted = extraction_result.pages[i]
            score = run_structure_checks_sync(
                html=page.html,
                url=page.url,
                main_content=extracted.main_content,
                word_count=extracted.word_count,
            )
            structure_scores.append(score)

    if structure_scores:
        structure_score = aggregate_structure_scores(structure_scores)
        print(f"      Score: {structure_score.total_score:.1f}/100 ({structure_score.level})")

        # Get component scores from breakdown
        heading_score = next(
            (c.raw_score for c in structure_score.components if "heading" in c.name.lower()), 0
        )
        faq_score = next(
            (c.raw_score for c in structure_score.components if "faq" in c.name.lower()), 0
        )
        answer_score = next(
            (c.raw_score for c in structure_score.components if "answer" in c.name.lower()), 0
        )

        print(
            f"      - Heading hierarchy: {'Valid' if heading_score >= 70 else 'Issues found'} ({heading_score:.0f}%)"
        )
        print(f"      - FAQ quality: {faq_score:.0f}%")
        print(f"      - Answer-first: {answer_score:.0f}%")
        print(f"      - Critical issues: {len(structure_score.critical_issues)}")

        results["pillars"]["structure"] = {
            "score": structure_score.total_score,
            "level": structure_score.level,
            "heading_score": heading_score,
            "faq_score": faq_score,
        }

    # =========================================================
    # Step 5: Schema Analysis
    # =========================================================
    print("\n[5/6] Schema analysis...")
    schema_scores = []
    for page in crawl_result.pages:
        if page.html:
            score = run_schema_checks_sync(html=page.html, url=page.url)
            schema_scores.append(score)

    if schema_scores:
        schema_score = aggregate_schema_scores(schema_scores)
        print(f"      Score: {schema_score.total_score:.1f}/100 ({schema_score.level})")

        # Get schema details from analysis
        analysis = schema_score.schema_analysis
        if analysis:
            types_found = analysis.schema_types_found or []
            print(f"      - Schema types found: {', '.join(types_found) or 'None'}")
            print(f"      - FAQPage: {'Yes' if analysis.has_faq_page else 'No'}")
            print(f"      - Article: {'Yes' if analysis.has_article else 'No'}")
            print(f"      - Validation errors: {analysis.error_count}")
        else:
            types_found = []
            print("      - No schema markup found")

        print(f"      - Critical issues: {len(schema_score.critical_issues)}")

        results["pillars"]["schema"] = {
            "score": schema_score.total_score,
            "level": schema_score.level,
            "types_found": types_found,
            "errors": schema_score.critical_issues,
        }

    # =========================================================
    # Step 6: Authority Analysis
    # =========================================================
    print("\n[6/6] Authority analysis...")
    authority_scores = []
    for i, page in enumerate(crawl_result.pages):
        if page.html and i < len(extraction_result.pages):
            extracted = extraction_result.pages[i]
            score = run_authority_checks_sync(
                html=page.html,
                url=page.url,
                main_content=extracted.main_content,
            )
            authority_scores.append(score)

    if authority_scores:
        authority_score = aggregate_authority_scores(authority_scores)
        print(f"      Score: {authority_score.total_score:.1f}/100 ({authority_score.level})")

        # Get authority details from analysis
        analysis = authority_score.authority_analysis
        if analysis:
            print(f"      - Author attribution: {'Yes' if analysis.has_author else 'No'}")
            print(f"      - Credentials found: {'Yes' if analysis.has_credentials else 'No'}")
            print(
                f"      - Citations: {analysis.total_citations} ({analysis.authoritative_citations} authoritative)"
            )
            print(f"      - Original data: {'Yes' if analysis.has_original_data else 'No'}")
            print(f"      - Visible date: {'Yes' if analysis.has_visible_date else 'No'}")

            results["pillars"]["authority"] = {
                "score": authority_score.total_score,
                "level": authority_score.level,
                "has_author": analysis.has_author,
                "citations": analysis.total_citations,
            }
        else:
            print("      - No authority signals detected")
            results["pillars"]["authority"] = {
                "score": authority_score.total_score,
                "level": authority_score.level,
            }

    # =========================================================
    # Calculate v2 Score
    # =========================================================
    print(f"\n{'='*60}")
    print("FINDABLE SCORE v2 RESULTS")
    print(f"{'='*60}\n")

    # Pass actual score objects to v2 calculator
    calculator = FindableScoreCalculatorV2()
    v2_score = calculator.calculate(
        technical_score=(
            technical_score
            if "technical" in results["pillars"] and "error" not in results["pillars"]["technical"]
            else None
        ),
        structure_score=structure_score if "structure" in results["pillars"] else None,
        schema_score=schema_score if "schema" in results["pillars"] else None,
        authority_score=authority_score if "authority" in results["pillars"] else None,
        simulation_breakdown=None,  # No simulation run in this script
    )

    grade = v2_score.grade.value if hasattr(v2_score.grade, "value") else str(v2_score.grade)

    if v2_score.is_partial:
        print(
            f"Score: {v2_score.total_score:.1f}/{v2_score.max_evaluated_points:.0f} evaluated points"
        )
        print(f"Adjusted: {v2_score.evaluated_score_pct:.1f}% of what was measured")
        print(f"Grade: {grade} - {v2_score.grade_description}")
        print(f"NOTE: {v2_score.pillars_not_evaluated} pillar(s) not run - partial analysis")
    else:
        print(f"Total Score: {v2_score.total_score:.1f}/100")
        print(f"Grade: {grade} - {v2_score.grade_description}")

    print()
    print("Pillar Breakdown:")
    print("-" * 50)

    for pillar in v2_score.pillars:
        if not pillar.evaluated:
            print(f"  {pillar.display_name:20} [----NOT RUN----] --/-- pts (-)")
        else:
            # raw_score is 0-100, so divide by 5 to get 0-20 scale
            bar_filled = int(pillar.raw_score / 5)
            bar_empty = 20 - bar_filled
            bar = "#" * bar_filled + "-" * bar_empty
            level_icon = {"good": "+", "warning": "!", "critical": "x"}.get(pillar.level, "?")
            print(
                f"  {pillar.display_name:20} [{bar}] {pillar.points_earned:.1f}/{pillar.max_points:.0f} pts ({level_icon})"
            )

    print()
    print(f"Evaluated: {v2_score.pillars_evaluated}/6 pillars")
    print(
        f"Pillars: {v2_score.pillars_good} good, {v2_score.pillars_warning} warning, {v2_score.pillars_critical} critical"
    )

    results["v2_score"] = {
        "total": v2_score.total_score,
        "grade": grade,
        "grade_description": v2_score.grade_description,
        "pillars_good": v2_score.pillars_good,
        "pillars_warning": v2_score.pillars_warning,
        "pillars_critical": v2_score.pillars_critical,
        "pillars_evaluated": v2_score.pillars_evaluated,
        "pillars_not_evaluated": v2_score.pillars_not_evaluated,
        "max_evaluated_points": v2_score.max_evaluated_points,
        "is_partial": v2_score.is_partial,
        "evaluated_score_pct": v2_score.evaluated_score_pct,
    }
    results["completed_at"] = datetime.now().isoformat()

    print(f"\n{'='*60}")
    print(f"Analysis complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_site_analysis.py <url> [max_pages]")
        print("Example: python scripts/run_site_analysis.py https://example.com 10")
        sys.exit(1)

    url = sys.argv[1]
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    # Ensure URL has protocol
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    results = asyncio.run(analyze_site(url, max_pages))

    # Save results to JSON
    output_file = (
        f"analysis_{url.replace('https://', '').replace('http://', '').replace('/', '_')}.json"
    )
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to: {output_file}")
