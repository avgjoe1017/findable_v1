"""Site management endpoints."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from api.auth import CurrentUser
from api.database import DbSession
from api.deps import PaginationDep
from api.exceptions import ConflictError, NotFoundError
from api.models import Report, Run
from api.schemas.responses import PaginatedResponse, SuccessResponse
from api.schemas.site import (
    CompetitorListUpdate,
    CompetitorRead,
    SiteCreate,
    SiteList,
    SiteUpdate,
    SiteWithCompetitors,
)
from api.services import site_service

router = APIRouter(prefix="/sites", tags=["sites"])


@router.post(
    "",
    response_model=SuccessResponse[SiteWithCompetitors],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new site",
)
async def create_site(
    site_in: SiteCreate,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[SiteWithCompetitors]:
    """
    Create a new site for the authenticated user.

    - Validates domain uniqueness for the user
    - Enforces plan limits for number of competitors
    - Automatically normalizes the domain
    """
    try:
        site = await site_service.create_site(db, user, site_in)
        return SuccessResponse(data=SiteWithCompetitors.model_validate(site))
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get(
    "",
    response_model=PaginatedResponse[SiteList],
    summary="List all sites",
)
async def list_sites(
    db: DbSession,
    user: CurrentUser,
    pagination: PaginationDep,
) -> PaginatedResponse[SiteList]:
    """
    List all sites for the authenticated user.

    Returns paginated results with summary information.
    """
    sites, total = await site_service.list_sites(
        db,
        user.id,
        skip=pagination.offset,
        limit=pagination.limit,
    )

    # Batch load latest reports for all sites in ONE query (avoids N+1)
    site_ids = [s.id for s in sites]
    latest_reports_map: dict[uuid.UUID, Report] = {}
    if site_ids:
        # Subquery: max report created_at per site
        latest_report_sub = (
            select(
                Run.site_id,
                func.max(Report.created_at).label("max_created"),
            )
            .join(Report, Report.run_id == Run.id)
            .where(Run.site_id.in_(site_ids), Run.status == "complete")
            .group_by(Run.site_id)
            .subquery()
        )
        # Join back to get actual Report rows
        ReportAlias = aliased(Report)
        RunAlias = aliased(Run)
        report_result = await db.execute(
            select(ReportAlias, RunAlias.site_id)
            .join(RunAlias, ReportAlias.run_id == RunAlias.id)
            .join(
                latest_report_sub,
                (RunAlias.site_id == latest_report_sub.c.site_id)
                & (ReportAlias.created_at == latest_report_sub.c.max_created),
            )
        )
        for report, sid in report_result.all():
            latest_reports_map[sid] = report

    # Convert to list schema with competitor counts
    site_list = []
    for site in sites:
        latest_report = latest_reports_map.get(site.id)
        latest_score = latest_report.score_typical if latest_report else None
        latest_mention_rate = latest_report.mention_rate if latest_report else None

        site_list.append(
            SiteList(
                id=site.id,
                domain=site.domain,
                name=site.name,
                business_model=site.business_model,
                monitoring_enabled=site.monitoring_enabled,
                competitor_count=len(site.competitors),
                latest_score=latest_score,
                latest_mention_rate=latest_mention_rate,
                next_snapshot_at=site.next_snapshot_at,
                created_at=site.created_at,
            )
        )

    return PaginatedResponse.create(
        data=site_list,
        total=total,
        page=pagination.page,
        per_page=pagination.per_page,
    )


@router.get(
    "/{site_id}",
    response_model=SuccessResponse[SiteWithCompetitors],
    summary="Get site details",
)
async def get_site(
    site_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[SiteWithCompetitors]:
    """
    Get detailed information about a specific site.

    Includes all competitors and configuration.
    """
    try:
        site = await site_service.get_site(db, site_id, user.id)
        return SuccessResponse(data=SiteWithCompetitors.model_validate(site))
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )


@router.patch(
    "/{site_id}",
    response_model=SuccessResponse[SiteWithCompetitors],
    summary="Update a site",
)
async def update_site(
    site_id: uuid.UUID,
    site_in: SiteUpdate,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[SiteWithCompetitors]:
    """
    Update site settings.

    Only provided fields will be updated.
    """
    try:
        site = await site_service.get_site(db, site_id, user.id)
        updated = await site_service.update_site(db, site, site_in)
        return SuccessResponse(data=SiteWithCompetitors.model_validate(updated))
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )


@router.delete(
    "/{site_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a site",
)
async def delete_site(
    site_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> None:
    """
    Delete a site and all associated data.

    This permanently removes:
    - The site configuration
    - All competitors
    - All audit runs
    - All reports
    """
    try:
        site = await site_service.get_site(db, site_id, user.id)
        await site_service.delete_site(db, site)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )


@router.put(
    "/{site_id}/competitors",
    response_model=SuccessResponse[list[CompetitorRead]],
    summary="Update competitors",
)
async def update_competitors(
    site_id: uuid.UUID,
    competitors_in: CompetitorListUpdate,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[list[CompetitorRead]]:
    """
    Replace all competitors for a site.

    - Removes existing competitors
    - Adds new competitors from the list
    - Enforces plan limits
    """
    try:
        site = await site_service.get_site(db, site_id, user.id)
        updated = await site_service.update_competitors(db, site, user, competitors_in.competitors)
        competitors = [CompetitorRead.model_validate(c) for c in updated.competitors]
        return SuccessResponse(data=competitors)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.post(
    "/{site_id}/cache/invalidate",
    response_model=SuccessResponse[dict],
    summary="Invalidate crawl cache",
)
async def invalidate_cache(
    site_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[dict]:
    """
    Invalidate the crawl cache for a site.

    Forces the next audit to perform a fresh crawl instead of using cached data.
    Useful when site content has changed significantly.
    """
    from worker.crawler.cache import crawl_cache

    try:
        site = await site_service.get_site(db, site_id, user.id)
        invalidated = await crawl_cache.invalidate(site.domain)
        return SuccessResponse(
            data={
                "domain": site.domain,
                "cache_invalidated": invalidated,
            }
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )
