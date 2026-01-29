"""Run service for run-related operations."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.exceptions import NotFoundError
from api.models import Report, Run, Site
from api.schemas.run import RunCreate


class RunService:
    """Service for run operations."""

    async def get_run(
        self,
        db: AsyncSession,
        run_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Run:
        """Get a run by ID, ensuring user owns the site."""
        result = await db.execute(
            select(Run).join(Site).where(Run.id == run_id, Site.user_id == user_id)
        )
        run = result.scalar_one_or_none()
        if not run:
            raise NotFoundError("Run", str(run_id))
        return run  # type: ignore[no-any-return]

    async def get_active_run(
        self,
        db: AsyncSession,
        site_id: uuid.UUID,
    ) -> Run | None:
        """Get any active (non-terminal) run for a site."""
        active_statuses = [
            "queued",
            "crawling",
            "extracting",
            "chunking",
            "embedding",
            "simulating",
            "observing",
            "assembling",
        ]
        result = await db.execute(
            select(Run).where(
                Run.site_id == site_id,
                Run.status.in_(active_statuses),
            )
        )
        return result.scalar_one_or_none()  # type: ignore[no-any-return]

    async def list_runs(
        self,
        db: AsyncSession,
        site_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Run], int]:
        """List all runs for a site."""
        result = await db.execute(
            select(Run)
            .where(Run.site_id == site_id)
            .order_by(Run.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        runs = list(result.scalars().all())

        count_result = await db.execute(
            select(func.count()).select_from(Run).where(Run.site_id == site_id)
        )
        total = count_result.scalar_one()

        return runs, total

    async def create_run(
        self,
        db: AsyncSession,
        site: Site,
        run_in: RunCreate,
    ) -> Run:
        """Create a new run for a site."""
        run = Run(
            site_id=site.id,
            run_type=run_in.run_type,
            status="queued",
            config=run_in.config.model_dump(),
            progress={
                "pages_crawled": 0,
                "pages_total": 0,
                "chunks_created": 0,
                "questions_processed": 0,
                "questions_total": 0,
                "current_step": "queued",
            },
        )
        db.add(run)
        await db.flush()
        await db.refresh(run)
        return run

    async def update_run_status(
        self,
        db: AsyncSession,
        run: Run,
        status: str,
        *,
        progress: dict | None = None,
        error_message: str | None = None,
        error_details: dict | None = None,
    ) -> Run:
        """Update run status and progress."""
        run.status = status

        if progress:
            current_progress = run.progress or {}
            current_progress.update(progress)
            run.progress = current_progress

        if status == "crawling" and not run.started_at:
            run.started_at = datetime.now(UTC)

        if status in ("complete", "failed"):
            run.completed_at = datetime.now(UTC)

        if error_message:
            run.error_message = error_message
            run.error_details = error_details

        await db.flush()
        await db.refresh(run)
        return run

    async def set_run_report(
        self,
        db: AsyncSession,
        run: Run,
        report: Report,
    ) -> Run:
        """Associate a report with a run."""
        run.report_id = report.id
        await db.flush()
        await db.refresh(run)
        return run

    async def get_report(
        self,
        db: AsyncSession,
        report_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Report:
        """Get a report by ID, ensuring user owns the site."""
        result = await db.execute(
            select(Report)
            .join(Run)
            .join(Site)
            .where(Report.id == report_id, Site.user_id == user_id)
        )
        report = result.scalar_one_or_none()
        if not report:
            raise NotFoundError("Report", str(report_id))
        return report  # type: ignore[no-any-return]

    async def create_report(
        self,
        db: AsyncSession,
        data: dict,
    ) -> Report:
        """Create a new report."""
        # Extract quick access fields from data
        score = data.get("score", {})
        bands = score.get("bands", {})
        observation = data.get("observation", {})
        runs = observation.get("runs", [])

        mention_rate = None
        if runs and len(runs) > 0:
            mention_rate = runs[0].get("observed", {}).get("mention_rate")

        report = Report(
            report_version=data.get("report_version", "1.0"),
            data=data,
            score_conservative=bands.get("conservative"),
            score_typical=bands.get("typical"),
            score_generous=bands.get("generous"),
            mention_rate=mention_rate,
        )
        db.add(report)
        await db.flush()
        await db.refresh(report)
        return report


# Singleton instance
run_service = RunService()
