"""Quick end-to-end test for auditing real websites (fewer pages, faster).

Usage:
    python scripts/e2e_quick_test.py
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime
from typing import NamedTuple

# Add project root to path
sys.path.insert(0, ".")

import structlog  # noqa: E402

# Configure logging - minimal output
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
    grade: str
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


async def audit_site(url: str, max_pages: int = 15) -> SiteResult:
    """Run full audit pipeline on a single site."""
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
    print(f"\n{'='*60}")
    print(f"AUDITING: {domain}")
    print(f"{'='*60}")

    try:
        # Step 1: Technical Check
        print("  [1/10] Technical check...", end=" ", flush=True)
        technical_score = None
        try:
            technical_score = await run_technical_checks_parallel(url=url, html=None, timeout=10.0)
            print(f"Score: {technical_score.total_score:.0f}")
        except Exception as e:
            print(f"Failed: {e}")

        # Step 2: Crawl (minimal pages)
        print(f"  [2/10] Crawling (max {max_pages} pages)...", end=" ", flush=True)
        config = CrawlConfig(
            max_pages=max_pages,
            max_depth=2,
            timeout=20.0,
            user_agent="FindableBot/1.0 (Testing)",
        )
        crawler = Crawler(config)
        crawl_result = await crawler.crawl(url)
        print(f"Got {len(crawl_result.pages)} pages")

        if not crawl_result.pages:
            raise ValueError("No pages crawled")

        # Step 3: Extract
        print("  [3/10] Extracting content...", end=" ", flush=True)
        extractor = ContentExtractor()
        extraction_result = extractor.extract_crawl(crawl_result)
        print(f"{extraction_result.total_words} words")

        # Update technical with JS detection
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

        # Step 4: Structure (skip slow link analysis - just headings/format)
        print("  [4/10] Structure analysis...", end=" ", flush=True)
        structure_score = None
        try:
            page_scores = []
            for i, page in enumerate(crawl_result.pages[:5]):  # Only first 5 pages
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
                print(f"Score: {structure_score.total_score:.0f}")
        except Exception as e:
            print(f"Failed: {e}")

        # Step 5: Schema
        print("  [5/10] Schema analysis...", end=" ", flush=True)
        schema_score = None
        try:
            schema_page_scores = []
            for page in crawl_result.pages[:10]:  # First 10 pages
                if page.html:
                    page_schema = run_schema_checks_sync(html=page.html, url=page.url)
                    schema_page_scores.append(page_schema)
            if schema_page_scores:
                schema_score = aggregate_schema_scores(schema_page_scores)
                print(f"Score: {schema_score.total_score:.0f}")
        except Exception as e:
            print(f"Failed: {e}")

        # Step 6: Authority
        print("  [6/10] Authority analysis...", end=" ", flush=True)
        authority_score = None
        try:
            authority_page_scores = []
            for i, page in enumerate(crawl_result.pages[:10]):
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
                print(f"Score: {authority_score.total_score:.0f}")
        except Exception as e:
            print(f"Failed: {e}")

        # Step 7: Chunk
        print("  [7/10] Chunking...", end=" ", flush=True)
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
        print(f"{total_chunks} chunks")

        # Step 8: Embed
        print("  [8/10] Embedding...", end=" ", flush=True)
        embedder = Embedder()
        embedded_pages = embedder.embed_pages(chunked_pages)
        total_embeddings = sum(len(ep.embeddings) for ep in embedded_pages)
        print(f"{total_embeddings} embeddings")

        # Step 9: Build retriever and simulate
        print("  [9/10] Simulating retrieval...", end=" ", flush=True)
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

        # Generate questions and simulate
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

        site_id = uuid.uuid4()
        run_id = uuid.uuid4()

        simulation_runner = SimulationRunner(retriever=retriever)
        simulation_result = simulation_runner.run(
            site_id=site_id,
            run_id=run_id,
            company_name=site_context.company_name,
            questions=questions,
        )
        print(f"{simulation_result.questions_answered}/{len(questions)} questions answered")

        # Step 10: Calculate scores
        print("  [10/10] Calculating final score...", end=" ", flush=True)
        score_calculator = ScoreCalculator()
        v1_breakdown = score_calculator.calculate(simulation_result)

        v2_score = calculate_findable_score_v2(
            technical_score=technical_score,
            structure_score=structure_score,
            schema_score=schema_score,
            authority_score=authority_score,
            simulation_breakdown=v1_breakdown,
        )

        end_time = datetime.now(UTC)
        duration = (end_time - start_time).total_seconds()

        print("DONE!")
        print(f"\n{'='*60}")
        print(f"RESULT: {domain}")
        print(f"{'='*60}")
        print(v2_score.show_the_math())

        return SiteResult(
            domain=domain,
            total_score=v2_score.total_score,
            grade=v2_score.grade.value,
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
        print(f"\n  ERROR: {e}")

        return SiteResult(
            domain=domain,
            total_score=0,
            grade="F",
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
    """Run quick audits on selected sites."""

    sites = [
        "https://www.notion.so",
        "https://airtable.com",
        "https://www.figma.com",
    ]

    print("\n" + "=" * 70)
    print("FINDABLE SCORE v2 - QUICK END-TO-END TEST")
    print("=" * 70)
    print(f"Testing {len(sites)} sites with max 15 pages each")
    print("=" * 70)

    results: list[SiteResult] = []

    for url in sites:
        result = await audit_site(url, max_pages=15)
        results.append(result)
        await asyncio.sleep(1)

    # Print summary table
    print("\n\n" + "=" * 110)
    print("FINAL RESULTS SUMMARY")
    print("=" * 110)
    print(
        f"{'Domain':<25} {'Score':>7} {'Grade':>6} {'Tech':>6} {'Struc':>6} {'Schema':>6} {'Auth':>6} {'Retr':>6} {'Cov':>6} {'Time':>7}"
    )
    print("-" * 110)

    for r in sorted(results, key=lambda x: x.total_score, reverse=True):
        if r.error:
            print(f"{r.domain:<25} {'ERR':<7} {'-':<6}")
        else:
            print(
                f"{r.domain:<25} {r.total_score:>6.1f} {r.grade:>6} "
                f"{r.technical_score:>6.0f} {r.structure_score:>6.0f} {r.schema_score:>6.0f} "
                f"{r.authority_score:>6.0f} {r.retrieval_score:>6.0f} {r.coverage_score:>6.0f} "
                f"{r.duration_seconds:>6.0f}s"
            )

    print("=" * 110)


if __name__ == "__main__":
    asyncio.run(main())
