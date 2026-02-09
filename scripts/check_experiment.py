"""Check status of running A/B experiment with early warning diagnostics."""

import asyncio
import sys

sys.path.insert(0, "c:/Users/joeba/Documents/findable")

from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import selectinload, sessionmaker

from api.config import get_settings
from api.models.calibration import (
    CalibrationExperiment,
    ExperimentStatus,
)
from worker.calibration.experiment import (
    analyze_experiment,
    update_experiment_sample_counts,
)


async def main():
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

            # Check for concluded experiments
            result = await session.execute(
                select(CalibrationExperiment)
                .where(CalibrationExperiment.status == ExperimentStatus.CONCLUDED.value)
                .order_by(CalibrationExperiment.concluded_at.desc())
            )
            concluded = result.scalars().all()

            if concluded:
                print(f"\nFound {len(concluded)} concluded experiment(s):")
                for exp in concluded[:3]:
                    print(f"  - {exp.name}")
                    print(f"    Winner: {exp.winner}")
                    print(
                        f"    Control accuracy: {exp.control_accuracy:.1%}"
                        if exp.control_accuracy
                        else "    Control accuracy: N/A"
                    )
                    print(
                        f"    Treatment accuracy: {exp.treatment_accuracy:.1%}"
                        if exp.treatment_accuracy
                        else "    Treatment accuracy: N/A"
                    )
                    print(f"    Concluded: {exp.concluded_at}")
            return

        print("=" * 70)
        print(f"EXPERIMENT: {experiment.name}")
        print("=" * 70)
        print(f"ID: {experiment.id}")
        print(f"Started: {experiment.started_at}")
        print(f"Treatment allocation: {experiment.treatment_allocation:.0%}")
        print(f"Min samples per arm: {experiment.min_samples_per_arm}")
        print()

    # Update sample counts
    await update_experiment_sample_counts(experiment.id)

    # Analyze experiment
    results = await analyze_experiment(experiment.id)

    print("SAMPLE COUNTS:")
    print(f"  Control samples:   {results.control_samples:>4}")
    print(f"  Treatment samples: {results.treatment_samples:>4}")
    print(f"  Total:             {results.control_samples + results.treatment_samples:>4}")
    print()

    control_pct = results.control_samples / results.min_samples_per_arm * 100
    treatment_pct = results.treatment_samples / results.min_samples_per_arm * 100
    print(f"PROGRESS: Control {control_pct:.0f}% | Treatment {treatment_pct:.0f}%")

    bar_width = 40
    control_bar = int(min(control_pct, 100) / 100 * bar_width)
    treatment_bar = int(min(treatment_pct, 100) / 100 * bar_width)
    print(
        f"  Control:   [{'#' * control_bar}{'-' * (bar_width - control_bar)}] {results.control_samples}/{results.min_samples_per_arm}"
    )
    print(
        f"  Treatment: [{'#' * treatment_bar}{'-' * (bar_width - treatment_bar)}] {results.treatment_samples}/{results.min_samples_per_arm}"
    )
    print()

    if results.control_samples >= 10 and results.treatment_samples >= 10:
        print("ACCURACY:")
        print(f"  Control:   {results.control_accuracy:.1%}")
        print(f"  Treatment: {results.treatment_accuracy:.1%}")
        print(f"  Difference: {results.accuracy_difference:+.1%}")
        print()

        if results.p_value is not None:
            print("STATISTICAL ANALYSIS:")
            print(f"  p-value: {results.p_value:.4f}")
            print(f"  Significant: {'Yes (p < 0.05)' if results.is_significant else 'No'}")
            print()

    if results.ready_to_conclude:
        print("STATUS: Ready to conclude!")
        print(f"  Winner: {results.winner}")
        print(f"  Reason: {results.winner_reason}")
        print()
        print("To conclude: python scripts/conclude_experiment.py")
    else:
        samples_needed = max(
            results.min_samples_per_arm - results.control_samples,
            results.min_samples_per_arm - results.treatment_samples,
        )
        print(f"STATUS: Need {samples_needed} more samples to conclude")

    print("=" * 70)

    # Early warning diagnostics
    print()
    print("EARLY WARNING DIAGNOSTICS:")
    print("-" * 70)

    async with async_session() as session:
        # Get all samples for this experiment with site info
        from api.models.calibration import CalibrationSample

        samples_result = await session.execute(
            select(CalibrationSample)
            .options(selectinload(CalibrationSample.site))
            .where(CalibrationSample.experiment_id == experiment.id)
        )
        all_samples = list(samples_result.scalars().all())

        # Separate by arm
        control_samples = [s for s in all_samples if s.config_id == experiment.control_config_id]
        treatment_samples = [
            s for s in all_samples if s.config_id == experiment.treatment_config_id
        ]

        # Unique domains per arm
        control_domains = set(s.site.domain if s.site else str(s.site_id) for s in control_samples)
        treatment_domains = set(
            s.site.domain if s.site else str(s.site_id) for s in treatment_samples
        )

        print("Unique Domains:")
        print(
            f"  Control:   {len(control_domains):>3} unique domains ({len(control_samples)} samples)"
        )
        print(
            f"  Treatment: {len(treatment_domains):>3} unique domains ({len(treatment_samples)} samples)"
        )

        if len(control_samples) > 0:
            avg_samples_per_domain_control = (
                len(control_samples) / len(control_domains) if control_domains else 0
            )
            print(f"  Control avg samples/domain: {avg_samples_per_domain_control:.1f}")
        if len(treatment_samples) > 0:
            avg_samples_per_domain_treatment = (
                len(treatment_samples) / len(treatment_domains) if treatment_domains else 0
            )
            print(f"  Treatment avg samples/domain: {avg_samples_per_domain_treatment:.1f}")

        print()

        # Top 5 most-sampled domains
        all_domain_counts = Counter(
            s.site.domain if s.site else str(s.site_id) for s in all_samples
        )
        print("Top 5 Most-Sampled Domains:")
        for domain, count in all_domain_counts.most_common(5):
            pct = count / len(all_samples) * 100 if all_samples else 0
            print(f"  {domain}: {count} samples ({pct:.1f}%)")

        print()

        # Observation model distribution
        model_counts = Counter(s.obs_model for s in all_samples if s.obs_model)
        if model_counts:
            print("Observation Model Distribution:")
            for model, count in model_counts.most_common():
                pct = count / len(all_samples) * 100 if all_samples else 0
                print(f"  {model}: {count} ({pct:.1f}%)")
        else:
            print("Observation Model Distribution: No model data recorded")

        print()

        # Accuracy by domain, per arm
        print("ACCURACY BY DOMAIN:")
        print("-" * 50)

        # Control arm accuracy by domain
        control_by_domain = {}
        for s in control_samples:
            domain = s.site.domain if s.site else str(s.site_id)
            if domain not in control_by_domain:
                control_by_domain[domain] = {"correct": 0, "total": 0}
            control_by_domain[domain]["total"] += 1
            if s.prediction_accurate:
                control_by_domain[domain]["correct"] += 1

        print("  CONTROL:")
        for domain in sorted(control_by_domain.keys()):
            stats = control_by_domain[domain]
            acc = stats["correct"] / stats["total"] * 100 if stats["total"] > 0 else 0
            print(f"    {domain}: {acc:.0f}% ({stats['correct']}/{stats['total']})")

        # Treatment arm accuracy by domain
        treatment_by_domain = {}
        for s in treatment_samples:
            domain = s.site.domain if s.site else str(s.site_id)
            if domain not in treatment_by_domain:
                treatment_by_domain[domain] = {"correct": 0, "total": 0}
            treatment_by_domain[domain]["total"] += 1
            if s.prediction_accurate:
                treatment_by_domain[domain]["correct"] += 1

        print("  TREATMENT:")
        for domain in sorted(treatment_by_domain.keys()):
            stats = treatment_by_domain[domain]
            acc = stats["correct"] / stats["total"] * 100 if stats["total"] > 0 else 0
            print(f"    {domain}: {acc:.0f}% ({stats['correct']}/{stats['total']})")

        print()

        # Prediction bias breakdown
        print("PREDICTION BIAS:")
        control_over = sum(1 for s in control_samples if s.outcome_match == "optimistic")
        control_under = sum(1 for s in control_samples if s.outcome_match == "pessimistic")
        control_correct = sum(1 for s in control_samples if s.outcome_match == "correct")

        treatment_over = sum(1 for s in treatment_samples if s.outcome_match == "optimistic")
        treatment_under = sum(1 for s in treatment_samples if s.outcome_match == "pessimistic")
        treatment_correct = sum(1 for s in treatment_samples if s.outcome_match == "correct")

        print(f"  Control:   correct={control_correct} over={control_over} under={control_under}")
        print(
            f"  Treatment: correct={treatment_correct} over={treatment_over} under={treatment_under}"
        )

        if len(control_samples) > 0:
            print(
                f"  Control bias:   over={control_over/len(control_samples)*100:.1f}% under={control_under/len(control_samples)*100:.1f}%"
            )
        if len(treatment_samples) > 0:
            print(
                f"  Treatment bias: over={treatment_over/len(treatment_samples)*100:.1f}% under={treatment_under/len(treatment_samples)*100:.1f}%"
            )

        print()

        # Warning flags
        warnings = []

        # Check for domain concentration (>50% samples from one domain)
        if all_domain_counts:
            top_domain, top_count = all_domain_counts.most_common(1)[0]
            if len(all_samples) > 0 and top_count / len(all_samples) > 0.5:
                warnings.append(
                    f"[!] Domain concentration: {top_domain} has {top_count/len(all_samples)*100:.0f}% of samples"
                )

        # Check for arm imbalance (>2x difference)
        if len(control_samples) > 0 and len(treatment_samples) > 0:
            ratio = max(len(control_samples), len(treatment_samples)) / min(
                len(control_samples), len(treatment_samples)
            )
            if ratio > 2.0:
                warnings.append(f"[!] Arm imbalance: {ratio:.1f}x difference in sample counts")

        # Check for too few unique domains
        if len(all_samples) > 20:
            if len(control_domains) < 3:
                warnings.append(
                    f"[!] Low domain diversity in control: only {len(control_domains)} unique domains"
                )
            if len(treatment_domains) < 3:
                warnings.append(
                    f"[!] Low domain diversity in treatment: only {len(treatment_domains)} unique domains"
                )

        if warnings:
            print("WARNINGS:")
            for w in warnings:
                print(f"  {w}")
        else:
            print("[OK] No early warning flags detected")

    print("=" * 70)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
