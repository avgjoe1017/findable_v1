"""Validation Study: Simulation vs Observation Accuracy.

Runs the full Findable Score pipeline on real sites, then queries a real AI model
(via OpenRouter) with the same questions to measure prediction accuracy.

This answers the core question: "Does the Findable Score predict real AI citability?"

Usage:
    python scripts/run_validation_study.py
    python scripts/run_validation_study.py --sites "https://moz.com,https://calendly.com"
    python scripts/run_validation_study.py --max-pages 20 --model openai/gpt-4o-mini
"""

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlparse

sys.path.insert(0, ".")

import structlog  # noqa: E402

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    wrapper_class=structlog.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger(__name__)


class ValidationResult(NamedTuple):
    """Result for a single site's validation."""

    domain: str
    findable_score: float
    level_label: str

    # Simulation metrics
    sim_questions_total: int
    sim_questions_answerable: int
    sim_coverage_pct: float

    # Observation metrics
    obs_questions_completed: int
    obs_company_mention_rate: float
    obs_domain_mention_rate: float
    obs_citation_rate: float

    # Comparison metrics
    prediction_accuracy: float
    correct_predictions: int
    optimistic_predictions: int
    pessimistic_predictions: int
    unknown_predictions: int

    # Citation depth (0-5 scale)
    avg_citation_depth: float
    depth_distribution: dict[int, int]
    position_distribution: dict[str, int]
    framing_distribution: dict[str, int]
    avg_competitors: float
    pct_citable: float  # % depth >= 3
    pct_strongly_sourced: float  # % depth >= 4
    depth_confidence: str  # "high" | "medium" | "low"

    # Cost
    obs_cost_usd: float
    obs_latency_ms: float
    depth_cost_usd: float

    # Metadata
    duration_seconds: float
    error: str | None = None
    insights: tuple[str, ...] = ()
    recommendations: tuple[str, ...] = ()


# Default sites — same as lead audit minus known-blocked sites
DEFAULT_VALIDATION_SITES = [
    "https://moz.com",
    "https://backlinko.com",
    "https://ahrefs.com",
    "https://calendly.com",
    "https://www.loom.com",
    "https://www.typeform.com",
    "https://mailchimp.com",
    "https://www.bain.com",
    "https://docs.python.org",
    "https://stripe.com/docs",
]


async def validate_site(
    url: str,
    max_pages: int = 30,
    model: str = "openai/gpt-4o-mini",
    openrouter_key: str = "",
    openai_key: str = "",
) -> ValidationResult:
    """
    Run full audit + observation on a single site and compare.

    Args:
        url: Site URL to validate
        max_pages: Maximum pages to crawl
        model: AI model to use for observation
        openrouter_key: OpenRouter API key
        openai_key: OpenAI API key

    Returns:
        ValidationResult with accuracy metrics
    """
    from worker.chunking.chunker import SemanticChunker
    from worker.crawler.crawler import CrawlConfig, Crawler
    from worker.embeddings.embedder import Embedder
    from worker.extraction.extractor import ContentExtractor
    from worker.observation.comparison import compare_simulation_observation
    from worker.observation.models import ProviderType
    from worker.observation.runner import ObservationRunner, RunConfig
    from worker.questions.generator import QuestionGenerator, SiteContext
    from worker.retrieval.retriever import HybridRetriever
    from worker.scoring.calculator import ScoreCalculator
    from worker.scoring.calculator_v2 import calculate_findable_score_v2
    from worker.simulation.runner import Answerability, SimulationRunner
    from worker.tasks.authority_check import aggregate_authority_scores, run_authority_checks_sync
    from worker.tasks.schema_check import aggregate_schema_scores, run_schema_checks_sync
    from worker.tasks.structure_check import aggregate_structure_scores, run_structure_checks_sync
    from worker.tasks.technical_check import run_technical_checks_parallel

    parsed = urlparse(url)
    domain = parsed.netloc or url.replace("https://", "").replace("http://", "").split("/")[0]

    start_time = datetime.now(UTC)

    try:
        logger.info("validation_starting", domain=domain)

        # ===========================================================
        # PHASE 1: Full Audit Pipeline (same as e2e_test_sites.py)
        # ===========================================================

        # Step 1: Technical Check
        technical_score = None
        try:
            technical_score = await run_technical_checks_parallel(url=url, html=None, timeout=10.0)
        except Exception as e:
            logger.warning("technical_check_failed", error=str(e))

        # Step 2: Crawl
        logger.info("crawling", domain=domain, max_pages=max_pages)
        config = CrawlConfig(
            max_pages=max_pages,
            max_depth=2,
            timeout=30.0,
            user_agent="FindableBot/1.0 (Validation Study)",
        )
        crawler = Crawler(config)
        crawl_result = await crawler.crawl(url)

        if not crawl_result.pages:
            duration = (datetime.now(UTC) - start_time).total_seconds()
            return ValidationResult(
                domain=domain,
                findable_score=0,
                level_label="Blocked",
                sim_questions_total=0,
                sim_questions_answerable=0,
                sim_coverage_pct=0,
                obs_questions_completed=0,
                obs_company_mention_rate=0,
                obs_domain_mention_rate=0,
                obs_citation_rate=0,
                prediction_accuracy=0,
                correct_predictions=0,
                optimistic_predictions=0,
                pessimistic_predictions=0,
                unknown_predictions=0,
                avg_citation_depth=0,
                depth_distribution={},
                position_distribution={},
                framing_distribution={},
                avg_competitors=0,
                pct_citable=0,
                pct_strongly_sourced=0,
                depth_confidence="low",
                obs_cost_usd=0,
                obs_latency_ms=0,
                depth_cost_usd=0,
                duration_seconds=duration,
                error="No pages crawled - site blocked or requires JS rendering",
            )

        logger.info("crawled", pages=len(crawl_result.pages))

        # Step 3: Extract
        extractor = ContentExtractor()
        extraction_result = extractor.extract_crawl(crawl_result)

        # Update technical score with JS detection
        if technical_score and crawl_result.pages:
            from worker.extraction.js_detection import detect_js_dependency
            from worker.scoring.technical import calculate_technical_score

            homepage_html = crawl_result.pages[0].html
            if homepage_html:
                try:
                    js_result = detect_js_dependency(homepage_html, url)
                    technical_score = calculate_technical_score(
                        robots_result=technical_score.robots_result,
                        ttfb_result=technical_score.ttfb_result,
                        llms_txt_result=technical_score.llms_txt_result,
                        js_result=js_result,
                        is_https=technical_score.is_https,
                    )
                except Exception:
                    pass

        # Step 4: Structure Analysis
        structure_score = None
        try:
            page_scores = []
            for i, page in enumerate(crawl_result.pages):
                if page.html and i < len(extraction_result.pages):
                    extracted = extraction_result.pages[i]
                    page_score = run_structure_checks_sync(
                        html=page.html,
                        url=page.url,
                        main_content=extracted.main_content,
                        word_count=extracted.word_count,
                    )
                    page_scores.append(page_score)
            if page_scores:
                structure_score = aggregate_structure_scores(page_scores)
        except Exception as e:
            logger.warning("structure_analysis_failed", error=str(e))

        # Step 5: Schema Analysis
        schema_score = None
        try:
            schema_page_scores = []
            for page in crawl_result.pages:
                if page.html:
                    page_schema = run_schema_checks_sync(html=page.html, url=page.url)
                    schema_page_scores.append(page_schema)
            if schema_page_scores:
                schema_score = aggregate_schema_scores(schema_page_scores)
        except Exception as e:
            logger.warning("schema_analysis_failed", error=str(e))

        # Step 6: Authority Analysis
        authority_score = None
        try:
            authority_page_scores = []
            for i, page in enumerate(crawl_result.pages):
                if page.html and i < len(extraction_result.pages):
                    extracted = extraction_result.pages[i]
                    page_authority = run_authority_checks_sync(
                        html=page.html,
                        url=page.url,
                        main_content=extracted.main_content,
                    )
                    authority_page_scores.append(page_authority)
            if authority_page_scores:
                authority_score = aggregate_authority_scores(authority_page_scores)
        except Exception as e:
            logger.warning("authority_analysis_failed", error=str(e))

        # Step 7: Chunking
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

        # Step 8: Embedding
        embedder = Embedder()
        embedded_pages = embedder.embed_pages(chunked_pages)

        # Step 9: Build Retriever
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

        # Step 10: Generate Questions
        schema_types = list(set(extraction_result.schema_types_found))
        headings: dict[str, list[str]] = {"h1": [], "h2": [], "h3": []}
        for page in extraction_result.pages:
            page_headings = page.metadata.headings or {}
            for level in ["h1", "h2", "h3"]:
                if level in page_headings:
                    headings[level].extend(page_headings[level])

        company_name = domain.replace("www.", "").split(".")[0].title()
        site_context = SiteContext(
            company_name=company_name,
            domain=domain,
            schema_types=schema_types,
            headings=headings,
        )

        question_generator = QuestionGenerator()
        questions = question_generator.generate(site_context)
        logger.info("questions_generated", count=len(questions))

        # Step 11: Simulation
        site_id = uuid.uuid4()
        run_id = uuid.uuid4()

        simulation_runner = SimulationRunner(retriever=retriever)
        simulation_result = simulation_runner.run(
            site_id=site_id,
            run_id=run_id,
            company_name=company_name,
            questions=questions,
        )

        logger.info(
            "simulation_done",
            overall=simulation_result.overall_score,
            answered=simulation_result.questions_answered,
            partial=simulation_result.questions_partial,
            unanswered=simulation_result.questions_unanswered,
        )

        # Step 12: V1 + V2 scoring
        score_calculator = ScoreCalculator()
        v1_breakdown = score_calculator.calculate(simulation_result)

        v2_score = calculate_findable_score_v2(
            technical_score=technical_score,
            structure_score=structure_score,
            schema_score=schema_score,
            authority_score=authority_score,
            simulation_breakdown=v1_breakdown,
        )

        logger.info(
            "scoring_done",
            findable_score=round(v2_score.total_score, 1),
            level=v2_score.level_label,
        )

        # ===========================================================
        # PHASE 2: Observation (Real AI Queries)
        # ===========================================================
        logger.info(
            "observation_starting",
            domain=domain,
            model=model,
            questions=len(questions),
        )

        # Prepare questions for observation
        obs_questions = [
            (qr.question_id, qr.question_text) for qr in simulation_result.question_results
        ]

        # Configure observation (with citation depth enabled)
        obs_config = RunConfig(
            primary_provider=ProviderType.OPENROUTER,
            fallback_provider=ProviderType.OPENAI,
            model=model,
            openrouter_api_key=openrouter_key,
            openai_api_key=openai_key,
            max_retries=2,
            requests_per_minute=20,
            concurrent_requests=3,
            request_timeout_seconds=60.0,
            total_timeout_seconds=300.0,
            max_questions=25,
            max_cost_per_run=0.50,
            citation_depth_enabled=True,
        )

        obs_runner = ObservationRunner(
            config=obs_config,
            progress_callback=lambda c, t, s: logger.info(
                "obs_progress", completed=c, total=t, status=s
            ),
        )

        obs_run = await obs_runner.run_observation(
            site_id=site_id,
            run_id=run_id,
            company_name=company_name,
            domain=domain,
            questions=obs_questions,
        )

        logger.info(
            "observation_done",
            completed=obs_run.questions_completed,
            failed=obs_run.questions_failed,
            mention_rate=obs_run.company_mention_rate,
            citation_rate=obs_run.citation_rate,
            avg_citation_depth=round(obs_run.avg_citation_depth, 2),
            cost=obs_run.total_usage.estimated_cost_usd,
        )

        # ===========================================================
        # PHASE 3: Compare Simulation vs Observation
        # ===========================================================
        logger.info("comparing_results", domain=domain)

        comparison = compare_simulation_observation(
            simulation=simulation_result,
            observation=obs_run,
        )

        logger.info(
            "comparison_done",
            accuracy=comparison.prediction_accuracy,
            correct=comparison.correct_predictions,
            optimistic=comparison.optimistic_predictions,
            pessimistic=comparison.pessimistic_predictions,
        )

        # Calculate sim coverage
        sim_answerable = sum(
            1
            for r in simulation_result.question_results
            if r.answerability
            in (
                Answerability.FULLY_ANSWERABLE,
                Answerability.PARTIALLY_ANSWERABLE,
            )
        )

        duration = (datetime.now(UTC) - start_time).total_seconds()

        # Build citation depth distributions from per-result data
        depth_dist: dict[int, int] = {}
        position_dist: dict[str, int] = {}
        framing_dist: dict[str, int] = {}
        total_competitors = 0
        depth_count = 0

        depths_list: list[int] = []
        heuristic_list: list[int] = []
        for r in obs_run.results:
            if r.response and r.response.success:
                depth_dist[r.citation_depth] = depth_dist.get(r.citation_depth, 0) + 1
                position_dist[r.mention_position] = position_dist.get(r.mention_position, 0) + 1
                framing_dist[r.source_framing] = framing_dist.get(r.source_framing, 0) + 1
                total_competitors += r.competitors_mentioned
                depth_count += 1
                depths_list.append(r.citation_depth)
                heuristic_list.append(r.heuristic_depth)

        # Citable index metrics
        if depth_count:
            pct_citable = sum(1 for d in depths_list if d >= 3) / depth_count * 100
            pct_strongly = sum(1 for d in depths_list if d >= 4) / depth_count * 100
            div = (
                sum(abs(d - h) for d, h in zip(depths_list, heuristic_list, strict=False))
                / depth_count
            )
            depth_conf = "low" if div >= 2.0 else "medium" if div >= 1.0 else "high"
        else:
            pct_citable = 0.0
            pct_strongly = 0.0
            depth_conf = "low"

        return ValidationResult(
            domain=domain,
            findable_score=round(v2_score.total_score, 1),
            level_label=v2_score.level_label,
            sim_questions_total=simulation_result.total_questions,
            sim_questions_answerable=sim_answerable,
            sim_coverage_pct=round(simulation_result.coverage_score, 1),
            obs_questions_completed=obs_run.questions_completed,
            obs_company_mention_rate=round(obs_run.company_mention_rate, 3),
            obs_domain_mention_rate=round(obs_run.domain_mention_rate, 3),
            obs_citation_rate=round(obs_run.citation_rate, 3),
            prediction_accuracy=round(comparison.prediction_accuracy, 3),
            correct_predictions=comparison.correct_predictions,
            optimistic_predictions=comparison.optimistic_predictions,
            pessimistic_predictions=comparison.pessimistic_predictions,
            unknown_predictions=comparison.unknown_predictions,
            avg_citation_depth=round(obs_run.avg_citation_depth, 2),
            depth_distribution=depth_dist,
            position_distribution=position_dist,
            framing_distribution=framing_dist,
            avg_competitors=round(total_competitors / depth_count, 1) if depth_count else 0,
            pct_citable=round(pct_citable, 1),
            pct_strongly_sourced=round(pct_strongly, 1),
            depth_confidence=depth_conf,
            obs_cost_usd=round(obs_run.total_usage.estimated_cost_usd, 4),
            obs_latency_ms=round(obs_run.total_latency_ms, 0),
            depth_cost_usd=0.001,  # Approximate batch classifier cost
            duration_seconds=round(duration, 1),
            insights=tuple(comparison.insights),
            recommendations=tuple(comparison.recommendations),
        )

    except Exception as e:
        duration = (datetime.now(UTC) - start_time).total_seconds()
        logger.error("validation_failed", domain=domain, error=str(e))
        import traceback

        traceback.print_exc()

        return ValidationResult(
            domain=domain,
            findable_score=0,
            level_label="Error",
            sim_questions_total=0,
            sim_questions_answerable=0,
            sim_coverage_pct=0,
            obs_questions_completed=0,
            obs_company_mention_rate=0,
            obs_domain_mention_rate=0,
            obs_citation_rate=0,
            prediction_accuracy=0,
            correct_predictions=0,
            optimistic_predictions=0,
            pessimistic_predictions=0,
            unknown_predictions=0,
            avg_citation_depth=0,
            depth_distribution={},
            position_distribution={},
            framing_distribution={},
            avg_competitors=0,
            pct_citable=0,
            pct_strongly_sourced=0,
            depth_confidence="low",
            obs_cost_usd=0,
            obs_latency_ms=0,
            depth_cost_usd=0,
            duration_seconds=round(duration, 1),
            error=str(e),
        )


def print_validation_report(results: list[ValidationResult]) -> None:
    """Print comprehensive validation report."""
    print("\n\n" + "=" * 140)
    print("FINDABLE SCORE VALIDATION STUDY")
    print(f"Date: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 140)

    # Per-site results table
    print(
        f"\n{'Domain':<25} {'Score':>6} {'Level':<20} "
        f"{'Accuracy':>9} {'Depth':>6} "
        f"{'MentionR':>9} {'CiteR':>6} {'Framing':<15} {'Cost':>7}"
    )
    print("-" * 140)

    valid_results = [r for r in results if r.error is None]
    errored = [r for r in results if r.error is not None]

    for r in sorted(valid_results, key=lambda x: x.avg_citation_depth, reverse=True):
        # Find dominant framing
        dominant_framing = (
            max(r.framing_distribution, key=r.framing_distribution.get)
            if r.framing_distribution
            else "-"
        )
        print(
            f"{r.domain:<25} {r.findable_score:>5.1f} {r.level_label:<20} "
            f"{r.prediction_accuracy:>8.0%} {r.avg_citation_depth:>5.1f} "
            f"{r.obs_company_mention_rate:>8.0%} {r.obs_citation_rate:>5.0%} "
            f"{dominant_framing:<15} "
            f"${r.obs_cost_usd:>5.3f}"
        )

    for r in errored:
        print(f"{r.domain:<25} {'ERROR':>6} {r.error or '':<20}")

    print("-" * 140)

    if not valid_results:
        print("\nNo valid results to analyze.")
        return

    # ===========================================================
    # AGGREGATE METRICS
    # ===========================================================
    total_questions = sum(r.sim_questions_total for r in valid_results)
    total_correct = sum(r.correct_predictions for r in valid_results)
    total_optimistic = sum(r.optimistic_predictions for r in valid_results)
    total_pessimistic = sum(r.pessimistic_predictions for r in valid_results)
    total_unknown = sum(r.unknown_predictions for r in valid_results)
    total_cost = sum(r.obs_cost_usd for r in valid_results)

    aggregate_accuracy = total_correct / total_questions if total_questions > 0 else 0

    avg_accuracy = sum(r.prediction_accuracy for r in valid_results) / len(valid_results)
    avg_score = sum(r.findable_score for r in valid_results) / len(valid_results)
    avg_mention = sum(r.obs_company_mention_rate for r in valid_results) / len(valid_results)
    avg_citation = sum(r.obs_citation_rate for r in valid_results) / len(valid_results)

    print("\n" + "=" * 80)
    print("AGGREGATE VALIDATION METRICS")
    print("=" * 80)

    print(f"\n  Sites validated:           {len(valid_results)}")
    print(f"  Total questions:           {total_questions}")
    print(f"  Total API cost:            ${total_cost:.4f}")

    print("\n  PREDICTION ACCURACY")
    print("  -------------------------------------------")
    print(
        f"  Aggregate accuracy:        {aggregate_accuracy:.1%}  ({total_correct}/{total_questions})"
    )
    print(f"  Per-site avg accuracy:     {avg_accuracy:.1%}")
    print(f"  Correct predictions:       {total_correct}")
    print(f"  Optimistic (sim too high): {total_optimistic}")
    print(f"  Pessimistic (sim too low): {total_pessimistic}")
    print(f"  Unknown (model refused):   {total_unknown}")

    # Bias analysis
    if total_optimistic + total_pessimistic > 0:
        bias_ratio = total_optimistic / (total_optimistic + total_pessimistic)
        if bias_ratio > 0.65:
            bias_direction = "OPTIMISTIC"
            bias_desc = "Simulation over-predicts AI citability"
        elif bias_ratio < 0.35:
            bias_direction = "PESSIMISTIC"
            bias_desc = "Simulation under-predicts AI citability"
        else:
            bias_direction = "BALANCED"
            bias_desc = "Simulation errors are roughly symmetric"

        print("\n  BIAS ANALYSIS")
        print("  -------------------------------------------")
        print(f"  Direction:                 {bias_direction}")
        print(f"  Optimistic/Total errors:   {bias_ratio:.0%}")
        print(f"  Interpretation:            {bias_desc}")

    print("\n  OBSERVATION RATES (Ground Truth)")
    print("  -------------------------------------------")
    print(f"  Avg company mention rate:  {avg_mention:.0%}")
    print(f"  Avg citation rate:         {avg_citation:.0%}")

    # ===========================================================
    # CITATION DEPTH ANALYSIS
    # ===========================================================
    avg_depth = sum(r.avg_citation_depth for r in valid_results) / len(valid_results)
    total_depth_cost = sum(r.depth_cost_usd for r in valid_results)

    # Aggregate depth distribution
    agg_depth_dist: dict[int, int] = {}
    agg_position_dist: dict[str, int] = {}
    agg_framing_dist: dict[str, int] = {}
    for r in valid_results:
        for k, v in r.depth_distribution.items():
            agg_depth_dist[k] = agg_depth_dist.get(k, 0) + v
        for k, v in r.position_distribution.items():
            agg_position_dist[k] = agg_position_dist.get(k, 0) + v
        for k, v in r.framing_distribution.items():
            agg_framing_dist[k] = agg_framing_dist.get(k, 0) + v

    depth_labels = {
        0: "NOT_MENTIONED",
        1: "PASSING",
        2: "DESCRIBED",
        3: "RECOMMENDED",
        4: "FEATURED",
        5: "AUTHORITY",
    }

    print("\n  CITATION DEPTH (0-5 Scale)")
    print("  -------------------------------------------")
    print(f"  Average citation depth:    {avg_depth:.2f}/5.0")
    print(f"  Classifier cost:           ${total_depth_cost:.4f}")
    print("  Depth distribution:")
    for level in range(6):
        count = agg_depth_dist.get(level, 0)
        label = depth_labels[level]
        bar = "#" * count
        print(f"    {level} {label:<15} {count:>3}  {bar}")

    # Citable Index
    avg_citable = sum(r.pct_citable for r in valid_results) / len(valid_results)
    avg_strongly = sum(r.pct_strongly_sourced for r in valid_results) / len(valid_results)
    conf_counts: dict[str, int] = {}
    for r in valid_results:
        conf_counts[r.depth_confidence] = conf_counts.get(r.depth_confidence, 0) + 1

    print("\n  CITABLE INDEX")
    print("  -------------------------------------------")
    print(f"  Avg % citable (depth >= 3):        {avg_citable:.1f}%")
    print(f"  Avg % strongly sourced (depth >= 4): {avg_strongly:.1f}%")
    print(f"  Confidence distribution:  {conf_counts}")
    print("\n  Per-site depth breakdown:")
    for r in valid_results:
        dist_str = " ".join(f"D{k}={v}" for k, v in sorted(r.depth_distribution.items()))
        print(
            f"    {r.domain:<28} depth={r.avg_citation_depth:.1f}  "
            f"citable={r.pct_citable:.0f}%  "
            f"strong={r.pct_strongly_sourced:.0f}%  "
            f"conf={r.depth_confidence}  "
            f"[{dist_str}]"
        )

    print("\n  Mention position:")
    for pos, count in sorted(agg_position_dist.items(), key=lambda x: -x[1]):
        print(f"    {pos:<20} {count:>3}")

    print("\n  Source framing:")
    for framing, count in sorted(agg_framing_dist.items(), key=lambda x: -x[1]):
        print(f"    {framing:<20} {count:>3}")

    avg_comp = sum(r.avg_competitors for r in valid_results) / len(valid_results)
    print(f"\n  Avg competitors per answer: {avg_comp:.1f}")

    # Score vs citation depth correlation (the key metric!)
    print("\n  SCORE vs CITATION DEPTH CORRELATION")
    print("  -------------------------------------------")
    print(f"  Avg Findable Score:        {avg_score:.1f}/100")
    print(f"  Avg Citation Depth:        {avg_depth:.2f}/5.0")

    if len(valid_results) >= 4:
        sorted_by_score = sorted(valid_results, key=lambda r: r.findable_score)
        bottom_half = sorted_by_score[: len(sorted_by_score) // 2]
        top_half = sorted_by_score[len(sorted_by_score) // 2 :]

        bottom_depth = sum(r.avg_citation_depth for r in bottom_half) / len(bottom_half)
        top_depth = sum(r.avg_citation_depth for r in top_half) / len(top_half)

        bottom_mention = sum(r.obs_company_mention_rate for r in bottom_half) / len(bottom_half)
        top_mention = sum(r.obs_company_mention_rate for r in top_half) / len(top_half)

        print(
            f"\n  Bottom-half scores (avg {sum(r.findable_score for r in bottom_half)/len(bottom_half):.1f}):"
        )
        print(f"    Mention rate:  {bottom_mention:.0%}")
        print(f"    Citation depth: {bottom_depth:.2f}/5.0")

        print(
            f"  Top-half scores (avg {sum(r.findable_score for r in top_half)/len(top_half):.1f}):"
        )
        print(f"    Mention rate:  {top_mention:.0%}")
        print(f"    Citation depth: {top_depth:.2f}/5.0")

        depth_delta = top_depth - bottom_depth
        if depth_delta > 0.3:
            print(f"\n  Correlation:  POSITIVE (+{depth_delta:.2f} depth for higher scores)")
            print("  >> Higher Findable Scores = deeper AI citation")
        elif depth_delta < -0.3:
            print(f"\n  Correlation:  NEGATIVE ({depth_delta:.2f} depth for higher scores)")
            print("  >> Score may not predict citation quality")
        else:
            print(f"\n  Correlation:  WEAK ({depth_delta:+.2f} depth delta)")
            print("  >> Score-to-depth relationship is inconclusive at this sample size")

    # ===========================================================
    # VERDICT
    # ===========================================================
    print("\n" + "=" * 80)
    print("VERDICT")
    print("=" * 80)

    if aggregate_accuracy >= 0.70:
        print(f"\n  PASS: Prediction accuracy {aggregate_accuracy:.0%} >= 70%")
        print("  The Findable Score is a defensible predictor of AI citability.")
    elif aggregate_accuracy >= 0.60:
        print(f"\n  MARGINAL: Prediction accuracy {aggregate_accuracy:.0%} (60-70%)")
        print("  The score has some predictive value but pillar weights may need calibration.")
    else:
        print(f"\n  FAIL: Prediction accuracy {aggregate_accuracy:.0%} < 60%")
        print("  The Findable Score does NOT reliably predict AI citability.")
        print("  Pillar weights need recalibration before launch.")

    # Per-site insights
    sites_with_insights = [r for r in valid_results if r.insights]
    if sites_with_insights:
        print("\n  KEY INSIGHTS")
        print("  -------------------------------------------")
        for r in sites_with_insights:
            for insight in r.insights:
                print(f"  [{r.domain}] {insight}")

    sites_with_recs = [r for r in valid_results if r.recommendations]
    if sites_with_recs:
        print("\n  RECOMMENDATIONS")
        print("  -------------------------------------------")
        # Deduplicate recommendations across sites
        seen_recs: set[str] = set()
        for r in sites_with_recs:
            for rec in r.recommendations:
                if rec not in seen_recs:
                    seen_recs.add(rec)
                    print(f"  - {rec}")

    print("\n" + "=" * 140)


def save_validation_results(results: list[ValidationResult], output_path: Path) -> None:
    """Save detailed results to JSON."""
    valid_results = [r for r in results if r.error is None]
    total_questions = sum(r.sim_questions_total for r in valid_results)
    total_correct = sum(r.correct_predictions for r in valid_results)

    data = {
        "study_type": "validation_study",
        "timestamp": datetime.now(UTC).isoformat(),
        "summary": {
            "sites_validated": len(valid_results),
            "sites_errored": len(results) - len(valid_results),
            "total_questions": total_questions,
            "aggregate_accuracy": (
                round(total_correct / total_questions, 3) if total_questions > 0 else 0
            ),
            "avg_per_site_accuracy": (
                round(sum(r.prediction_accuracy for r in valid_results) / len(valid_results), 3)
                if valid_results
                else 0
            ),
            "total_cost_usd": round(sum(r.obs_cost_usd for r in valid_results), 4),
            "total_correct": total_correct,
            "total_optimistic": sum(r.optimistic_predictions for r in valid_results),
            "total_pessimistic": sum(r.pessimistic_predictions for r in valid_results),
            "total_unknown": sum(r.unknown_predictions for r in valid_results),
        },
        "results": [
            {
                "domain": r.domain,
                "findable_score": r.findable_score,
                "level_label": r.level_label,
                "sim_questions_total": r.sim_questions_total,
                "sim_questions_answerable": r.sim_questions_answerable,
                "sim_coverage_pct": r.sim_coverage_pct,
                "obs_questions_completed": r.obs_questions_completed,
                "obs_company_mention_rate": r.obs_company_mention_rate,
                "obs_domain_mention_rate": r.obs_domain_mention_rate,
                "obs_citation_rate": r.obs_citation_rate,
                "prediction_accuracy": r.prediction_accuracy,
                "correct_predictions": r.correct_predictions,
                "optimistic_predictions": r.optimistic_predictions,
                "pessimistic_predictions": r.pessimistic_predictions,
                "unknown_predictions": r.unknown_predictions,
                "avg_citation_depth": r.avg_citation_depth,
                "depth_distribution": {str(k): v for k, v in r.depth_distribution.items()},
                "pct_citable": r.pct_citable,
                "pct_strongly_sourced": r.pct_strongly_sourced,
                "depth_confidence": r.depth_confidence,
                "position_distribution": r.position_distribution,
                "framing_distribution": r.framing_distribution,
                "avg_competitors": r.avg_competitors,
                "obs_cost_usd": r.obs_cost_usd,
                "obs_latency_ms": r.obs_latency_ms,
                "depth_cost_usd": r.depth_cost_usd,
                "duration_seconds": r.duration_seconds,
                "error": r.error,
                "insights": list(r.insights),
                "recommendations": list(r.recommendations),
            }
            for r in results
        ],
    }

    output_path.write_text(json.dumps(data, indent=2))
    print(f"\nDetailed results saved to: {output_path}")


async def main() -> None:
    """Run validation study."""
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="Findable Score Validation Study")
    parser.add_argument("--sites", type=str, help="Comma-separated site URLs")
    parser.add_argument("--max-pages", type=int, default=30, help="Max pages to crawl per site")
    parser.add_argument(
        "--model", type=str, default="openai/gpt-4o-mini", help="AI model for observation"
    )
    parser.add_argument(
        "--output", type=str, default="validation_study_results.json", help="Output JSON file"
    )

    args = parser.parse_args()

    sites = [s.strip() for s in args.sites.split(",")] if args.sites else DEFAULT_VALIDATION_SITES

    # Load API keys from env
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    if not openrouter_key and not openai_key:
        print("ERROR: No API keys found. Set OPENROUTER_API_KEY or OPENAI_API_KEY in .env")
        sys.exit(1)

    provider = "OpenRouter" if openrouter_key else "OpenAI"
    print("\n" + "=" * 80)
    print("FINDABLE SCORE VALIDATION STUDY")
    print("=" * 80)
    print(f"Sites:    {len(sites)}")
    print(f"Model:    {args.model}")
    print(f"Provider: {provider}")
    print(f"Max pages: {args.max_pages}")
    print(f"Est. cost: ~${len(sites) * 0.01:.2f} (at gpt-4o-mini rates)")
    print("=" * 80 + "\n")

    results: list[ValidationResult] = []

    for i, url in enumerate(sites, 1):
        print(f"\n{'=' * 80}")
        print(f"[{i}/{len(sites)}] VALIDATING: {url}")
        print("=" * 80)

        result = await validate_site(
            url=url,
            max_pages=args.max_pages,
            model=args.model,
            openrouter_key=openrouter_key,
            openai_key=openai_key,
        )
        results.append(result)

        # Brief summary
        if result.error:
            print(f"  >> ERROR: {result.error[:80]}")
        else:
            print(
                f"  >> Score: {result.findable_score} | "
                f"Accuracy: {result.prediction_accuracy:.0%} | "
                f"Depth: {result.avg_citation_depth:.1f}/5 | "
                f"Citable: {result.pct_citable:.0f}% | "
                f"Conf: {result.depth_confidence} | "
                f"Cost: ${result.obs_cost_usd:.3f}"
            )

        # Pause between sites
        if i < len(sites):
            await asyncio.sleep(3)

    # Print full report
    print_validation_report(results)

    # Save results
    output_path = Path(args.output)
    save_validation_results(results, output_path)


if __name__ == "__main__":
    asyncio.run(main())
