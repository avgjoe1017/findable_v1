"""Audit run management endpoints."""

import uuid

from fastapi import APIRouter, HTTPException, status

from api.auth import CurrentUser
from api.database import DbSession
from api.deps import PaginationDep
from api.exceptions import ConflictError, NotFoundError
from api.schemas.responses import PaginatedResponse, SuccessResponse
from api.schemas.run import RunCreate, RunRead, RunWithReport
from api.services import job_service, run_service, site_service

router = APIRouter(prefix="/sites/{site_id}/runs", tags=["runs"])


@router.post(
    "",
    response_model=SuccessResponse[RunRead],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a new audit run",
)
async def create_run(
    site_id: uuid.UUID,
    run_in: RunCreate,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[RunRead]:
    """
    Start a new audit run for a site.

    The run is queued for background processing.
    Use the returned run ID or job ID to poll for status.
    """
    try:
        # Verify user owns site
        site = await site_service.get_site(db, site_id, user.id)

        # Check for existing active run
        active_run = await run_service.get_active_run(db, site_id)
        if active_run:
            raise ConflictError(
                f"Site already has an active run ({active_run.id}) in status '{active_run.status}'"
            )

        # Create run record
        run = await run_service.create_run(db, site, run_in)

        # Enqueue background job
        job_id = job_service.enqueue_audit(run, site)

        # Update run with job ID
        run.job_id = job_id
        await db.flush()
        await db.refresh(run)

        return SuccessResponse(
            data=RunRead.model_validate(run),
            meta={"job_id": job_id},
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get(
    "",
    response_model=PaginatedResponse[RunRead],
    summary="List audit runs",
)
async def list_runs(
    site_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    pagination: PaginationDep,
) -> PaginatedResponse[RunRead]:
    """
    List all audit runs for a site.

    Returns paginated results ordered by creation date (newest first).
    """
    try:
        # Verify user owns site
        await site_service.get_site(db, site_id, user.id)

        runs, total = await run_service.list_runs(
            db,
            site_id,
            skip=pagination.offset,
            limit=pagination.limit,
        )

        return PaginatedResponse.create(
            data=[RunRead.model_validate(r) for r in runs],
            total=total,
            page=pagination.page,
            per_page=pagination.per_page,
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )


@router.get(
    "/{run_id}",
    response_model=SuccessResponse[RunWithReport],
    summary="Get run details",
)
async def get_run(
    site_id: uuid.UUID,
    run_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[RunWithReport]:
    """
    Get detailed information about a specific run.

    Includes progress information and report summary if complete.
    """
    try:
        # Verify user owns site
        await site_service.get_site(db, site_id, user.id)

        run = await run_service.get_run(db, run_id, user.id)

        # Get job status if available
        job_status = None
        if run.job_id:
            job_info = job_service.get_job_status(run.job_id)
            if job_info:
                job_status = job_info.status.value

        return SuccessResponse(
            data=RunWithReport.model_validate(run),
            meta={"job_status": job_status} if job_status else None,
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.delete(
    "/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a run",
)
async def cancel_run(
    site_id: uuid.UUID,
    run_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> None:
    """
    Cancel a queued or running audit.

    Only works for runs that haven't completed.
    """
    try:
        # Verify user owns site
        await site_service.get_site(db, site_id, user.id)

        run = await run_service.get_run(db, run_id, user.id)

        if run.status in ("complete", "failed"):
            raise ConflictError(f"Cannot cancel run in status '{run.status}'")

        # Cancel the background job if it exists
        if run.job_id:
            job_service.cancel_job(run.job_id)

        # Mark run as failed
        await run_service.update_run_status(
            db,
            run,
            "failed",
            error_message="Cancelled by user",
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


# Separate router for report access
reports_router = APIRouter(prefix="/reports", tags=["reports"])


@reports_router.get(
    "/{report_id}",
    response_model=SuccessResponse[dict],
    summary="Get full report",
)
async def get_report(
    report_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[dict]:
    """
    Get the full report data.

    Returns the complete report JSON including:
    - Score breakdown with all three bands
    - Question-level analysis
    - Recommended fixes
    - Observation data (if included)
    """
    try:
        report = await run_service.get_report(db, report_id, user.id)
        return SuccessResponse(
            data=report.data,
            meta={
                "report_id": str(report.id),
                "report_version": report.report_version,
                "created_at": report.created_at.isoformat(),
            },
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id} not found",
        )
