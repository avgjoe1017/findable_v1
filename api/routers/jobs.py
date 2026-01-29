"""Job status endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, status

from api.auth import CurrentUser
from api.schemas.responses import SuccessResponse
from api.services import job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get(
    "/{job_id}",
    response_model=SuccessResponse[dict[str, Any]],
    summary="Get job status",
)
async def get_job_status(
    job_id: str,
    _user: CurrentUser,
) -> SuccessResponse[dict[str, Any]]:
    """
    Get the status of a background job.

    Returns job status, progress metadata, and result if complete.
    """
    job_info = job_service.get_job_status(job_id)

    if not job_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # Note: For now we allow any authenticated user to check job status
    # In production, verify job_info.meta["user_id"] matches current user

    return SuccessResponse(data=job_info.to_dict())


@router.delete(
    "/{job_id}",
    response_model=SuccessResponse[dict[str, str]],
    summary="Cancel a job",
)
async def cancel_job(
    job_id: str,
    _user: CurrentUser,
) -> SuccessResponse[dict[str, str]]:
    """
    Cancel a queued background job.

    Only jobs in queued/deferred/scheduled status can be cancelled.
    """
    job_info = job_service.get_job_status(job_id)

    if not job_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    success = job_service.cancel_job(job_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job cannot be cancelled (already started or finished)",
        )

    return SuccessResponse(data={"status": "cancelled", "job_id": job_id})


@router.get(
    "/",
    response_model=SuccessResponse[dict[str, Any]],
    summary="Get queue statistics",
)
async def get_queue_stats(
    _user: CurrentUser,
) -> SuccessResponse[dict[str, Any]]:
    """
    Get statistics for all job queues.

    Returns counts of jobs in various states for each queue.
    """
    stats = job_service.get_queue_stats()
    return SuccessResponse(data={"queues": stats})
