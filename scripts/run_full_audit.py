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
import os
import sys
import uuid
from datetime import datetime

# Add project root to path
sys.path.insert(0, ".")

# Load .env file if present
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv not installed, rely on system env vars


async def run_full_audit(url: str, max_pages: int = 10) -> dict:
    """Run full v2 audit with all 6 pillars including simulation."""
    from urllib.parse import urlparse

    from worker.chunking.chunker import SemanticChunker
    from worker.crawler.crawler import crawl_site
    from worker.embeddings.embedder import Embedder
    from worker.extraction.extractor import ContentExtractor
    from worker.extraction.site_type import detect_site_type
    from worker.observation.models import ProviderType
    from worker.observation.runner import ObservationRunner, RunConfig
    from worker.questions.generator import QuestionGenerator, SiteContext
    from worker.retrieval.retriever import HybridRetriever
    from worker.scoring.calculator import ScoreCalculator
    from worker.scoring.calculator_v2 import FindableScoreCalculatorV2
    from worker.scoring.citation_context import generate_citation_context
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
    # SITE TYPE: Content Type Classification
    # =========================================================
    print("\n[SITE TYPE] Detecting site content type...")
    site_type_result = None
    citation_context = None
    try:
        page_urls = [page.url for page in crawl_result.pages]
        page_htmls = [page.html for page in crawl_result.pages]

        site_type_result = detect_site_type(
            domain=domain,
            page_urls=page_urls,
            page_htmls=page_htmls,
        )

        print(f"      Type: {site_type_result.site_type.value}")
        print(f"      Confidence: {site_type_result.confidence:.0%}")
        print(f"      Citation Baseline: {site_type_result.citation_baseline:.0%}")
        print(f"      Signals: {', '.join(site_type_result.signals[:3])}")

        # Generate citation context
        citation_context = generate_citation_context(site_type_result)

        results["site_type"] = site_type_result.to_dict()
        results["citation_context"] = citation_context.to_dict()

    except Exception as e:
        print(f"      Error: {e}")

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
        "pillars": [p.to_dict() for p in v2_score.pillars],
    }

    # =========================================================
    # OBSERVATION: Live AI Citation Depth (Citable Index)
    # =========================================================
    print("\n[OBSERVATION] Running live AI observations...")

    # Check for API keys
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    observation_run = None
    citable_index = None

    if openrouter_key or openai_key:
        # Configure observation
        if openrouter_key:
            primary = ProviderType.OPENROUTER
            fallback = ProviderType.OPENAI if openai_key else ProviderType.MOCK
        else:
            primary = ProviderType.OPENAI
            fallback = ProviderType.MOCK

        obs_config = RunConfig(
            primary_provider=primary,
            fallback_provider=fallback,
            model="openai/gpt-4o-mini",
            openrouter_api_key=openrouter_key,
            openai_api_key=openai_key,
            max_questions=20,  # Limit for testing
            max_cost_per_run=0.50,  # Cost cap
            citation_depth_enabled=True,  # Enable citation depth analysis
            concurrent_requests=3,
        )

        # Prepare questions as (id, text) tuples
        obs_questions = [(q.id, q.text) for q in questions[:20]]

        def progress_cb(done: int, total: int, status: str) -> None:
            print(f"      [{done}/{total}] {status}")

        obs_runner = ObservationRunner(config=obs_config, progress_callback=progress_cb)

        observation_run = await obs_runner.run_observation(
            site_id=site_id,
            run_id=run_id,
            company_name=company_name,
            domain=domain,
            questions=obs_questions,
        )

        print(f"      Status: {observation_run.status.value}")
        print(f"      Questions completed: {observation_run.questions_completed}")
        print(f"      Company mention rate: {observation_run.company_mention_rate:.1%}")
        print(f"      Domain mention rate: {observation_run.domain_mention_rate:.1%}")
        print(f"      Citation rate: {observation_run.citation_rate:.1%}")
        print(f"      Avg citation depth: {observation_run.avg_citation_depth:.2f}")
        print(f"      Total cost: ${observation_run.total_usage.estimated_cost_usd:.4f}")

        # Calculate Citable Index metrics
        completed_results = [
            r for r in observation_run.results if r.response and r.response.success
        ]
        if completed_results:
            n = len(completed_results)
            pct_citable = sum(1 for r in completed_results if r.citation_depth >= 3) / n * 100
            pct_strongly_sourced = (
                sum(1 for r in completed_results if r.citation_depth >= 4) / n * 100
            )

            # Track URL-floor rule usage (transparency metric)
            # Floored = mentions_url but heuristic_depth < 3 (floor raised it to 3)
            floored_count = sum(
                1
                for r in completed_results
                if r.mentions_url and getattr(r, "heuristic_depth", 0) < 3 and r.citation_depth >= 3
            )
            pct_floored = floored_count / n * 100 if n else 0.0

            # Determine bands
            citable_band = "low" if pct_citable < 10 else ("mid" if pct_citable < 25 else "high")
            strongly_band = (
                "low"
                if pct_strongly_sourced < 5
                else ("mid" if pct_strongly_sourced < 15 else "high")
            )

            # Top wins (depth >= 4) and misses (depth <= 1)
            top_wins = sorted(
                [r for r in completed_results if r.citation_depth >= 4],
                key=lambda r: -r.citation_depth,
            )[:3]
            top_misses = sorted(
                [r for r in completed_results if r.citation_depth <= 1],
                key=lambda r: r.citation_depth,
            )[:3]

            # Build miss reason for each miss
            def get_miss_reason(r):
                if not r.mentions_company:
                    return "not mentioned"
                elif not r.mentions_url:
                    return "no URL"
                else:
                    return "listed only"

            citable_index = {
                "avg_depth": round(observation_run.avg_citation_depth, 2),
                "pct_citable": round(pct_citable, 1),
                "pct_strongly_sourced": round(pct_strongly_sourced, 1),
                "pct_floored": round(pct_floored, 1),  # % boosted by URL-floor rule
                "citable_band": citable_band,
                "strongly_sourced_band": strongly_band,
                "questions_observed": n,
                "company_mention_rate": round(observation_run.company_mention_rate * 100, 1),
                "citation_rate": round(observation_run.citation_rate * 100, 1),
                "top_wins": [
                    {
                        "question": r.question_text[:60],
                        "depth": r.citation_depth,
                        "label": r.citation_depth_label,
                    }
                    for r in top_wins
                ],
                "top_misses": [
                    {
                        "question": r.question_text[:60],
                        "depth": r.citation_depth,
                        "reason": get_miss_reason(r),
                    }
                    for r in top_misses
                ],
            }

            results["citable_index"] = citable_index

            # Store observation results
            results["observation"] = {
                "status": observation_run.status.value,
                "questions_completed": observation_run.questions_completed,
                "questions_failed": observation_run.questions_failed,
                "company_mention_rate": round(observation_run.company_mention_rate, 3),
                "domain_mention_rate": round(observation_run.domain_mention_rate, 3),
                "citation_rate": round(observation_run.citation_rate, 3),
                "avg_citation_depth": round(observation_run.avg_citation_depth, 2),
                "total_cost_usd": round(observation_run.total_usage.estimated_cost_usd, 4),
            }

            print()
            print(f"      CITABLE INDEX: {pct_citable:.1f}% citable ({citable_band})")
            print(f"      Strongly sourced: {pct_strongly_sourced:.1f}% ({strongly_band})")
    else:
        print("      Skipped: No OPENROUTER_API_KEY or OPENAI_API_KEY found")
        print("      Set one of these environment variables to enable observation")

    # Build headline (2-axis model)
    if citable_index:
        pct_cit = citable_index["pct_citable"]
        pct_strong = citable_index["pct_strongly_sourced"]
        # More accurate wording: depth 3 = "citable" (URL included), depth 4+ = "strongly sourced"
        if pct_strong > 0:
            headline_summary = (
                f"Your site scores {v2_score.total_score:.0f}/100 ({v2_score.level_label}). "
                f"{pct_cit:.0f}% of AI answers include your URL (citable), "
                f"{pct_strong:.0f}% treat you as authoritative."
            )
        else:
            headline_summary = (
                f"Your site scores {v2_score.total_score:.0f}/100 ({v2_score.level_label}). "
                f"{pct_cit:.0f}% of AI answers include your URL, but 0% treat you as the authority."
            )
        results["headline"] = {
            "findable_score": round(v2_score.total_score, 1),
            "findable_level": v2_score.level,
            "findable_level_label": v2_score.level_label,
            "pct_citable": citable_index["pct_citable"],
            "pct_strongly_sourced": citable_index["pct_strongly_sourced"],
            "avg_depth": citable_index["avg_depth"],
            "citable_band": citable_index["citable_band"],
            "strongly_sourced_band": citable_index["strongly_sourced_band"],
            "pct_floored": citable_index.get("pct_floored", 0),
            "summary": headline_summary,
        }
    else:
        results["headline"] = {
            "findable_score": round(v2_score.total_score, 1),
            "findable_level": v2_score.level,
            "findable_level_label": v2_score.level_label,
            "pct_citable": None,
            "citable_band": None,
            "summary": (
                f"Your site scores {v2_score.total_score:.0f}/100 ({v2_score.level_label}). "
                "Run observation to measure live citation depth."
            ),
        }

    # Build top 3 causes from weakest pillars + observation
    pillar_cause_map = {
        "technical": {
            "cause": "AI crawlers can't access your content",
            "fix": "Fix robots.txt blocks, improve page speed, and ensure HTTPS.",
        },
        "structure": {
            "cause": "Content isn't structured for AI extraction",
            "fix": "Fix heading hierarchy, lead with answers, and add FAQ sections.",
        },
        "schema": {
            "cause": "Missing structured data markup",
            "fix": "Add FAQPage, HowTo, Article, and Organization schema.",
        },
        "authority": {
            "cause": "Weak trust and authority signals",
            "fix": "Add author attribution, credentials, citations, and visible dates.",
        },
        "entity_recognition": {
            "cause": "AI doesn't recognize your brand as an entity",
            "fix": "Build external brand presence (Wikipedia, Wikidata, domain authority).",
        },
        "retrieval": {
            "cause": "Content doesn't surface in AI retrieval",
            "fix": "Improve content depth, reduce boilerplate, and add quotable statements.",
        },
        "coverage": {
            "cause": "Missing answers to common questions about your domain",
            "fix": "Create content covering entity facts and product/how-to questions.",
        },
    }

    evaluated_pillars = [p for p in v2_score.pillars if p.evaluated]
    weakest = sorted(evaluated_pillars, key=lambda p: p.raw_score)[:2]

    top_causes = []
    for pillar in weakest:
        cause_info = pillar_cause_map.get(
            pillar.name,
            {
                "cause": f"Low {pillar.display_name} score",
                "fix": "Review and improve this area.",
            },
        )
        proof_parts = [f"{pillar.display_name} score: {pillar.raw_score:.0f}/100"]
        if pillar.critical_issues:
            proof_parts.append(pillar.critical_issues[0])
        top_causes.append(
            {
                "cause": cause_info["cause"],
                "proof": "; ".join(proof_parts),
                "fix": cause_info["fix"],
                "source": "pillar",
                "pillar_name": pillar.name,
            }
        )

    # Add observation-based cause (identify gaps, not positives)
    if citable_index:
        pct_cit = citable_index["pct_citable"]
        pct_strong = citable_index["pct_strongly_sourced"]
        pct_floor = citable_index.get("pct_floored", 0)

        if pct_cit < 25:
            # Low citation rate is a real problem
            top_causes.append(
                {
                    "cause": "AI rarely includes your URLs in answers",
                    "proof": f"Only {pct_cit:.0f}% of responses include a {domain} URL (citable threshold)",
                    "fix": "Add unique data, quotable statistics, and explicit source attribution.",
                    "source": "observation",
                    "pillar_name": None,
                }
            )
        elif pct_strong < 5 and pct_cit >= 25:
            # High URL presence but no authority framing — the real gap
            top_causes.append(
                {
                    "cause": "URLs included but rarely treated as authoritative",
                    "proof": (
                        f"{pct_cit:.0f}% include a URL (citable), but {pct_strong:.0f}% strongly sourced. "
                        f"Floored by URL rule: {pct_floor:.0f}%."
                    ),
                    "fix": "Create primary-source pages with unique research, definitions, and expert commentary.",
                    "source": "observation",
                    "pillar_name": None,
                }
            )
        elif pct_floor > 50:
            # Most citable % is from floor rule, not earned
            top_causes.append(
                {
                    "cause": "Citation depth inflated by URL presence",
                    "proof": f"{pct_floor:.0f}% of citable scores came from URL-floor rule, not organic authority.",
                    "fix": "Build content that earns depth 3+ without relying on URL links.",
                    "source": "observation",
                    "pillar_name": None,
                }
            )
        else:
            # Strong observation — don't put in causes, note as strength
            # But we need a 3rd cause, so use a minor gap if available
            if pct_strong < 15:
                top_causes.append(
                    {
                        "cause": "Room to grow from citable to authoritative",
                        "proof": f"{pct_cit:.0f}% citable but only {pct_strong:.0f}% strongly sourced (depth 4+).",
                        "fix": "Add original research, expert quotes, and explicit source attribution.",
                        "source": "observation",
                        "pillar_name": None,
                    }
                )
    else:
        top_causes.append(
            {
                "cause": "Citation depth unknown",
                "proof": "Observation not run — no live AI responses analyzed.",
                "fix": "Run observation to measure how deeply AI cites your content.",
                "source": "observation",
                "pillar_name": None,
            }
        )

    results["top_causes"] = {"causes": top_causes[:3]}

    # Print headline and top causes
    print()
    print("=" * 70)
    print("HEADLINE (2-AXIS MODEL)")
    print("=" * 70)

    # All 4 numbers in a tight block
    print(f"  Findable Score:    {v2_score.total_score:.0f}/100 ({v2_score.level_label})")
    if citable_index:
        print(
            f"  Citable:           {citable_index['pct_citable']:.0f}% of answers include your URL"
        )
        print(
            f"  Strongly Sourced:  {citable_index['pct_strongly_sourced']:.0f}% treat you as authoritative"
        )
        print(f"  Avg Depth:         {citable_index['avg_depth']:.1f}/5")
        if citable_index.get("pct_floored", 0) > 0:
            print(f"  (Floored by URL:   {citable_index['pct_floored']:.0f}%)")

        if citable_index.get("top_wins"):
            print()
            print("  Top Wins (depth 4+):")
            for win in citable_index["top_wins"][:2]:
                print(f"    + {win['question'][:50]}... [depth {win['depth']}]")
        if citable_index.get("top_misses"):
            print()
            print("  Top Misses (depth 0-1):")
            for miss in citable_index["top_misses"][:2]:
                print(f"    - {miss['question'][:50]}... [depth {miss['depth']}: {miss['reason']}]")
    else:
        print("AXIS 2 - Citable Index: [Observation not run]")
    print()
    print("TOP 3 CAUSES:")
    for i, cause in enumerate(top_causes[:3], 1):
        print(f"  {i}. {cause['cause']}")
        print(f"     Proof: {cause['proof']}")
        print(f"     Fix: {cause['fix']}")

    # Print citation context if available
    if citation_context:
        print()
        print(citation_context.show_citation_context())

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
