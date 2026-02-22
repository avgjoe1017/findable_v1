"""Audit run management endpoints."""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from api.auth import CurrentUser, current_user_optional
from api.config import get_settings
from api.database import DbSession, get_session_maker
from api.deps import PaginationDep
from api.exceptions import ConflictError, NotFoundError
from api.models.user import User
from api.schemas.responses import PaginatedResponse, SuccessResponse
from api.schemas.run import RunCreate, RunRead, RunWithReport
from api.services import job_service, run_service, site_service

router = APIRouter(prefix="/sites/{site_id}/runs", tags=["runs"])


async def get_user_from_token_param(
    token: Annotated[str | None, Query(description="JWT token for SSE auth")] = None,
) -> User | None:
    """Get user from token query parameter (for SSE/EventSource which can't send headers)."""
    if not token:
        return None

    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience="fastapi-users:auth",
        )
        user_id = payload.get("sub")
        if not user_id:
            return None

        async with get_session_maker()() as session:
            result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
            user: User | None = result.scalar_one_or_none()
            if user and user.is_active:
                return user
    except (jwt.InvalidTokenError, ValueError):
        pass

    return None


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


@router.get(
    "/{run_id}/progress/stream",
    summary="Stream run progress (SSE)",
    response_class=StreamingResponse,
)
async def stream_run_progress(
    site_id: uuid.UUID,
    run_id: uuid.UUID,
    db: DbSession,
    user: Annotated[User | None, Depends(current_user_optional)] = None,
    token_user: Annotated[User | None, Depends(get_user_from_token_param)] = None,
) -> StreamingResponse:
    """
    Stream real-time progress updates for a run using Server-Sent Events.

    Supports authentication via:
    - Authorization header (Bearer token)
    - Query parameter (?token=...) for EventSource compatibility

    The stream emits events in the format:
    ```
    event: progress
    data: {"status": "crawling", "progress": {...}}

    event: complete
    data: {"status": "complete", "report_id": "..."}
    ```

    The stream closes when the run completes or fails.
    """
    # Allow auth via either header or query param (for EventSource)
    auth_user = user or token_user
    if not auth_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    try:
        # Verify user owns site
        await site_service.get_site(db, site_id, auth_user.id)

        # Verify run exists
        await run_service.get_run(db, run_id, auth_user.id)

        async def event_generator() -> AsyncGenerator[str, None]:
            """Generate SSE events for run progress."""
            from sqlalchemy import select

            from api.models import Run

            last_status = None
            last_progress = None
            timeout_counter = 0
            max_timeout = 600  # 10 minutes

            while timeout_counter < max_timeout:
                # Get fresh run data
                async with get_session_maker()() as session:
                    result = await session.execute(select(Run).where(Run.id == run_id))
                    current_run = result.scalar_one_or_none()

                    if not current_run:
                        yield f"event: error\ndata: {json.dumps({'error': 'Run not found'})}\n\n"
                        break

                    # Check if status or progress changed
                    current_status = current_run.status
                    current_progress = current_run.progress

                    if current_status != last_status or current_progress != last_progress:
                        # Emit progress event
                        event_data = {
                            "status": current_status,
                            "progress": current_progress,
                        }

                        if current_status == "complete":
                            event_data["report_id"] = (
                                str(current_run.report_id) if current_run.report_id else None
                            )
                            yield f"event: complete\ndata: {json.dumps(event_data)}\n\n"
                            break
                        elif current_status == "failed":
                            event_data["error"] = current_run.error_message
                            yield f"event: failed\ndata: {json.dumps(event_data)}\n\n"
                            break
                        else:
                            yield f"event: progress\ndata: {json.dumps(event_data)}\n\n"

                        last_status = current_status
                        last_progress = current_progress

                await asyncio.sleep(2)
                timeout_counter += 2

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
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
