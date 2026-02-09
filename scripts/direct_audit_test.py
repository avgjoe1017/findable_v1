"""Direct audit test - bypasses queue to test calibration sample collection."""

import argparse
import asyncio
import sys

sys.path.insert(0, "c:/Users/joeba/Documents/findable")

from uuid import NAMESPACE_DNS, uuid4, uuid5

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.config import get_settings
from api.models.calibration import CalibrationSample
from api.models.run import Run
from api.models.site import Site
from api.models.user import User
from worker.calibration.experiment import get_experiment_arm
from worker.scoring.calculator_v2 import get_cached_config_name, load_active_calibration_weights
from worker.tasks.audit import run_audit


async def main(domain: str = "example.com", site_name: str = "Test Site"):
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Load active calibration weights from DB
    print("Loading calibration weights...")
    weights = await load_active_calibration_weights()
    config_name = get_cached_config_name()
    print(f"Using calibration config: {config_name or 'default'}")
    print(f"Weights: {weights}")
    print()

    print(f"Testing domain: {domain}")

    # Use deterministic site_id based on domain for consistent experiment assignment
    site_id = uuid5(NAMESPACE_DNS, domain)
    run_id = uuid4()
    user_id = uuid4()

    # Show experiment arm assignment
    arm = get_experiment_arm(site_id, treatment_allocation=0.5)
    print(f"Experiment arm: {arm.value.upper()}")
    print()

    async with async_session() as session:
        # Check if site already exists
        existing_site = await session.execute(select(Site).where(Site.id == site_id))
        existing = existing_site.scalar_one_or_none()

        if existing:
            print(f"Reusing existing site: {site_id}")
            user_id = existing.user_id
        else:
            # Create user first
            user = User(
                id=user_id,
                email=f"test_{site_id.hex[:8]}@example.com",
                hashed_password="dummy",
                name="Test User",
            )
            session.add(user)

            # Create site
            site = Site(
                id=site_id,
                user_id=user_id,
                domain=domain,
                name=site_name,
                business_model="unknown",
            )
            session.add(site)
            print(f"Created site: {site_id}")

        # Create run
        run = Run(
            id=run_id,
            site_id=site_id,
            run_type="starter_audit",
            status="queued",
            config={
                "include_observation": True,
                "include_benchmark": False,
                "bands": ["conservative", "typical", "generous"],
                "provider": {"preferred": "router", "model": "auto"},
            },
        )
        session.add(run)
        await session.commit()
        print(f"Created run: {run_id}")

    # Run the audit directly (not through queue)
    print("\nRunning audit directly...")
    try:
        result = await run_audit(run_id, site_id)
        print("\nAudit completed!")
        print(f"Score: {result.get('score', 'N/A')}")
        print(f"Grade: {result.get('grade', 'N/A')}")
    except Exception as e:
        print(f"\nAudit failed: {e}")
        import traceback

        traceback.print_exc()
        return

    # Check for calibration samples
    print("\nChecking calibration samples...")
    async with async_session() as session:
        result = await session.execute(
            select(func.count())
            .select_from(CalibrationSample)
            .where(CalibrationSample.run_id == run_id)
        )
        count = result.scalar()
        print(f"Samples collected for this run: {count}")

        if count > 0:
            result = await session.execute(
                select(CalibrationSample).where(CalibrationSample.run_id == run_id).limit(3)
            )
            samples = result.scalars().all()
            for sample in samples:
                print("---")
                print(f"Question: {sample.question_text[:60]}...")
                print(f"Sim: {sample.sim_answerability}")
                print(f"Obs: mentioned={sample.obs_mentioned}, cited={sample.obs_cited}")
                print(f"Match: {sample.outcome_match}")

    await engine.dispose()
    print("\nDone!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run audit test on a domain")
    parser.add_argument("domain", nargs="?", default="example.com", help="Domain to audit")
    parser.add_argument("--name", default=None, help="Site name (defaults to domain)")
    args = parser.parse_args()

    site_name = args.name or args.domain.replace("www.", "").split(".")[0].title()
    asyncio.run(main(domain=args.domain, site_name=site_name))
