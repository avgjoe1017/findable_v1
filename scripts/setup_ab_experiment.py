"""Set up A/B experiment: default weights vs optimized weights."""

import asyncio
import sys

sys.path.insert(0, "c:/Users/joeba/Documents/findable")

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.config import get_settings
from api.models.calibration import (
    CalibrationConfig,
    CalibrationConfigStatus,
    CalibrationExperiment,
    ExperimentStatus,
)
from worker.calibration.experiment import start_experiment


async def main():
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. Check if default config exists, create if not
        print("1. Checking for default config...")
        result = await session.execute(
            select(CalibrationConfig).where(CalibrationConfig.name == "default_v2")
        )
        control_config = result.scalar_one_or_none()

        if not control_config:
            print("   Creating default_v2 config...")
            control_config = CalibrationConfig(
                id=uuid4(),
                name="default_v2",
                description="Default pillar weights for A/B experiment control",
                status=CalibrationConfigStatus.VALIDATED.value,
                is_active=False,
                # Default weights
                weight_technical=12.0,
                weight_structure=18.0,
                weight_schema=13.0,
                weight_authority=12.0,
                weight_entity_recognition=13.0,
                weight_retrieval=22.0,
                weight_coverage=10.0,
                # Thresholds
                threshold_fully_answerable=0.7,
                threshold_partially_answerable=0.3,
                threshold_signal_match=0.6,
                # Scoring weights
                scoring_relevance_weight=0.4,
                scoring_signal_weight=0.4,
                scoring_confidence_weight=0.2,
            )
            session.add(control_config)
            await session.commit()
            print(f"   Created: {control_config.id}")
        else:
            print(f"   Found: {control_config.id}")

        print(f"   Control weights: {control_config.weights}")

        # 2. Get the optimized config (treatment)
        print("\n2. Getting optimized config (treatment)...")
        result = await session.execute(
            select(CalibrationConfig).where(CalibrationConfig.name == "optimized_v2_2026_02")
        )
        treatment_config = result.scalar_one_or_none()

        if not treatment_config:
            print("   ERROR: optimized_v2_2026_02 config not found!")
            return

        print(f"   Found: {treatment_config.id}")
        print(f"   Treatment weights: {treatment_config.weights}")

        # 3. Check for existing running experiment
        print("\n3. Checking for running experiments...")
        result = await session.execute(
            select(CalibrationExperiment).where(
                CalibrationExperiment.status == ExperimentStatus.RUNNING.value
            )
        )
        running = result.scalar_one_or_none()

        if running:
            print(f"   Experiment already running: {running.id}")
            print(f"   Name: {running.name}")
            print(f"   Started: {running.started_at}")
            print(f"   Control samples: {running.control_samples}")
            print(f"   Treatment samples: {running.treatment_samples}")
            return

        # 4. Create the experiment
        print("\n4. Creating experiment...")
        experiment = CalibrationExperiment(
            id=uuid4(),
            name="Default vs Optimized Weights (Feb 2026)",
            description=(
                "A/B test comparing default pillar weights vs optimized weights "
                "(authority=35%, schema=25%). Optimized weights were derived from "
                "531 calibration samples with 85.9% holdout accuracy."
            ),
            control_config_id=control_config.id,
            treatment_config_id=treatment_config.id,
            treatment_allocation=0.5,  # 50/50 split for faster results
            status=ExperimentStatus.DRAFT.value,
            min_samples_per_arm=100,
        )
        session.add(experiment)
        await session.commit()
        print(f"   Created: {experiment.id}")

        # 5. Start the experiment
        print("\n5. Starting experiment...")

    # Use the async function from experiment module
    result = await start_experiment(experiment.id)
    print(f"   Result: {result}")

    if result.get("status") == "running":
        print("\n" + "=" * 60)
        print("EXPERIMENT STARTED SUCCESSFULLY")
        print("=" * 60)
        print(f"Experiment ID: {experiment.id}")
        print(f"Name: {experiment.name}")
        print("Treatment allocation: 50%")
        print("Min samples per arm: 100")
        print()
        print("Arms:")
        print("  Control: default_v2 (standard weights)")
        print("  Treatment: optimized_v2_2026_02 (authority=35%, schema=25%)")
        print()
        print("Next steps:")
        print("  1. Run audits on diverse sites to collect samples")
        print("  2. Monitor with: python scripts/check_experiment.py")
        print("  3. Conclude when 100 samples per arm reached")
        print("=" * 60)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
