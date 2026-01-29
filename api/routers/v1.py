"""V1 API router - aggregates all versioned endpoints."""

from fastapi import APIRouter

from api.routers import auth, jobs, runs, sites

router = APIRouter()

# Auth endpoints
router.include_router(auth.router, prefix="/auth", tags=["Auth"])

# Job endpoints
router.include_router(jobs.router)

# Site endpoints
router.include_router(sites.router)

# Run endpoints (nested under sites)
router.include_router(runs.router)

# Report endpoints
router.include_router(runs.reports_router)


@router.get("/")
async def v1_root() -> dict[str, str]:
    """V1 API root endpoint."""
    return {
        "version": "1",
        "status": "active",
    }
