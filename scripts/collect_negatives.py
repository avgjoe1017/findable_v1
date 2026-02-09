"""Run audits on known_uncited sites to collect negative calibration samples.

These sites have good content but are typically NOT cited by AI answer engines.
Collecting these samples balances the training set which is currently 99.75% positive.

Usage:
    # Audit all known_uncited sites
    python scripts/collect_negatives.py

    # Audit a specific site
    python scripts/collect_negatives.py --domain backlinko.com

    # Dry run (show sites without auditing)
    python scripts/collect_negatives.py --dry-run
"""

import argparse
import asyncio
import io
import sys

# Fix Windows cp1252 encoding for structlog emoji output
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

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
from worker.tasks.audit import run_audit
from worker.testing.corpus import KNOWN_UNCITED_SITES


async def audit_site(async_session, domain: str, site_name: str) -> dict:
    """Run a single audit and return result summary."""
    site_id = uuid5(NAMESPACE_DNS, domain)
    run_id = uuid4()

    async with async_session() as session:
        # Check if site exists
        existing = await session.execute(select(Site).where(Site.id == site_id))
        site = existing.scalar_one_or_none()

        if site:
            user_id = site.user_id
        else:
            user_id = uuid4()
            user = User(
                id=user_id,
                email=f"neg_{site_id.hex[:8]}@calibration.test",
                hashed_password="dummy",
                name=f"Calibration Test ({domain})",
            )
            session.add(user)

            site = Site(
                id=site_id,
                user_id=user_id,
                domain=domain,
                name=site_name,
                business_model="unknown",
            )
            session.add(site)

        run = Run(
            id=run_id,
            site_id=site_id,
            run_type="starter_audit",
            status="queued",
            config={
                "include_observation": True,
                "include_benchmark": False,
                "bands": ["typical"],
                "provider": {"preferred": "router", "model": "auto"},
            },
        )
        session.add(run)
        await session.commit()

    try:
        result = await run_audit(run_id, site_id)

        # Count calibration samples
        async with async_session() as session:
            count_result = await session.execute(
                select(func.count())
                .select_from(CalibrationSample)
                .where(CalibrationSample.run_id == run_id)
            )
            sample_count = count_result.scalar()

            # Count mentioned vs not mentioned
            mentioned_result = await session.execute(
                select(
                    CalibrationSample.obs_mentioned,
                    func.count(),
                )
                .where(CalibrationSample.run_id == run_id)
                .group_by(CalibrationSample.obs_mentioned)
            )
            mentioned_counts = dict(mentioned_result.all())

        return {
            "domain": domain,
            "status": "success",
            "score": result.get("score", "N/A"),
            "grade": result.get("grade", "N/A"),
            "samples": sample_count,
            "mentioned": mentioned_counts.get(True, 0),
            "not_mentioned": mentioned_counts.get(False, 0),
        }

    except Exception as e:
        return {
            "domain": domain,
            "status": "failed",
            "error": str(e),
            "samples": 0,
        }


async def main(domain: str | None = None, dry_run: bool = False):
    if domain:
        sites = [s for s in KNOWN_UNCITED_SITES if domain in s.url]
        if not sites:
            # Treat as a custom domain
            from worker.testing.corpus import SiteCategory, TestSite

            sites = [
                TestSite(
                    url=f"https://{domain}",
                    name=domain.split(".")[0].title(),
                    category=SiteCategory.KNOWN_UNCITED,
                    industry="Unknown",
                    authority_level="medium",
                    notes="Custom negative sample target",
                )
            ]
    else:
        sites = KNOWN_UNCITED_SITES

    print("=" * 70)
    print("NEGATIVE SAMPLE COLLECTION")
    print("=" * 70)
    print(f"Sites to audit: {len(sites)}")
    print()

    for i, site in enumerate(sites, 1):
        print(f"  {i:2}. {site.name:<25} {site.url}")
    print()

    if dry_run:
        print("DRY RUN - no audits will be run.")
        return

    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Check current negative sample count
    async with async_session_maker() as session:
        neg_count = await session.execute(
            select(func.count())
            .select_from(CalibrationSample)
            .where(CalibrationSample.obs_mentioned.is_(False))
        )
        current_negatives = neg_count.scalar()
        print(f"Current negative samples in DB: {current_negatives}")
        print()

    results = []
    for i, site in enumerate(sites, 1):
        domain_name = site.domain
        print(f"[{i}/{len(sites)}] Auditing {site.name} ({domain_name})...")

        result = await audit_site(async_session_maker, domain_name, site.name)
        results.append(result)

        if result["status"] == "success":
            print(
                f"  Score: {result['score']}, Samples: {result['samples']}, "
                f"Mentioned: {result['mentioned']}, Not mentioned: {result['not_mentioned']}"
            )
        else:
            print(f"  FAILED: {result.get('error', 'unknown')[:80]}")
        print()

    # Summary
    print("=" * 70)
    print("COLLECTION SUMMARY")
    print("=" * 70)

    total_samples = sum(r.get("samples", 0) for r in results)
    total_not_mentioned = sum(r.get("not_mentioned", 0) for r in results)
    total_mentioned = sum(r.get("mentioned", 0) for r in results)
    succeeded = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")

    print(f"Sites audited: {succeeded} succeeded, {failed} failed")
    print(f"New samples: {total_samples}")
    print(f"  Mentioned (positive): {total_mentioned}")
    print(f"  Not mentioned (negative): {total_not_mentioned}")
    print()

    # Check new totals
    async with async_session_maker() as session:
        neg_count = await session.execute(
            select(func.count())
            .select_from(CalibrationSample)
            .where(CalibrationSample.obs_mentioned.is_(False))
        )
        new_negatives = neg_count.scalar()

        total_count = await session.execute(select(func.count()).select_from(CalibrationSample))
        new_total = total_count.scalar()

    print("DB totals after collection:")
    print(f"  Total samples: {new_total}")
    print(f"  Negative samples: {new_negatives} (was {current_negatives})")
    print(f"  Balance: {new_negatives / new_total * 100:.1f}% negative")

    if new_negatives >= 50:
        print(
            f"\nGood: {new_negatives} negative samples is enough to run meaningful weight optimization."
        )
        print("Run: python scripts/run_optimizer.py --save")
    else:
        print(
            f"\nNeed more: {50 - new_negatives} additional negative samples recommended (target: 50)."
        )

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect negative calibration samples")
    parser.add_argument("--domain", type=str, help="Specific domain to audit")
    parser.add_argument("--dry-run", action="store_true", help="Show sites without auditing")
    args = parser.parse_args()

    asyncio.run(main(domain=args.domain, dry_run=args.dry_run))
