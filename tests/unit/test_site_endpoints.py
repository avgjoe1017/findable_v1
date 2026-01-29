"""Tests for site endpoint schemas and validation."""

import uuid
from datetime import UTC, datetime

from api.schemas.responses import PaginatedResponse
from api.schemas.site import (
    CompetitorCreate,
    CompetitorListUpdate,
    CompetitorRead,
    SiteCreate,
    SiteList,
    SiteUpdate,
    SiteWithCompetitors,
)


class TestSiteCreate:
    """Tests for SiteCreate schema."""

    def test_site_create_with_competitors(self) -> None:
        """Test creating site with competitors."""
        site = SiteCreate(
            domain="example.com",
            name="Example Site",
            competitors=[
                CompetitorCreate(domain="competitor1.com"),
                CompetitorCreate(domain="competitor2.com", name="Competitor 2"),
            ],
        )

        assert site.domain == "example.com"
        assert site.name == "Example Site"
        assert len(site.competitors) == 2
        assert site.competitors[0].domain == "competitor1.com"

    def test_site_create_domain_normalization(self) -> None:
        """Test domain is normalized."""
        site = SiteCreate(domain="HTTPS://WWW.Example.COM/")

        assert site.domain == "example.com"


class TestSiteUpdate:
    """Tests for SiteUpdate schema."""

    def test_site_update_partial(self) -> None:
        """Test partial update."""
        update = SiteUpdate(name="New Name")

        assert update.name == "New Name"
        assert update.business_model is None
        assert update.settings is None

    def test_site_update_monitoring(self) -> None:
        """Test monitoring flag update."""
        update = SiteUpdate(monitoring_enabled=True)

        assert update.monitoring_enabled is True


class TestSiteList:
    """Tests for SiteList schema."""

    def test_site_list_schema(self) -> None:
        """Test site list schema."""
        now = datetime.now(UTC)
        site = SiteList(
            id=uuid.uuid4(),
            domain="example.com",
            name="Example",
            business_model="saas",
            monitoring_enabled=True,
            competitor_count=2,
            latest_score=75,
            latest_mention_rate=0.45,
            next_snapshot_at=now,
            created_at=now,
        )

        assert site.domain == "example.com"
        assert site.competitor_count == 2
        assert site.latest_score == 75


class TestSiteWithCompetitors:
    """Tests for SiteWithCompetitors schema."""

    def test_site_with_competitors(self) -> None:
        """Test full site with competitors."""
        now = datetime.now(UTC)
        site = SiteWithCompetitors(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            domain="example.com",
            name="Example",
            business_model="saas",
            business_model_confidence=0.95,
            industry_tags=["technology", "b2b"],
            settings={"key": "value"},
            monitoring_enabled=True,
            next_snapshot_at=now,
            created_at=now,
            updated_at=now,
            competitors=[
                CompetitorRead(
                    id=uuid.uuid4(),
                    site_id=uuid.uuid4(),
                    domain="competitor.com",
                    name="Competitor",
                    created_at=now,
                )
            ],
        )

        assert site.domain == "example.com"
        assert len(site.competitors) == 1
        assert site.competitors[0].domain == "competitor.com"


class TestCompetitorListUpdate:
    """Tests for CompetitorListUpdate schema."""

    def test_competitor_list_update(self) -> None:
        """Test updating competitor list."""
        update = CompetitorListUpdate(
            competitors=[
                CompetitorCreate(domain="new1.com"),
                CompetitorCreate(domain="new2.com", name="New 2"),
            ]
        )

        assert len(update.competitors) == 2


class TestPaginatedResponse:
    """Tests for PaginatedResponse.create()."""

    def test_paginated_response_create(self) -> None:
        """Test creating paginated response."""
        data = [{"id": 1}, {"id": 2}]
        response = PaginatedResponse.create(
            data=data,
            total=50,
            page=1,
            per_page=20,
        )

        assert response.data == data
        assert response.meta.total == 50
        assert response.meta.page == 1
        assert response.meta.per_page == 20
        assert response.meta.total_pages == 3
        assert response.meta.has_next is True
        assert response.meta.has_prev is False

    def test_paginated_response_last_page(self) -> None:
        """Test paginated response for last page."""
        response = PaginatedResponse.create(
            data=[],
            total=50,
            page=3,
            per_page=20,
        )

        assert response.meta.has_next is False
        assert response.meta.has_prev is True

    def test_paginated_response_empty(self) -> None:
        """Test paginated response with no items."""
        response = PaginatedResponse.create(
            data=[],
            total=0,
            page=1,
            per_page=20,
        )

        assert response.meta.total == 0
        assert response.meta.total_pages == 0
        assert response.meta.has_next is False
        assert response.meta.has_prev is False
