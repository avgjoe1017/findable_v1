"""Conclude the running A/B experiment and optionally activate winner."""

import argparse
import asyncio
import sys

sys.path.insert(0, "c:/Users/joeba/Documents/findable")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.config import get_settings
from api.models.calibration import CalibrationExperiment, ExperimentStatus
from worker.calibration.experiment import conclude_experiment


async def main(activate_winner: bool = False):
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Get running experiment
        result = await session.execute(
            select(CalibrationExperiment).where(
                CalibrationExperiment.status == ExperimentStatus.RUNNING.value
            )
        )
        experiment = result.scalar_one_or_none()

        if not experiment:
            print("No running experiment found.")
            return

        print(f"Found running experiment: {experiment.name}")
        print(f"ID: {experiment.id}")
        print()

    # Conclude the experiment
    result = await conclude_experiment(experiment.id, activate_winner=activate_winner)

    if "error" in result:
        print(f"ERROR: {result['error']}")
        if "control_samples" in result:
            print(f"  Control samples: {result['control_samples']}")
            print(f"  Treatment samples: {result['treatment_samples']}")
            print(f"  Min required: {result['min_required']}")
        return

    print("=" * 70)
    print("EXPERIMENT CONCLUDED")
    print("=" * 70)
    print(f"Winner: {result['winner']}")
    print(f"Reason: {result['winner_reason']}")
    print(f"Significant: {result['is_significant']}")
    print()
    print(f"Control accuracy: {result['control_accuracy']:.1%}")
    print(f"Treatment accuracy: {result['treatment_accuracy']:.1%}")
    print()

    if result.get("activated_config_id"):
        print(f"ACTIVATED CONFIG: {result['activated_config_id']}")
        print("The winning config is now active and will be used for all new audits.")
    elif result["winner"] != "none":
        print("To activate the winner:")
        print("  python scripts/conclude_experiment.py --activate")

    print("=" * 70)

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Conclude A/B experiment")
    parser.add_argument(
        "--activate",
        action="store_true",
        help="Activate the winning config",
    )
    args = parser.parse_args()

    asyncio.run(main(activate_winner=args.activate))
