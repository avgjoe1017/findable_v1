"""Analyze pillar score distributions across calibration samples."""

import asyncio
import io
import json
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, "c:/Users/joeba/Documents/findable")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.config import get_settings
from api.models.calibration import CalibrationSample
from api.models.site import Site
from worker.calibration.optimizer import DEFAULT_WEIGHTS


async def main():
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        result = await session.execute(
            select(CalibrationSample, Site.domain)
            .join(Site, CalibrationSample.site_id == Site.id)
            .where(CalibrationSample.pillar_scores.isnot(None))
        )
        rows = result.all()

    pillars = list(DEFAULT_WEIGHTS.keys())

    # Per-domain analysis
    domain_data = {}
    for sample, domain in rows:
        ps = sample.pillar_scores
        cw = sum(DEFAULT_WEIGHTS[p] for p in pillars if ps.get(p) is not None)
        if domain not in domain_data:
            domain_data[domain] = {
                "total": 0,
                "covered": 0,
                "cited": 0,
                "uncited": 0,
                "pillars": {p: set() for p in pillars},
                "retrieval_cited": [],
                "retrieval_uncited": [],
                "coverage_cited": [],
                "coverage_uncited": [],
                "wscore_cited": [],
                "wscore_uncited": [],
            }
        d = domain_data[domain]
        d["total"] += 1
        if cw >= 70:
            d["covered"] += 1
            for p in pillars:
                v = ps.get(p)
                if v is not None:
                    d["pillars"][p].add(round(v, 1))
            retr = ps.get("retrieval", 0)
            cover = ps.get("coverage", 0)
            ws = sum(ps.get(p, 0) * (DEFAULT_WEIGHTS[p] / 100.0) for p in pillars)
            if sample.obs_cited:
                d["cited"] += 1
                d["retrieval_cited"].append(retr)
                d["coverage_cited"].append(cover)
                d["wscore_cited"].append(ws)
            else:
                d["uncited"] += 1
                d["retrieval_uncited"].append(retr)
                d["coverage_uncited"].append(cover)
                d["wscore_uncited"].append(ws)

    print("=" * 100)
    print("PER-DOMAIN PILLAR SCORE ANALYSIS")
    print("=" * 100)
    print()

    for domain in sorted(domain_data.keys()):
        d = domain_data[domain]
        if d["covered"] == 0:
            # Still show filtered-out domains
            print(f"  {domain}: {d['total']} samples, ALL filtered (0 covered)")
            continue

        cite_rate = d["cited"] / d["covered"] * 100 if d["covered"] > 0 else 0
        print(
            f"{domain} — covered={d['covered']}/{d['total']}, cited={d['cited']}, uncited={d['uncited']} ({cite_rate:.0f}% citation)"
        )

        for p in pillars:
            vals = sorted(d["pillars"][p])
            if not vals:
                print(f"  {p:>20}: MISSING")
            elif len(vals) == 1:
                print(f"  {p:>20}: {vals[0]:>5.0f}  (constant)")
            elif len(vals) <= 8:
                print(f"  {p:>20}: {', '.join(f'{v:.0f}' for v in vals)}  ({len(vals)} unique)")
            else:
                print(
                    f"  {p:>20}: {min(vals):.0f}-{max(vals):.0f}  ({len(vals)} unique, mean={sum(vals)/len(vals):.1f})"
                )

        # Show cited vs uncited weighted score overlap
        if d["wscore_cited"] and d["wscore_uncited"]:
            import statistics

            cm = statistics.mean(d["wscore_cited"])
            um = statistics.mean(d["wscore_uncited"])
            print(
                f"  {'weighted_score':>20}: cited_mean={cm:.1f} uncited_mean={um:.1f} gap={cm-um:+.1f}"
            )
        elif d["wscore_cited"]:
            import statistics

            print(
                f"  {'weighted_score':>20}: cited_mean={statistics.mean(d['wscore_cited']):.1f} (no uncited)"
            )
        elif d["wscore_uncited"]:
            import statistics

            print(
                f"  {'weighted_score':>20}: uncited_mean={statistics.mean(d['wscore_uncited']):.1f} (no cited)"
            )
        print()

    # Now show the JSON from a few domains
    print("=" * 100)
    print("SAMPLE pillar_scores JSON (one per domain, covered only)")
    print("=" * 100)
    seen = set()
    for sample, domain in rows:
        ps = sample.pillar_scores
        cw = sum(DEFAULT_WEIGHTS[p] for p in pillars if ps.get(p) is not None)
        if cw >= 70 and domain not in seen:
            seen.add(domain)
            print(f"  {domain}: {json.dumps(ps)}")

    # Summary: how many domains have varying vs constant pillar scores
    print()
    print("=" * 100)
    print("VARIANCE SUMMARY")
    print("=" * 100)
    for p in pillars:
        domains_with_variation = 0
        domains_constant = 0
        domains_missing = 0
        for domain, d in domain_data.items():
            if d["covered"] == 0:
                continue
            vals = d["pillars"][p]
            if not vals:
                domains_missing += 1
            elif len(vals) == 1:
                domains_constant += 1
            else:
                domains_with_variation += 1
        print(
            f"  {p:>20}: varies_in={domains_with_variation} domains, constant_in={domains_constant} domains, missing_in={domains_missing} domains"
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
