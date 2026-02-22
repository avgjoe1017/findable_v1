"""Integration tests for the calibration flow.

These tests verify the full calibration pipeline:
1. Sample collection from observation results
2. Analysis of collected samples
3. Optimization based on samples
4. Config management and activation

Note: These tests require a running PostgreSQL database.
Run with: pytest tests/integration/test_calibration_flow.py -v -m integration
"""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set environment before imports (use CI-compatible credentials when not overridden)
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/findable_test"
os.environ.setdefault("ENV", "test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-ci")


def _make_session_maker() -> async_sessionmaker[AsyncSession]:
    """Create a fresh async session maker for the current event loop."""
    db_url = os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/findable_test"
    )
    engine = create_async_engine(db_url, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _create_test_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Create a test user if it doesn't exist (needed for FK chain)."""
    from sqlalchemy import select

    from api.models.user import User

    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        user = User(
            id=user_id,
            email=f"test-{user_id.hex[:8]}@test.local",
            hashed_password="not_a_real_password",
            name="Test User",
        )
        db.add(user)
        await db.flush()


async def _create_test_site(db: AsyncSession, site_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Create a test site if it doesn't exist (needed for FK chain)."""
    from sqlalchemy import select

    from api.models.site import Site

    result = await db.execute(select(Site).where(Site.id == site_id))
    if not result.scalar_one_or_none():
        site = Site(
            id=site_id,
            user_id=user_id,
            domain="test-integration.example.com",
            name="Test Integration Site",
            business_model="unknown",
        )
        db.add(site)
        await db.flush()


async def _create_test_run(db: AsyncSession, run_id: uuid.UUID, site_id: uuid.UUID) -> None:
    """Create a test run if it doesn't exist (needed for FK chain)."""
    from sqlalchemy import select

    from api.models.run import Run

    result = await db.execute(select(Run).where(Run.id == run_id))
    if not result.scalar_one_or_none():
        run = Run(
            id=run_id,
            site_id=site_id,
            run_type="starter_audit",
            status="complete",
        )
        db.add(run)
        await db.flush()


async def _setup_fk_chain(
    db: AsyncSession,
    user_id: uuid.UUID,
    site_id: uuid.UUID,
    run_id: uuid.UUID,
) -> None:
    """Create the full User -> Site -> Run FK chain for CalibrationSample tests."""
    await _create_test_user(db, user_id)
    await _create_test_site(db, site_id, user_id)
    await _create_test_run(db, run_id, site_id)
    await db.flush()


async def _cleanup_fk_chain(
    db: AsyncSession,
    user_id: uuid.UUID,
    site_id: uuid.UUID,
    run_id: uuid.UUID,
) -> None:
    """Clean up FK chain in reverse order (Run -> Site -> User)."""
    from api.models.run import Run
    from api.models.site import Site
    from api.models.user import User

    await db.execute(delete(Run).where(Run.id == run_id))
    await db.execute(delete(Site).where(Site.id == site_id))
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_calibration_sample_creation():
    """Test creating and querying calibration samples."""
    from sqlalchemy import select

    from api.models.calibration import CalibrationSample, OutcomeMatch

    session_maker = _make_session_maker()
    sample_id = uuid.uuid4()
    user_id = uuid.uuid4()
    site_id = uuid.uuid4()
    run_id = uuid.uuid4()

    async with session_maker() as db:
        # Set up FK chain: User -> Site -> Run
        await _setup_fk_chain(db, user_id, site_id, run_id)

        # Create a calibration sample
        sample = CalibrationSample(
            id=sample_id,
            site_id=site_id,
            run_id=run_id,
            question_id="q_test_123",
            question_text="What is the test question?",
            question_category="general",
            question_difficulty="medium",
            sim_answerability="fully_answerable",
            sim_score=0.85,
            sim_signals_found=8,
            sim_signals_total=10,
            sim_relevance_score=0.8,
            obs_mentioned=True,
            obs_cited=True,
            obs_provider="test_provider",
            obs_model="test_model",
            outcome_match=OutcomeMatch.CORRECT.value,
            prediction_accurate=True,
            pillar_scores={
                "technical": 85.0,
                "structure": 80.0,
                "schema": 75.0,
                "authority": 70.0,
                "entity_recognition": 65.0,
                "retrieval": 90.0,
                "coverage": 85.0,
            },
        )
        db.add(sample)
        await db.commit()

        # Query the sample back
        result = await db.execute(
            select(CalibrationSample).where(CalibrationSample.id == sample_id)
        )
        fetched = result.scalar_one()

        assert fetched.sim_score == 0.85
        assert fetched.obs_mentioned is True
        assert fetched.prediction_accurate is True
        assert fetched.pillar_scores["retrieval"] == 90.0
        assert fetched.pillar_scores["entity_recognition"] == 65.0

        # Clean up (samples first due to FK, then chain)
        await db.execute(delete(CalibrationSample).where(CalibrationSample.id == sample_id))
        await db.commit()
        await _cleanup_fk_chain(db, user_id, site_id, run_id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_calibration_config_lifecycle():
    """Test creating, validating, and activating calibration configs."""
    from sqlalchemy import select, update

    from api.models.calibration import CalibrationConfig

    session_maker = _make_session_maker()
    config_id = uuid.uuid4()

    async with session_maker() as db:
        # Clean up
        await db.execute(delete(CalibrationConfig).where(CalibrationConfig.id == config_id))
        await db.commit()

        # Create a draft config with 7-pillar weights
        config = CalibrationConfig(
            id=config_id,
            name="test_integration_config",
            description="Integration test config",
            weight_technical=12.0,
            weight_structure=18.0,
            weight_schema=13.0,
            weight_authority=12.0,
            weight_entity_recognition=13.0,
            weight_retrieval=22.0,
            weight_coverage=10.0,
            threshold_fully_answerable=0.70,
            threshold_partially_answerable=0.30,
            is_active=False,
        )
        db.add(config)
        await db.commit()

        # Verify weights sum to 100
        result = await db.execute(
            select(CalibrationConfig).where(CalibrationConfig.id == config_id)
        )
        fetched = result.scalar_one()

        weights = fetched.weights
        assert sum(weights.values()) == 100.0
        assert weights["entity_recognition"] == 13.0

        # Validate weights
        errors = fetched.validate_weights()
        assert len(errors) == 0

        # Activate the config
        await db.execute(
            update(CalibrationConfig)
            .where(CalibrationConfig.id == config_id)
            .values(is_active=True, activated_at=datetime.now(UTC))
        )
        await db.commit()

        # Verify activation
        result = await db.execute(
            select(CalibrationConfig).where(CalibrationConfig.id == config_id)
        )
        fetched = result.scalar_one()
        assert fetched.is_active is True

        # Clean up
        await db.execute(delete(CalibrationConfig).where(CalibrationConfig.id == config_id))
        await db.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_calibration_experiment_flow():
    """Test the A/B experiment lifecycle."""
    from sqlalchemy import select

    from api.models.calibration import (
        CalibrationConfig,
        CalibrationExperiment,
        ExperimentStatus,
    )

    session_maker = _make_session_maker()
    control_id = uuid.uuid4()
    treatment_id = uuid.uuid4()
    experiment_id = uuid.uuid4()

    async with session_maker() as db:
        # Clean up
        await db.execute(
            delete(CalibrationExperiment).where(CalibrationExperiment.id == experiment_id)
        )
        await db.execute(
            delete(CalibrationConfig).where(CalibrationConfig.id.in_([control_id, treatment_id]))
        )
        await db.commit()

        # Create control config
        control = CalibrationConfig(
            id=control_id,
            name="control_config",
            weight_technical=12.0,
            weight_structure=18.0,
            weight_schema=13.0,
            weight_authority=12.0,
            weight_entity_recognition=13.0,
            weight_retrieval=22.0,
            weight_coverage=10.0,
            is_active=True,
        )
        db.add(control)

        # Create treatment config (optimized weights)
        treatment = CalibrationConfig(
            id=treatment_id,
            name="treatment_config",
            weight_technical=10.0,
            weight_structure=20.0,
            weight_schema=15.0,
            weight_authority=10.0,
            weight_entity_recognition=15.0,
            weight_retrieval=20.0,
            weight_coverage=10.0,
            is_active=False,
        )
        db.add(treatment)
        await db.flush()

        # Create experiment
        experiment = CalibrationExperiment(
            id=experiment_id,
            name="Test Experiment",
            description="Integration test experiment",
            control_config_id=control_id,
            treatment_config_id=treatment_id,
            treatment_allocation=0.1,
            status=ExperimentStatus.DRAFT.value,
            min_samples_per_arm=100,
        )
        db.add(experiment)
        await db.commit()

        # Verify experiment created
        result = await db.execute(
            select(CalibrationExperiment).where(CalibrationExperiment.id == experiment_id)
        )
        fetched = result.scalar_one()

        assert fetched.status == "draft"
        assert fetched.treatment_allocation == 0.1
        assert fetched.control_config_id == control_id

        # Clean up
        await db.execute(
            delete(CalibrationExperiment).where(CalibrationExperiment.id == experiment_id)
        )
        await db.execute(
            delete(CalibrationConfig).where(CalibrationConfig.id.in_([control_id, treatment_id]))
        )
        await db.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_calibration_drift_alert_creation():
    """Test creating and managing drift alerts."""
    from sqlalchemy import select

    from api.models.calibration import CalibrationDriftAlert, DriftAlertStatus

    session_maker = _make_session_maker()
    alert_id = uuid.uuid4()

    async with session_maker() as db:
        # Clean up
        await db.execute(delete(CalibrationDriftAlert).where(CalibrationDriftAlert.id == alert_id))
        await db.commit()

        # Create a drift alert
        alert = CalibrationDriftAlert(
            id=alert_id,
            drift_type="accuracy",
            expected_value=0.75,
            observed_value=0.60,
            drift_magnitude=0.15,
            sample_window_start=datetime.now(UTC) - timedelta(days=7),
            sample_window_end=datetime.now(UTC),
            sample_count=100,
            status=DriftAlertStatus.OPEN.value,
        )
        db.add(alert)
        await db.commit()

        # Query the alert
        result = await db.execute(
            select(CalibrationDriftAlert).where(CalibrationDriftAlert.id == alert_id)
        )
        fetched = result.scalar_one()

        assert fetched.drift_type == "accuracy"
        assert fetched.drift_magnitude == 0.15
        assert fetched.status == "open"

        # Clean up
        await db.execute(delete(CalibrationDriftAlert).where(CalibrationDriftAlert.id == alert_id))
        await db.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_sample_pillar_score_aggregation():
    """Test that pillar scores can be aggregated across samples."""
    from sqlalchemy import select

    from api.models.calibration import CalibrationSample, OutcomeMatch

    session_maker = _make_session_maker()
    user_id = uuid.uuid4()
    site_id = uuid.uuid4()
    run_id = uuid.uuid4()
    sample_ids = [uuid.uuid4() for _ in range(5)]

    async with session_maker() as db:
        # Set up FK chain: User -> Site -> Run
        await _setup_fk_chain(db, user_id, site_id, run_id)

        # Create multiple samples with varying scores
        pillar_scores_list = [
            {
                "technical": 80,
                "structure": 70,
                "schema": 60,
                "authority": 50,
                "entity_recognition": 40,
                "retrieval": 90,
                "coverage": 80,
            },
            {
                "technical": 85,
                "structure": 75,
                "schema": 65,
                "authority": 55,
                "entity_recognition": 45,
                "retrieval": 85,
                "coverage": 85,
            },
            {
                "technical": 90,
                "structure": 80,
                "schema": 70,
                "authority": 60,
                "entity_recognition": 50,
                "retrieval": 80,
                "coverage": 90,
            },
            {
                "technical": 75,
                "structure": 65,
                "schema": 55,
                "authority": 45,
                "entity_recognition": 35,
                "retrieval": 95,
                "coverage": 75,
            },
            {
                "technical": 70,
                "structure": 60,
                "schema": 50,
                "authority": 40,
                "entity_recognition": 30,
                "retrieval": 100,
                "coverage": 70,
            },
        ]

        for i, (sid, scores) in enumerate(zip(sample_ids, pillar_scores_list, strict=False)):
            sample = CalibrationSample(
                id=sid,
                site_id=site_id,
                run_id=run_id,
                question_id=f"q_test_{i}",
                question_text=f"Test question {i}",
                question_category="general",
                question_difficulty="medium",
                sim_answerability="fully_answerable",
                sim_score=0.8 + i * 0.02,
                sim_signals_found=8,
                sim_signals_total=10,
                sim_relevance_score=0.7,
                obs_mentioned=True,
                obs_cited=i % 2 == 0,
                obs_provider="test_provider",
                obs_model="test_model",
                outcome_match=OutcomeMatch.CORRECT.value,
                prediction_accurate=True,
                pillar_scores=scores,
            )
            db.add(sample)

        await db.commit()

        # Query and verify samples
        result = await db.execute(
            select(CalibrationSample).where(CalibrationSample.site_id == site_id)
        )
        samples = result.scalars().all()

        assert len(samples) == 5

        # Calculate average retrieval score
        avg_retrieval = sum(s.pillar_scores["retrieval"] for s in samples) / len(samples)
        assert avg_retrieval == 90.0  # (90 + 85 + 80 + 95 + 100) / 5

        # Calculate average entity_recognition score
        avg_entity = sum(s.pillar_scores["entity_recognition"] for s in samples) / len(samples)
        assert avg_entity == 40.0  # (40 + 45 + 50 + 35 + 30) / 5

        # Clean up (samples first due to FK, then chain)
        for sid in sample_ids:
            await db.execute(delete(CalibrationSample).where(CalibrationSample.id == sid))
        await db.commit()
        await _cleanup_fk_chain(db, user_id, site_id, run_id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_outcome_match_distribution():
    """Test querying samples by outcome match type."""
    from sqlalchemy import func, select

    from api.models.calibration import CalibrationSample, OutcomeMatch

    session_maker = _make_session_maker()
    user_id = uuid.uuid4()
    site_id = uuid.uuid4()
    run_id = uuid.uuid4()
    sample_ids = [uuid.uuid4() for _ in range(6)]

    async with session_maker() as db:
        # Set up FK chain: User -> Site -> Run
        await _setup_fk_chain(db, user_id, site_id, run_id)

        # Create samples with different outcomes
        outcomes = [
            OutcomeMatch.CORRECT,
            OutcomeMatch.CORRECT,
            OutcomeMatch.CORRECT,
            OutcomeMatch.OPTIMISTIC,
            OutcomeMatch.PESSIMISTIC,
            OutcomeMatch.UNKNOWN,
        ]

        for sid, outcome in zip(sample_ids, outcomes, strict=False):
            sample = CalibrationSample(
                id=sid,
                site_id=site_id,
                run_id=run_id,
                question_id=f"q_{sid}",
                question_text="Test question",
                question_category="general",
                question_difficulty="medium",
                sim_answerability="fully_answerable",
                sim_score=0.8,
                sim_signals_found=8,
                sim_signals_total=10,
                sim_relevance_score=0.7,
                obs_mentioned=outcome != OutcomeMatch.UNKNOWN,
                obs_cited=outcome == OutcomeMatch.CORRECT,
                obs_provider="test_provider",
                obs_model="test_model",
                outcome_match=outcome.value,
                prediction_accurate=outcome == OutcomeMatch.CORRECT,
                pillar_scores={
                    "technical": 80,
                    "structure": 70,
                    "schema": 60,
                    "authority": 50,
                    "entity_recognition": 40,
                    "retrieval": 90,
                    "coverage": 80,
                },
            )
            db.add(sample)

        await db.commit()

        # Count by outcome
        correct_result = await db.execute(
            select(func.count(CalibrationSample.id)).where(
                CalibrationSample.site_id == site_id,
                CalibrationSample.outcome_match == OutcomeMatch.CORRECT.value,
            )
        )
        correct_count = correct_result.scalar()
        assert correct_count == 3

        # Count accurate predictions
        accurate_result = await db.execute(
            select(func.count(CalibrationSample.id)).where(
                CalibrationSample.site_id == site_id,
                CalibrationSample.prediction_accurate == True,  # noqa: E712
            )
        )
        accurate_count = accurate_result.scalar()
        assert accurate_count == 3

        # Clean up (samples first due to FK, then chain)
        for sid in sample_ids:
            await db.execute(delete(CalibrationSample).where(CalibrationSample.id == sid))
        await db.commit()
        await _cleanup_fk_chain(db, user_id, site_id, run_id)
