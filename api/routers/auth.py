"""Authentication endpoints."""

from fastapi import APIRouter

from api.auth import CurrentUser, auth_backend, fastapi_users
from api.schemas.user import PlanInfo, UserCreate, UserRead, UserUpdate, get_plan_limits

router = APIRouter()

# Include FastAPI-Users routers
router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="",
    tags=["Auth"],
)

router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="",
    tags=["Auth"],
)

router.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="",
    tags=["Auth"],
)

router.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="",
    tags=["Auth"],
)

router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["Users"],
)


@router.get("/me/plan", response_model=PlanInfo, tags=["Users"])
async def get_current_user_plan(user: CurrentUser) -> PlanInfo:
    """Get current user's plan and limits."""
    return PlanInfo(
        plan=user.plan,
        limits=get_plan_limits(user.plan),
    )
