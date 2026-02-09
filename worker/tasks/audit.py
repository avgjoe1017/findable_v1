"""Audit run background task."""

import uuid
from datetime import UTC, datetime

import structlog
from rq import get_current_job
from sqlalchemy import select

from api.config import SCORE_BAND_CONSERVATIVE, SCORE_BAND_GENEROUS, get_settings
from api.database import async_session_maker
from api.models import Report, Run, Site
from worker.chunking.chunker import SemanticChunker
from worker.crawler.cache import get_cached_or_crawl
from worker.crawler.crawler import crawl_site
from worker.embeddings.embedder import Embedder
from worker.embeddings.storage import EmbeddingStore
from worker.extraction.entity_recognition import (
    EntityRecognitionAnalyzer,
    EntityRecognitionResult,
)
from worker.extraction.extractor import ContentExtractor
from worker.extraction.site_type import SiteType, SiteTypeResult, detect_site_type
from worker.fixes.generator import FixGenerator
from worker.observation.comparison import compare_simulation_observation
from worker.observation.runner import ObservationRunner, RunConfig
from worker.questions.generator import QuestionGenerator, SiteContext
from worker.reports.assembler import assemble_report
from worker.retrieval.retriever import HybridRetriever
from worker.scoring.authority import AuthoritySignalsScore
from worker.scoring.calculator import ScoreCalculator
from worker.scoring.schema import SchemaRichnessScore
from worker.scoring.structure import StructureQualityScore
from worker.scoring.technical import TechnicalReadinessScore
from worker.simulation.runner import SimulationRunner
from worker.tasks.authority_check import (
    aggregate_authority_scores,
    generate_authority_fixes,
    run_authority_checks_sync,
)
from worker.tasks.calibration import collect_calibration_samples
from worker.tasks.schema_check import (
    aggregate_schema_scores,
    generate_schema_fixes,
    run_schema_checks_sync,
)
from worker.tasks.structure_check import (
    aggregate_structure_scores,
    generate_structure_fixes,
    run_structure_checks_sync,
)
from worker.tasks.technical_check import generate_technical_fixes, run_technical_checks_parallel

logger = structlog.get_logger(__name__)


async def update_run_status(
    run_id: uuid.UUID,
    status: str,
    progress: dict | None = None,
    error_message: str | None = None,
    max_retries: int = 3,
) -> None:
    """
    Update run status in database with optimistic locking.

    Uses SQLAlchemy's version_id_col for conflict detection.
    Retries on StaleDataError (concurrent update detected).
    """
    from sqlalchemy.orm.exc import StaleDataError

    for attempt in range(max_retries):
        try:
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
                return

        except StaleDataError:
            if attempt < max_retries - 1:
                logger.warning(
                    "run_status_update_conflict",
                    run_id=str(run_id),
                    status=status,
                    attempt=attempt + 1,
                )
                # Brief pause before retry
                import asyncio

                await asyncio.sleep(0.1 * (attempt + 1))
            else:
                logger.error(
                    "run_status_update_failed",
                    run_id=str(run_id),
                    status=status,
                    reason="max_retries_exceeded",
                )
                raise


def run_audit_sync(run_id: str, site_id: str) -> dict:
    """
    Synchronous wrapper for audit task.

    This is the entry point for RQ which requires sync functions.
    It calls the async implementation.
    """
    import asyncio

    from api.database import reset_engine

    # Reset database connections before each job to ensure fresh connections
    # for the new event loop (required for SimpleWorker on Windows)
    reset_engine()

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
        # Step 0: Technical Readiness Check (v2)
        # =========================================================
        await update_run_status(
            run_id,
            "technical_check",
            {"checking": "robots.txt, TTFB, llms.txt, JS dependency"},
        )

        logger.info("technical_check_starting", domain=domain)

        start_url = f"https://{domain}"
        technical_score: TechnicalReadinessScore | None = None

        try:
            technical_score = await run_technical_checks_parallel(
                url=start_url,
                html=None,  # Will check JS after extraction
                timeout=10.0,
            )

            logger.info(
                "technical_check_completed",
                score=technical_score.total_score,
                level=technical_score.level,
                critical_issues=len(technical_score.critical_issues),
            )

            await update_run_status(
                run_id,
                "technical_check",
                {
                    "technical_score": technical_score.total_score,
                    "technical_level": technical_score.level,
                    "critical_issues": technical_score.critical_issues,
                },
            )

            # Log warning if critical issues found but continue
            if technical_score.critical_issues:
                logger.warning(
                    "technical_critical_issues",
                    domain=domain,
                    issues=technical_score.critical_issues,
                )

        except Exception as e:
            logger.warning(
                "technical_check_failed",
                domain=domain,
                error=str(e),
            )
            # Continue with audit even if technical check fails

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

        # Perform the crawl (with optional caching)
        if settings.crawler_cache_enabled:
            crawl_result = await get_cached_or_crawl(
                url=start_url,
                max_pages=settings.crawler_max_pages,
                max_depth=settings.crawler_max_depth,
                use_cache=True,
            )
        else:
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
        # Step 2.5: Update Technical Score with JS Detection
        # =========================================================
        if technical_score and crawl_result.pages:
            from worker.extraction.js_detection import detect_js_dependency

            # Check JS dependency on homepage HTML
            homepage_html = None
            for page in crawl_result.pages:
                if page.html:
                    homepage_html = page.html
                    break

            if homepage_html:
                try:
                    js_result = detect_js_dependency(homepage_html, start_url)

                    # Update technical score with JS result
                    from worker.scoring.technical import calculate_technical_score

                    technical_score = calculate_technical_score(
                        robots_result=technical_score.robots_result,
                        ttfb_result=technical_score.ttfb_result,
                        llms_txt_result=technical_score.llms_txt_result,
                        js_result=js_result,
                        is_https=technical_score.is_https,
                    )

                    logger.info(
                        "technical_js_detection_complete",
                        js_dependent=js_result.likely_js_dependent,
                        framework=js_result.framework_detected,
                        updated_score=technical_score.total_score,
                    )
                except Exception as e:
                    logger.warning("js_detection_failed", error=str(e))

        # =========================================================
        # Step 2.6: Site Content Type Classification
        # =========================================================
        site_type_result: SiteTypeResult | None = None

        try:
            page_urls = [page.url for page in crawl_result.pages]
            page_htmls = [page.html for page in crawl_result.pages]

            site_type_result = detect_site_type(
                domain=domain,
                page_urls=page_urls,
                page_htmls=page_htmls,
            )

            logger.info(
                "site_type_detected",
                domain=domain,
                site_type=site_type_result.site_type.value,
                confidence=site_type_result.confidence,
                citation_baseline=site_type_result.citation_baseline,
            )

        except Exception as e:
            logger.warning(
                "site_type_detection_failed",
                domain=domain,
                error=str(e),
            )
            # Continue with audit even if site type detection fails

        # =========================================================
        # Step 2.75: Semantic Structure Analysis (v2)
        # =========================================================
        await update_run_status(
            run_id,
            "structure_analysis",
            {"analyzing": "headings, answer-first, FAQ, links, formats"},
        )

        logger.info("structure_analysis_starting", pages=len(crawl_result.pages))

        structure_score: StructureQualityScore | None = None

        try:
            # Analyze structure of each page
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

            # Aggregate into site-level score
            if page_scores:
                structure_score = aggregate_structure_scores(page_scores)

                logger.info(
                    "structure_analysis_completed",
                    total_score=structure_score.total_score,
                    level=structure_score.level,
                    pages_analyzed=len(page_scores),
                )

                await update_run_status(
                    run_id,
                    "structure_analysis",
                    {
                        "structure_score": structure_score.total_score,
                        "structure_level": structure_score.level,
                        "pages_analyzed": len(page_scores),
                    },
                )

        except Exception as e:
            logger.warning(
                "structure_analysis_failed",
                error=str(e),
            )
            # Continue with audit even if structure analysis fails

        # =========================================================
        # Step 2.85: Schema Richness Analysis (v2)
        # =========================================================
        await update_run_status(
            run_id,
            "schema_analysis",
            {"analyzing": "FAQPage, Article, Organization, HowTo, validation"},
        )

        logger.info("schema_analysis_starting", pages=len(crawl_result.pages))

        schema_score: SchemaRichnessScore | None = None

        try:
            # Analyze schema of each page
            schema_page_scores = []
            for page in crawl_result.pages:
                if page.html:
                    page_schema_score = run_schema_checks_sync(
                        html=page.html,
                        url=page.url,
                    )
                    schema_page_scores.append(page_schema_score)

            # Aggregate into site-level score
            if schema_page_scores:
                schema_score = aggregate_schema_scores(schema_page_scores)

                logger.info(
                    "schema_analysis_completed",
                    total_score=schema_score.total_score,
                    level=schema_score.level,
                    pages_analyzed=len(schema_page_scores),
                )

                await update_run_status(
                    run_id,
                    "schema_analysis",
                    {
                        "schema_score": schema_score.total_score,
                        "schema_level": schema_score.level,
                        "pages_analyzed": len(schema_page_scores),
                    },
                )

        except Exception as e:
            logger.warning(
                "schema_analysis_failed",
                error=str(e),
            )
            # Continue with audit even if schema analysis fails

        # =========================================================
        # Step 2.9: Authority Signals Analysis (v2)
        # =========================================================
        await update_run_status(
            run_id,
            "authority_analysis",
            {"analyzing": "author, credentials, citations, freshness, original data"},
        )

        logger.info("authority_analysis_starting", pages=len(crawl_result.pages))

        authority_score: AuthoritySignalsScore | None = None

        try:
            # Analyze authority signals of each page
            authority_page_scores = []
            for i, page in enumerate(crawl_result.pages):
                if page.html and i < len(extraction_result.pages):
                    extracted = extraction_result.pages[i]
                    page_authority_score = run_authority_checks_sync(
                        html=page.html,
                        url=page.url,
                        main_content=extracted.main_content,
                    )
                    authority_page_scores.append(page_authority_score)

            # Aggregate into site-level score
            if authority_page_scores:
                authority_score = aggregate_authority_scores(authority_page_scores)

                logger.info(
                    "authority_analysis_completed",
                    total_score=authority_score.total_score,
                    level=authority_score.level,
                    pages_analyzed=len(authority_page_scores),
                )

                await update_run_status(
                    run_id,
                    "authority_analysis",
                    {
                        "authority_score": authority_score.total_score,
                        "authority_level": authority_score.level,
                        "pages_analyzed": len(authority_page_scores),
                    },
                )

        except Exception as e:
            logger.warning(
                "authority_analysis_failed",
                error=str(e),
            )
            # Continue with audit even if authority analysis fails

        # =========================================================
        # Step 2.95: Entity Recognition Analysis (v2)
        # =========================================================
        await update_run_status(
            run_id,
            "entity_recognition",
            {"analyzing": "Wikipedia, Wikidata, domain age, web presence"},
        )

        logger.info("entity_recognition_starting", domain=domain, company_name=company_name)

        entity_recognition_result: EntityRecognitionResult | None = None

        try:
            analyzer = EntityRecognitionAnalyzer(
                timeout=15.0,  # Give external APIs time
                skip_web_presence=False,  # Include all signals
            )
            entity_recognition_result = await analyzer.analyze(
                domain=domain,
                brand_name=company_name,
            )

            logger.info(
                "entity_recognition_completed",
                total_score=entity_recognition_result.total_score,
                normalized_score=entity_recognition_result.normalized_score,
                has_wikipedia=entity_recognition_result.wikipedia.has_page,
                has_wikidata=entity_recognition_result.wikidata.has_entity,
                domain_age_years=entity_recognition_result.domain_signals.domain_age_years,
            )

            await update_run_status(
                run_id,
                "entity_recognition",
                {
                    "entity_recognition_score": entity_recognition_result.normalized_score,
                    "has_wikipedia": entity_recognition_result.wikipedia.has_page,
                    "has_wikidata": entity_recognition_result.wikidata.has_entity,
                },
            )

        except Exception as e:
            logger.warning(
                "entity_recognition_failed",
                domain=domain,
                error=str(e),
            )
            # Continue with audit even if entity recognition fails

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
        # Step 5: Persist Embeddings + Build Retriever Index
        # =========================================================
        logger.info("indexing_starting", pages=len(embedded_pages))

        retriever = HybridRetriever(embedder=embedder)
        embedding_store = EmbeddingStore()

        # Persist embeddings to database for future reuse
        async with async_session_maker() as db:
            for page_idx, ep in enumerate(embedded_pages):
                # Generate a stable page_id from URL hash
                page_id = uuid.uuid5(uuid.NAMESPACE_URL, ep.url)

                for emb_result in ep.embeddings:
                    chunk = chunked_pages[page_idx].chunks[emb_result.chunk_index]

                    # Store embedding in database
                    await embedding_store.store_embedding(
                        session=db,
                        chunk_id=uuid.uuid5(page_id, emb_result.content_hash),
                        page_id=page_id,
                        site_id=site_id,
                        content=chunk.content,
                        content_hash=emb_result.content_hash,
                        embedding=emb_result.embedding,
                        model_name=settings.embedding_model,
                        chunk_index=emb_result.chunk_index,
                        chunk_type=(
                            chunk.chunk_type.value
                            if hasattr(chunk.chunk_type, "value")
                            else str(chunk.chunk_type)
                        ),
                        heading_context=emb_result.heading_context,
                        position_ratio=(
                            chunk.position_ratio if hasattr(chunk, "position_ratio") else 0.0
                        ),
                        source_url=emb_result.source_url,
                        page_title=emb_result.page_title,
                    )

                    # Also add to in-memory retriever for this run
                    retriever.add_document(
                        doc_id=emb_result.content_hash,
                        content=chunk.content,
                        embedding=emb_result.embedding,
                        source_url=emb_result.source_url,
                        page_title=emb_result.page_title,
                        heading_context=emb_result.heading_context,
                    )

            await db.commit()

        logger.info(
            "indexing_completed",
            documents=len(retriever._documents),
            persisted=total_embeddings,
        )

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
        # Step 7.5: Observation (Optional - Real AI Calls)
        # =========================================================
        observation_run = None
        comparison_summary = None

        # Check if observation is enabled and requested
        include_observation = False
        async with async_session_maker() as db:
            run_result = await db.execute(select(Run).where(Run.id == run_id))
            run_record = run_result.scalar_one_or_none()
            if run_record and run_record.config:
                include_observation = run_record.config.get("include_observation", False)

        if settings.observation_enabled and include_observation:
            await update_run_status(
                run_id,
                "observing",
                {"questions_to_observe": len(questions)},
            )

            logger.info("observation_starting", questions=len(questions))

            try:
                # Create questions list for observation (question_id, question_text tuples)
                observation_questions = [(str(q.id), q.text) for q in questions]

                # Run observations
                run_config = RunConfig.from_settings()
                observation_runner = ObservationRunner(config=run_config)
                observation_run = await observation_runner.run_observation(
                    site_id=site_id,
                    run_id=run_id,
                    company_name=company_name,
                    domain=domain,
                    questions=observation_questions,
                )

                logger.info(
                    "observation_completed",
                    status=observation_run.status.value,
                    mention_rate=observation_run.company_mention_rate,
                    citation_rate=observation_run.citation_rate,
                    total_cost=(
                        observation_run.total_usage.estimated_cost_usd
                        if observation_run.total_usage
                        else 0
                    ),
                )

                # Compare simulation with observation
                comparison_summary = compare_simulation_observation(
                    simulation=simulation_result,
                    observation=observation_run,
                )

                logger.info(
                    "comparison_completed",
                    prediction_accuracy=comparison_summary.prediction_accuracy,
                    optimistic_predictions=comparison_summary.optimistic_predictions,
                    pessimistic_predictions=comparison_summary.pessimistic_predictions,
                )

                # Collect calibration samples for learning
                if settings.calibration_enabled and settings.calibration_sample_collection:
                    pillar_scores_snapshot = None
                    if (
                        technical_score
                        or structure_score
                        or schema_score
                        or authority_score
                        or entity_recognition_result
                    ):
                        pillar_scores_snapshot = {
                            "technical": technical_score.total_score if technical_score else None,
                            "structure": structure_score.total_score if structure_score else None,
                            "schema": schema_score.total_score if schema_score else None,
                            "authority": authority_score.total_score if authority_score else None,
                            "entity_recognition": (
                                entity_recognition_result.normalized_score
                                if entity_recognition_result
                                else None
                            ),
                        }

                        # Add source primacy score (0-100 scale) for optimizer
                        try:
                            from worker.extraction.source_primacy import analyze_source_primacy

                            primacy_result = analyze_source_primacy(
                                domain=domain,
                                site_type=(
                                    site_type_result.site_type
                                    if site_type_result
                                    else SiteType.MIXED
                                ),
                                page_urls=page_urls if page_urls else [],
                                brand_name=company_name,
                            )
                            # Store as 0-100 to match pillar score scale
                            pillar_scores_snapshot["source_primacy"] = round(
                                primacy_result.primacy_score * 100, 1
                            )
                        except Exception as e:
                            logger.warning(
                                "source_primacy_for_calibration_failed",
                                error=str(e),
                            )

                    samples_collected = await collect_calibration_samples(
                        run_id=run_id,
                        simulation_result=simulation_result,
                        observation_run=observation_run,
                        pillar_scores=pillar_scores_snapshot,
                        site_type=(site_type_result.site_type.value if site_type_result else None),
                    )

                    logger.info(
                        "calibration_samples_collected",
                        samples=samples_collected,
                    )

                await update_run_status(
                    run_id,
                    "observing",
                    {
                        "questions_observed": len(observation_run.results),
                        "mention_rate": observation_run.company_mention_rate,
                        "citation_rate": observation_run.citation_rate,
                    },
                )

            except Exception as e:
                logger.warning(
                    "observation_failed",
                    error=str(e),
                )
                # Continue with audit even if observation fails

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

        # Generate technical fixes and merge if we have technical score
        technical_fixes_count = 0
        if technical_score:
            technical_fixes = generate_technical_fixes(technical_score)
            technical_fixes_count = len(technical_fixes)

            # Log technical fixes (they'll be included in the report via technical section)
            if technical_fixes:
                logger.info(
                    "technical_fixes_generated",
                    count=technical_fixes_count,
                    fixes=[f["title"] for f in technical_fixes],
                )

        # Generate structure fixes if we have structure score
        structure_fixes_count = 0
        if structure_score:
            structure_fixes = generate_structure_fixes(structure_score)
            structure_fixes_count = len(structure_fixes)

            # Log structure fixes
            if structure_fixes:
                logger.info(
                    "structure_fixes_generated",
                    count=structure_fixes_count,
                    fixes=[f["title"] for f in structure_fixes],
                )

        # Generate schema fixes if we have schema score
        schema_fixes_count = 0
        if schema_score:
            schema_fixes = generate_schema_fixes(schema_score)
            schema_fixes_count = len(schema_fixes)

            # Log schema fixes
            if schema_fixes:
                logger.info(
                    "schema_fixes_generated",
                    count=schema_fixes_count,
                    fixes=[f["title"] for f in schema_fixes],
                )

        # Generate authority fixes if we have authority score
        authority_fixes_count = 0
        if authority_score:
            authority_fixes = generate_authority_fixes(authority_score)
            authority_fixes_count = len(authority_fixes)

            # Log authority fixes
            if authority_fixes:
                logger.info(
                    "authority_fixes_generated",
                    count=authority_fixes_count,
                    fixes=[f["title"] for f in authority_fixes],
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

        # Build crawl data for report
        crawl_pages_data = []
        for i, page in enumerate(crawl_result.pages):
            # Find matching extraction and chunk data
            word_count = 0
            chunk_count = 0
            if i < len(extraction_result.pages):
                word_count = extraction_result.pages[i].word_count
            if i < len(chunked_pages):
                chunk_count = chunked_pages[i].total_chunks

            crawl_pages_data.append(
                {
                    "url": page.url,
                    "title": page.title,
                    "status_code": page.status_code,
                    "depth": page.depth,
                    "word_count": word_count,
                    "chunk_count": chunk_count,
                }
            )

        crawl_data = {
            "total_pages": len(crawl_result.pages),
            "total_words": extraction_result.total_words,
            "total_chunks": total_chunks,
            "urls_discovered": crawl_result.urls_discovered,
            "urls_failed": crawl_result.urls_failed,
            "max_depth_reached": crawl_result.max_depth_reached,
            "duration_seconds": crawl_result.duration_seconds,
            "pages": crawl_pages_data,
        }

        full_report = assemble_report(
            site_id=site_id,
            run_id=run_id,
            company_name=company_name,
            domain=domain,
            simulation=simulation_result,
            score_breakdown=score_breakdown,
            fix_plan=fix_plan,
            observation=observation_run,
            comparison=comparison_summary,
            crawl_data=crawl_data,
            technical_score=technical_score,
            structure_score=structure_score,
            schema_score=schema_score,
            authority_score=authority_score,
            entity_recognition_result=entity_recognition_result,
            site_type_result=site_type_result,
        )

        logger.info("report_assembly_completed", report_id=str(full_report.metadata.report_id))

        # =========================================================
        # Step 11: Save Report and Complete Run (atomic transaction)
        # =========================================================
        async with async_session_maker() as db:
            # Get mention rate from observation if available
            mention_rate = None
            if observation_run:
                mention_rate = observation_run.company_mention_rate

            report = Report(
                report_version=full_report.metadata.version,
                data=full_report.to_dict(),
                score_conservative=int(score_breakdown.total_score * SCORE_BAND_CONSERVATIVE),
                score_typical=int(score_breakdown.total_score),
                score_generous=int(min(100, score_breakdown.total_score * SCORE_BAND_GENEROUS)),
                mention_rate=mention_rate,
            )
            db.add(report)
            await db.flush()

            # Link report to run and mark complete in same transaction
            result = await db.execute(select(Run).where(Run.id == run_id))
            run = result.scalar_one()
            run.report_id = report.id
            run.status = "complete"
            run.completed_at = datetime.now(UTC)

            await db.commit()

            report_id = report.id

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
