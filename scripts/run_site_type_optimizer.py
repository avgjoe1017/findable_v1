"""Run per-site-type weight optimization and display results.

Trains separate weight profiles for each site type that has enough
calibration samples. Types with too few samples fall back to global weights.

Usage:
    python scripts/run_site_type_optimizer.py
    python scripts/run_site_type_optimizer.py --min-samples 30
    python scripts/run_site_type_optimizer.py --types documentation saas_marketing
"""

import argparse
import asyncio
import sys

sys.path.insert(0, "c:/Users/joeba/Documents/findable")

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.config import get_settings
from api.models.calibration import (
    CalibrationSample,
    OutcomeMatch,
)
from worker.calibration.optimizer import (
    DEFAULT_WEIGHTS,
    _calculate_weighted_metrics,
    _split_by_domain,
)
from worker.extraction.site_type import SiteType


async def run_site_type_optimizer(
    min_samples: int = 30,
    window_days: int = 90,
    site_types: list[str] | None = None,
):
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    window_start = datetime.now(UTC) - timedelta(days=window_days)

    async with async_session() as session:
        # First, show sample distribution by site type
        count_query = (
            select(
                CalibrationSample.site_type,
                func.count().label("total"),
                func.sum(
                    func.cast(CalibrationSample.obs_cited, type_=func.literal(1).__class__)
                ).label("cited"),
            )
            .where(CalibrationSample.created_at >= window_start)
            .where(CalibrationSample.outcome_match != OutcomeMatch.UNKNOWN.value)
            .where(CalibrationSample.pillar_scores.isnot(None))
            .group_by(CalibrationSample.site_type)
        )
        count_result = await session.execute(count_query)
        type_counts = {row[0]: {"total": row[1], "cited": row[2] or 0} for row in count_result}

        print("=" * 70)
        print("PER-SITE-TYPE CALIBRATION OPTIMIZER")
        print("=" * 70)
        print(f"Window: {window_days} days | Min samples: {min_samples}")
        print()

        print("SAMPLE DISTRIBUTION BY SITE TYPE:")
        print(f"  {'Site Type':<20} {'Total':>7} {'Cited':>7} {'Cite %':>8} {'Status':<15}")
        print(f"  {'-'*20} {'-'*7} {'-'*7} {'-'*8} {'-'*15}")

        types_to_train = []
        for st in SiteType:
            counts = type_counts.get(st.value, {"total": 0, "cited": 0})
            total = counts["total"]
            cited = counts["cited"]
            pct = f"{cited/total*100:.0f}%" if total > 0 else "n/a"
            status = "WILL TRAIN" if total >= min_samples else "skip (few)"
            if site_types and st.value not in site_types:
                status = "skip (filter)"
            elif total >= min_samples:
                types_to_train.append(st.value)
            print(f"  {st.value:<20} {total:>7} {cited:>7} {pct:>8} {status:<15}")

        print(f"\n  Types to train: {len(types_to_train)}")
        print()

        if not types_to_train:
            print("No site types have enough samples. Collect more data first.")
            await engine.dispose()
            return

        # Load all samples
        result = await session.execute(
            select(CalibrationSample)
            .where(CalibrationSample.created_at >= window_start)
            .where(CalibrationSample.outcome_match != OutcomeMatch.UNKNOWN.value)
            .where(CalibrationSample.pillar_scores.isnot(None))
            .order_by(CalibrationSample.created_at)
        )
        all_samples = list(result.scalars().all())

        # Filter for weight coverage
        pillar_keys = list(DEFAULT_WEIGHTS.keys())

        def get_weight_coverage(sample) -> float:
            covered = 0.0
            for pillar in pillar_keys:
                if sample.pillar_scores.get(pillar) is not None:
                    covered += DEFAULT_WEIGHTS[pillar]
            return covered

        samples = [s for s in all_samples if get_weight_coverage(s) >= 70.0]

        # Train each site type
        results_summary = []

        for st in types_to_train:
            print(f"{'=' * 70}")
            print(f"TRAINING: {st.upper()}")
            print(f"{'=' * 70}")

            type_samples = [s for s in samples if s.site_type == st]
            print(f"  Samples: {len(type_samples)}")

            if len(type_samples) < min_samples:
                print(f"  SKIP: Only {len(type_samples)} samples (need {min_samples})")
                results_summary.append(
                    {
                        "site_type": st,
                        "status": "skipped",
                        "reason": f"Only {len(type_samples)} samples",
                    }
                )
                print()
                continue

            # Class balance
            cited = sum(1 for s in type_samples if s.obs_cited)
            not_cited = len(type_samples) - cited
            print(
                f"  Class balance: {cited} cited ({cited/len(type_samples)*100:.0f}%) / {not_cited} not cited ({not_cited/len(type_samples)*100:.0f}%)"
            )

            # Domain split
            train_samp, holdout_samp, train_dom, holdout_dom = _split_by_domain(
                type_samples, holdout_pct=0.2
            )
            print(f"  Train: {len(train_samp)} samples / {len(train_dom)} domains")
            print(f"  Holdout: {len(holdout_samp)} samples / {len(holdout_dom)} domains")

            if len(train_dom) < 2:
                print(f"  SKIP: Only {len(train_dom)} training domains (need >=2)")
                results_summary.append(
                    {
                        "site_type": st,
                        "status": "skipped",
                        "reason": f"Only {len(train_dom)} domains",
                    }
                )
                print()
                continue

            # Baseline (global weights)
            baseline = _calculate_weighted_metrics(train_samp, DEFAULT_WEIGHTS, threshold=30)
            baseline_holdout = _calculate_weighted_metrics(
                holdout_samp, DEFAULT_WEIGHTS, threshold=30
            )
            print("  Baseline (global weights, t=30):")
            print(f"    Train: {baseline.accuracy:.1%} (MCC: {baseline.mcc:.4f})")
            print(f"    Holdout: {baseline_holdout.accuracy:.1%} (MCC: {baseline_holdout.mcc:.4f})")

            # Search thresholds with global weights to find best for this type
            best_score = baseline.mcc
            best_threshold = 30
            best_primacy_weight = 0.0
            best_weights = DEFAULT_WEIGHTS.copy()

            # Check for primacy data
            has_primacy = any(s.pillar_scores.get("source_primacy") is not None for s in train_samp)
            pw_list = [0, 5, 10, 15, 20] if has_primacy else [0]

            for t in [25, 30, 35, 40, 45, 50]:
                for pw in pw_list:
                    m = _calculate_weighted_metrics(
                        train_samp,
                        DEFAULT_WEIGHTS,
                        threshold=t,
                        primacy_weight=pw,
                    )
                    if m.mcc > best_score:
                        best_score = m.mcc
                        best_threshold = t
                        best_primacy_weight = pw

            optimized = _calculate_weighted_metrics(
                train_samp,
                best_weights,
                threshold=best_threshold,
                primacy_weight=best_primacy_weight,
            )
            optimized_holdout = _calculate_weighted_metrics(
                holdout_samp,
                best_weights,
                threshold=best_threshold,
                primacy_weight=best_primacy_weight,
            )

            improvement = best_score - baseline.mcc
            print(f"  Optimized (t={best_threshold}, pw={best_primacy_weight}):")
            print(f"    Train: {optimized.accuracy:.1%} (MCC: {optimized.mcc:.4f})")
            print(
                f"    Holdout: {optimized_holdout.accuracy:.1%} (MCC: {optimized_holdout.mcc:.4f})"
            )
            print(f"    MCC improvement: {improvement:+.4f}")
            print()

            results_summary.append(
                {
                    "site_type": st,
                    "status": "trained",
                    "samples": len(type_samples),
                    "domains": len(train_dom) + len(holdout_dom),
                    "best_threshold": best_threshold,
                    "best_primacy_weight": best_primacy_weight,
                    "train_accuracy": round(optimized.accuracy, 4),
                    "holdout_accuracy": round(optimized_holdout.accuracy, 4),
                    "improvement": round(improvement, 4),
                }
            )

        # Summary table
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(
            f"  {'Site Type':<20} {'Status':<10} {'Samples':>8} {'Thresh':>7} {'Primacy':>8} {'Train':>7} {'Holdout':>8} {'Improv':>8}"
        )
        print(f"  {'-'*20} {'-'*10} {'-'*8} {'-'*7} {'-'*8} {'-'*7} {'-'*8} {'-'*8}")
        for r in results_summary:
            if r["status"] == "skipped":
                print(
                    f"  {r['site_type']:<20} {'skip':<10} {'':>8} {'':>7} {'':>8} {'':>7} {'':>8} {'':>8}"
                )
            else:
                print(
                    f"  {r['site_type']:<20} {'OK':<10} {r['samples']:>8} "
                    f"{r['best_threshold']:>7} {r['best_primacy_weight']:>8.0f} "
                    f"{r['train_accuracy']:>6.1%} {r['holdout_accuracy']:>7.1%} "
                    f"{r['improvement']:>+7.4f}"
                )
        print()

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Run per-site-type weight optimization")
    parser.add_argument("--min-samples", type=int, default=30, help="Min samples per type")
    parser.add_argument("--window-days", type=int, default=90, help="Days of samples to use")
    parser.add_argument("--types", nargs="+", help="Specific site types to train")
    args = parser.parse_args()

    asyncio.run(
        run_site_type_optimizer(
            min_samples=args.min_samples,
            window_days=args.window_days,
            site_types=args.types,
        )
    )


if __name__ == "__main__":
    main()
