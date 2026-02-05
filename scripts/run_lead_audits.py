"""Run Findable Score audits on potential lead/customer sites.

This script tests the v2 scoring pipeline on sites that represent
actual target customers - agencies, consultants, and SMBs that would
benefit from AI findability optimization.

Usage:
    python scripts/run_lead_audits.py
    python scripts/run_lead_audits.py --sites "https://example.com,https://another.com"
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, ".")

from scripts.e2e_test_sites import SiteResult, audit_site  # noqa: E402

# Lead sites - representative of target customers:
# - Marketing agencies
# - SEO consultants
# - Local businesses
# - B2B SaaS startups
# - Professional services

DEFAULT_LEAD_SITES = [
    # Marketing/SEO Agencies
    "https://moz.com",
    "https://www.searchenginejournal.com",
    "https://backlinko.com",
    "https://ahrefs.com",
    # B2B SaaS (smaller scale)
    "https://calendly.com",
    "https://www.loom.com",
    "https://www.typeform.com",
    "https://mailchimp.com",
    # Professional Services / Consultants
    "https://www.mckinsey.com",
    "https://www.bain.com",
    # Documentation / Content Sites
    "https://docs.python.org",
    "https://stripe.com/docs",
]


async def run_lead_audits(sites: list[str], max_pages: int = 30) -> list[SiteResult]:
    """
    Run audits on lead/customer-type sites.

    Args:
        sites: List of URLs to audit
        max_pages: Max pages per site (lower for faster results)

    Returns:
        List of SiteResult objects
    """
    print("\n" + "=" * 80)
    print("FINDABLE SCORE v2 - LEAD AUDIT TEST")
    print("=" * 80)
    print(f"Testing {len(sites)} potential lead sites")
    print(f"Max pages per site: {max_pages}")
    print("=" * 80 + "\n")

    results: list[SiteResult] = []

    for i, url in enumerate(sites, 1):
        print(f"\n{'=' * 80}")
        print(f"[{i}/{len(sites)}] AUDITING: {url}")
        print("=" * 80)

        result = await audit_site(url, max_pages=max_pages)
        results.append(result)

        # Brief pause between sites
        if i < len(sites):
            await asyncio.sleep(1)

    return results


def print_results_summary(results: list[SiteResult]) -> None:
    """Print formatted results summary."""
    print("\n\n" + "=" * 120)
    print("LEAD AUDIT RESULTS SUMMARY")
    print("=" * 130)
    print(
        f"{'Domain':<30} {'Score':>8} {'Level':<22} {'Outcome':<16} "
        f"{'Tech':>6} {'Struct':>7} {'Schema':>7} {'Auth':>6}"
    )
    print("-" * 130)

    for r in sorted(results, key=lambda x: x.total_score, reverse=True):
        if r.outcome in ("blocked", "error"):
            print(
                f"{r.domain:<30} {'--':>8} {r.level_label:<22} {r.outcome.upper():<16} "
                f"{'-':>6} {'-':>7} {'-':>7} {'-':>6}"
            )
            if r.error:
                print(f"  >> {r.error[:80]}")
        else:
            print(
                f"{r.domain:<30} {r.total_score:>7.1f} {r.level_label:<22} "
                f"{r.outcome:<16} "
                f"{r.technical_score:>6.0f} {r.structure_score:>7.0f} "
                f"{r.schema_score:>7.0f} {r.authority_score:>6.0f}"
            )
            if r.warnings:
                for w in r.warnings:
                    print(f"  >> WARNING: {w}")

    print("-" * 130)

    # Three-tier outcome breakdown
    scored = [r for r in results if r.outcome == "scored"]
    extraction_weak = [r for r in results if r.outcome == "extraction_weak"]
    blocked = [r for r in results if r.outcome == "blocked"]
    errored = [r for r in results if r.outcome == "error"]

    print("\nOUTCOME TIERS:")
    print(f"  Scored (clean):        {len(scored)} sites")
    print(f"  Scored (weak extract): {len(extraction_weak)} sites")
    print(f"  Blocked / Uncrawlable: {len(blocked)} sites")
    print(f"  Errors:                {len(errored)} sites")

    # Statistics for scored sites
    successful = scored + extraction_weak
    if successful:
        avg_score = sum(r.total_score for r in successful) / len(successful)

        # Level distribution
        levels: dict[str, int] = {}
        for r in successful:
            levels[r.level_label] = levels.get(r.level_label, 0) + 1

        print("\nSTATISTICS (scored sites):")
        print(f"  Average score: {avg_score:.1f}/100")
        print("  Level distribution:")
        for level, count in sorted(levels.items(), key=lambda x: -x[1]):
            print(f"    {level}: {count} sites")

    print("=" * 130)


def save_results(results: list[SiteResult], output_path: Path) -> None:
    """Save results to JSON file."""
    data = {
        "timestamp": datetime.now(UTC).isoformat(),
        "total_sites": len(results),
        "outcome_tiers": {
            "scored": len([r for r in results if r.outcome == "scored"]),
            "extraction_weak": len([r for r in results if r.outcome == "extraction_weak"]),
            "blocked": len([r for r in results if r.outcome == "blocked"]),
            "error": len([r for r in results if r.outcome == "error"]),
        },
        "results": [
            {
                "domain": r.domain,
                "total_score": r.total_score,
                "level": r.level,
                "level_label": r.level_label,
                "outcome": r.outcome,
                "technical_score": r.technical_score,
                "structure_score": r.structure_score,
                "schema_score": r.schema_score,
                "authority_score": r.authority_score,
                "retrieval_score": r.retrieval_score,
                "coverage_score": r.coverage_score,
                "pages_crawled": r.pages_crawled,
                "total_chunks": r.total_chunks,
                "duration_seconds": r.duration_seconds,
                "error": r.error,
                "warnings": list(r.warnings),
            }
            for r in results
        ],
    }

    output_path.write_text(json.dumps(data, indent=2))
    print(f"\nResults saved to: {output_path}")


async def main():
    parser = argparse.ArgumentParser(description="Run Findable Score audits on lead sites")
    parser.add_argument(
        "--sites",
        type=str,
        help="Comma-separated list of URLs to audit",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=30,
        help="Maximum pages to crawl per site (default: 30)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="lead_audit_results.json",
        help="Output JSON file path",
    )

    args = parser.parse_args()

    sites = [s.strip() for s in args.sites.split(",")] if args.sites else DEFAULT_LEAD_SITES

    results = await run_lead_audits(sites, max_pages=args.max_pages)

    print_results_summary(results)

    output_path = Path(args.output)
    save_results(results, output_path)


if __name__ == "__main__":
    asyncio.run(main())
