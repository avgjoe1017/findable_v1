"""User model for authentication."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base

if TYPE_CHECKING:
    from api.models.site import Site


class PlanTier(str, Enum):
    """User plan tiers."""

    STARTER = "starter"
    PROFESSIONAL = "professional"
    AGENCY = "agency"


class User(SQLAlchemyBaseUserTableUUID, Base):
    """User model with FastAPI-Users integration."""

    __tablename__ = "users"

    # Override id to use proper UUID type
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Additional fields
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    plan: Mapped[str] = mapped_column(
        String(50),
        default=PlanTier.STARTER.value,
        nullable=False,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    sites: Mapped[list[Site]] = relationship(
        "Site", back_populates="user", cascade="all, delete-orphan"
    )
