#!/usr/bin/env python
"""Validation Runner - Accuracy Metrics & Disagreement Analysis.

Runs validation on sites and outputs:
1. Prediction accuracy (correct/optimistic/pessimistic breakdown)
2. Disagreement cases with explanations of WHY predictions failed
3. Top drivers of mismatch for calibration insights

Usage:
    # Run on default test sites
    python scripts/run_validation.py

    # Run on specific URLs
    python scripts/run_validation.py --sites "https://httpbin.org,https://example.com"

    # Run on validation study corpus (quick subset)
    python scripts/run_validation.py --corpus --max-sites 5

    # Full validation with detailed output
    python scripts/run_validation.py --corpus --verbose
"""

import argparse
import asyncio
import json
import sys
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, ".")


@dataclass
class DisagreementCase:
    """A case where prediction disagreed with observation."""

    question_text: str
    question_category: str
    site_domain: str

    # Prediction
    sim_answerability: str
    sim_score: float
    sim_signals_found: int
    sim_signals_total: int
    sim_top_chunks: list[str] = field(default_factory=list)

    # Observation
    obs_mentioned: bool = False
    obs_cited: bool = False
    obs_provider: str = ""
    obs_model: str = ""

    # Analysis
    outcome: str = ""  # "optimistic" or "pessimistic"
    explanation: str = ""
    mismatch_driver: str = ""  # Primary reason for mismatch


@dataclass
class ValidationResult:
    """Results from a validation run."""

    run_id: str
    started_at: str
    completed_at: str = ""

    # Sites processed
    sites_tested: int = 0
    sites_succeeded: int = 0
    sites_failed: int = 0

    # Accuracy metrics
    total_questions: int = 0
    correct_predictions: int = 0
    optimistic_predictions: int = 0  # False positives
    pessimistic_predictions: int = 0  # False negatives
    unknown_predictions: int = 0

    # Derived metrics
    accuracy: float = 0.0
    optimism_rate: float = 0.0
    pessimism_rate: float = 0.0

    # Breakdowns
    accuracy_by_category: dict[str, float] = field(default_factory=dict)
    accuracy_by_provider: dict[str, float] = field(default_factory=dict)

    # Disagreement analysis
    disagreement_cases: list[DisagreementCase] = field(default_factory=list)
    top_mismatch_drivers: list[tuple[str, int]] = field(default_factory=list)

    # Raw data
    per_site_results: list[dict] = field(default_factory=list)

    def calculate_metrics(self) -> None:
        """Calculate derived metrics from raw counts."""
        known = (
            self.correct_predictions + self.optimistic_predictions + self.pessimistic_predictions
        )
        if known > 0:
            self.accuracy = self.correct_predictions / known
            self.optimism_rate = self.optimistic_predictions / known
            self.pessimism_rate = self.pessimistic_predictions / known


def identify_mismatch_driver(case: DisagreementCase) -> str:
    """Analyze WHY a prediction was wrong and categorize the driver."""
    if case.outcome == "optimistic":
        # We predicted positive but AI didn't cite/mention
        if case.sim_signals_found < case.sim_signals_total * 0.5:
            return "low_signal_coverage"
        if case.sim_score < 50:
            return "borderline_score"
        if (
            "product" in case.question_category.lower()
            or "service" in case.question_category.lower()
        ):
            return "commercial_query_bias"
        if case.sim_top_chunks and len(case.sim_top_chunks[0]) < 200:
            return "thin_content"
        return "unknown_optimism"
    else:
        # We predicted negative but AI DID cite/mention
        if case.obs_cited:
            return "brand_authority_override"  # Brand is well-known despite low score
        if "what is" in case.question_text.lower() or "who is" in case.question_text.lower():
            return "identity_query_override"  # AI knows entity from training
        if case.obs_provider in ["perplexity", "openai"]:
            return "provider_specific_behavior"
        return "unknown_pessimism"


async def run_single_site_validation(
    url: str,
    company_name: str | None = None,
    max_pages: int = 10,
    verbose: bool = False,
) -> dict:
    """Run validation on a single site and return accuracy data."""

    from worker.chunking.chunker import SemanticChunker
    from worker.crawler.crawler import crawl_site
    from worker.embeddings.embedder import Embedder
    from worker.extraction.extractor import ContentExtractor
    from worker.observation.comparison import SimulationObservationComparator
    from worker.observation.models import ProviderType
    from worker.observation.runner import ObservationRunner, RunConfig
    from worker.questions.generator import QuestionGenerator, SiteContext
    from worker.retrieval.retriever import HybridRetriever
    from worker.simulation.runner import SimulationRunner

    parsed = urlparse(url)
    domain = parsed.netloc
    if not company_name:
        company_name = domain.split(".")[0].title()

    result = {
        "url": url,
        "domain": domain,
        "company_name": company_name,
        "success": False,
        "error": None,
        "questions": [],
        "accuracy_data": {
            "correct": 0,
            "optimistic": 0,
            "pessimistic": 0,
            "unknown": 0,
        },
        "disagreements": [],
    }

    try:
        if verbose:
            print(f"  [1/6] Crawling {url}...")
        crawl_result = await crawl_site(url=url, max_pages=max_pages, max_depth=2)
        if not crawl_result.pages:
            result["error"] = "No pages crawled"
            return result

        if verbose:
            print(f"  [2/6] Extracting content ({len(crawl_result.pages)} pages)...")
        extractor = ContentExtractor()
        extraction_result = extractor.extract_crawl(crawl_result)

        if verbose:
            print("  [3/6] Chunking and embedding...")
        chunker = SemanticChunker()
        chunked_pages = []
        for page in extraction_result.pages:
            chunked_page = chunker.chunk_text(
                text=page.main_content,
                url=page.url,
                title=page.title,
            )
            chunked_pages.append(chunked_page)

        embedder = Embedder()
        embedded_pages = embedder.embed_pages(chunked_pages)

        retriever = HybridRetriever(embedder=embedder)
        for page_idx, ep in enumerate(embedded_pages):
            for emb_result in ep.embeddings:
                chunk = chunked_pages[page_idx].chunks[emb_result.chunk_index]
                retriever.add_document(
                    doc_id=emb_result.content_hash,
                    content=chunk.content,
                    embedding=emb_result.embedding,
                    source_url=emb_result.source_url,
                    page_title=emb_result.page_title,
                    heading_context=emb_result.heading_context,
                )

        if verbose:
            print("  [4/6] Generating questions and running simulation...")
        schema_types = list(set(extraction_result.schema_types_found))
        headings = {"h1": [], "h2": [], "h3": []}
        for page in extraction_result.pages:
            page_headings = page.metadata.headings or {}
            for level in ["h1", "h2", "h3"]:
                if level in page_headings:
                    headings[level].extend(page_headings[level])

        site_context = SiteContext(
            company_name=company_name,
            domain=domain,
            schema_types=schema_types,
            headings=headings,
        )

        question_generator = QuestionGenerator()
        questions = question_generator.generate(site_context)

        site_id = uuid.uuid4()
        run_id = uuid.uuid4()

        simulation_runner = SimulationRunner(retriever=retriever)
        simulation_result = simulation_runner.run(
            site_id=site_id,
            run_id=run_id,
            company_name=company_name,
            questions=questions,
        )

        if verbose:
            print("  [5/6] Running observation (Mock Provider)...")

        run_config = RunConfig(
            primary_provider=ProviderType.MOCK,
            fallback_provider=ProviderType.MOCK,
            max_retries=1,
            request_timeout_seconds=30,
            concurrent_requests=5,
        )

        questions_for_obs = [(q.id, q.text) for q in questions]
        observation_runner = ObservationRunner(config=run_config)
        observation_run = await observation_runner.run_observation(
            site_id=site_id,
            run_id=run_id,
            company_name=company_name,
            domain=domain,
            questions=questions_for_obs,
        )

        if verbose:
            print("  [6/6] Comparing predictions vs observations...")

        comparator = SimulationObservationComparator()
        comparison = comparator.compare(
            simulation_result=simulation_result,
            observation_run=observation_run,
        )

        # Process comparison results
        for q_comp in comparison.question_comparisons:
            q_result = {
                "question_text": q_comp.question_text[:100],
                "question_category": q_comp.question_category,
                "sim_answerability": (
                    q_comp.sim_answerability.value if q_comp.sim_answerability else "unknown"
                ),
                "sim_score": q_comp.sim_score,
                "obs_mentioned": q_comp.obs_mentioned,
                "obs_cited": q_comp.obs_cited,
                "outcome": q_comp.outcome_match.value,
                "accurate": q_comp.prediction_accurate,
            }
            result["questions"].append(q_result)

            # Count by outcome
            if q_comp.outcome_match.value == "correct":
                result["accuracy_data"]["correct"] += 1
            elif q_comp.outcome_match.value == "optimistic":
                result["accuracy_data"]["optimistic"] += 1

                # Create disagreement case
                disagreement = DisagreementCase(
                    question_text=q_comp.question_text,
                    question_category=q_comp.question_category,
                    site_domain=domain,
                    sim_answerability=(
                        q_comp.sim_answerability.value if q_comp.sim_answerability else "unknown"
                    ),
                    sim_score=q_comp.sim_score,
                    sim_signals_found=q_comp.sim_signals_found or 0,
                    sim_signals_total=q_comp.sim_signals_total or 1,
                    sim_top_chunks=[],  # Would need to capture from simulation
                    obs_mentioned=q_comp.obs_mentioned,
                    obs_cited=q_comp.obs_cited,
                    obs_provider="mock",
                    obs_model="mock",
                    outcome="optimistic",
                    explanation=q_comp.explanation or "Predicted answerable but AI did not cite",
                )
                disagreement.mismatch_driver = identify_mismatch_driver(disagreement)
                result["disagreements"].append(asdict(disagreement))

            elif q_comp.outcome_match.value == "pessimistic":
                result["accuracy_data"]["pessimistic"] += 1

                disagreement = DisagreementCase(
                    question_text=q_comp.question_text,
                    question_category=q_comp.question_category,
                    site_domain=domain,
                    sim_answerability=(
                        q_comp.sim_answerability.value if q_comp.sim_answerability else "unknown"
                    ),
                    sim_score=q_comp.sim_score,
                    sim_signals_found=q_comp.sim_signals_found or 0,
                    sim_signals_total=q_comp.sim_signals_total or 1,
                    obs_mentioned=q_comp.obs_mentioned,
                    obs_cited=q_comp.obs_cited,
                    obs_provider="mock",
                    obs_model="mock",
                    outcome="pessimistic",
                    explanation=q_comp.explanation or "Predicted not answerable but AI cited",
                )
                disagreement.mismatch_driver = identify_mismatch_driver(disagreement)
                result["disagreements"].append(asdict(disagreement))

            else:
                result["accuracy_data"]["unknown"] += 1

        result["success"] = True

    except Exception as e:
        result["error"] = str(e)

    return result


async def run_validation(
    sites: list[tuple[str, str | None]],  # [(url, company_name), ...]
    max_pages: int = 10,
    verbose: bool = False,
) -> ValidationResult:
    """Run validation on multiple sites."""
    validation = ValidationResult(
        run_id=str(uuid.uuid4()),
        started_at=datetime.now(UTC).isoformat(),
    )

    all_drivers = []

    for i, (url, company_name) in enumerate(sites):
        print(f"\n[{i+1}/{len(sites)}] Validating {url}...")

        site_result = await run_single_site_validation(
            url=url,
            company_name=company_name,
            max_pages=max_pages,
            verbose=verbose,
        )

        if site_result["success"]:
            validation.sites_succeeded += 1
            validation.total_questions += len(site_result["questions"])
            validation.correct_predictions += site_result["accuracy_data"]["correct"]
            validation.optimistic_predictions += site_result["accuracy_data"]["optimistic"]
            validation.pessimistic_predictions += site_result["accuracy_data"]["pessimistic"]
            validation.unknown_predictions += site_result["accuracy_data"]["unknown"]

            # Collect disagreements
            for disagreement in site_result["disagreements"]:
                validation.disagreement_cases.append(DisagreementCase(**disagreement))
                all_drivers.append(disagreement["mismatch_driver"])

            print(
                f"    Accuracy: {site_result['accuracy_data']['correct']}/{len(site_result['questions'])} correct"
            )
            if site_result["accuracy_data"]["optimistic"]:
                print(
                    f"    Optimistic: {site_result['accuracy_data']['optimistic']} (false positives)"
                )
            if site_result["accuracy_data"]["pessimistic"]:
                print(
                    f"    Pessimistic: {site_result['accuracy_data']['pessimistic']} (false negatives)"
                )
        else:
            validation.sites_failed += 1
            print(f"    FAILED: {site_result['error']}")

        validation.per_site_results.append(site_result)
        validation.sites_tested += 1

    # Calculate final metrics
    validation.calculate_metrics()

    # Top mismatch drivers
    driver_counts = Counter(all_drivers)
    validation.top_mismatch_drivers = driver_counts.most_common(10)

    validation.completed_at = datetime.now(UTC).isoformat()

    return validation


def print_validation_report(validation: ValidationResult) -> None:
    """Print a human-readable validation report."""
    print("\n" + "=" * 70)
    print("VALIDATION REPORT")
    print("=" * 70)

    print(f"\nRun ID: {validation.run_id}")
    print(f"Started: {validation.started_at}")
    print(f"Completed: {validation.completed_at}")

    print("\n--- SITES ---")
    print(f"Tested: {validation.sites_tested}")
    print(f"Succeeded: {validation.sites_succeeded}")
    print(f"Failed: {validation.sites_failed}")

    print("\n--- ACCURACY METRICS ---")
    print(f"Total Questions: {validation.total_questions}")
    print(f"Correct Predictions: {validation.correct_predictions}")
    print(f"Optimistic (False Positives): {validation.optimistic_predictions}")
    print(f"Pessimistic (False Negatives): {validation.pessimistic_predictions}")
    print(f"Unknown: {validation.unknown_predictions}")

    print(f"\n  ACCURACY: {validation.accuracy:.1%}")
    print(f"  Optimism Rate: {validation.optimism_rate:.1%}")
    print(f"  Pessimism Rate: {validation.pessimism_rate:.1%}")

    if validation.top_mismatch_drivers:
        print("\n--- TOP MISMATCH DRIVERS ---")
        for driver, count in validation.top_mismatch_drivers:
            print(f"  {driver}: {count}")

    if validation.disagreement_cases:
        print(f"\n--- DISAGREEMENT CASES ({len(validation.disagreement_cases)} total) ---")
        print("-" * 70)

        # Show up to 10 examples
        for i, case in enumerate(validation.disagreement_cases[:10]):
            print(f"\n[{i+1}] {case.outcome.upper()}: {case.question_text[:60]}...")
            print(f"    Site: {case.site_domain}")
            print(f"    Category: {case.question_category}")
            print(
                f"    Sim: {case.sim_answerability} (score={case.sim_score:.2f}, signals={case.sim_signals_found}/{case.sim_signals_total})"
            )
            print(f"    Obs: mentioned={case.obs_mentioned}, cited={case.obs_cited}")
            print(f"    Driver: {case.mismatch_driver}")
            print(f"    Why: {case.explanation[:100]}")

        if len(validation.disagreement_cases) > 10:
            print(f"\n    ... and {len(validation.disagreement_cases) - 10} more disagreements")

    print("\n" + "=" * 70)


def save_validation_results(validation: ValidationResult, output_dir: Path) -> None:
    """Save validation results to files."""
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    # Save summary
    summary = {
        "run_id": validation.run_id,
        "started_at": validation.started_at,
        "completed_at": validation.completed_at,
        "sites_tested": validation.sites_tested,
        "sites_succeeded": validation.sites_succeeded,
        "total_questions": validation.total_questions,
        "accuracy": validation.accuracy,
        "optimism_rate": validation.optimism_rate,
        "pessimism_rate": validation.pessimism_rate,
        "top_mismatch_drivers": validation.top_mismatch_drivers,
    }
    summary_file = output_dir / f"validation_summary_{timestamp}.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)

    # Save disagreements
    disagreements_file = output_dir / f"disagreements_{timestamp}.json"
    with open(disagreements_file, "w") as f:
        json.dump([asdict(d) for d in validation.disagreement_cases], f, indent=2)

    # Save full results
    full_file = output_dir / f"validation_full_{timestamp}.json"
    with open(full_file, "w") as f:
        json.dump(validation.per_site_results, f, indent=2)

    print(f"\nResults saved to {output_dir}/")
    print(f"  - {summary_file.name}")
    print(f"  - {disagreements_file.name}")
    print(f"  - {full_file.name}")


def main():
    parser = argparse.ArgumentParser(
        description="Run validation and output accuracy metrics + disagreement cases"
    )
    parser.add_argument(
        "--sites",
        type=str,
        help="Comma-separated list of URLs to validate",
    )
    parser.add_argument(
        "--corpus",
        action="store_true",
        help="Use validation study corpus",
    )
    parser.add_argument(
        "--max-sites",
        type=int,
        default=5,
        help="Max sites to test from corpus",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help="Max pages to crawl per site",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="validation_results",
        help="Directory to save results",
    )

    args = parser.parse_args()

    # Build site list
    sites: list[tuple[str, str | None]] = []

    if args.sites:
        for url in args.sites.split(","):
            url = url.strip()
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            sites.append((url, None))
    elif args.corpus:
        from scripts.validation_study.corpus import get_real_sites

        corpus_sites = get_real_sites()
        for site in corpus_sites[: args.max_sites]:
            sites.append((site.url, site.name))
    else:
        # Default test sites
        sites = [
            ("https://httpbin.org", "HTTPBin"),
            ("https://example.com", "Example"),
        ]

    print("=" * 70)
    print("FINDABLE SCORE VALIDATION RUNNER")
    print("=" * 70)
    print(f"Sites to validate: {len(sites)}")
    print(f"Max pages per site: {args.max_pages}")
    print(f"Verbose: {args.verbose}")

    # Run validation
    validation = asyncio.run(
        run_validation(
            sites=sites,
            max_pages=args.max_pages,
            verbose=args.verbose,
        )
    )

    # Print report
    print_validation_report(validation)

    # Save results
    output_dir = Path(args.output_dir)
    save_validation_results(validation, output_dir)


if __name__ == "__main__":
    main()
