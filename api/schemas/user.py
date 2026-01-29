"""User schemas for API requests/responses."""

import uuid
from datetime import datetime

from fastapi_users import schemas
from pydantic import BaseModel, EmailStr, Field


class UserRead(schemas.BaseUser[uuid.UUID]):
    """Schema for reading user data."""

    name: str | None = None
    plan: str = "starter"
    created_at: datetime
    updated_at: datetime


class UserCreate(schemas.BaseUserCreate):
    """Schema for creating a user."""

    name: str | None = Field(None, max_length=255)


class UserUpdate(schemas.BaseUserUpdate):
    """Schema for updating a user."""

    name: str | None = Field(None, max_length=255)


class UserProfile(BaseModel):
    """Public user profile response."""

    id: uuid.UUID
    email: EmailStr
    name: str | None
    plan: str
    created_at: datetime

    class Config:
        from_attributes = True


class PlanInfo(BaseModel):
    """Plan information response."""

    plan: str
    limits: dict[str, int]


def get_plan_limits(plan: str) -> dict[str, int]:
    """Get limits for a plan tier."""
    limits = {
        "starter": {
            "competitors": 1,
            "custom_questions": 5,
            "weekly_snapshots": 4,
        },
        "professional": {
            "competitors": 2,
            "custom_questions": 5,
            "weekly_snapshots": -1,  # unlimited
        },
        "agency": {
            "competitors": 2,
            "custom_questions": 5,
            "weekly_snapshots": -1,
            "client_sites": 10,
        },
    }
    return limits.get(plan, limits["starter"])
