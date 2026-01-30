"""Alert service for managing notifications."""

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import (
    Alert,
    AlertConfig,
    AlertSeverity,
    AlertStatus,
    AlertType,
    Snapshot,
)

logger = structlog.get_logger(__name__)


class AlertService:
    """Service for managing alerts and notifications."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_config(self, user_id: uuid.UUID, site_id: uuid.UUID) -> AlertConfig:
        """Get or create alert configuration for a site."""
        result = await self.db.execute(
            select(AlertConfig).where(
                AlertConfig.user_id == user_id,
                AlertConfig.site_id == site_id,
            )
        )
        config = result.scalar_one_or_none()

        if not config:
            config = AlertConfig(user_id=user_id, site_id=site_id)
            self.db.add(config)
            await self.db.flush()
            await self.db.refresh(config)

        result_config: AlertConfig = config
        return result_config

    async def update_config(
        self,
        config: AlertConfig,
        updates: dict,
    ) -> AlertConfig:
        """Update alert configuration."""
        for key, value in updates.items():
            if value is not None and hasattr(config, key):
                setattr(config, key, value)

        await self.db.flush()
        await self.db.refresh(config)
        return config

    async def check_snapshot_alerts(
        self,
        snapshot: Snapshot,
        previous_snapshot: Snapshot | None,
    ) -> list[Alert]:
        """Check for alert conditions after a snapshot and create alerts."""
        alerts: list[Alert] = []

        # Get alert config for this site
        result = await self.db.execute(
            select(AlertConfig).where(AlertConfig.site_id == snapshot.site_id)
        )
        config = result.scalar_one_or_none()

        if not config or not config.enabled:
            return alerts

        # Check rate limiting
        if config.last_alert_at:
            hours_since_last = (datetime.now(UTC) - config.last_alert_at).total_seconds() / 3600
            if hours_since_last < config.min_hours_between_alerts:
                logger.debug(
                    "alert_rate_limited",
                    site_id=str(snapshot.site_id),
                    hours_since_last=hours_since_last,
                )
                return alerts

        # Get user for the site
        from api.models import Site

        site_result = await self.db.execute(select(Site).where(Site.id == snapshot.site_id))
        site = site_result.scalar_one_or_none()
        if not site:
            return alerts

        user_id = site.user_id

        # Check score drop
        if (
            config.alert_on_score_drop
            and previous_snapshot
            and snapshot.score_delta is not None
            and snapshot.score_delta < -config.score_drop_threshold
        ):
            alert = await self._create_alert(
                user_id=user_id,
                site_id=snapshot.site_id,
                alert_type=AlertType.SCORE_DROP,
                severity=AlertSeverity.WARNING,
                title=f"Score dropped by {abs(snapshot.score_delta)} points",
                message=f"Your AI sourceability score for {site.domain} decreased from {previous_snapshot.score_typical} to {snapshot.score_typical}.",
                data={
                    "previous_score": previous_snapshot.score_typical,
                    "current_score": snapshot.score_typical,
                    "delta": snapshot.score_delta,
                    "snapshot_id": str(snapshot.id),
                },
            )
            alerts.append(alert)

        # Check score improvement
        if (
            config.alert_on_score_improvement
            and previous_snapshot
            and snapshot.score_delta is not None
            and snapshot.score_delta >= config.score_improvement_threshold
        ):
            alert = await self._create_alert(
                user_id=user_id,
                site_id=snapshot.site_id,
                alert_type=AlertType.SCORE_IMPROVEMENT,
                severity=AlertSeverity.INFO,
                title=f"Score improved by {snapshot.score_delta} points",
                message=f"Your AI sourceability score for {site.domain} increased from {previous_snapshot.score_typical} to {snapshot.score_typical}.",
                data={
                    "previous_score": previous_snapshot.score_typical,
                    "current_score": snapshot.score_typical,
                    "delta": snapshot.score_delta,
                    "snapshot_id": str(snapshot.id),
                },
            )
            alerts.append(alert)

        # Check critical score - nested if kept for clarity
        if (  # noqa: SIM102
            config.alert_on_score_critical
            and snapshot.score_typical is not None
            and snapshot.score_typical < config.score_critical_threshold
        ):
            # Only alert if previous was above threshold
            if (
                not previous_snapshot
                or previous_snapshot.score_typical is None
                or previous_snapshot.score_typical >= config.score_critical_threshold
            ):
                alert = await self._create_alert(
                    user_id=user_id,
                    site_id=snapshot.site_id,
                    alert_type=AlertType.SCORE_CRITICAL,
                    severity=AlertSeverity.CRITICAL,
                    title=f"Score fell below critical threshold ({config.score_critical_threshold})",
                    message=f"Your AI sourceability score for {site.domain} is now {snapshot.score_typical}, which is below your critical threshold of {config.score_critical_threshold}.",
                    data={
                        "current_score": snapshot.score_typical,
                        "threshold": config.score_critical_threshold,
                        "snapshot_id": str(snapshot.id),
                    },
                )
                alerts.append(alert)

        # Check mention rate change
        if (
            config.alert_on_mention_rate_change
            and previous_snapshot
            and snapshot.mention_rate_delta is not None
            and abs(snapshot.mention_rate_delta) >= config.mention_rate_threshold
        ):
            if snapshot.mention_rate_delta < 0:
                alert = await self._create_alert(
                    user_id=user_id,
                    site_id=snapshot.site_id,
                    alert_type=AlertType.MENTION_RATE_DROP,
                    severity=AlertSeverity.WARNING,
                    title=f"Mention rate dropped by {abs(snapshot.mention_rate_delta):.1%}",
                    message=f"Your mention rate for {site.domain} decreased from {previous_snapshot.mention_rate:.1%} to {snapshot.mention_rate:.1%}.",
                    data={
                        "previous_rate": previous_snapshot.mention_rate,
                        "current_rate": snapshot.mention_rate,
                        "delta": snapshot.mention_rate_delta,
                        "snapshot_id": str(snapshot.id),
                    },
                )
            else:
                alert = await self._create_alert(
                    user_id=user_id,
                    site_id=snapshot.site_id,
                    alert_type=AlertType.MENTION_RATE_IMPROVEMENT,
                    severity=AlertSeverity.INFO,
                    title=f"Mention rate improved by {snapshot.mention_rate_delta:.1%}",
                    message=f"Your mention rate for {site.domain} increased from {previous_snapshot.mention_rate:.1%} to {snapshot.mention_rate:.1%}.",
                    data={
                        "previous_rate": previous_snapshot.mention_rate,
                        "current_rate": snapshot.mention_rate,
                        "delta": snapshot.mention_rate_delta,
                        "snapshot_id": str(snapshot.id),
                    },
                )
            alerts.append(alert)

        # Update last alert time if any alerts were created
        if alerts:
            config.last_alert_at = datetime.now(UTC)
            await self.db.flush()

        return alerts

    async def create_snapshot_failed_alert(
        self,
        site_id: uuid.UUID,
        error_message: str,
    ) -> Alert | None:
        """Create an alert for a failed snapshot."""
        # Get config
        result = await self.db.execute(select(AlertConfig).where(AlertConfig.site_id == site_id))
        config = result.scalar_one_or_none()

        if not config or not config.enabled or not config.alert_on_snapshot_failed:
            return None

        # Get site
        from api.models import Site

        site_result = await self.db.execute(select(Site).where(Site.id == site_id))
        site = site_result.scalar_one_or_none()
        if not site:
            return None

        return await self._create_alert(
            user_id=site.user_id,
            site_id=site_id,
            alert_type=AlertType.SNAPSHOT_FAILED,
            severity=AlertSeverity.WARNING,
            title="Scheduled snapshot failed",
            message=f"The scheduled monitoring snapshot for {site.domain} failed: {error_message}",
            data={"error": error_message},
        )

    async def _create_alert(
        self,
        user_id: uuid.UUID,
        site_id: uuid.UUID,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        message: str,
        data: dict | None = None,
    ) -> Alert:
        """Create a new alert."""
        alert = Alert(
            user_id=user_id,
            site_id=site_id,
            alert_type=alert_type.value,
            severity=severity.value,
            status=AlertStatus.PENDING.value,
            title=title,
            message=message,
            data=data,
        )
        self.db.add(alert)
        await self.db.flush()
        await self.db.refresh(alert)

        logger.info(
            "alert_created",
            alert_id=str(alert.id),
            alert_type=alert_type.value,
            severity=severity.value,
            site_id=str(site_id),
        )

        return alert

    async def list_alerts(
        self,
        user_id: uuid.UUID,
        site_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Alert], int, int]:
        """List alerts for a user with optional filters.

        Returns: (alerts, total_count, unread_count)
        """
        # Base query
        query = select(Alert).where(Alert.user_id == user_id)

        if site_id:
            query = query.where(Alert.site_id == site_id)

        if status:
            query = query.where(Alert.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        # Get unread count
        unread_query = select(func.count()).where(
            Alert.user_id == user_id,
            Alert.status.in_([AlertStatus.PENDING.value, AlertStatus.SENT.value]),
        )
        unread_result = await self.db.execute(unread_query)
        unread = unread_result.scalar_one()

        # Get paginated results
        result = await self.db.execute(
            query.order_by(Alert.created_at.desc()).limit(limit).offset(offset)
        )
        alerts = list(result.scalars().all())

        return alerts, total, unread

    async def acknowledge_alerts(
        self,
        user_id: uuid.UUID,
        alert_ids: list[uuid.UUID],
    ) -> int:
        """Acknowledge alerts. Returns count of updated alerts."""
        from sqlalchemy import update

        result = await self.db.execute(
            update(Alert)
            .where(
                Alert.user_id == user_id,
                Alert.id.in_(alert_ids),
                Alert.acknowledged_at.is_(None),
            )
            .values(
                status=AlertStatus.ACKNOWLEDGED.value,
                acknowledged_at=datetime.now(UTC),
            )
        )
        return result.rowcount or 0

    async def dismiss_alerts(
        self,
        user_id: uuid.UUID,
        alert_ids: list[uuid.UUID],
    ) -> int:
        """Dismiss alerts. Returns count of updated alerts."""
        from sqlalchemy import update

        result = await self.db.execute(
            update(Alert)
            .where(
                Alert.user_id == user_id,
                Alert.id.in_(alert_ids),
                Alert.dismissed_at.is_(None),
            )
            .values(
                status=AlertStatus.DISMISSED.value,
                dismissed_at=datetime.now(UTC),
            )
        )
        return result.rowcount or 0

    async def get_stats(self, user_id: uuid.UUID) -> dict:
        """Get alert statistics for a user."""
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)

        # Total alerts
        total_result = await self.db.execute(select(func.count()).where(Alert.user_id == user_id))
        total = total_result.scalar_one()

        # Unread count
        unread_result = await self.db.execute(
            select(func.count()).where(
                Alert.user_id == user_id,
                Alert.status.in_([AlertStatus.PENDING.value, AlertStatus.SENT.value]),
            )
        )
        unread = unread_result.scalar_one()

        # By severity
        critical_result = await self.db.execute(
            select(func.count()).where(
                Alert.user_id == user_id,
                Alert.severity == AlertSeverity.CRITICAL.value,
                Alert.status.in_([AlertStatus.PENDING.value, AlertStatus.SENT.value]),
            )
        )
        critical = critical_result.scalar_one()

        warning_result = await self.db.execute(
            select(func.count()).where(
                Alert.user_id == user_id,
                Alert.severity == AlertSeverity.WARNING.value,
                Alert.status.in_([AlertStatus.PENDING.value, AlertStatus.SENT.value]),
            )
        )
        warning = warning_result.scalar_one()

        info_result = await self.db.execute(
            select(func.count()).where(
                Alert.user_id == user_id,
                Alert.severity == AlertSeverity.INFO.value,
                Alert.status.in_([AlertStatus.PENDING.value, AlertStatus.SENT.value]),
            )
        )
        info = info_result.scalar_one()

        # Today
        today_result = await self.db.execute(
            select(func.count()).where(
                Alert.user_id == user_id,
                Alert.created_at >= today_start,
            )
        )
        today = today_result.scalar_one()

        # This week
        week_result = await self.db.execute(
            select(func.count()).where(
                Alert.user_id == user_id,
                Alert.created_at >= week_start,
            )
        )
        week = week_result.scalar_one()

        return {
            "total_alerts": total,
            "unread_count": unread,
            "critical_count": critical,
            "warning_count": warning,
            "info_count": info,
            "alerts_today": today,
            "alerts_this_week": week,
        }
