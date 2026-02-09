"""Site and Competitor models."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base

if TYPE_CHECKING:
    from api.models.embedding import Embedding
    from api.models.run import Run
    from api.models.user import User


class BusinessModel(StrEnum):
    """Business model types for site classification."""

    LOCAL_SERVICE = "local_service"
    ECOMMERCE = "ecommerce"
    SAAS = "saas"
    PUBLISHER = "publisher"
    MARKETPLACE = "marketplace"
    PROFESSIONAL_SERVICES = "professional_services"
    NONPROFIT = "nonprofit"
    B2B_INDUSTRIAL = "b2b_industrial"
    HEALTHCARE = "healthcare"
    EVENTS = "events"
    UNKNOWN = "unknown"


class Site(Base):
    """Site model - represents a website to analyze."""

    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Owner
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Site info
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Classification
    business_model: Mapped[str] = mapped_column(
        String(50),
        default=BusinessModel.UNKNOWN.value,
        nullable=False,
    )
    business_model_confidence: Mapped[float | None] = mapped_column(nullable=True)
    industry_tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Settings
    settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Monitoring
    monitoring_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    next_snapshot_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
    user: Mapped[User] = relationship("User", back_populates="sites")
    competitors: Mapped[list[Competitor]] = relationship(
        "Competitor", back_populates="site", cascade="all, delete-orphan"
    )
    runs: Mapped[list[Run]] = relationship(
        "Run", back_populates="site", cascade="all, delete-orphan"
    )
    embeddings: Mapped[list[Embedding]] = relationship(
        "Embedding", back_populates="site", cascade="all, delete-orphan"
    )


class Competitor(Base):
    """Competitor model - competitor domains for a site."""

    __tablename__ = "competitors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    site: Mapped[Site] = relationship("Site", back_populates="competitors")
