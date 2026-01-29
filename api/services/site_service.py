"""Site service for site-related operations."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.exceptions import ConflictError, NotFoundError
from api.models import Competitor, Report, Run, Site, User
from api.schemas.site import CompetitorCreate, SiteCreate, SiteUpdate
from api.schemas.user import get_plan_limits


class SiteService:
    """Service for site operations."""

    async def get_site(
        self,
        db: AsyncSession,
        site_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Site:
        """Get a site by ID, ensuring user owns it."""
        result = await db.execute(
            select(Site)
            .options(selectinload(Site.competitors))
            .where(Site.id == site_id, Site.user_id == user_id)
        )
        site = result.scalar_one_or_none()
        if not site:
            raise NotFoundError("Site", str(site_id))
        return site  # type: ignore[no-any-return]

    async def list_sites(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Site], int]:
        """List all sites for a user with competitor counts."""
        # Get sites
        result = await db.execute(
            select(Site)
            .options(selectinload(Site.competitors))
            .where(Site.user_id == user_id)
            .order_by(Site.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        sites = list(result.scalars().all())

        # Get total count
        count_result = await db.execute(
            select(func.count()).select_from(Site).where(Site.user_id == user_id)
        )
        total = count_result.scalar_one()

        return sites, total

    async def create_site(
        self,
        db: AsyncSession,
        user: User,
        site_in: SiteCreate,
    ) -> Site:
        """Create a new site with competitors."""
        # Check plan limits for competitors
        plan_limits = get_plan_limits(user.plan)
        max_competitors = plan_limits.get("competitors", 1)

        if len(site_in.competitors) > max_competitors:
            raise ConflictError(
                f"Plan '{user.plan}' allows maximum {max_competitors} competitor(s)"
            )

        # Check for duplicate domain
        existing = await db.execute(
            select(Site).where(Site.user_id == user.id, Site.domain == site_in.domain)
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"Site with domain '{site_in.domain}' already exists")

        # Create site
        site = Site(
            user_id=user.id,
            domain=site_in.domain,
            name=site_in.name,
            business_model=site_in.business_model,
            settings=site_in.settings,
        )
        db.add(site)
        await db.flush()

        # Create competitors
        for comp_in in site_in.competitors:
            competitor = Competitor(
                site_id=site.id,
                domain=comp_in.domain,
                name=comp_in.name,
            )
            db.add(competitor)

        await db.flush()
        await db.refresh(site)

        # Load competitors relationship
        result = await db.execute(
            select(Site).options(selectinload(Site.competitors)).where(Site.id == site.id)
        )
        return result.scalar_one()  # type: ignore[no-any-return]

    async def update_site(
        self,
        db: AsyncSession,
        site: Site,
        site_in: SiteUpdate,
    ) -> Site:
        """Update a site."""
        update_data = site_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(site, field, value)

        await db.flush()
        await db.refresh(site)
        return site

    async def delete_site(
        self,
        db: AsyncSession,
        site: Site,
    ) -> None:
        """Delete a site and all related data."""
        await db.delete(site)
        await db.flush()

    async def update_competitors(
        self,
        db: AsyncSession,
        site: Site,
        user: User,
        competitors: list[CompetitorCreate],
    ) -> Site:
        """Update competitors for a site."""
        # Check plan limits
        plan_limits = get_plan_limits(user.plan)
        max_competitors = plan_limits.get("competitors", 1)

        if len(competitors) > max_competitors:
            raise ConflictError(
                f"Plan '{user.plan}' allows maximum {max_competitors} competitor(s)"
            )

        # Delete existing competitors
        for comp in site.competitors:
            await db.delete(comp)

        # Create new competitors
        for comp_in in competitors:
            competitor = Competitor(
                site_id=site.id,
                domain=comp_in.domain,
                name=comp_in.name,
            )
            db.add(competitor)

        await db.flush()

        # Reload site with competitors
        result = await db.execute(
            select(Site).options(selectinload(Site.competitors)).where(Site.id == site.id)
        )
        return result.scalar_one()  # type: ignore[no-any-return]

    async def get_latest_report(
        self,
        db: AsyncSession,
        site_id: uuid.UUID,
    ) -> Report | None:
        """Get the latest report for a site."""
        result = await db.execute(
            select(Report)
            .join(Run)
            .where(Run.site_id == site_id, Run.status == "complete")
            .order_by(Report.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()  # type: ignore[no-any-return]


# Singleton instance
site_service = SiteService()
