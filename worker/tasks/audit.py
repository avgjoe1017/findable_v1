"""Audit run background task."""

import uuid
from datetime import UTC, datetime

import structlog
from rq import get_current_job
from sqlalchemy import select

from api.config import get_settings
from api.database import async_session_maker
from api.models import Report, Run, Site

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
    4. Runs simulations
    5. Generates report

    Args:
        run_id: The Run record ID
        site_id: The Site record ID

    Returns:
        Dict with run results
    """
    job = get_current_job()
    settings = get_settings()

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

        # Update job metadata
        if job:
            job.meta["domain"] = domain
            job.meta["run_id"] = str(run_id)
            job.save_meta()

        # Step 1: Crawling
        await update_run_status(
            run_id,
            "crawling",
            {"pages_crawled": 0, "pages_total": settings.crawler_max_pages},
        )

        # TODO: Implement actual crawling in Day 7
        # For now, simulate with placeholder
        await update_run_status(run_id, "crawling", {"pages_crawled": 10})

        # Step 2: Extracting
        await update_run_status(run_id, "extracting")

        # TODO: Implement extraction in Day 8

        # Step 3: Chunking
        await update_run_status(run_id, "chunking", {"chunks_created": 0})

        # TODO: Implement chunking in Day 10

        # Step 4: Embedding
        await update_run_status(run_id, "embedding")

        # TODO: Implement embedding in Day 11

        # Step 5: Simulating
        await update_run_status(
            run_id,
            "simulating",
            {"questions_processed": 0, "questions_total": 20},
        )

        # TODO: Implement simulation in Day 15

        # Step 6: Assembling report
        await update_run_status(run_id, "assembling")

        # Create placeholder report
        async with async_session_maker() as db:
            report = Report(
                report_version="1.0",
                data={
                    "report_version": "1.0",
                    "generated_at": datetime.now(UTC).isoformat(),
                    "site": {"domain": domain},
                    "score": {
                        "bands": {
                            "conservative": 45,
                            "typical": 52,
                            "generous": 60,
                        }
                    },
                    "questions": [],
                    "fixes": [],
                },
                score_conservative=45,
                score_typical=52,
                score_generous=60,
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
        )

        return {
            "status": "complete",
            "run_id": str(run_id),
            "report_id": str(report_id),
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
