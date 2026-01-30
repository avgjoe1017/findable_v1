"""Alert management endpoints."""

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from api.auth import CurrentUser
from api.database import DbSession
from api.schemas.alert import (
    AlertAcknowledgeRequest,
    AlertConfigCreate,
    AlertConfigResponse,
    AlertConfigUpdate,
    AlertDismissRequest,
    AlertListResponse,
    AlertResponse,
    AlertStats,
    WebhookTestRequest,
    WebhookTestResponse,
)
from api.schemas.responses import SuccessResponse
from api.services import site_service
from api.services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["alerts"])
config_router = APIRouter(prefix="/sites/{site_id}/alerts", tags=["alerts"])


@router.get(
    "",
    response_model=SuccessResponse[AlertListResponse],
    summary="List all alerts for the user",
)
async def list_alerts(
    db: DbSession,
    user: CurrentUser,
    site_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[AlertListResponse]:
    """
    List all alerts for the authenticated user.

    Optionally filter by site or status.
    """
    service = AlertService(db)
    alerts, total, unread = await service.list_alerts(
        user_id=user.id,
        site_id=site_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )

    return SuccessResponse(
        data=AlertListResponse(
            items=[AlertResponse.model_validate(a) for a in alerts],
            total=total,
            limit=limit,
            offset=offset,
            unread_count=unread,
        )
    )


@router.get(
    "/stats",
    response_model=SuccessResponse[AlertStats],
    summary="Get alert statistics",
)
async def get_alert_stats(
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[AlertStats]:
    """Get alert statistics for the authenticated user."""
    service = AlertService(db)
    stats = await service.get_stats(user.id)
    return SuccessResponse(data=AlertStats(**stats))


@router.get(
    "/{alert_id}",
    response_model=SuccessResponse[AlertResponse],
    summary="Get a specific alert",
)
async def get_alert(
    alert_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[AlertResponse]:
    """Get details of a specific alert."""
    from sqlalchemy import select

    from api.models import Alert

    result = await db.execute(
        select(Alert).where(
            Alert.id == alert_id,
            Alert.user_id == user.id,
        )
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )

    return SuccessResponse(data=AlertResponse.model_validate(alert))


@router.post(
    "/acknowledge",
    response_model=SuccessResponse[dict],
    summary="Acknowledge alerts",
)
async def acknowledge_alerts(
    request: AlertAcknowledgeRequest,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[dict]:
    """Mark alerts as acknowledged."""
    service = AlertService(db)
    count = await service.acknowledge_alerts(user.id, request.alert_ids)
    await db.commit()

    return SuccessResponse(
        data={"acknowledged_count": count, "alert_ids": [str(id) for id in request.alert_ids]}
    )


@router.post(
    "/dismiss",
    response_model=SuccessResponse[dict],
    summary="Dismiss alerts",
)
async def dismiss_alerts(
    request: AlertDismissRequest,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[dict]:
    """Dismiss alerts (hide from view)."""
    service = AlertService(db)
    count = await service.dismiss_alerts(user.id, request.alert_ids)
    await db.commit()

    return SuccessResponse(
        data={"dismissed_count": count, "alert_ids": [str(id) for id in request.alert_ids]}
    )


@router.post(
    "/test-webhook",
    response_model=SuccessResponse[WebhookTestResponse],
    summary="Test a webhook URL",
)
async def test_webhook(
    request: WebhookTestRequest,
    _user: CurrentUser,  # Required for auth, not used in logic
) -> SuccessResponse[WebhookTestResponse]:
    """
    Test a webhook URL with a test payload.

    Returns success status and response time.
    """
    from worker.alerts.providers import test_webhook

    result = await test_webhook(request.webhook_url)

    return SuccessResponse(
        data=WebhookTestResponse(
            success=result.success,
            status_code=result.response_data.get("status_code") if result.response_data else None,
            error=result.error,
            response_time_ms=result.response_time_ms,
        )
    )


# Site-specific alert configuration endpoints


@config_router.get(
    "/config",
    response_model=SuccessResponse[AlertConfigResponse],
    summary="Get alert configuration for a site",
)
async def get_alert_config(
    site_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[AlertConfigResponse]:
    """Get alert configuration for a specific site."""
    # Verify site ownership
    try:
        await site_service.get_site(db, site_id, user.id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )

    service = AlertService(db)
    config = await service.get_or_create_config(user.id, site_id)
    await db.commit()

    return SuccessResponse(data=AlertConfigResponse.model_validate(config))


@config_router.post(
    "/config",
    response_model=SuccessResponse[AlertConfigResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create alert configuration for a site",
)
async def create_alert_config(
    site_id: uuid.UUID,
    request: AlertConfigCreate,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[AlertConfigResponse]:
    """Create or update alert configuration for a site."""
    # Verify site ownership
    try:
        await site_service.get_site(db, site_id, user.id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )

    service = AlertService(db)
    config = await service.get_or_create_config(user.id, site_id)

    # Update with request values
    updates = request.model_dump(exclude_unset=True)
    config = await service.update_config(config, updates)
    await db.commit()

    return SuccessResponse(data=AlertConfigResponse.model_validate(config))


@config_router.patch(
    "/config",
    response_model=SuccessResponse[AlertConfigResponse],
    summary="Update alert configuration for a site",
)
async def update_alert_config(
    site_id: uuid.UUID,
    request: AlertConfigUpdate,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[AlertConfigResponse]:
    """Partially update alert configuration for a site."""
    # Verify site ownership
    try:
        await site_service.get_site(db, site_id, user.id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )

    service = AlertService(db)
    config = await service.get_or_create_config(user.id, site_id)

    # Update with non-None values
    updates = request.model_dump(exclude_unset=True, exclude_none=True)
    config = await service.update_config(config, updates)
    await db.commit()

    return SuccessResponse(data=AlertConfigResponse.model_validate(config))


@config_router.delete(
    "/config",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete alert configuration for a site",
)
async def delete_alert_config(
    site_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> None:
    """Delete alert configuration for a site (resets to defaults)."""
    from sqlalchemy import select

    from api.models import AlertConfig

    # Verify site ownership
    try:
        await site_service.get_site(db, site_id, user.id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )

    result = await db.execute(
        select(AlertConfig).where(
            AlertConfig.user_id == user.id,
            AlertConfig.site_id == site_id,
        )
    )
    config = result.scalar_one_or_none()

    if config:
        await db.delete(config)
        await db.commit()
