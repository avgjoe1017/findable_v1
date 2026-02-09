"""Debug holdout samples to understand why accuracy is 0%."""

import asyncio
import sys

sys.path.insert(0, "c:/Users/joeba/Documents/findable")

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.config import get_settings
from api.models.calibration import CalibrationSample, OutcomeMatch

DEFAULT_WEIGHTS = {
    "technical": 12.0,
    "structure": 18.0,
    "schema": 13.0,
    "authority": 12.0,
    "entity_recognition": 13.0,
    "retrieval": 22.0,
    "coverage": 10.0,
}


async def main():
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    window_start = datetime.now(UTC) - timedelta(days=60)

    async with async_session() as session:
        # Load all samples
        result = await session.execute(
            select(CalibrationSample)
            .where(CalibrationSample.created_at >= window_start)
            .where(CalibrationSample.outcome_match != OutcomeMatch.UNKNOWN.value)
            .where(CalibrationSample.pillar_scores.isnot(None))
            .order_by(CalibrationSample.created_at)
        )
        all_samples = list(result.scalars().all())

        # Filter for samples with 70%+ weight coverage
        pillar_keys = list(DEFAULT_WEIGHTS.keys())

        def get_weight_coverage(sample) -> float:
            covered_weight = 0.0
            for pillar in pillar_keys:
                if sample.pillar_scores.get(pillar) is not None:
                    covered_weight += DEFAULT_WEIGHTS[pillar]
            return covered_weight

        samples = [s for s in all_samples if get_weight_coverage(s) >= 70.0]

        print(f"Total samples: {len(all_samples)}")
        print(f"With 70%+ weight coverage: {len(samples)}")
        print()

        # Group by domain
        domain_samples = {}
        for s in samples:
            domain = str(s.site_id)
            if domain not in domain_samples:
                domain_samples[domain] = []
            domain_samples[domain].append(s)

        domains = list(domain_samples.keys())
        holdout_count = max(1, int(len(domains) * 0.2))
        holdout_domains = set(domains[-holdout_count:])

        print(f"Total domains: {len(domains)}")
        print(f"Holdout domains: {len(holdout_domains)}")
        print()

        print("=" * 80)
        print("HOLDOUT DOMAIN ANALYSIS")
        print("=" * 80)

        for domain in holdout_domains:
            domain_list = domain_samples[domain]
            print(f"\nDomain: {domain[:8]}... ({len(domain_list)} samples)")
            print("-" * 60)

            for i, s in enumerate(domain_list[:5]):  # First 5 samples
                # Calculate weighted score
                weighted_score = 0.0
                pillar_details = []
                for pillar, weight in DEFAULT_WEIGHTS.items():
                    pillar_score = s.pillar_scores.get(pillar)
                    if pillar_score is None:
                        pillar_score = 0.0
                        pillar_details.append(f"{pillar[:4]}=None")
                    else:
                        pillar_details.append(f"{pillar[:4]}={pillar_score:.0f}")
                    weighted_score += pillar_score * (weight / 100.0)

                predicted_findable = weighted_score >= 50
                was_mentioned = s.obs_mentioned

                is_correct = predicted_findable == was_mentioned

                print(f"  Sample {i+1}:")
                print(f"    Pillars: {', '.join(pillar_details)}")
                print(
                    f"    Weighted: {weighted_score:.1f} -> Predicted: {'findable' if predicted_findable else 'NOT findable'}"
                )
                print(f"    Actual: obs_mentioned={was_mentioned}, obs_cited={s.obs_cited}")
                print(f"    Outcome: {s.outcome_match}")
                print(f"    Correct: {'YES' if is_correct else 'NO'}")

            # Summary for domain
            correct = 0
            total = len(domain_list)
            for s in domain_list:
                weighted_score = 0.0
                for pillar, weight in DEFAULT_WEIGHTS.items():
                    ps = s.pillar_scores.get(pillar) or 0.0
                    weighted_score += ps * (weight / 100.0)
                predicted = weighted_score >= 50
                if predicted == s.obs_mentioned:
                    correct += 1

            print(f"  DOMAIN ACCURACY: {correct}/{total} = {correct/total*100:.1f}%")

        print("\n" + "=" * 80)
        print("SUMMARY: All holdout samples metrics")
        print("=" * 80)

        holdout_samples = []
        for domain in holdout_domains:
            holdout_samples.extend(domain_samples[domain])

        total = 0
        correct = 0
        over = 0  # Predicted findable but wasn't
        under = 0  # Predicted not findable but was
        scores = []

        for s in holdout_samples:
            # Check weight coverage
            if get_weight_coverage(s) < 70.0:
                continue

            weighted_score = 0.0
            for pillar, weight in DEFAULT_WEIGHTS.items():
                ps = s.pillar_scores.get(pillar) or 0.0
                weighted_score += ps * (weight / 100.0)

            scores.append(weighted_score)
            predicted = weighted_score >= 50
            actual = s.obs_mentioned

            total += 1
            if predicted == actual:
                correct += 1
            elif predicted and not actual:
                over += 1
            else:
                under += 1

        if scores:
            print(f"Holdout samples analyzed: {total}")
            print(f"Weighted score range: {min(scores):.1f} - {max(scores):.1f}")
            print(f"Weighted score avg: {sum(scores)/len(scores):.1f}")
            print(
                f"Scores >= 50: {sum(1 for s in scores if s >= 50)} ({sum(1 for s in scores if s >= 50)/len(scores)*100:.1f}%)"
            )
            print(
                f"Scores < 50: {sum(1 for s in scores if s < 50)} ({sum(1 for s in scores if s < 50)/len(scores)*100:.1f}%)"
            )
            print()
            print(f"Correct: {correct} ({correct/total*100:.1f}%)")
            print(f"Over (false positive): {over} ({over/total*100:.1f}%)")
            print(f"Under (false negative): {under} ({under/total*100:.1f}%)")

        # Compare with training samples
        print("\n" + "=" * 80)
        print("TRAINING VS HOLDOUT COMPARISON")
        print("=" * 80)

        training_samples = []
        for domain in set(domains) - holdout_domains:
            training_samples.extend(domain_samples[domain])

        # Training stats
        training_scores = []
        for s in training_samples:
            non_null = sum(1 for p in pillar_keys if s.pillar_scores.get(p) is not None)
            if non_null < 5:
                continue
            weighted_score = 0.0
            for pillar, weight in DEFAULT_WEIGHTS.items():
                ps = s.pillar_scores.get(pillar) or 0.0
                weighted_score += ps * (weight / 100.0)
            training_scores.append(weighted_score)

        training_mentioned = sum(1 for s in training_samples if s.obs_mentioned)
        holdout_mentioned = sum(1 for s in holdout_samples if s.obs_mentioned)

        print(
            f"Training: {len(training_samples)} samples, avg score={sum(training_scores)/len(training_scores) if training_scores else 0:.1f}"
        )
        print(
            f"  obs_mentioned=True: {training_mentioned} ({training_mentioned/len(training_samples)*100:.1f}%)"
        )
        print(
            f"Holdout: {len(holdout_samples)} samples, avg score={sum(scores)/len(scores) if scores else 0:.1f}"
        )
        print(
            f"  obs_mentioned=True: {holdout_mentioned} ({holdout_mentioned/len(holdout_samples)*100:.1f}%)"
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
