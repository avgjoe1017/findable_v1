#!/usr/bin/env python
"""Run a FULL Findable Score v2 audit on a real site.

This script demonstrates the complete v2 analysis pipeline with ALL 6 pillars:
1. Technical readiness (15 pts)
2. Semantic structure (20 pts)
3. Schema richness (15 pts)
4. Authority signals (15 pts)
5. Retrieval quality (25 pts) - requires simulation
6. Answer coverage (10 pts) - requires simulation

Usage:
    python scripts/run_full_audit.py https://example.com [max_pages]
"""

import asyncio
import json
import sys
import uuid
from datetime import datetime

# Add project root to path
sys.path.insert(0, ".")


async def run_full_audit(url: str, max_pages: int = 10) -> dict:
    """Run full v2 audit with all 6 pillars including simulation."""
    from urllib.parse import urlparse

    from worker.chunking.chunker import SemanticChunker
    from worker.crawler.crawler import crawl_site
    from worker.embeddings.embedder import Embedder
    from worker.extraction.extractor import ContentExtractor
    from worker.questions.generator import QuestionGenerator, SiteContext
    from worker.retrieval.retriever import HybridRetriever
    from worker.scoring.calculator import ScoreCalculator
    from worker.scoring.calculator_v2 import FindableScoreCalculatorV2
    from worker.simulation.runner import SimulationRunner
    from worker.tasks.authority_check import aggregate_authority_scores, run_authority_checks_sync
    from worker.tasks.schema_check import aggregate_schema_scores, run_schema_checks_sync
    from worker.tasks.structure_check import aggregate_structure_scores, run_structure_checks_sync
    from worker.tasks.technical_check import run_technical_checks_parallel

    print(f"\n{'='*70}")
    print("FINDABLE SCORE v2 - FULL AUDIT (All 6 Pillars)")
    print(f"{'='*70}")
    print(f"URL: {url}")
    print(f"Max Pages: {max_pages}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")

    results = {
        "url": url,
        "started_at": datetime.now().isoformat(),
        "pillars": {},
    }

    # Extract domain and company name
    parsed = urlparse(url)
    domain = parsed.netloc
    company_name = domain.split(".")[0].title()

    # =========================================================
    # PILLAR 1: Technical Readiness (15 points)
    # =========================================================
    print("[1/6] Technical Readiness Check...")
    technical_score = None
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
        }
    except Exception as e:
        print(f"      Error: {e}")
        results["pillars"]["technical"] = {"error": str(e)}

    # =========================================================
    # CRAWL: Get site content
    # =========================================================
    print(f"\n[CRAWL] Crawling site (max {max_pages} pages)...")
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
    # EXTRACT: Get content from pages
    # =========================================================
    print("\n[EXTRACT] Extracting content...")
    extractor = ContentExtractor()
    extraction_result = extractor.extract_crawl(crawl_result)
    print(f"      Pages extracted: {extraction_result.total_pages}")
    print(f"      Total words: {extraction_result.total_words:,}")

    results["extraction"] = {
        "pages": extraction_result.total_pages,
        "words": extraction_result.total_words,
    }

    # Update technical score with JS detection
    if technical_score and crawl_result.pages and crawl_result.pages[0].html:
        from worker.extraction.js_detection import detect_js_dependency
        from worker.scoring.technical import calculate_technical_score

        js_result = detect_js_dependency(crawl_result.pages[0].html, url)
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
    # PILLAR 2: Semantic Structure (20 points)
    # =========================================================
    print("\n[2/6] Semantic Structure Analysis...")
    structure_score = None
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
        print(f"      Pages analyzed: {len(structure_scores)}")
        results["pillars"]["structure"] = {
            "score": structure_score.total_score,
            "level": structure_score.level,
        }

    # =========================================================
    # PILLAR 3: Schema Richness (15 points)
    # =========================================================
    print("\n[3/6] Schema Richness Analysis...")
    schema_score = None
    schema_scores = []
    for page in crawl_result.pages:
        if page.html:
            score = run_schema_checks_sync(html=page.html, url=page.url)
            schema_scores.append(score)

    if schema_scores:
        schema_score = aggregate_schema_scores(schema_scores)
        print(f"      Score: {schema_score.total_score:.1f}/100 ({schema_score.level})")
        types_found = (
            schema_score.schema_analysis.schema_types_found if schema_score.schema_analysis else []
        )
        print(f"      Schema types: {', '.join(types_found) or 'None'}")
        results["pillars"]["schema"] = {
            "score": schema_score.total_score,
            "level": schema_score.level,
            "types": types_found,
        }

    # =========================================================
    # PILLAR 4: Authority Signals (15 points)
    # =========================================================
    print("\n[4/6] Authority Signals Analysis...")
    authority_score = None
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
        analysis = authority_score.authority_analysis
        if analysis:
            print(f"      - Author: {'Yes' if analysis.has_author else 'No'}")
            print(
                f"      - Citations: {analysis.total_citations} ({analysis.authoritative_citations} authoritative)"
            )
        results["pillars"]["authority"] = {
            "score": authority_score.total_score,
            "level": authority_score.level,
        }

    # =========================================================
    # CHUNK: Prepare content for retrieval
    # =========================================================
    print("\n[CHUNK] Chunking content...")
    chunker = SemanticChunker()
    chunked_pages = []
    total_chunks = 0

    for page in extraction_result.pages:
        chunked_page = chunker.chunk_text(
            text=page.main_content,
            url=page.url,
            title=page.title,
        )
        chunked_pages.append(chunked_page)
        total_chunks += chunked_page.total_chunks

    print(f"      Total chunks: {total_chunks}")
    results["chunking"] = {"total_chunks": total_chunks}

    # =========================================================
    # EMBED: Create embeddings for retrieval
    # =========================================================
    print("\n[EMBED] Creating embeddings...")
    embedder = Embedder()
    embedded_pages = embedder.embed_pages(chunked_pages)
    total_embeddings = sum(len(ep.embeddings) for ep in embedded_pages)
    print(f"      Total embeddings: {total_embeddings}")
    results["embedding"] = {"total_embeddings": total_embeddings}

    # =========================================================
    # INDEX: Build retriever
    # =========================================================
    print("\n[INDEX] Building retriever index...")
    retriever = HybridRetriever(embedder=embedder)

    for page_idx, ep in enumerate(embedded_pages):
        for emb_result in ep.embeddings:
            chunk = chunked_pages[page_idx].chunks[emb_result.chunk_index]
            retriever.add_document(
                doc_id=emb_result.content_hash,
                content=chunk.content,
                embedding=emb_result.embedding,
                source_url=emb_result.source_url,
                page_title=emb_result.page_title,
                heading_context=emb_result.heading_context,
            )

    print(f"      Documents indexed: {len(retriever._documents)}")

    # =========================================================
    # QUESTIONS: Generate test questions
    # =========================================================
    print("\n[QUESTIONS] Generating questions...")

    # Collect schema types and headings
    schema_types = list(set(extraction_result.schema_types_found))
    headings = {"h1": [], "h2": [], "h3": []}
    for page in extraction_result.pages:
        page_headings = page.metadata.headings or {}
        for level in ["h1", "h2", "h3"]:
            if level in page_headings:
                headings[level].extend(page_headings[level])

    site_context = SiteContext(
        company_name=company_name,
        domain=domain,
        schema_types=schema_types,
        headings=headings,
    )

    question_generator = QuestionGenerator()
    questions = question_generator.generate(site_context)
    print(f"      Questions generated: {len(questions)}")
    results["questions"] = {"count": len(questions)}

    # =========================================================
    # PILLAR 5 & 6: Simulation (Retrieval + Coverage)
    # =========================================================
    print("\n[5/6 & 6/6] Running Simulation (Retrieval + Coverage)...")
    site_id = uuid.uuid4()
    run_id = uuid.uuid4()

    simulation_runner = SimulationRunner(retriever=retriever)
    simulation_result = simulation_runner.run(
        site_id=site_id,
        run_id=run_id,
        company_name=company_name,
        questions=questions,
    )

    print(f"      Questions answered: {simulation_result.questions_answered}")
    print(f"      Questions partial: {simulation_result.questions_partial}")
    print(f"      Questions unanswered: {simulation_result.questions_unanswered}")
    print(f"      Overall score: {simulation_result.overall_score:.1f}")

    results["simulation"] = {
        "questions_answered": simulation_result.questions_answered,
        "questions_partial": simulation_result.questions_partial,
        "questions_unanswered": simulation_result.questions_unanswered,
        "overall_score": simulation_result.overall_score,
    }

    # Calculate v1 score breakdown for retrieval/coverage pillars
    score_calculator = ScoreCalculator()
    score_breakdown = score_calculator.calculate(simulation_result)

    print(f"      Coverage: {score_breakdown.coverage_percentage:.1f}%")
    print(f"      Retrieval quality: {score_breakdown.total_score:.1f}")

    results["pillars"]["retrieval"] = {
        "score": score_breakdown.total_score,
        "level": (
            "good"
            if score_breakdown.total_score >= 70
            else "warning" if score_breakdown.total_score >= 40 else "critical"
        ),
    }
    results["pillars"]["coverage"] = {
        "score": score_breakdown.coverage_percentage,
        "level": (
            "good"
            if score_breakdown.coverage_percentage >= 70
            else "warning" if score_breakdown.coverage_percentage >= 40 else "critical"
        ),
    }

    # =========================================================
    # FINAL: Calculate v2 Score with ALL 6 Pillars
    # =========================================================
    print(f"\n{'='*70}")
    print("FINDABLE SCORE v2 - FINAL RESULTS (All 6 Pillars)")
    print(f"{'='*70}\n")

    calculator = FindableScoreCalculatorV2()
    v2_score = calculator.calculate(
        technical_score=technical_score,
        structure_score=structure_score,
        schema_score=schema_score,
        authority_score=authority_score,
        simulation_breakdown=score_breakdown,
    )

    if v2_score.is_partial:
        print(
            f"Score: {v2_score.total_score:.1f}/{v2_score.max_evaluated_points:.0f} evaluated points"
        )
        print(f"Adjusted: {v2_score.evaluated_score_pct:.1f}%")
        print(f"NOTE: {v2_score.pillars_not_evaluated} pillar(s) not run")
    else:
        print(f"Total Score: {v2_score.total_score:.1f}/100")

    print(f"Level: {v2_score.level_label.upper()}")
    print(f'"{v2_score.level_summary}"')
    print(f"Focus: {v2_score.level_focus}")
    print()
    print("Pillar Breakdown:")
    print("-" * 60)

    for pillar in v2_score.pillars:
        if not pillar.evaluated:
            print(f"  {pillar.display_name:20} [----NOT RUN----] --/-- pts (-)")
        else:
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

    # Show calculation breakdown
    print()
    print("Calculation:")
    print("-" * 60)
    for step in v2_score.calculation_summary:
        if step:
            print(f"  {step}")

    # Show critical issues if any
    if v2_score.all_critical_issues:
        print()
        print("Critical Issues:")
        print("-" * 60)
        for issue in v2_score.all_critical_issues[:5]:
            print(f"  * {issue}")

    # Show top recommendations
    if v2_score.top_recommendations:
        print()
        print("Top Recommendations:")
        print("-" * 60)
        for rec in v2_score.top_recommendations[:5]:
            print(f"  * {rec}")

    results["v2_score"] = {
        "total": v2_score.total_score,
        "level": v2_score.level,
        "level_label": v2_score.level_label,
        "level_summary": v2_score.level_summary,
        "level_focus": v2_score.level_focus,
        "next_milestone": v2_score.next_milestone.to_dict() if v2_score.next_milestone else None,
        "points_to_milestone": v2_score.points_to_milestone,
        "pillars_evaluated": v2_score.pillars_evaluated,
        "pillars_not_evaluated": v2_score.pillars_not_evaluated,
        "max_evaluated_points": v2_score.max_evaluated_points,
        "is_partial": v2_score.is_partial,
        "evaluated_score_pct": v2_score.evaluated_score_pct,
        "pillars_good": v2_score.pillars_good,
        "pillars_warning": v2_score.pillars_warning,
        "pillars_critical": v2_score.pillars_critical,
        "strengths": v2_score.strengths,
    }
    results["completed_at"] = datetime.now().isoformat()

    print(f"\n{'='*70}")
    print(f"Analysis complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_full_audit.py <url> [max_pages]")
        print("Example: python scripts/run_full_audit.py https://example.com 5")
        sys.exit(1)

    url = sys.argv[1]
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    # Ensure URL has protocol
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    results = asyncio.run(run_full_audit(url, max_pages))

    # Save results to JSON
    output_file = (
        f"full_audit_{url.replace('https://', '').replace('http://', '').replace('/', '_')}.json"
    )
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to: {output_file}")
