"""Site and Competitor schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class CompetitorBase(BaseModel):
    """Base competitor schema."""

    domain: str = Field(..., max_length=255)
    name: str | None = Field(None, max_length=255)


class CompetitorCreate(CompetitorBase):
    """Schema for creating a competitor."""

    pass


class CompetitorRead(CompetitorBase):
    """Schema for reading a competitor."""

    id: uuid.UUID
    site_id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


class SiteBase(BaseModel):
    """Base site schema."""

    domain: str = Field(..., max_length=255)
    name: str | None = Field(None, max_length=255)
    business_model: str = Field(default="unknown", max_length=50)

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, v: str) -> str:
        """Normalize domain by removing protocol and trailing slash."""
        v = v.lower().strip()
        for prefix in ["https://", "http://", "www."]:
            if v.startswith(prefix):
                v = v[len(prefix) :]
        return v.rstrip("/")


class SiteCreate(SiteBase):
    """Schema for creating a site."""

    settings: dict | None = None
    competitors: list[CompetitorCreate] = Field(default_factory=list, max_length=2)


class SiteUpdate(BaseModel):
    """Schema for updating a site."""

    name: str | None = Field(None, max_length=255)
    business_model: str | None = Field(None, max_length=50)
    settings: dict | None = None
    monitoring_enabled: bool | None = None


class SiteRead(SiteBase):
    """Schema for reading a site."""

    id: uuid.UUID
    user_id: uuid.UUID
    business_model_confidence: float | None
    industry_tags: list[str] | None
    settings: dict | None
    monitoring_enabled: bool
    next_snapshot_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SiteWithCompetitors(SiteRead):
    """Site with competitors included."""

    competitors: list[CompetitorRead] = []


class SiteList(BaseModel):
    """Schema for listing sites with summary info."""

    id: uuid.UUID
    domain: str
    name: str | None
    business_model: str
    monitoring_enabled: bool
    competitor_count: int
    latest_score: int | None = None
    latest_mention_rate: float | None = None
    next_snapshot_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class CompetitorListUpdate(BaseModel):
    """Schema for updating competitor list."""

    competitors: list[CompetitorCreate] = Field(..., max_length=2)
