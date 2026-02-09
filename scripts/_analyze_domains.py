"""Analyze what distinguishes always-cited from never-cited domains."""

import asyncio
import sys

sys.path.insert(0, "c:/Users/joeba/Documents/findable")

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.config import get_settings
from api.models.calibration import CalibrationSample
from api.models.site import Site


async def main():
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(
            select(CalibrationSample, Site.domain, Site.name).join(
                Site, Site.id == CalibrationSample.site_id
            )
        )
        rows = result.all()

    await engine.dispose()

    # Group by domain
    domains = defaultdict(
        lambda: {
            "name": "",
            "samples": [],
            "cited": 0,
            "total": 0,
            "pillars": defaultdict(list),
            "by_category": defaultdict(lambda: {"total": 0, "cited": 0}),
            "by_difficulty": defaultdict(lambda: {"total": 0, "cited": 0}),
            "by_answerability": defaultdict(lambda: {"total": 0, "cited": 0}),
        }
    )

    for sample, domain, name in rows:
        d = domains[domain]
        d["name"] = name
        d["total"] += 1
        if sample.obs_cited:
            d["cited"] += 1

        # Pillar scores
        if sample.pillar_scores:
            for p in [
                "technical",
                "structure",
                "schema",
                "authority",
                "entity_recognition",
                "retrieval",
                "coverage",
            ]:
                v = sample.pillar_scores.get(p)
                if v is not None:
                    d["pillars"][p].append(v)

        # By question category
        cat = sample.question_category or "unknown"
        d["by_category"][cat]["total"] += 1
        if sample.obs_cited:
            d["by_category"][cat]["cited"] += 1

        # By difficulty
        diff = sample.question_difficulty or "unknown"
        d["by_difficulty"][diff]["total"] += 1
        if sample.obs_cited:
            d["by_difficulty"][diff]["cited"] += 1

        # By sim answerability
        ans = sample.sim_answerability or "unknown"
        d["by_answerability"][ans]["total"] += 1
        if sample.obs_cited:
            d["by_answerability"][ans]["cited"] += 1

    # Sort by citation rate
    sorted_domains = sorted(
        domains.items(),
        key=lambda x: x[1]["cited"] / x[1]["total"] if x[1]["total"] > 0 else 0,
        reverse=True,
    )

    pillars = [
        "technical",
        "structure",
        "schema",
        "authority",
        "entity_recognition",
        "retrieval",
        "coverage",
    ]
    short = {
        "technical": "Tech",
        "structure": "Struct",
        "schema": "Schema",
        "authority": "Auth",
        "entity_recognition": "Entity",
        "retrieval": "Retr",
        "coverage": "Cover",
    }

    print("=" * 140)
    print("PER-DOMAIN ANALYSIS: What predicts citation?")
    print("=" * 140)
    print()
    print(
        f"{'Domain':<22} {'Cited%':>6} {'N':>4}  {'Tech':>5} {'Struct':>6} {'Schema':>6} {'Auth':>5} {'Entity':>6} {'Retr':>5} {'Cover':>5}  {'IdentCite':>9} {'DiffCite':>8} {'EasyCite':>8} {'HardCite':>8}"
    )
    print("-" * 140)

    for domain, d in sorted_domains:
        cite_pct = d["cited"] / d["total"] * 100 if d["total"] > 0 else 0

        def avg_pillar(p, d=d):
            vals = d["pillars"].get(p, [])
            return f"{sum(vals)/len(vals):5.1f}" if vals else "  N/A"

        def cat_cite(cat, d=d):
            c = d["by_category"].get(cat, {"total": 0, "cited": 0})
            return f"{c['cited']/c['total']*100:.0f}%" if c["total"] > 0 else "N/A"

        def diff_cite(diff, d=d):
            c = d["by_difficulty"].get(diff, {"total": 0, "cited": 0})
            return f"{c['cited']/c['total']*100:.0f}%" if c["total"] > 0 else "N/A"

        print(
            f"{domain:<22} {cite_pct:5.1f}% {d['total']:>4}  "
            f"{avg_pillar('technical')} {avg_pillar('structure')} {avg_pillar('schema')} "
            f"{avg_pillar('authority')} {avg_pillar('entity_recognition')} "
            f"{avg_pillar('retrieval')} {avg_pillar('coverage')}  "
            f"{cat_cite('identity'):>9} {cat_cite('differentiation'):>8} "
            f"{diff_cite('easy'):>8} {diff_cite('hard'):>8}"
        )

    # Group into tiers and compare
    high = [
        (dom, d)
        for dom, d in sorted_domains
        if d["cited"] / d["total"] >= 0.8 and "example" not in dom
    ]
    mid = [
        (dom, d)
        for dom, d in sorted_domains
        if 0.4 <= d["cited"] / d["total"] < 0.8 and "example" not in dom
    ]
    low = [
        (dom, d)
        for dom, d in sorted_domains
        if d["cited"] / d["total"] < 0.4 and "example" not in dom
    ]

    print()
    print("=" * 140)
    print("TIER COMPARISON: What separates always-cited from never-cited?")
    print("=" * 140)

    for label, group in [
        ("HIGH CITATION (>=80%)", high),
        ("MID CITATION (40-79%)", mid),
        ("LOW CITATION (<40%)", low),
    ]:
        if not group:
            continue
        print(f"\n{label}:")
        print(f"  Domains: {', '.join(d for d, _ in group)}")

        for p in pillars:
            all_vals = []
            for _, d in group:
                all_vals.extend(d["pillars"].get(p, []))
            avg = sum(all_vals) / len(all_vals) if all_vals else 0
            print(f"  Avg {short[p]:<8}: {avg:5.1f}")

        # Category breakdown
        for cat in ["identity", "differentiation", "expertise", "comparison", "how_to"]:
            total = sum(d["by_category"].get(cat, {"total": 0})["total"] for _, d in group)
            cited = sum(d["by_category"].get(cat, {"cited": 0})["cited"] for _, d in group)
            if total > 0:
                print(f"  {cat:<20} cited: {cited}/{total} = {cited/total*100:.0f}%")

        # Answerability breakdown
        for ans in ["fully_answerable", "partially_answerable", "not_answerable"]:
            total = sum(d["by_answerability"].get(ans, {"total": 0})["total"] for _, d in group)
            cited = sum(d["by_answerability"].get(ans, {"cited": 0})["cited"] for _, d in group)
            if total > 0:
                print(f"  sim={ans:<25} cited: {cited}/{total} = {cited/total*100:.0f}%")


asyncio.run(main())
