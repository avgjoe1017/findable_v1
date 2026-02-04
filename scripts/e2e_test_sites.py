"""End-to-end test script for auditing real websites.

This script runs the full Findable Score v2 pipeline on real sites
without requiring database setup.

Usage:
    python scripts/e2e_test_sites.py
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime
from typing import NamedTuple

# Add project root to path
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


class SiteResult(NamedTuple):
    """Result for a single site audit."""

    domain: str
    total_score: float
    level: str  # Findability level
    level_label: str  # Human-readable level
    technical_score: float
    structure_score: float
    schema_score: float
    authority_score: float
    retrieval_score: float
    coverage_score: float
    pages_crawled: int
    total_chunks: int
    duration_seconds: float
    error: str | None = None


async def audit_site(url: str, max_pages: int = 50) -> SiteResult:
    """
    Run full audit pipeline on a single site.

    Args:
        url: Site URL to audit
        max_pages: Maximum pages to crawl

    Returns:
        SiteResult with all scores
    """
    from urllib.parse import urlparse

    from worker.chunking.chunker import SemanticChunker
    from worker.crawler.crawler import CrawlConfig, Crawler
    from worker.embeddings.embedder import Embedder
    from worker.extraction.extractor import ContentExtractor
    from worker.questions.generator import QuestionGenerator, SiteContext
    from worker.retrieval.retriever import HybridRetriever
    from worker.scoring.calculator import ScoreCalculator
    from worker.scoring.calculator_v2 import calculate_findable_score_v2
    from worker.simulation.runner import SimulationRunner
    from worker.tasks.authority_check import aggregate_authority_scores, run_authority_checks_sync
    from worker.tasks.schema_check import aggregate_schema_scores, run_schema_checks_sync
    from worker.tasks.structure_check import aggregate_structure_scores, run_structure_checks_sync
    from worker.tasks.technical_check import run_technical_checks_parallel

    parsed = urlparse(url)
    domain = parsed.netloc
    if not domain:
        domain = url.replace("https://", "").replace("http://", "").split("/")[0]

    start_time = datetime.now(UTC)

    try:
        logger.info("audit_starting", domain=domain)

        # =========================================================
        # Step 1: Technical Check
        # =========================================================
        logger.info("step_1_technical_check", domain=domain)

        technical_score = None
        try:
            technical_score = await run_technical_checks_parallel(
                url=url,
                html=None,
                timeout=10.0,
            )
            logger.info("technical_check_done", score=technical_score.total_score)
        except Exception as e:
            logger.warning("technical_check_failed", error=str(e))

        # =========================================================
        # Step 2: Crawl
        # =========================================================
        logger.info("step_2_crawling", domain=domain, max_pages=max_pages)

        config = CrawlConfig(
            max_pages=max_pages,
            max_depth=2,
            timeout=30.0,
            user_agent="FindableBot/1.0 (Testing)",
        )
        crawler = Crawler(config)
        crawl_result = await crawler.crawl(url)

        logger.info(
            "crawl_done",
            pages=len(crawl_result.pages),
            discovered=crawl_result.urls_discovered,
        )

        if not crawl_result.pages:
            raise ValueError("No pages crawled")

        # =========================================================
        # Step 3: Extract Content
        # =========================================================
        logger.info("step_3_extracting", pages=len(crawl_result.pages))

        extractor = ContentExtractor()
        extraction_result = extractor.extract_crawl(crawl_result)

        logger.info(
            "extraction_done",
            pages=extraction_result.total_pages,
            words=extraction_result.total_words,
        )

        # Update technical score with JS detection from HTML
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
                except Exception as e:
                    logger.warning("js_detection_failed", error=str(e))

        # =========================================================
        # Step 4: Structure Analysis
        # =========================================================
        logger.info("step_4_structure_analysis", pages=len(crawl_result.pages))

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
                logger.info("structure_done", score=structure_score.total_score)
        except Exception as e:
            logger.warning("structure_analysis_failed", error=str(e))

        # =========================================================
        # Step 5: Schema Analysis
        # =========================================================
        logger.info("step_5_schema_analysis", pages=len(crawl_result.pages))

        schema_score = None
        try:
            schema_page_scores = []
            for page in crawl_result.pages:
                if page.html:
                    page_schema = run_schema_checks_sync(
                        html=page.html,
                        url=page.url,
                    )
                    schema_page_scores.append(page_schema)

            if schema_page_scores:
                schema_score = aggregate_schema_scores(schema_page_scores)
                logger.info("schema_done", score=schema_score.total_score)
        except Exception as e:
            logger.warning("schema_analysis_failed", error=str(e))

        # =========================================================
        # Step 6: Authority Analysis
        # =========================================================
        logger.info("step_6_authority_analysis", pages=len(crawl_result.pages))

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
                logger.info("authority_done", score=authority_score.total_score)
        except Exception as e:
            logger.warning("authority_analysis_failed", error=str(e))

        # =========================================================
        # Step 7: Chunking
        # =========================================================
        logger.info("step_7_chunking", pages=extraction_result.total_pages)

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

        logger.info("chunking_done", chunks=total_chunks)

        # =========================================================
        # Step 8: Embedding
        # =========================================================
        logger.info("step_8_embedding", chunks=total_chunks)

        embedder = Embedder()
        embedded_pages = embedder.embed_pages(chunked_pages)

        total_embeddings = sum(len(ep.embeddings) for ep in embedded_pages)
        logger.info("embedding_done", embeddings=total_embeddings)

        # =========================================================
        # Step 9: Build Retriever Index
        # =========================================================
        logger.info("step_9_indexing")

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

        logger.info("indexing_done", documents=len(retriever._documents))

        # =========================================================
        # Step 10: Generate Questions
        # =========================================================
        logger.info("step_10_questions")

        schema_types = list(set(extraction_result.schema_types_found))
        headings: dict[str, list[str]] = {"h1": [], "h2": [], "h3": []}
        for page in extraction_result.pages:
            page_headings = page.metadata.headings or {}
            for level in ["h1", "h2", "h3"]:
                if level in page_headings:
                    headings[level].extend(page_headings[level])

        site_context = SiteContext(
            company_name=domain.replace("www.", "").split(".")[0].title(),
            domain=domain,
            schema_types=schema_types,
            headings=headings,
        )

        question_generator = QuestionGenerator()
        questions = question_generator.generate(site_context)

        logger.info("questions_done", count=len(questions))

        # =========================================================
        # Step 11: Simulation
        # =========================================================
        logger.info("step_11_simulation", questions=len(questions))

        site_id = uuid.uuid4()
        run_id = uuid.uuid4()

        simulation_runner = SimulationRunner(retriever=retriever)
        simulation_result = simulation_runner.run(
            site_id=site_id,
            run_id=run_id,
            company_name=site_context.company_name,
            questions=questions,
        )

        logger.info(
            "simulation_done",
            overall=simulation_result.overall_score,
            answered=simulation_result.questions_answered,
        )

        # =========================================================
        # Step 12: Calculate v1 Score (for retrieval + coverage)
        # =========================================================
        logger.info("step_12_v1_scoring")

        score_calculator = ScoreCalculator()
        v1_breakdown = score_calculator.calculate(simulation_result)

        logger.info("v1_score_done", score=v1_breakdown.total_score)

        # =========================================================
        # Step 13: Calculate v2 Score (unified pillars)
        # =========================================================
        logger.info("step_13_v2_scoring")

        v2_score = calculate_findable_score_v2(
            technical_score=technical_score,
            structure_score=structure_score,
            schema_score=schema_score,
            authority_score=authority_score,
            simulation_breakdown=v1_breakdown,
        )

        end_time = datetime.now(UTC)
        duration = (end_time - start_time).total_seconds()

        logger.info(
            "audit_complete",
            domain=domain,
            total_score=v2_score.total_score,
            level=v2_score.level,
            level_label=v2_score.level_label,
            duration=round(duration, 1),
        )

        # Print the full breakdown
        print("\n" + v2_score.show_the_math())

        return SiteResult(
            domain=domain,
            total_score=v2_score.total_score,
            level=v2_score.level,
            level_label=v2_score.level_label,
            technical_score=technical_score.total_score if technical_score else 0,
            structure_score=structure_score.total_score if structure_score else 0,
            schema_score=schema_score.total_score if schema_score else 0,
            authority_score=authority_score.total_score if authority_score else 0,
            retrieval_score=v2_score.pillar_breakdown["retrieval"].raw_score,
            coverage_score=v2_score.pillar_breakdown["coverage"].raw_score,
            pages_crawled=len(crawl_result.pages),
            total_chunks=total_chunks,
            duration_seconds=duration,
        )

    except Exception as e:
        end_time = datetime.now(UTC)
        duration = (end_time - start_time).total_seconds()

        logger.error("audit_failed", domain=domain, error=str(e))

        return SiteResult(
            domain=domain,
            total_score=0,
            level="not_yet_findable",
            level_label="Not Yet Findable",
            technical_score=0,
            structure_score=0,
            schema_score=0,
            authority_score=0,
            retrieval_score=0,
            coverage_score=0,
            pages_crawled=0,
            total_chunks=0,
            duration_seconds=duration,
            error=str(e),
        )


async def main():
    """Run audits on all test sites."""

    sites = [
        "https://slack.com",
        "https://www.notion.so",
        "https://airtable.com",
        "https://asana.com",
        "https://monday.com",
        "https://www.zendesk.com",
        "https://www.intercom.com",
        "https://www.figma.com",
        "https://www.hubspot.com",
        "https://zoom.us",
    ]

    print("\n" + "=" * 80)
    print("FINDABLE SCORE v2 - END-TO-END TEST")
    print("=" * 80)
    print(f"Testing {len(sites)} sites with max 50 pages each")
    print("=" * 80 + "\n")

    results: list[SiteResult] = []

    for i, url in enumerate(sites, 1):
        print(f"\n{'=' * 80}")
        print(f"[{i}/{len(sites)}] AUDITING: {url}")
        print("=" * 80)

        result = await audit_site(url, max_pages=50)
        results.append(result)

        # Brief pause between sites to be polite
        if i < len(sites):
            await asyncio.sleep(2)

    # Print summary table
    print("\n\n" + "=" * 130)
    print("FINAL RESULTS SUMMARY")
    print("=" * 130)
    print(
        f"{'Domain':<25} {'Score':>8} {'Level':<20} {'Tech':>6} {'Struct':>7} {'Schema':>7} {'Auth':>6} {'Retr':>6} {'Cov':>6} {'Pages':>6} {'Time':>8}"
    )
    print("-" * 130)

    for r in sorted(results, key=lambda x: x.total_score, reverse=True):
        if r.error:
            print(
                f"{r.domain:<25} {'ERROR':<8} {'-':<20} {'-':<6} {'-':<7} {'-':<7} {'-':<6} {'-':<6} {'-':<6} {'-':<6} {r.duration_seconds:>7.1f}s"
            )
            print(f"  Error: {r.error[:80]}")
        else:
            print(
                f"{r.domain:<25} {r.total_score:>7.1f} {r.level_label:<20} "
                f"{r.technical_score:>6.0f} {r.structure_score:>7.0f} {r.schema_score:>7.0f} "
                f"{r.authority_score:>6.0f} {r.retrieval_score:>6.0f} {r.coverage_score:>6.0f} "
                f"{r.pages_crawled:>6} {r.duration_seconds:>7.1f}s"
            )

    print("-" * 130)

    # Calculate averages for successful runs
    successful = [r for r in results if not r.error]
    if successful:
        avg_score = sum(r.total_score for r in successful) / len(successful)
        avg_tech = sum(r.technical_score for r in successful) / len(successful)
        avg_struct = sum(r.structure_score for r in successful) / len(successful)
        avg_schema = sum(r.schema_score for r in successful) / len(successful)
        avg_auth = sum(r.authority_score for r in successful) / len(successful)
        avg_retr = sum(r.retrieval_score for r in successful) / len(successful)
        avg_cov = sum(r.coverage_score for r in successful) / len(successful)
        avg_time = sum(r.duration_seconds for r in successful) / len(successful)

        print(
            f"{'AVERAGE':<25} {avg_score:>7.1f} {'--':<20} "
            f"{avg_tech:>6.0f} {avg_struct:>7.0f} {avg_schema:>7.0f} "
            f"{avg_auth:>6.0f} {avg_retr:>6.0f} {avg_cov:>6.0f} "
            f"{'--':>6} {avg_time:>7.1f}s"
        )

    print("=" * 130)
    print(f"\nCompleted: {len(successful)}/{len(results)} sites")
    print(f"Failed: {len(results) - len(successful)} sites")


if __name__ == "__main__":
    asyncio.run(main())
