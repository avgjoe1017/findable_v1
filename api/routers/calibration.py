"""Calibration management endpoints.

Provides API endpoints for:
- Querying calibration samples
- Viewing calibration analysis/metrics
- Managing calibration configurations
- Managing A/B experiments
- Viewing drift alerts
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from api.auth import CurrentUser
from api.database import DbSession
from api.models.calibration import (
    CalibrationConfig,
    CalibrationConfigStatus,
    CalibrationDriftAlert,
    CalibrationSample,
    DriftAlertStatus,
)
from api.schemas.calibration import (
    AnswerabilityAccuracy,
    CalibrationAnalysisResponse,
    CalibrationConfigCreate,
    CalibrationConfigListResponse,
    CalibrationConfigResponse,
    CalibrationDetailedAnalysisResponse,
    CalibrationRecommendation,
    CalibrationSampleListResponse,
    CalibrationSampleResponse,
    CalibrationSummaryResponse,
    DriftAlertListResponse,
    DriftAlertResolve,
    DriftAlertResponse,
    OutcomeCounts,
    PillarCorrelation,
    ProviderAccuracy,
)
from api.schemas.responses import SuccessResponse

router = APIRouter(prefix="/calibration", tags=["calibration"])


# ============================================================================
# Calibration Samples Endpoints
# ============================================================================


@router.get(
    "/samples",
    response_model=SuccessResponse[CalibrationSampleListResponse],
    summary="Query calibration samples",
)
async def list_calibration_samples(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=200),
    outcome_match: str | None = Query(
        default=None, description="Filter by outcome: correct, optimistic, pessimistic"
    ),
    category: str | None = Query(default=None, description="Filter by question category"),
    days: int = Query(default=30, ge=1, le=365, description="Look back N days"),
) -> SuccessResponse[CalibrationSampleListResponse]:
    """
    Query calibration samples with filters.

    Requires superuser access for now (calibration is admin-only).
    """
    # Check if user is superuser
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Calibration access requires admin privileges",
        )

    # Build query
    window_start = datetime.now(UTC) - timedelta(days=days)
    query = select(CalibrationSample).where(CalibrationSample.created_at >= window_start)

    if outcome_match:
        query = query.where(CalibrationSample.outcome_match == outcome_match)
    if category:
        query = query.where(CalibrationSample.question_category == category)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    query = query.order_by(CalibrationSample.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    samples = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size

    return SuccessResponse(
        data=CalibrationSampleListResponse(
            samples=[CalibrationSampleResponse.model_validate(s) for s in samples],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    )


# ============================================================================
# Calibration Analysis Endpoints
# ============================================================================


@router.get(
    "/analysis",
    response_model=SuccessResponse[CalibrationAnalysisResponse],
    summary="Get calibration analysis",
)
async def get_calibration_analysis(
    db: DbSession,
    user: CurrentUser,
    days: int = Query(default=30, ge=7, le=365, description="Analysis window in days"),
    min_samples: int = Query(default=100, ge=50, le=1000, description="Minimum samples required"),
) -> SuccessResponse[CalibrationAnalysisResponse]:
    """
    Get current calibration analysis including accuracy and bias metrics.
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Calibration access requires admin privileges",
        )

    window_start = datetime.now(UTC) - timedelta(days=days)

    # Count total samples
    total_count_result = await db.execute(
        select(func.count(CalibrationSample.id)).where(CalibrationSample.created_at >= window_start)
    )
    total_samples = total_count_result.scalar() or 0

    if total_samples < min_samples:
        return SuccessResponse(
            data=CalibrationAnalysisResponse(
                total_samples=total_samples,
                sufficient_data=False,
                min_required=min_samples,
            )
        )

    # Count by outcome
    outcome_results = await db.execute(
        select(
            CalibrationSample.outcome_match,
            func.count(CalibrationSample.id),
        )
        .where(CalibrationSample.created_at >= window_start)
        .group_by(CalibrationSample.outcome_match)
    )
    outcome_counts_raw = dict(outcome_results.fetchall())

    correct = outcome_counts_raw.get("correct", 0)
    optimistic = outcome_counts_raw.get("optimistic", 0)
    pessimistic = outcome_counts_raw.get("pessimistic", 0)
    unknown = outcome_counts_raw.get("unknown", 0)

    known_samples = total_samples - unknown
    prediction_accuracy = correct / known_samples if known_samples > 0 else 0.0
    optimism_bias = optimistic / known_samples if known_samples > 0 else 0.0
    pessimism_bias = pessimistic / known_samples if known_samples > 0 else 0.0

    # Accuracy by category
    category_results = await db.execute(
        select(
            CalibrationSample.question_category,
            func.count(CalibrationSample.id).filter(CalibrationSample.prediction_accurate),
            func.count(CalibrationSample.id),
        )
        .where(CalibrationSample.created_at >= window_start)
        .where(CalibrationSample.outcome_match != "unknown")
        .group_by(CalibrationSample.question_category)
    )
    accuracy_by_category = {}
    for row in category_results.fetchall():
        cat_accurate = row[1] or 0
        cat_total = row[2] or 0
        if cat_total > 0:
            accuracy_by_category[row[0]] = round(cat_accurate / cat_total, 3)

    # Accuracy by difficulty
    difficulty_results = await db.execute(
        select(
            CalibrationSample.question_difficulty,
            func.count(CalibrationSample.id).filter(CalibrationSample.prediction_accurate),
            func.count(CalibrationSample.id),
        )
        .where(CalibrationSample.created_at >= window_start)
        .where(CalibrationSample.outcome_match != "unknown")
        .group_by(CalibrationSample.question_difficulty)
    )
    accuracy_by_difficulty = {}
    for row in difficulty_results.fetchall():
        diff_accurate = row[1] or 0
        diff_total = row[2] or 0
        if diff_total > 0:
            accuracy_by_difficulty[row[0]] = round(diff_accurate / diff_total, 3)

    return SuccessResponse(
        data=CalibrationAnalysisResponse(
            total_samples=total_samples,
            sufficient_data=True,
            min_required=min_samples,
            known_samples=known_samples,
            prediction_accuracy=round(prediction_accuracy, 3),
            optimism_bias=round(optimism_bias, 3),
            pessimism_bias=round(pessimism_bias, 3),
            outcome_counts=OutcomeCounts(
                correct=correct,
                optimistic=optimistic,
                pessimistic=pessimistic,
                unknown=unknown,
            ),
            accuracy_by_category=accuracy_by_category,
            accuracy_by_difficulty=accuracy_by_difficulty,
            window_start=window_start,
            window_days=days,
        )
    )


@router.get(
    "/analysis/detailed",
    response_model=SuccessResponse[CalibrationDetailedAnalysisResponse],
    summary="Get detailed calibration analysis with pillar correlations",
)
async def get_calibration_analysis_detailed(
    user: CurrentUser,
    days: int = Query(default=30, ge=7, le=365, description="Analysis window in days"),
    min_samples: int = Query(default=50, ge=20, le=500, description="Minimum samples required"),
) -> SuccessResponse[CalibrationDetailedAnalysisResponse]:
    """
    Get detailed calibration analysis including:
    - Basic metrics (accuracy, bias)
    - Accuracy by answerability level
    - Accuracy by provider/model
    - Pillar score correlations with outcomes
    - Actionable recommendations
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Calibration access requires admin privileges",
        )

    # Import here to avoid circular imports
    from worker.tasks.calibration import analyze_calibration_detailed

    analysis = await analyze_calibration_detailed(
        window_days=days,
        min_samples=min_samples,
    )

    if not analysis.get("sufficient_data"):
        return SuccessResponse(
            data=CalibrationDetailedAnalysisResponse(
                total_samples=analysis.get("total_samples", 0),
                sufficient_data=False,
                min_required=min_samples,
            )
        )

    # Transform nested dicts to typed models
    accuracy_by_answerability = None
    if analysis.get("accuracy_by_answerability"):
        accuracy_by_answerability = {
            k: AnswerabilityAccuracy(**v) for k, v in analysis["accuracy_by_answerability"].items()
        }

    accuracy_by_provider = None
    if analysis.get("accuracy_by_provider"):
        accuracy_by_provider = {
            k: ProviderAccuracy(**v) for k, v in analysis["accuracy_by_provider"].items()
        }

    pillar_correlation = None
    if analysis.get("pillar_correlation"):
        pillar_correlation = {
            k: PillarCorrelation(**v) for k, v in analysis["pillar_correlation"].items()
        }

    recommendations = None
    if analysis.get("recommendations"):
        recommendations = [CalibrationRecommendation(**r) for r in analysis["recommendations"]]

    outcome_counts = None
    if analysis.get("outcome_counts"):
        outcome_counts = OutcomeCounts(**analysis["outcome_counts"])

    return SuccessResponse(
        data=CalibrationDetailedAnalysisResponse(
            total_samples=analysis.get("total_samples", 0),
            sufficient_data=True,
            min_required=min_samples,
            known_samples=analysis.get("known_samples"),
            prediction_accuracy=analysis.get("prediction_accuracy"),
            optimism_bias=analysis.get("optimism_bias"),
            pessimism_bias=analysis.get("pessimism_bias"),
            outcome_counts=outcome_counts,
            accuracy_by_category=analysis.get("accuracy_by_category"),
            accuracy_by_difficulty=analysis.get("accuracy_by_difficulty"),
            window_start=analysis.get("window_start"),
            window_days=analysis.get("window_days"),
            accuracy_by_answerability=accuracy_by_answerability,
            accuracy_by_provider=accuracy_by_provider,
            pillar_correlation=pillar_correlation,
            recommendations=recommendations,
        )
    )


@router.get(
    "/summary",
    response_model=SuccessResponse[CalibrationSummaryResponse],
    summary="Get calibration summary for dashboards",
)
async def get_calibration_summary_endpoint(
    user: CurrentUser,
) -> SuccessResponse[CalibrationSummaryResponse]:
    """
    Get a concise summary of current calibration state.

    Returns health status and key metrics for quick checks.
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Calibration access requires admin privileges",
        )

    # Import here to avoid circular imports
    from worker.tasks.calibration import get_calibration_summary

    summary = await get_calibration_summary()

    outcome_breakdown = None
    if summary.get("outcome_breakdown"):
        outcome_breakdown = OutcomeCounts(**summary["outcome_breakdown"])

    return SuccessResponse(
        data=CalibrationSummaryResponse(
            status=summary["status"],
            prediction_accuracy=summary.get("prediction_accuracy"),
            optimism_bias=summary.get("optimism_bias"),
            pessimism_bias=summary.get("pessimism_bias"),
            samples_last_7_days=summary.get("samples_last_7_days"),
            samples_collected=summary.get("samples_collected"),
            samples_needed=summary.get("samples_needed"),
            outcome_breakdown=outcome_breakdown,
        )
    )


# ============================================================================
# Calibration Config Endpoints
# ============================================================================


@router.get(
    "/configs",
    response_model=SuccessResponse[CalibrationConfigListResponse],
    summary="List calibration configs",
)
async def list_calibration_configs(
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[CalibrationConfigListResponse]:
    """
    List all calibration configurations.
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Calibration access requires admin privileges",
        )

    result = await db.execute(
        select(CalibrationConfig).order_by(CalibrationConfig.created_at.desc())
    )
    configs = result.scalars().all()

    # Find active config
    active_config_id = None
    for config in configs:
        if config.is_active:
            active_config_id = config.id
            break

    return SuccessResponse(
        data=CalibrationConfigListResponse(
            configs=[CalibrationConfigResponse.model_validate(c) for c in configs],
            active_config_id=active_config_id,
        )
    )


@router.post(
    "/configs",
    response_model=SuccessResponse[CalibrationConfigResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create calibration config",
)
async def create_calibration_config(
    request: CalibrationConfigCreate,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[CalibrationConfigResponse]:
    """
    Create a new calibration configuration (draft status).
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Calibration access requires admin privileges",
        )

    # Check name uniqueness
    existing = await db.execute(
        select(CalibrationConfig).where(CalibrationConfig.name == request.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Config with name '{request.name}' already exists",
        )

    # Validate weights sum to 100 (7-pillar system)
    weights = request.weights
    total_weight = (
        weights.technical
        + weights.structure
        + weights.schema_
        + weights.authority
        + weights.entity_recognition
        + weights.retrieval
        + weights.coverage
    )
    if abs(total_weight - 100.0) > 0.01:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Weights must sum to 100, got {total_weight:.2f}",
        )

    config = CalibrationConfig(
        id=uuid.uuid4(),
        name=request.name,
        description=request.description,
        status=CalibrationConfigStatus.DRAFT.value,
        is_active=False,
        weight_technical=weights.technical,
        weight_structure=weights.structure,
        weight_schema=weights.schema_,
        weight_authority=weights.authority,
        weight_entity_recognition=weights.entity_recognition,
        weight_retrieval=weights.retrieval,
        weight_coverage=weights.coverage,
        threshold_fully_answerable=request.thresholds.fully_answerable,
        threshold_partially_answerable=request.thresholds.partially_answerable,
        notes=request.notes,
        created_by=user.id,
    )

    db.add(config)
    await db.commit()
    await db.refresh(config)

    return SuccessResponse(data=CalibrationConfigResponse.model_validate(config))


@router.get(
    "/configs/{config_id}",
    response_model=SuccessResponse[CalibrationConfigResponse],
    summary="Get calibration config",
)
async def get_calibration_config(
    config_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[CalibrationConfigResponse]:
    """
    Get a specific calibration configuration.
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Calibration access requires admin privileges",
        )

    result = await db.execute(select(CalibrationConfig).where(CalibrationConfig.id == config_id))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config {config_id} not found",
        )

    return SuccessResponse(data=CalibrationConfigResponse.model_validate(config))


@router.post(
    "/configs/{config_id}/activate",
    response_model=SuccessResponse[CalibrationConfigResponse],
    summary="Activate calibration config",
)
async def activate_calibration_config(
    config_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[CalibrationConfigResponse]:
    """
    Activate a calibration configuration.

    Deactivates any currently active config.
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Calibration access requires admin privileges",
        )

    result = await db.execute(select(CalibrationConfig).where(CalibrationConfig.id == config_id))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config {config_id} not found",
        )

    if config.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Config is already active",
        )

    # Deactivate current active config
    current_active_result = await db.execute(
        select(CalibrationConfig).where(CalibrationConfig.is_active == True)  # noqa: E712
    )
    current_active = current_active_result.scalar_one_or_none()
    if current_active:
        current_active.is_active = False
        current_active.status = CalibrationConfigStatus.ARCHIVED.value

    # Activate new config
    config.is_active = True
    config.status = CalibrationConfigStatus.ACTIVE.value
    config.activated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(config)

    return SuccessResponse(data=CalibrationConfigResponse.model_validate(config))


# ============================================================================
# Drift Alert Endpoints
# ============================================================================


@router.get(
    "/drift-alerts",
    response_model=SuccessResponse[DriftAlertListResponse],
    summary="List drift alerts",
)
async def list_drift_alerts(
    db: DbSession,
    user: CurrentUser,
    status_filter: str | None = Query(
        default=None, alias="status", description="Filter by status: open, acknowledged, resolved"
    ),
    days: int = Query(default=30, ge=1, le=365, description="Look back N days"),
) -> SuccessResponse[DriftAlertListResponse]:
    """
    List calibration drift alerts.
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Calibration access requires admin privileges",
        )

    window_start = datetime.now(UTC) - timedelta(days=days)
    query = select(CalibrationDriftAlert).where(CalibrationDriftAlert.created_at >= window_start)

    if status_filter:
        query = query.where(CalibrationDriftAlert.status == status_filter)

    query = query.order_by(CalibrationDriftAlert.created_at.desc())

    result = await db.execute(query)
    alerts = result.scalars().all()

    # Count open alerts
    open_count_result = await db.execute(
        select(func.count(CalibrationDriftAlert.id)).where(
            CalibrationDriftAlert.status == DriftAlertStatus.OPEN.value
        )
    )
    open_count = open_count_result.scalar() or 0

    return SuccessResponse(
        data=DriftAlertListResponse(
            alerts=[DriftAlertResponse.model_validate(a) for a in alerts],
            total=len(alerts),
            open_count=open_count,
        )
    )


@router.post(
    "/drift-alerts/{alert_id}/acknowledge",
    response_model=SuccessResponse[DriftAlertResponse],
    summary="Acknowledge drift alert",
)
async def acknowledge_drift_alert(
    alert_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[DriftAlertResponse]:
    """
    Acknowledge a drift alert.
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Calibration access requires admin privileges",
        )

    result = await db.execute(
        select(CalibrationDriftAlert).where(CalibrationDriftAlert.id == alert_id)
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )

    if alert.status != DriftAlertStatus.OPEN.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Alert is already {alert.status}",
        )

    alert.status = DriftAlertStatus.ACKNOWLEDGED.value
    alert.acknowledged_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(alert)

    return SuccessResponse(data=DriftAlertResponse.model_validate(alert))


@router.post(
    "/drift-alerts/{alert_id}/resolve",
    response_model=SuccessResponse[DriftAlertResponse],
    summary="Resolve drift alert",
)
async def resolve_drift_alert(
    alert_id: uuid.UUID,
    request: DriftAlertResolve,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[DriftAlertResponse]:
    """
    Resolve a drift alert with notes.
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Calibration access requires admin privileges",
        )

    result = await db.execute(
        select(CalibrationDriftAlert).where(CalibrationDriftAlert.id == alert_id)
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )

    if alert.status == DriftAlertStatus.RESOLVED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Alert is already resolved",
        )

    alert.status = DriftAlertStatus.RESOLVED.value
    alert.resolved_by = user.id
    alert.resolution_notes = request.resolution_notes
    alert.resolution_action = request.resolution_action
    alert.resolved_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(alert)

    return SuccessResponse(data=DriftAlertResponse.model_validate(alert))


# ============================================================================
# Optimization Endpoints
# ============================================================================


@router.post(
    "/optimize/weights",
    response_model=SuccessResponse[dict],
    summary="Run weight optimization",
)
async def run_weight_optimization(
    user: CurrentUser,
    window_days: int = Query(default=60, ge=30, le=365, description="Days of samples to use"),
    min_samples: int = Query(default=200, ge=100, le=1000, description="Minimum samples required"),
    min_improvement: float = Query(
        default=0.02, ge=0.01, le=0.10, description="Minimum improvement threshold"
    ),
) -> SuccessResponse[dict]:
    """
    Run pillar weight optimization using grid search.

    Searches for weights that maximize prediction accuracy compared to
    observation outcomes. Uses coarse-then-fine search for efficiency.

    Requires admin privileges.
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Calibration access requires admin privileges",
        )

    from worker.calibration.optimizer import optimize_pillar_weights

    result = await optimize_pillar_weights(
        window_days=window_days,
        min_samples=min_samples,
        min_improvement=min_improvement,
        coarse_then_fine=True,
    )

    return SuccessResponse(data=result.to_dict())


@router.post(
    "/optimize/thresholds",
    response_model=SuccessResponse[dict],
    summary="Run threshold optimization",
)
async def run_threshold_optimization(
    user: CurrentUser,
    window_days: int = Query(default=60, ge=30, le=365, description="Days of samples to use"),
    min_samples: int = Query(default=200, ge=100, le=1000, description="Minimum samples required"),
    min_improvement: float = Query(
        default=0.02, ge=0.01, le=0.10, description="Minimum improvement threshold"
    ),
) -> SuccessResponse[dict]:
    """
    Run answerability threshold optimization using grid search.

    Finds optimal fully_answerable and partially_answerable thresholds
    that best predict observation outcomes.

    Requires admin privileges.
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Calibration access requires admin privileges",
        )

    from worker.calibration.optimizer import optimize_answerability_thresholds

    result = await optimize_answerability_thresholds(
        window_days=window_days,
        min_samples=min_samples,
        min_improvement=min_improvement,
    )

    return SuccessResponse(data=result.to_dict())


@router.post(
    "/configs/{config_id}/validate",
    response_model=SuccessResponse[dict],
    summary="Validate config against samples",
)
async def validate_calibration_config(
    config_id: uuid.UUID,
    user: CurrentUser,
    window_days: int = Query(default=30, ge=7, le=365, description="Days of samples to use"),
    min_samples: int = Query(default=100, ge=50, le=500, description="Minimum samples required"),
) -> SuccessResponse[dict]:
    """
    Validate a calibration config against recent samples.

    Compares the config's accuracy to the default baseline.
    Use this before activating a new config.

    Requires admin privileges.
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Calibration access requires admin privileges",
        )

    from worker.calibration.optimizer import validate_config_improvement

    result = await validate_config_improvement(
        config_id=config_id,
        window_days=window_days,
        min_samples=min_samples,
    )

    if not result.get("valid"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Validation failed"),
        )

    return SuccessResponse(data=result)
