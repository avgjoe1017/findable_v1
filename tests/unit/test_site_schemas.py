"""Tests for site schemas."""

from api.schemas.site import CompetitorCreate, SiteCreate


def test_site_create_domain_normalization() -> None:
    """Test domain normalization in SiteCreate."""
    site = SiteCreate(domain="https://www.Example.com/")
    assert site.domain == "example.com"

    site2 = SiteCreate(domain="HTTP://EXAMPLE.COM")
    assert site2.domain == "example.com"

    site3 = SiteCreate(domain="example.com")
    assert site3.domain == "example.com"


def test_site_create_with_competitors() -> None:
    """Test SiteCreate with competitors."""
    site = SiteCreate(
        domain="example.com",
        name="Example Site",
        competitors=[
            CompetitorCreate(domain="competitor1.com"),
            CompetitorCreate(domain="competitor2.com", name="Competitor 2"),
        ],
    )
    assert len(site.competitors) == 2
    assert site.competitors[0].domain == "competitor1.com"
    assert site.competitors[1].name == "Competitor 2"


def test_site_create_defaults() -> None:
    """Test SiteCreate default values."""
    site = SiteCreate(domain="example.com")
    assert site.name is None
    assert site.business_model == "unknown"
    assert site.settings is None
    assert site.competitors == []
