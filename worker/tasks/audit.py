"""Audit run background task."""

import uuid
from datetime import UTC, datetime

import structlog
from rq import get_current_job
from sqlalchemy import select

from api.config import get_settings
from api.database import async_session_maker
from api.models import Report, Run, Site
from worker.chunking.chunker import SemanticChunker
from worker.crawler.crawler import crawl_site
from worker.embeddings.embedder import Embedder
from worker.extraction.extractor import ContentExtractor
from worker.fixes.generator import FixGenerator
from worker.questions.generator import QuestionGenerator, SiteContext
from worker.reports.assembler import assemble_report
from worker.retrieval.retriever import HybridRetriever
from worker.scoring.calculator import ScoreCalculator
from worker.simulation.runner import SimulationRunner

logger = structlog.get_logger(__name__)


async def update_run_status(
    run_id: uuid.UUID,
    status: str,
    progress: dict | None = None,
    error_message: str | None = None,
) -> None:
    """Update run status in database."""
    async with async_session_maker() as db:
        result = await db.execute(select(Run).where(Run.id == run_id))
        run = result.scalar_one_or_none()

        if not run:
            logger.error("run_not_found", run_id=str(run_id))
            return

        run.status = status

        if progress:
            current_progress = run.progress or {}
            current_progress.update(progress)
            current_progress["current_step"] = status
            run.progress = current_progress

        if status == "crawling" and not run.started_at:
            run.started_at = datetime.now(UTC)

        if status in ("complete", "failed"):
            run.completed_at = datetime.now(UTC)

        if error_message:
            run.error_message = error_message

        await db.commit()
        logger.info("run_status_updated", run_id=str(run_id), status=status)


def run_audit_sync(run_id: str, site_id: str) -> dict:
    """
    Synchronous wrapper for audit task.

    This is the entry point for RQ which requires sync functions.
    It calls the async implementation.
    """
    import asyncio

    return asyncio.run(run_audit(uuid.UUID(run_id), uuid.UUID(site_id)))


async def run_audit(run_id: uuid.UUID, site_id: uuid.UUID) -> dict:
    """
    Execute an audit run for a site.

    This is the main audit pipeline that:
    1. Crawls the site
    2. Extracts content
    3. Chunks and embeds
    4. Generates questions
    5. Runs simulations
    6. Calculates scores
    7. Generates fixes
    8. Assembles report

    Args:
        run_id: The Run record ID
        site_id: The Site record ID

    Returns:
        Dict with run results
    """
    job = get_current_job()
    settings = get_settings()
    run_started_at = datetime.now(UTC)

    logger.info(
        "audit_started",
        run_id=str(run_id),
        site_id=str(site_id),
        job_id=job.id if job else None,
    )

    try:
        # Load site from database
        async with async_session_maker() as db:
            result = await db.execute(select(Site).where(Site.id == site_id))
            site = result.scalar_one_or_none()

            if not site:
                raise ValueError(f"Site {site_id} not found")

            domain = site.domain
            company_name = site.name or domain

        # Update job metadata
        if job:
            job.meta["domain"] = domain
            job.meta["run_id"] = str(run_id)
            job.save_meta()

        # =========================================================
        # Step 1: Crawling
        # =========================================================
        await update_run_status(
            run_id,
            "crawling",
            {"pages_crawled": 0, "pages_total": settings.crawler_max_pages},
        )

        logger.info("crawl_starting", domain=domain, max_pages=settings.crawler_max_pages)

        # Progress callback for crawl updates
        async def crawl_progress(pages_crawled: int, total_discovered: int) -> None:
            await update_run_status(
                run_id,
                "crawling",
                {"pages_crawled": pages_crawled, "urls_discovered": total_discovered},
            )

        # Perform the crawl
        start_url = f"https://{domain}"
        crawl_result = await crawl_site(
            url=start_url,
            max_pages=settings.crawler_max_pages,
            max_depth=settings.crawler_max_depth,
        )

        logger.info(
            "crawl_completed",
            pages_crawled=len(crawl_result.pages),
            urls_discovered=crawl_result.urls_discovered,
            duration_seconds=crawl_result.duration_seconds,
        )

        await update_run_status(
            run_id,
            "crawling",
            {
                "pages_crawled": len(crawl_result.pages),
                "urls_discovered": crawl_result.urls_discovered,
            },
        )

        # =========================================================
        # Step 2: Extracting
        # =========================================================
        await update_run_status(
            run_id,
            "extracting",
            {"pages_to_extract": len(crawl_result.pages)},
        )

        logger.info("extraction_starting", pages=len(crawl_result.pages))

        extractor = ContentExtractor()
        extraction_result = extractor.extract_crawl(crawl_result)

        logger.info(
            "extraction_completed",
            pages_extracted=extraction_result.total_pages,
            total_words=extraction_result.total_words,
            errors=extraction_result.extraction_errors,
        )

        await update_run_status(
            run_id,
            "extracting",
            {
                "pages_extracted": extraction_result.total_pages,
                "total_words": extraction_result.total_words,
            },
        )

        # =========================================================
        # Step 3: Chunking
        # =========================================================
        await update_run_status(
            run_id,
            "chunking",
            {"chunks_created": 0},
        )

        logger.info("chunking_starting", pages=extraction_result.total_pages)

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

        logger.info("chunking_completed", total_chunks=total_chunks)

        await update_run_status(
            run_id,
            "chunking",
            {"chunks_created": total_chunks},
        )

        # =========================================================
        # Step 4: Embedding
        # =========================================================
        await update_run_status(
            run_id,
            "embedding",
            {"chunks_to_embed": total_chunks},
        )

        logger.info("embedding_starting", chunks=total_chunks)

        embedder = Embedder()
        embedded_pages = embedder.embed_pages(chunked_pages)

        total_embeddings = sum(len(ep.embeddings) for ep in embedded_pages)
        logger.info("embedding_completed", total_embeddings=total_embeddings)

        await update_run_status(
            run_id,
            "embedding",
            {"chunks_embedded": total_embeddings},
        )

        # =========================================================
        # Step 5: Build Retriever Index
        # =========================================================
        logger.info("indexing_starting", pages=len(embedded_pages))

        retriever = HybridRetriever()

        for ep in embedded_pages:
            for emb_result in ep.embeddings:
                retriever.add_document(
                    doc_id=emb_result.content_hash,
                    content=chunked_pages[embedded_pages.index(ep)]
                    .chunks[emb_result.chunk_index]
                    .content,
                    embedding=emb_result.embedding,
                    source_url=emb_result.source_url,
                    page_title=emb_result.page_title,
                    heading_context=emb_result.heading_context,
                )

        logger.info("indexing_completed", documents=len(retriever._documents))

        # =========================================================
        # Step 6: Generate Questions
        # =========================================================
        await update_run_status(
            run_id,
            "generating_questions",
            {},
        )

        logger.info("question_generation_starting", company=company_name)

        # Collect schema types and headings from extraction
        schema_types = list(set(extraction_result.schema_types_found))
        headings: dict[str, list[str]] = {"h1": [], "h2": [], "h3": []}
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

        logger.info("question_generation_completed", questions=len(questions))

        await update_run_status(
            run_id,
            "generating_questions",
            {"questions_generated": len(questions)},
        )

        # =========================================================
        # Step 7: Simulating
        # =========================================================
        await update_run_status(
            run_id,
            "simulating",
            {"questions_processed": 0, "questions_total": len(questions)},
        )

        logger.info("simulation_starting", questions=len(questions))

        simulation_runner = SimulationRunner(retriever=retriever)
        simulation_result = simulation_runner.run(
            site_id=site_id,
            run_id=run_id,
            company_name=company_name,
            questions=questions,
        )

        logger.info(
            "simulation_completed",
            overall_score=simulation_result.overall_score,
            questions_answered=simulation_result.questions_answered,
            questions_partial=simulation_result.questions_partial,
            questions_unanswered=simulation_result.questions_unanswered,
        )

        await update_run_status(
            run_id,
            "simulating",
            {
                "questions_processed": len(questions),
                "questions_total": len(questions),
            },
        )

        # =========================================================
        # Step 8: Scoring
        # =========================================================
        await update_run_status(
            run_id,
            "scoring",
            {},
        )

        logger.info("scoring_starting")

        score_calculator = ScoreCalculator()
        score_breakdown = score_calculator.calculate(simulation_result)

        logger.info(
            "scoring_completed",
            total_score=score_breakdown.total_score,
            grade=score_breakdown.grade,
        )

        # =========================================================
        # Step 9: Generate Fixes
        # =========================================================
        await update_run_status(
            run_id,
            "generating_fixes",
            {},
        )

        logger.info("fix_generation_starting")

        # Build site content map for fix generation
        site_content = {page.url: page.main_content for page in extraction_result.pages}

        fix_generator = FixGenerator()
        fix_plan = fix_generator.generate(
            simulation=simulation_result,
            site_content=site_content,
        )

        logger.info(
            "fix_generation_completed",
            total_fixes=fix_plan.total_fixes,
            critical_fixes=fix_plan.critical_fixes,
        )

        # =========================================================
        # Step 10: Assembling Report
        # =========================================================
        await update_run_status(
            run_id,
            "assembling",
            {},
        )

        run_completed_at = datetime.now(UTC)

        logger.info("report_assembly_starting")

        full_report = assemble_report(
            site_id=site_id,
            run_id=run_id,
            company_name=company_name,
            domain=domain,
            simulation=simulation_result,
            score_breakdown=score_breakdown,
            fix_plan=fix_plan,
        )

        logger.info("report_assembly_completed", report_id=str(full_report.metadata.report_id))

        # =========================================================
        # Step 11: Save Report to Database
        # =========================================================
        async with async_session_maker() as db:
            report = Report(
                report_version=full_report.metadata.version,
                data=full_report.to_dict(),
                score_conservative=int(score_breakdown.total_score * 0.85),
                score_typical=int(score_breakdown.total_score),
                score_generous=int(min(100, score_breakdown.total_score * 1.15)),
            )
            db.add(report)
            await db.flush()

            # Link report to run
            result = await db.execute(select(Run).where(Run.id == run_id))
            run = result.scalar_one()
            run.report_id = report.id

            await db.commit()

            report_id = report.id

        # Mark complete
        await update_run_status(run_id, "complete")

        logger.info(
            "audit_completed",
            run_id=str(run_id),
            site_id=str(site_id),
            report_id=str(report_id),
            total_score=score_breakdown.total_score,
            grade=score_breakdown.grade,
            duration_seconds=(run_completed_at - run_started_at).total_seconds(),
        )

        return {
            "status": "complete",
            "run_id": str(run_id),
            "report_id": str(report_id),
            "score": score_breakdown.total_score,
            "grade": score_breakdown.grade,
        }

    except Exception as e:
        logger.exception(
            "audit_failed",
            run_id=str(run_id),
            site_id=str(site_id),
            error=str(e),
        )

        await update_run_status(
            run_id,
            "failed",
            error_message=str(e),
        )

        raise
