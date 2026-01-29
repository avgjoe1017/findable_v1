"""V1 API router - aggregates all versioned endpoints."""

from fastapi import APIRouter

from api.routers import auth

router = APIRouter()

# Auth endpoints
router.include_router(auth.router, prefix="/auth", tags=["Auth"])

# Future routers will be added here:
# router.include_router(sites.router, prefix="/sites", tags=["Sites"])
# router.include_router(runs.router, prefix="/runs", tags=["Runs"])
# router.include_router(reports.router, prefix="/reports", tags=["Reports"])


@router.get("/")
async def v1_root() -> dict[str, str]:
    """V1 API root endpoint."""
    return {
        "version": "1",
        "status": "active",
    }
