"""V1 API router - aggregates all versioned endpoints."""

from fastapi import APIRouter

router = APIRouter()


# Placeholder for future routers
# from api.routers import auth, sites, questions, runs, reports, fixes, monitoring
# router.include_router(auth.router, prefix="/auth", tags=["Auth"])
# router.include_router(sites.router, prefix="/sites", tags=["Sites"])
# router.include_router(questions.router, prefix="/sites/{site_id}/questions", tags=["Questions"])
# router.include_router(runs.router, prefix="/runs", tags=["Runs"])
# router.include_router(reports.router, prefix="/reports", tags=["Reports"])
# router.include_router(fixes.router, prefix="/fixes", tags=["Fixes"])
# router.include_router(monitoring.router, prefix="/monitoring", tags=["Monitoring"])


@router.get("/")
async def v1_root() -> dict[str, str]:
    """V1 API root endpoint."""
    return {
        "version": "1",
        "status": "active",
    }
