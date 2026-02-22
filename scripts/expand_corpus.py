"""Batch audit script to expand calibration corpus.

Runs audits on all corpus sites (or a filtered subset) to collect
calibration samples. Supports resuming interrupted runs and filtering
by site category or site type.

Usage:
    # Dry run — show all sites without auditing
    python scripts/expand_corpus.py --dry-run

    # Audit all new sites (skip already-audited domains)
    python scripts/expand_corpus.py --resume

    # Audit only known_cited sites
    python scripts/expand_corpus.py --category known_cited --resume

    # Audit a specific domain
    python scripts/expand_corpus.py --domain docs.python.org

    # Skip observation (faster, no LLM costs, but no calibration samples)
    python scripts/expand_corpus.py --no-observation --resume

    # Limit to N sites (useful for testing)
    python scripts/expand_corpus.py --limit 5 --resume
"""

import argparse
import asyncio
import io
import sys
import time

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
from worker.testing.corpus import (
    COMPETITOR_SITES,
    KNOWN_CITED_SITES,
    KNOWN_UNCITED_SITES,
    OWN_PROPERTY_SITES,
    SiteCategory,
    TestCorpus,
    TestSite,
)

# Calibration user for corpus audits
CALIBRATION_USER_EMAIL = "corpus@calibration.findable"
CALIBRATION_USER_ID = uuid5(NAMESPACE_DNS, CALIBRATION_USER_EMAIL)


async def get_audited_domains(async_session) -> set[str]:
    """Get set of domains that already have calibration samples."""
    async with async_session() as session:
        result = await session.execute(
            select(Site.domain)
            .join(Run, Run.site_id == Site.id)
            .where(Run.status == "complete")
            .distinct()
        )
        return {row[0] for row in result.all()}


async def ensure_calibration_user(async_session) -> None:
    """Create the calibration user if it doesn't exist."""
    async with async_session() as session:
        existing = await session.execute(select(User).where(User.id == CALIBRATION_USER_ID))
        if not existing.scalar_one_or_none():
            user = User(
                id=CALIBRATION_USER_ID,
                email=CALIBRATION_USER_EMAIL,
                hashed_password="calibration_user_no_login",
                name="Corpus Calibration",
            )
            session.add(user)
            await session.commit()
            print(f"Created calibration user: {CALIBRATION_USER_EMAIL}")


async def audit_site(
    async_session,
    test_site: TestSite,
    include_observation: bool = True,
) -> dict:
    """Run a single audit and return result summary."""
    domain = test_site.domain
    site_id = uuid5(NAMESPACE_DNS, domain)
    run_id = uuid4()

    async with async_session() as session:
        # Check if site exists
        existing = await session.execute(select(Site).where(Site.id == site_id))
        site = existing.scalar_one_or_none()

        if not site:
            site = Site(
                id=site_id,
                user_id=CALIBRATION_USER_ID,
                domain=domain,
                name=test_site.name,
                business_model="unknown",
            )
            session.add(site)

        run = Run(
            id=run_id,
            site_id=site_id,
            run_type="starter_audit",
            status="queued",
            config={
                "include_observation": include_observation,
                "include_benchmark": False,
                "bands": ["typical"],
                "provider": {"preferred": "router", "model": "auto"},
            },
        )
        session.add(run)
        await session.commit()

    start_time = time.time()
    try:
        result = await run_audit(run_id, site_id)
        duration = time.time() - start_time

        # Count calibration samples
        async with async_session() as session:
            count_result = await session.execute(
                select(func.count())
                .select_from(CalibrationSample)
                .where(CalibrationSample.run_id == run_id)
            )
            sample_count = count_result.scalar()

            # Count cited vs not cited
            cited_result = await session.execute(
                select(
                    CalibrationSample.obs_cited,
                    func.count(),
                )
                .where(CalibrationSample.run_id == run_id)
                .group_by(CalibrationSample.obs_cited)
            )
            cited_counts = dict(cited_result.all())

        return {
            "domain": domain,
            "name": test_site.name,
            "category": test_site.category.value,
            "status": "success",
            "score": result.get("score", "N/A"),
            "grade": result.get("grade", "N/A"),
            "samples": sample_count,
            "cited": cited_counts.get(True, 0),
            "not_cited": cited_counts.get(False, 0),
            "duration_seconds": round(duration, 1),
        }

    except Exception as e:
        duration = time.time() - start_time
        return {
            "domain": domain,
            "name": test_site.name,
            "category": test_site.category.value,
            "status": "failed",
            "error": str(e)[:200],
            "samples": 0,
            "duration_seconds": round(duration, 1),
        }


def get_sites(
    category: str | None = None,
    domain: str | None = None,
) -> list[TestSite]:
    """Get filtered list of sites to audit."""
    if domain:
        # Find specific domain in full corpus
        corpus = TestCorpus.full()
        matches = [s for s in corpus.sites if domain in s.url or domain == s.domain]
        if matches:
            return matches
        # Treat as custom domain
        return [
            TestSite(
                url=f"https://{domain}",
                name=domain.split(".")[0].title(),
                category=SiteCategory.KNOWN_UNCITED,
                industry="Unknown",
                authority_level="medium",
                notes="Custom corpus addition",
            )
        ]

    if category:
        category_map = {
            "known_cited": KNOWN_CITED_SITES,
            "known_uncited": KNOWN_UNCITED_SITES,
            "own_property": OWN_PROPERTY_SITES,
            "competitor": COMPETITOR_SITES,
        }
        return category_map.get(category, TestCorpus.full().sites)

    return TestCorpus.full().sites


async def main(
    category: str | None = None,
    domain: str | None = None,
    resume: bool = False,
    dry_run: bool = False,
    include_observation: bool = True,
    limit: int | None = None,
):
    sites = get_sites(category=category, domain=domain)

    print("=" * 78)
    print("CORPUS EXPANSION - BATCH AUDIT")
    print("=" * 78)
    print(f"Total sites in selection: {len(sites)}")

    if resume or dry_run:
        settings = get_settings()
        engine = create_async_engine(str(settings.database_url))
        async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        if resume:
            audited = await get_audited_domains(async_session_factory)
            original_count = len(sites)
            sites = [s for s in sites if s.domain not in audited]
            print(f"Already audited: {original_count - len(sites)} domains")
            print(f"Remaining to audit: {len(sites)}")
        else:
            audited = set()

        if dry_run:
            print("\nDRY RUN - showing sites that would be audited:\n")
            for i, site in enumerate(sites, 1):
                status = "SKIP (already audited)" if site.domain in audited else "PENDING"
                print(
                    f"  {i:3}. [{site.category.value:14}] {site.name:<25} {site.domain:<35} {status}"
                )
            print(f"\nTotal pending: {len([s for s in sites if s.domain not in audited])}")
            if not resume:
                await engine.dispose()
            return

    if limit:
        sites = sites[:limit]
        print(f"Limited to: {limit} sites")

    if not sites:
        print("\nNo sites to audit. All domains already have samples.")
        return

    print(f"\nSites to audit: {len(sites)}")
    print(f"Observation: {'enabled' if include_observation else 'disabled'}")
    print()

    for i, site in enumerate(sites, 1):
        print(f"  {i:3}. [{site.category.value:14}] {site.name:<25} {site.domain}")
    print()

    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    await ensure_calibration_user(async_session_factory)

    results = []
    total_start = time.time()

    for i, site in enumerate(sites, 1):
        print(f"\n[{i}/{len(sites)}] Auditing {site.name} ({site.domain})...")

        result = await audit_site(
            async_session_factory,
            site,
            include_observation=include_observation,
        )
        results.append(result)

        if result["status"] == "success":
            print(
                f"  Score: {result['score']}, "
                f"Samples: {result['samples']}, "
                f"Cited: {result.get('cited', 0)}, "
                f"Not cited: {result.get('not_cited', 0)}, "
                f"Time: {result['duration_seconds']}s"
            )
        else:
            print(f"  FAILED: {result.get('error', 'unknown')}")

    total_duration = time.time() - total_start

    # Summary
    print("\n" + "=" * 78)
    print("BATCH AUDIT SUMMARY")
    print("=" * 78)

    succeeded = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "failed"]

    print(f"Sites audited: {len(succeeded)} succeeded, {len(failed)} failed")
    print(f"Total time: {total_duration:.0f}s ({total_duration / 60:.1f} min)")
    print()

    total_samples = sum(r.get("samples", 0) for r in succeeded)
    total_cited = sum(r.get("cited", 0) for r in succeeded)
    total_not_cited = sum(r.get("not_cited", 0) for r in succeeded)

    print(f"New calibration samples: {total_samples}")
    print(f"  Cited (positive): {total_cited}")
    print(f"  Not cited (negative): {total_not_cited}")
    if total_samples > 0:
        print(f"  Citation rate: {total_cited / total_samples * 100:.1f}%")
    print()

    # Per-category breakdown

    category_stats: dict[str, dict] = {}
    for r in succeeded:
        cat = r["category"]
        if cat not in category_stats:
            category_stats[cat] = {"count": 0, "cited": 0, "not_cited": 0, "samples": 0}
        category_stats[cat]["count"] += 1
        category_stats[cat]["cited"] += r.get("cited", 0)
        category_stats[cat]["not_cited"] += r.get("not_cited", 0)
        category_stats[cat]["samples"] += r.get("samples", 0)

    print("Per-category breakdown:")
    for cat, stats in sorted(category_stats.items()):
        rate = f"{stats['cited'] / stats['samples'] * 100:.0f}%" if stats["samples"] > 0 else "N/A"
        print(
            f"  {cat:14} — {stats['count']} sites, "
            f"{stats['samples']} samples, "
            f"citation rate: {rate}"
        )
    print()

    if failed:
        print("Failed sites:")
        for r in failed:
            print(f"  {r['domain']}: {r.get('error', 'unknown')}")
        print()

    # Check DB totals
    async with async_session_factory() as session:
        total_count = await session.execute(select(func.count()).select_from(CalibrationSample))
        db_total = total_count.scalar()

        cited_count = await session.execute(
            select(func.count())
            .select_from(CalibrationSample)
            .where(CalibrationSample.obs_cited.is_(True))
        )
        db_cited = cited_count.scalar()

        domain_count = await session.execute(
            select(func.count(func.distinct(CalibrationSample.site_id))).select_from(
                CalibrationSample
            )
        )
        db_domains = domain_count.scalar()

    print("Database totals:")
    print(f"  Total samples: {db_total}")
    print(f"  Cited samples: {db_cited}")
    print(f"  Unique domains: {db_domains}")
    if db_total and db_total > 0:
        print(f"  Overall citation rate: {db_cited / db_total * 100:.1f}%")
    print()

    if db_domains and db_domains >= 20:
        print("Ready to run optimizer:")
        print(
            '  powershell -Command "set PYTHONIOENCODING=utf-8 && python scripts/run_optimizer.py --save"'
        )
    else:
        print(f"Need more domains: {20 - (db_domains or 0)} more domains recommended (target: 20+)")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Expand calibration corpus by auditing test sites")
    parser.add_argument(
        "--category",
        type=str,
        choices=["known_cited", "known_uncited", "own_property", "competitor"],
        help="Filter by site category",
    )
    parser.add_argument("--domain", type=str, help="Audit a specific domain")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip domains that already have audit results",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show sites without auditing",
    )
    parser.add_argument(
        "--no-observation",
        action="store_true",
        help="Skip observation (faster, no LLM costs, but no calibration samples)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit to N sites",
    )
    args = parser.parse_args()

    asyncio.run(
        main(
            category=args.category,
            domain=args.domain,
            resume=args.resume,
            dry_run=args.dry_run,
            include_observation=not args.no_observation,
            limit=args.limit,
        )
    )
