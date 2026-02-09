#!/usr/bin/env python
"""Backfill site_type for all domains in the calibration corpus.

Runs site type detection on each corpus domain using URL patterns and
domain heuristics (no crawl needed), then prints a summary table.

This can also update existing CalibrationSample rows in the database
if --update-db is passed and a database connection is available.

Usage:
    python scripts/backfill_site_types.py              # Dry run, print table
    python scripts/backfill_site_types.py --update-db  # Also update DB samples
"""

import asyncio
import sys

sys.path.insert(0, ".")

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from worker.extraction.site_type import SiteType, SiteTypeDetector
from worker.testing.corpus import (
    COMPETITOR_SITES,
    KNOWN_CITED_SITES,
    KNOWN_UNCITED_SITES,
    OWN_PROPERTY_SITES,
)

# Manual overrides for corpus domains where we know the type
# but the detector can't determine from a single homepage URL.
# These are validated against actual citation data from the calibration corpus.
CORPUS_OVERRIDES: dict[str, str] = {
    # SEO/Marketing authorities — SaaS with strong blog content
    "moz.com": SiteType.SAAS_MARKETING,
    "hubspot.com": SiteType.SAAS_MARKETING,
    "neilpatel.com": SiteType.BLOG,
    "openai.com": SiteType.DEVELOPER_TOOLS,
    "anthropic.com": SiteType.DEVELOPER_TOOLS,
    # Findable + competitors are SaaS marketing
    "findable.so": SiteType.SAAS_MARKETING,
    "otterly.ai": SiteType.SAAS_MARKETING,
    "rankscale.ai": SiteType.SAAS_MARKETING,
    "amsive.com": SiteType.SAAS_MARKETING,
}


def classify_corpus() -> list[dict]:
    """Classify all corpus domains and return results."""
    detector = SiteTypeDetector()
    all_sites = KNOWN_CITED_SITES + KNOWN_UNCITED_SITES + OWN_PROPERTY_SITES + COMPETITOR_SITES

    results = []
    for site in all_sites:
        domain = site.domain

        # Check for manual override first
        if domain in CORPUS_OVERRIDES:
            from worker.extraction.site_type import CITATION_BASELINES

            override_type = SiteType(CORPUS_OVERRIDES[domain])
            baseline = CITATION_BASELINES[override_type]
            results.append(
                {
                    "domain": domain,
                    "name": site.name,
                    "category": site.category.value,
                    "site_type": override_type.value,
                    "confidence": 0.90,  # Manual override = high confidence
                    "citation_baseline": baseline["citation_rate"],
                    "signals": ["manual_override"],
                    "source": "override",
                }
            )
            continue

        # Use domain-level detection (no crawl needed for classification)
        # Pass the site URL as the only page URL for URL pattern analysis
        result = detector.detect(
            domain=domain,
            page_urls=[site.url],
            page_htmls=None,
        )

        results.append(
            {
                "domain": domain,
                "name": site.name,
                "category": site.category.value,
                "site_type": result.site_type.value,
                "confidence": result.confidence,
                "citation_baseline": result.citation_baseline,
                "signals": result.signals,
                "source": "detector",
            }
        )

    return results


def print_results(results: list[dict]) -> None:
    """Print a formatted results table."""
    print(f"\n{'='*100}")
    print("SITE TYPE CLASSIFICATION - CORPUS BACKFILL")
    print(f"{'='*100}\n")

    # Group by category
    for category in ["known_cited", "known_uncited", "own_property", "competitor"]:
        cat_results = [r for r in results if r["category"] == category]
        if not cat_results:
            continue

        print(f"\n--- {category.upper().replace('_', ' ')} ({len(cat_results)} sites) ---")
        print(f"{'Domain':<30} {'Name':<20} {'Site Type':<20} {'Conf':>5} {'Cite Base':>10}")
        print("-" * 90)

        for r in cat_results:
            print(
                f"{r['domain']:<30} "
                f"{r['name'][:19]:<20} "
                f"{r['site_type']:<20} "
                f"{r['confidence']:>4.0%} "
                f"{r['citation_baseline']:>9.0%}"
            )

    # Summary stats
    print(f"\n{'='*100}")
    print("SUMMARY BY SITE TYPE")
    print(f"{'='*100}\n")

    type_counts: dict[str, list[str]] = {}
    for r in results:
        st = r["site_type"]
        if st not in type_counts:
            type_counts[st] = []
        type_counts[st].append(r["category"])

    print(f"{'Site Type':<20} {'Count':>6} {'Cited':>7} {'Uncited':>8}")
    print("-" * 45)

    for st in sorted(type_counts.keys()):
        cats = type_counts[st]
        cited = sum(1 for c in cats if c == "known_cited")
        uncited = sum(1 for c in cats if c == "known_uncited")
        print(f"{st:<20} {len(cats):>6} {cited:>7} {uncited:>8}")

    print(f"\nTotal domains classified: {len(results)}")


async def update_database(results: list[dict]) -> int:
    """Update CalibrationSample rows with site_type based on domain."""
    try:
        from sqlalchemy import select, update

        from api.database import async_session_maker
        from api.models.calibration import CalibrationSample
        from api.models.site import Site
    except Exception as e:
        print(f"\nDatabase not available: {e}")
        print("Skipping DB update. Run with a valid DATABASE_URL to update samples.")
        return 0

    # Build domain -> site_type map
    domain_to_type = {r["domain"]: r["site_type"] for r in results}

    updated = 0
    async with async_session_maker() as db:
        # Get all samples that don't have site_type set
        samples_result = await db.execute(
            select(CalibrationSample.id, CalibrationSample.site_id).where(
                CalibrationSample.site_type.is_(None)
            )
        )
        samples = samples_result.fetchall()

        if not samples:
            print("\nNo samples missing site_type found.")
            return 0

        # Get site_id -> domain mapping
        site_ids = list({row[1] for row in samples})
        sites_result = await db.execute(select(Site.id, Site.domain).where(Site.id.in_(site_ids)))
        site_domain_map = {row[0]: row[1] for row in sites_result.fetchall()}

        # Update samples
        for sample_id, site_id in samples:
            domain = site_domain_map.get(site_id)
            if not domain:
                continue

            site_type = domain_to_type.get(domain)
            if not site_type:
                # Try to classify this domain on-the-fly
                detector = SiteTypeDetector()
                result = detector.detect(
                    domain=domain,
                    page_urls=[f"https://{domain}"],
                )
                site_type = result.site_type.value

            await db.execute(
                update(CalibrationSample)
                .where(CalibrationSample.id == sample_id)
                .values(site_type=site_type)
            )
            updated += 1

        await db.commit()

    print(f"\nUpdated {updated} calibration samples with site_type.")
    return updated


def main() -> None:
    update_db = "--update-db" in sys.argv

    results = classify_corpus()
    print_results(results)

    if update_db:
        print("\n--- Updating database ---")
        count = asyncio.run(update_database(results))
        print(f"Database update complete: {count} rows updated.")
    else:
        print("\nDry run. Pass --update-db to update calibration_samples in the database.")


if __name__ == "__main__":
    main()
