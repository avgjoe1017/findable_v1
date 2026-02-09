"""Run the calibration optimizer and optionally save results as a new config.

Usage:
    # Standard run (coarse-then-fine, bias-adjusted, constrained ±10%)
    python scripts/run_optimizer.py

    # Unconstrained wide search
    python scripts/run_optimizer.py --unconstrained

    # Save result as new config
    python scripts/run_optimizer.py --save

    # Custom parameters
    python scripts/run_optimizer.py --window-days 90 --min-samples 100 --step 5
"""

import argparse
import asyncio
import json
import sys

sys.path.insert(0, "c:/Users/joeba/Documents/findable")

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.config import get_settings
from api.models.calibration import (
    CalibrationConfig,
    CalibrationConfigStatus,
    CalibrationSample,
    OutcomeMatch,
)
from worker.calibration.optimizer import (
    DEFAULT_WEIGHTS,
    _batch_evaluate,
    _calculate_weighted_metrics,
    _generate_constrained_combinations,
    _generate_fine_search_combinations,
    _prepare_sample_matrices,
    _split_by_domain,
    generate_weight_combinations,
)


async def run_optimizer(
    window_days: int = 60,
    min_samples: int = 100,
    step: float = 5.0,
    max_weight_change: float = 10.0,
    coarse_then_fine: bool = True,
    save_config: bool = False,
    config_name: str | None = None,
):
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    window_start = datetime.now(UTC) - timedelta(days=window_days)

    async with async_session() as session:
        # Load samples
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
        min_weight_coverage = 70.0

        def get_weight_coverage(sample) -> float:
            covered = 0.0
            for pillar in pillar_keys:
                if sample.pillar_scores.get(pillar) is not None:
                    covered += DEFAULT_WEIGHTS[pillar]
            return covered

        samples = [s for s in all_samples if get_weight_coverage(s) >= min_weight_coverage]

        print("=" * 70)
        print("CALIBRATION OPTIMIZER")
        print("=" * 70)
        print(f"Window: {window_days} days")
        print(f"Total samples: {len(all_samples)}")
        print(f"With 70%+ weight coverage: {len(samples)}")
        print(f"Filtered out: {len(all_samples) - len(samples)}")
        print()

        # Class balance analysis (using obs_cited as target, not obs_mentioned)
        # obs_mentioned is 99.8% positive (useless). obs_cited has ~68/32 split.
        cited_positive = sum(1 for s in samples if s.obs_cited)
        cited_negative = len(samples) - cited_positive
        mentioned_positive = sum(1 for s in samples if s.obs_mentioned)
        mentioned_negative = len(samples) - mentioned_positive
        print("CLASS BALANCE (calibration target = obs_cited):")
        print(
            f"  obs_cited=True  (positive): {cited_positive} ({cited_positive/len(samples)*100:.1f}%)"
        )
        print(
            f"  obs_cited=False (negative): {cited_negative} ({cited_negative/len(samples)*100:.1f}%)"
        )
        print(
            f"  (obs_mentioned: {mentioned_positive} positive / {mentioned_negative} negative — too imbalanced)"
        )
        if cited_negative < 20:
            print(f"  WARNING: Only {cited_negative} negative samples. Need more data.")
        print()

        if len(samples) < min_samples:
            print(f"ERROR: Insufficient samples ({len(samples)} < {min_samples})")
            await engine.dispose()
            return

        # Domain-stratified split
        training_samples, holdout_samples, training_domains, holdout_domains = _split_by_domain(
            samples, holdout_pct=0.2
        )

        print(f"Training: {len(training_samples)} samples across {len(training_domains)} domains")
        print(f"Holdout:  {len(holdout_samples)} samples across {len(holdout_domains)} domains")
        print()

        # Baseline
        baseline_metrics = _calculate_weighted_metrics(
            training_samples, DEFAULT_WEIGHTS, threshold=50
        )
        baseline_holdout = _calculate_weighted_metrics(
            holdout_samples, DEFAULT_WEIGHTS, threshold=50
        )

        print("BASELINE (default weights, threshold=50):")
        print(
            f"  Training accuracy:  {baseline_metrics.accuracy:.1%} (bias-adj: {baseline_metrics.bias_adjusted_score:.4f})"
        )
        print(
            f"  Training bias:      over={baseline_metrics.over_rate:.1%} under={baseline_metrics.under_rate:.1%}"
        )
        print(
            f"  Holdout accuracy:   {baseline_holdout.accuracy:.1%} (bias-adj: {baseline_holdout.bias_adjusted_score:.4f})"
        )
        print(
            f"  Holdout bias:       over={baseline_holdout.over_rate:.1%} under={baseline_holdout.under_rate:.1%}"
        )
        print()

        # Test baseline at different thresholds
        print("BASELINE THRESHOLD SENSITIVITY:")
        for t in [30, 35, 40, 45, 50, 55, 60]:
            m = _calculate_weighted_metrics(training_samples, DEFAULT_WEIGHTS, threshold=t)
            h = _calculate_weighted_metrics(holdout_samples, DEFAULT_WEIGHTS, threshold=t)
            marker = " <-- current" if t == 50 else ""
            print(
                f"  threshold={t}: train={m.accuracy:.1%} holdout={h.accuracy:.1%} over={m.over_rate:.1%} under={m.under_rate:.1%}{marker}"
            )
        print()

        # Phase 1: Coarse search (step=5 for 7 pillars; step=10 produces 0 valid combos)
        coarse_step = 5.0 if coarse_then_fine else step
        coarse_radius = max(max_weight_change, 15.0) if coarse_then_fine else max_weight_change
        print(
            f"PHASE 1: {'Coarse' if coarse_then_fine else 'Single'} search (step={coarse_step}, max_change=±{coarse_radius})"
        )

        if coarse_radius < 35:
            combinations = _generate_constrained_combinations(
                DEFAULT_WEIGHTS, max_change=coarse_radius, step=coarse_step
            )
        else:
            combinations = generate_weight_combinations(step=coarse_step)

        print(f"  Weight combinations: {len(combinations)}")

        thresholds_to_test = [30, 35, 40, 45, 50, 55, 60]
        print(f"  Thresholds to test: {thresholds_to_test}")
        print(f"  Total evaluations: {len(combinations) * len(thresholds_to_test)}")

        best_score = baseline_metrics.bias_adjusted_score
        best_weights = DEFAULT_WEIGHTS.copy()
        best_metrics = baseline_metrics
        best_threshold = 50

        # Pre-compute numpy arrays for vectorized evaluation
        pillar_order = list(DEFAULT_WEIGHTS.keys())
        train_matrix, train_actuals, train_primacy = _prepare_sample_matrices(
            training_samples, pillar_order
        )

        # Check if source primacy data is available
        has_primacy_data = train_primacy.any()
        primacy_weights_to_test = [0, 5, 10, 15, 20] if has_primacy_data else [0]
        best_primacy_weight = 0.0

        if has_primacy_data:
            primacy_count = int((train_primacy > 0).sum())
            print(
                f"SOURCE PRIMACY: {primacy_count}/{len(training_samples)} samples have primacy data"
            )
            print(f"  Primacy weights to search: {primacy_weights_to_test}")
            print()

        if combinations:
            coarse_weights, coarse_threshold, coarse_score, coarse_metrics, coarse_pw = (
                _batch_evaluate(
                    train_matrix,
                    train_actuals,
                    combinations,
                    pillar_order,
                    thresholds_to_test,
                    primacy_scores=train_primacy if has_primacy_data else None,
                    primacy_weights=primacy_weights_to_test,
                )
            )
            if coarse_score > best_score:
                best_score = coarse_score
                best_weights = coarse_weights
                best_metrics = coarse_metrics
                best_threshold = coarse_threshold
                best_primacy_weight = coarse_pw

        print(f"  Best coarse score: {best_score:.4f} (accuracy={best_metrics.accuracy:.1%})")
        print(f"  Best coarse threshold: {best_threshold}")
        if has_primacy_data:
            print(f"  Best coarse primacy weight: {best_primacy_weight}")
        print(
            f"  Best coarse weights: {json.dumps({k: v for k, v in best_weights.items()}, indent=None)}"
        )
        print()

        # Phase 2: Fine search around best coarse result
        if coarse_then_fine:
            fine_step = min(step, 2.0)
            fine_radius = max(coarse_step, 10.0)
            fine_combinations = _generate_fine_search_combinations(
                best_weights, step=fine_step, radius=fine_radius
            )
            fine_thresholds = list(
                range(max(20, best_threshold - 10), min(70, best_threshold + 11), 2)
            )
            if has_primacy_data:
                fine_primacy = list(
                    range(
                        max(0, int(best_primacy_weight) - 5),
                        min(25, int(best_primacy_weight) + 6),
                        2,
                    )
                )
            else:
                fine_primacy = [0]

            print(f"PHASE 2: Fine search (step={fine_step}, radius=±{fine_radius})")
            print(f"  Weight combinations: {len(fine_combinations)}")
            print(f"  Thresholds: {fine_thresholds}")
            if has_primacy_data:
                print(f"  Primacy weights: {fine_primacy}")
            print(
                f"  Total evaluations: {len(fine_combinations) * len(fine_thresholds) * len(fine_primacy)}"
            )

            if fine_combinations:
                fine_weights, fine_threshold, fine_score, fine_metrics, fine_pw = _batch_evaluate(
                    train_matrix,
                    train_actuals,
                    fine_combinations,
                    pillar_order,
                    fine_thresholds,
                    primacy_scores=train_primacy if has_primacy_data else None,
                    primacy_weights=fine_primacy,
                )
                if fine_score > best_score:
                    best_score = fine_score
                    best_weights = fine_weights
                    best_metrics = fine_metrics
                    best_threshold = fine_threshold
                    best_primacy_weight = fine_pw

            print(f"  Best fine score: {best_score:.4f} (accuracy={best_metrics.accuracy:.1%})")
            print(f"  Best fine threshold: {best_threshold}")
            if has_primacy_data:
                print(f"  Best fine primacy weight: {best_primacy_weight}")
            print()

        # Holdout validation
        holdout_metrics = _calculate_weighted_metrics(
            holdout_samples,
            best_weights,
            threshold=best_threshold,
            primacy_weight=best_primacy_weight,
        )

        print("=" * 70)
        print("RESULTS")
        print("=" * 70)
        print()
        print("Best Weights:")
        for pillar, weight in best_weights.items():
            default = DEFAULT_WEIGHTS[pillar]
            delta = weight - default
            marker = f" ({delta:+.0f})" if delta != 0 else ""
            print(f"  {pillar:>20}: {weight:5.1f}%{marker}")
        print(f"  {'sum':>20}: {sum(best_weights.values()):.0f}%")
        if has_primacy_data:
            print(f"  {'source_primacy bonus':>20}: {best_primacy_weight:5.1f}%")
        print()
        print(f"Best Findability Threshold: {best_threshold}")
        if has_primacy_data:
            print(f"Best Primacy Weight: {best_primacy_weight}")
        print()

        print("Performance:")
        print(f"  {'Metric':<25} {'Baseline':>12} {'Optimized':>12} {'Delta':>10}")
        print(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*10}")
        print(
            f"  {'Training accuracy':<25} {baseline_metrics.accuracy:>11.1%} {best_metrics.accuracy:>11.1%} {best_metrics.accuracy - baseline_metrics.accuracy:>+9.1%}"
        )
        print(
            f"  {'Training bias-adj':<25} {baseline_metrics.bias_adjusted_score:>12.4f} {best_metrics.bias_adjusted_score:>12.4f} {best_metrics.bias_adjusted_score - baseline_metrics.bias_adjusted_score:>+10.4f}"
        )
        print(
            f"  {'Holdout accuracy':<25} {baseline_holdout.accuracy:>11.1%} {holdout_metrics.accuracy:>11.1%} {holdout_metrics.accuracy - baseline_holdout.accuracy:>+9.1%}"
        )
        print(
            f"  {'Holdout bias-adj':<25} {baseline_holdout.bias_adjusted_score:>12.4f} {holdout_metrics.bias_adjusted_score:>12.4f} {holdout_metrics.bias_adjusted_score - baseline_holdout.bias_adjusted_score:>+10.4f}"
        )
        print()

        print("Bias Breakdown:")
        print(f"  {'Set':<15} {'Over Rate':>10} {'Under Rate':>10}")
        print(f"  {'-'*15} {'-'*10} {'-'*10}")
        print(
            f"  {'Train base':<15} {baseline_metrics.over_rate:>9.1%} {baseline_metrics.under_rate:>9.1%}"
        )
        print(f"  {'Train opt':<15} {best_metrics.over_rate:>9.1%} {best_metrics.under_rate:>9.1%}")
        print(
            f"  {'Holdout base':<15} {baseline_holdout.over_rate:>9.1%} {baseline_holdout.under_rate:>9.1%}"
        )
        print(
            f"  {'Holdout opt':<15} {holdout_metrics.over_rate:>9.1%} {holdout_metrics.under_rate:>9.1%}"
        )
        print()

        # Per-domain accuracy breakdown
        print("PER-DOMAIN ACCURACY (optimized):")
        print(
            f"  {'Domain':<12} {'Set':<8} {'Samples':>7} {'Accuracy':>9} {'Over':>6} {'Under':>6}"
        )
        print(f"  {'-'*12} {'-'*8} {'-'*7} {'-'*9} {'-'*6} {'-'*6}")

        domain_samples_map: dict[str, list] = {}
        for s in samples:
            d = str(s.site_id)[:8]
            if d not in domain_samples_map:
                domain_samples_map[d] = []
            domain_samples_map[d].append(s)

        for domain, dsamps in sorted(domain_samples_map.items()):
            dm = _calculate_weighted_metrics(
                dsamps,
                best_weights,
                threshold=best_threshold,
                primacy_weight=best_primacy_weight,
            )
            which_set = (
                "holdout" if any(str(s.site_id) in holdout_domains for s in dsamps) else "train"
            )
            print(
                f"  {domain:<12} {which_set:<8} {dm.total:>7} {dm.accuracy:>8.1%} {dm.over_rate:>5.1%} {dm.under_rate:>5.1%}"
            )

        print()

        # Generalization check
        gap = best_metrics.accuracy - holdout_metrics.accuracy
        if gap > 0.10:
            print(f"WARNING: Large train-holdout gap ({gap:.1%}). Possible overfitting.")
        elif holdout_metrics.accuracy >= baseline_holdout.accuracy:
            print(
                f"GOOD: Holdout accuracy improved or maintained ({holdout_metrics.accuracy:.1%} vs {baseline_holdout.accuracy:.1%} baseline)."
            )
        else:
            print(
                f"NOTE: Holdout accuracy dropped from {baseline_holdout.accuracy:.1%} to {holdout_metrics.accuracy:.1%}."
            )

        improvement = best_score - baseline_metrics.bias_adjusted_score
        print(
            f"\nOverall improvement (bias-adjusted): {improvement:+.4f} ({improvement/max(0.001, baseline_metrics.bias_adjusted_score)*100:+.1f}%)"
        )

        # Save as config
        if save_config and improvement > 0:
            name = config_name or f"optimized_v3_{datetime.now(UTC).strftime('%Y_%m')}"
            print(f"\nSaving as config: {name}")

            # Check if name exists
            existing = await session.execute(
                select(CalibrationConfig).where(CalibrationConfig.name == name)
            )
            if existing.scalar_one_or_none():
                print(
                    f"  Config '{name}' already exists. Use --config-name to specify a different name."
                )
            else:
                config = CalibrationConfig(
                    id=uuid4(),
                    name=name,
                    description=(
                        f"Optimizer output: coarse-then-fine search, "
                        f"bias-adjusted scoring, ±{max_weight_change} constraint. "
                        f"Training accuracy: {best_metrics.accuracy:.1%}, "
                        f"Holdout accuracy: {holdout_metrics.accuracy:.1%}, "
                        f"Threshold: {best_threshold}. "
                        f"Based on {len(samples)} samples across {len(training_domains) + len(holdout_domains)} domains."
                    ),
                    status=CalibrationConfigStatus.VALIDATED.value,
                    is_active=False,
                    weight_technical=best_weights["technical"],
                    weight_structure=best_weights["structure"],
                    weight_schema=best_weights["schema"],
                    weight_authority=best_weights["authority"],
                    weight_entity_recognition=best_weights["entity_recognition"],
                    weight_retrieval=best_weights["retrieval"],
                    weight_coverage=best_weights["coverage"],
                    threshold_fully_answerable=0.7,
                    threshold_partially_answerable=0.3,
                    threshold_signal_match=0.6,
                    scoring_relevance_weight=0.4,
                    scoring_signal_weight=0.4,
                    scoring_confidence_weight=0.2,
                    validation_accuracy=holdout_metrics.accuracy,
                    validation_sample_count=len(holdout_samples),
                    validation_optimism_bias=holdout_metrics.over_rate,
                    validation_pessimism_bias=holdout_metrics.under_rate,
                    notes=json.dumps(
                        {
                            "optimizer_version": "v4",
                            "findability_threshold": best_threshold,
                            "primacy_weight": best_primacy_weight,
                            "training_accuracy": round(best_metrics.accuracy, 4),
                            "training_bias_adjusted": round(best_score, 4),
                            "holdout_accuracy": round(holdout_metrics.accuracy, 4),
                            "holdout_bias_adjusted": round(holdout_metrics.bias_adjusted_score, 4),
                            "window_days": window_days,
                            "sample_count": len(samples),
                            "domain_count": len(training_domains) + len(holdout_domains),
                            "max_weight_change": max_weight_change,
                            "step": step,
                        }
                    ),
                )
                session.add(config)
                await session.commit()
                print(f"  Saved: {config.id}")
                print(
                    f"  To set up A/B test: update scripts/setup_ab_experiment.py with config name '{name}'"
                )

        print("\n" + "=" * 70)

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Run calibration optimizer")
    parser.add_argument("--window-days", type=int, default=60, help="Days of samples to use")
    parser.add_argument("--min-samples", type=int, default=100, help="Minimum samples required")
    parser.add_argument("--step", type=float, default=5.0, help="Fine search step size")
    parser.add_argument(
        "--max-change", type=float, default=10.0, help="Max weight change per pillar"
    )
    parser.add_argument(
        "--unconstrained", action="store_true", help="Remove weight change constraint"
    )
    parser.add_argument(
        "--no-coarse-fine", action="store_true", help="Skip coarse-then-fine, use single pass"
    )
    parser.add_argument("--save", action="store_true", help="Save result as new CalibrationConfig")
    parser.add_argument("--config-name", type=str, help="Name for saved config")
    args = parser.parse_args()

    max_change = 35.0 if args.unconstrained else args.max_change

    asyncio.run(
        run_optimizer(
            window_days=args.window_days,
            min_samples=args.min_samples,
            step=args.step,
            max_weight_change=max_change,
            coarse_then_fine=not args.no_coarse_fine,
            save_config=args.save,
            config_name=args.config_name,
        )
    )


if __name__ == "__main__":
    main()
