"""CLI runner for real-world validation testing.

Usage:
    python -m worker.testing.runner --corpus full --queries all --output results/
    python -m worker.testing.runner --corpus quick --skip-ai-queries
    python -m worker.testing.runner --url https://example.com --queries all
"""

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import click
import structlog

from worker.testing.config import AIQueryConfig, TestRunConfig
from worker.testing.corpus import SiteCategory, TestCorpus, TestSite
from worker.testing.queries import (
    TEST_QUERIES,
    QueryCategory,
    get_geo_queries,
    get_queries_by_category,
)

logger = structlog.get_logger(__name__)


def get_corpus(corpus_name: str) -> TestCorpus:
    """Get test corpus by name."""
    corpus_map = {
        "full": TestCorpus.full,
        "quick": TestCorpus.quick,
        "own": TestCorpus.own,
        "competitors": TestCorpus.competitors,
        "known_cited": TestCorpus.known_cited,
        "known_uncited": TestCorpus.known_uncited,
    }
    if corpus_name not in corpus_map:
        raise click.BadParameter(f"Unknown corpus: {corpus_name}")
    return corpus_map[corpus_name]()


def get_queries(query_filter: str) -> list:
    """Get queries by filter."""
    if query_filter == "all":
        return TEST_QUERIES
    elif query_filter == "informational":
        return get_queries_by_category(QueryCategory.INFORMATIONAL)
    elif query_filter == "tools":
        return get_queries_by_category(QueryCategory.TOOL_COMPARISON)
    elif query_filter == "how_to":
        return get_queries_by_category(QueryCategory.HOW_TO)
    elif query_filter == "technical":
        return get_queries_by_category(QueryCategory.TECHNICAL)
    elif query_filter == "brand":
        return get_queries_by_category(QueryCategory.BRAND)
    elif query_filter == "geo":
        return get_geo_queries()
    else:
        raise click.BadParameter(f"Unknown query filter: {query_filter}")


def setup_output_dir(config: TestRunConfig) -> Path:
    """Create output directory structure."""
    output_dir = config.run_output_dir

    # Create directory structure
    (output_dir / "raw" / "pipeline").mkdir(parents=True, exist_ok=True)
    (output_dir / "raw" / "ai_responses").mkdir(parents=True, exist_ok=True)
    (output_dir / "raw" / "ground_truth").mkdir(parents=True, exist_ok=True)
    (output_dir / "analysis").mkdir(parents=True, exist_ok=True)
    (output_dir / "reports" / "per_site").mkdir(parents=True, exist_ok=True)

    return output_dir


def save_run_metadata(config: TestRunConfig, corpus: TestCorpus, queries: list):
    """Save run metadata to output directory."""
    output_dir = config.run_output_dir

    metadata = {
        "run_id": config.run_id,
        "started_at": datetime.now(UTC).isoformat(),
        "config": config.to_dict(),
        "corpus": corpus.to_dict(),
        "query_count": len(queries),
        "queries": [
            {
                "query": q.query,
                "category": q.category.value,
                "expected_sources": q.expected_sources,
            }
            for q in queries
        ],
    }

    with open(output_dir / "run_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info("run_metadata_saved", output_dir=str(output_dir))


def print_run_summary(config: TestRunConfig, corpus: TestCorpus, queries: list):
    """Print a summary of what will be run."""
    click.echo("\n" + "=" * 60)
    click.echo("REAL-WORLD VALIDATION TEST RUN")
    click.echo("=" * 60)
    click.echo(f"\nRun ID: {config.run_id}")
    click.echo(f"Output: {config.run_output_dir}")
    click.echo(f"\nCorpus: {corpus.name} ({len(corpus)} sites)")

    # Show site breakdown by category
    categories = {}
    for site in corpus.sites:
        cat = site.category.value
        categories[cat] = categories.get(cat, 0) + 1
    for cat, count in sorted(categories.items()):
        click.echo(f"  - {cat}: {count}")

    click.echo(f"\nQueries: {len(queries)}")

    # Show query breakdown by category
    query_cats = {}
    for q in queries:
        cat = q.category.value
        query_cats[cat] = query_cats.get(cat, 0) + 1
    for cat, count in sorted(query_cats.items()):
        click.echo(f"  - {cat}: {count}")

    click.echo("\nOptions:")
    click.echo(f"  - Skip AI queries: {config.skip_ai_queries}")
    click.echo(f"  - Skip pipeline: {config.skip_pipeline}")
    click.echo(f"  - Site concurrency: {config.site_concurrency}")
    click.echo(f"  - Verbose: {config.verbose}")

    if config.dry_run:
        click.echo("\n[DRY RUN - No actual processing will occur]")

    click.echo("\n" + "-" * 60)


async def run_validation_async(config: TestRunConfig) -> dict:
    """Run the validation pipeline asynchronously."""
    # Get corpus and queries
    corpus = get_corpus(config.corpus)
    queries = get_queries(config.query_filter)

    # Setup output
    output_dir = setup_output_dir(config)
    save_run_metadata(config, corpus, queries)

    # Print summary
    print_run_summary(config, corpus, queries)

    if config.dry_run:
        return {"status": "dry_run", "sites": len(corpus), "queries": len(queries)}

    results = {
        "run_id": config.run_id,
        "started_at": datetime.now(UTC).isoformat(),
        "corpus_name": corpus.name,
        "site_count": len(corpus),
        "query_count": len(queries),
        "pipeline_results": [],
        "ground_truth_results": [],
        "comparisons": [],
        "errors": [],
    }

    click.echo("\nPhase 1: Running scoring pipeline on test sites...")
    click.echo("-" * 40)

    if not config.skip_pipeline:
        from worker.testing.pipeline import PipelineConfig, run_pipeline_batch

        # Create pipeline config from test run config
        pipeline_config = PipelineConfig(
            max_pages=config.pipeline.max_pages if config.pipeline else 50,
            max_depth=config.pipeline.max_depth if config.pipeline else 2,
            cache_ttl_hours=config.pipeline.cache_ttl_hours if config.pipeline else 24,
        )

        # Get URLs from corpus
        urls = [site.url for site in corpus.sites]
        cache_dir = output_dir / "raw" / "pipeline"

        click.echo(
            f"  Running pipeline on {len(urls)} sites (concurrency: {config.site_concurrency})..."
        )

        # Run pipeline on all sites
        pipeline_results = await run_pipeline_batch(
            urls=urls,
            config=pipeline_config,
            cache_dir=cache_dir,
            use_cache=True,
            concurrency=config.site_concurrency,
        )

        # Process results
        success_count = 0
        cached_count = 0
        failed_count = 0

        for i, (site, result) in enumerate(zip(corpus.sites, pipeline_results, strict=False), 1):
            status_icon = (
                "✓" if result.status == "success" else ("●" if result.status == "cached" else "✗")
            )

            if result.status == "success":
                success_count += 1
                click.echo(
                    f"  [{i}/{len(corpus)}] {status_icon} {site.name}: score={result.overall_score:.1f}"
                )
            elif result.status == "cached":
                cached_count += 1
                click.echo(
                    f"  [{i}/{len(corpus)}] {status_icon} {site.name}: score={result.overall_score:.1f} (cached)"
                )
            else:
                failed_count += 1
                click.echo(
                    f"  [{i}/{len(corpus)}] {status_icon} {site.name}: FAILED - {result.error_message}"
                )

            # Add to results
            results["pipeline_results"].append(result.to_dict())

            # Track errors
            if result.status == "failed":
                results["errors"].append(
                    {
                        "phase": "pipeline",
                        "site": site.url,
                        "error": result.error_message,
                    }
                )

        click.echo(
            f"\n  Summary: {success_count} success, {cached_count} cached, {failed_count} failed"
        )
    else:
        click.echo("  [Skipped - using cached results]")
        # Try to load cached results
        cache_dir = output_dir / "raw" / "pipeline"
        for site in corpus.sites:
            from worker.testing.pipeline import PipelineConfig, load_cached_result

            pipeline_config = PipelineConfig()
            cached = load_cached_result(site.url, pipeline_config, cache_dir)
            if cached:
                results["pipeline_results"].append(cached.to_dict())

    click.echo("\nPhase 2: Querying AI systems for ground truth...")
    click.echo("-" * 40)

    if not config.skip_ai_queries:
        from worker.testing.ground_truth import collect_ground_truth_batch

        # Get AI query config
        ai_config = config.ai_query if config.ai_query else AIQueryConfig()
        cache_dir = output_dir / "raw" / "ground_truth"

        # Build provider list for display
        providers = []
        if ai_config.query_chatgpt:
            providers.append("ChatGPT")
        if ai_config.query_claude:
            providers.append("Claude")
        if ai_config.query_perplexity:
            providers.append("Perplexity")

        click.echo(
            f"  Querying {len(queries)} queries across {len(providers)} providers: {', '.join(providers)}"
        )
        click.echo(f"  (concurrency: {config.query_concurrency})")

        # Run ground truth collection
        ground_truth_results = await collect_ground_truth_batch(
            queries=queries,
            config=ai_config,
            cache_dir=cache_dir,
            use_cache=True,
            concurrency=config.query_concurrency,
        )

        # Process results
        success_count = 0
        cached_count = 0
        error_count = 0

        for i, gt_result in enumerate(ground_truth_results, 1):
            if gt_result.cached:
                cached_count += 1
                icon = "●"
            elif any(r.error for r in gt_result.provider_responses):
                error_count += 1
                icon = "✗"
            else:
                success_count += 1
                icon = "✓"

            # Show first 10 queries in detail
            if i <= 10:
                domains_found = len(gt_result.all_cited_domains)
                query_preview = (
                    gt_result.query[:40] + "..." if len(gt_result.query) > 40 else gt_result.query
                )
                status = "(cached)" if gt_result.cached else ""
                click.echo(
                    f"  [{i}/{len(queries)}] {icon} {query_preview}: {domains_found} domains {status}"
                )

            results["ground_truth_results"].append(gt_result.to_dict())

            # Track errors
            for response in gt_result.provider_responses:
                if response.error:
                    results["errors"].append(
                        {
                            "phase": "ground_truth",
                            "query": gt_result.query[:50],
                            "provider": response.provider,
                            "error": response.error,
                        }
                    )

        if len(queries) > 10:
            click.echo(f"  ... and {len(queries) - 10} more queries")

        click.echo(
            f"\n  Summary: {success_count} success, {cached_count} cached, {error_count} errors"
        )
    else:
        click.echo("  [Skipped - using cached ground truth]")
        # Try to load cached results
        cache_dir = output_dir / "raw" / "ground_truth"
        if cache_dir.exists():
            from worker.testing.ground_truth import load_cached_result

            ai_config = config.ai_query if config.ai_query else AIQueryConfig()
            providers = []
            if ai_config.query_chatgpt:
                providers.append("chatgpt")
            if ai_config.query_claude:
                providers.append("claude")
            if ai_config.query_perplexity:
                providers.append("perplexity")

            for query in queries:
                cached = load_cached_result(
                    query.query, providers, cache_dir, ai_config.cache_ttl_hours
                )
                if cached:
                    results["ground_truth_results"].append(cached.to_dict())

    click.echo("\nPhase 3: Comparing predictions to reality...")
    click.echo("-" * 40)

    from worker.testing.comparison import compare_all
    from worker.testing.ground_truth import GroundTruthResult
    from worker.testing.pipeline import PipelineResult

    # Reconstruct objects from results dicts
    pipeline_objs = [PipelineResult.from_dict(r) for r in results.get("pipeline_results", [])]
    ground_truth_objs = [
        GroundTruthResult.from_dict(r) for r in results.get("ground_truth_results", [])
    ]

    if pipeline_objs and ground_truth_objs:
        validation_report = compare_all(
            sites=corpus.sites,
            pipeline_results=pipeline_objs,
            ground_truth_results=ground_truth_objs,
            run_id=config.run_id,
            corpus_name=corpus.name,
        )

        results["comparisons"] = [c.to_dict() for c in validation_report.site_comparisons]
        results["validation_metrics"] = (
            validation_report.metrics.to_dict() if validation_report.metrics else None
        )
        results["insights"] = validation_report.insights
        results["recommendations"] = validation_report.recommendations

        # Display comparison summary
        metrics = validation_report.metrics
        if metrics:
            click.echo(f"  Sites compared: {metrics.sites_compared}")
            click.echo(f"  Accuracy: {metrics.accuracy:.1%}")
            click.echo(f"  Precision: {metrics.precision:.1%}")
            click.echo(f"  Recall: {metrics.recall:.1%}")
            click.echo(f"  F1 Score: {metrics.f1_score:.2f}")
            click.echo(f"\n  True Positives: {metrics.true_positives}")
            click.echo(f"  True Negatives: {metrics.true_negatives}")
            click.echo(f"  False Positives: {metrics.false_positives} (optimistic)")
            click.echo(f"  False Negatives: {metrics.false_negatives} (pessimistic)")
    else:
        click.echo("  [Insufficient data for comparison]")
        validation_report = None

    click.echo("\nPhase 4: Generating validation report...")
    click.echo("-" * 40)

    results["completed_at"] = datetime.now(UTC).isoformat()

    # Save validation report
    if validation_report:
        report_path = output_dir / "reports" / "validation_report.json"
        with open(report_path, "w") as f:
            json.dump(validation_report.to_dict(), f, indent=2)
        click.echo(f"  Validation report: {report_path}")

        # Display insights
        if validation_report.insights:
            click.echo("\n  Insights:")
            for insight in validation_report.insights:
                click.echo(f"    • {insight}")

        # Display recommendations
        if validation_report.recommendations:
            click.echo("\n  Recommendations:")
            for rec in validation_report.recommendations:
                click.echo(f"    → {rec}")

        # Save per-site reports
        for comparison in validation_report.site_comparisons:
            site_report_path = (
                output_dir / "reports" / "per_site" / f"{comparison.site_domain}.json"
            )
            with open(site_report_path, "w") as f:
                json.dump(comparison.to_dict(), f, indent=2)
    else:
        click.echo("  [No validation report generated - insufficient data]")

    # Save full run results
    with open(output_dir / "analysis" / "run_results.json", "w") as f:
        json.dump(results, f, indent=2)

    click.echo("\n" + "=" * 60)
    click.echo("RUN COMPLETE")
    click.echo("=" * 60)
    click.echo(f"\nResults saved to: {output_dir}")

    return results


@click.command()
@click.option(
    "--corpus",
    type=click.Choice(["full", "quick", "own", "competitors", "known_cited", "known_uncited"]),
    default="quick",
    help="Test corpus to use",
)
@click.option(
    "--queries",
    "query_filter",
    type=click.Choice(["all", "informational", "tools", "how_to", "technical", "brand", "geo"]),
    default="all",
    help="Query filter",
)
@click.option(
    "--output",
    type=click.Path(),
    default="results",
    help="Output directory",
)
@click.option(
    "--url",
    type=str,
    default=None,
    help="Single URL to test (overrides corpus)",
)
@click.option(
    "--skip-ai-queries",
    is_flag=True,
    help="Skip AI queries, use cached ground truth",
)
@click.option(
    "--skip-pipeline",
    is_flag=True,
    help="Skip pipeline, use cached results",
)
@click.option(
    "--use-cache",
    is_flag=True,
    help="Use all cached data where available",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without actually running",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Verbose output",
)
@click.option(
    "--concurrency",
    type=int,
    default=3,
    help="Number of sites to process concurrently",
)
def run_validation(
    corpus: str,
    query_filter: str,
    output: str,
    url: str | None,
    skip_ai_queries: bool,
    skip_pipeline: bool,
    use_cache: bool,
    dry_run: bool,
    verbose: bool,
    concurrency: int,
):
    """Run real-world validation against test corpus.

    This tool validates Findable Score predictions against actual AI citation
    behavior by:

    1. Running the scoring pipeline on test sites
    2. Querying AI systems (ChatGPT, Perplexity, etc.) with test queries
    3. Comparing predicted findability to actual citations
    4. Generating a validation report with accuracy metrics

    Examples:

        # Quick validation run
        python -m worker.testing.runner --corpus quick --dry-run

        # Full validation with all queries
        python -m worker.testing.runner --corpus full --queries all

        # Test own properties only
        python -m worker.testing.runner --corpus own --queries geo

        # Single site deep dive
        python -m worker.testing.runner --url https://moz.com --queries all

        # Re-run with cached AI responses (save API costs)
        python -m worker.testing.runner --corpus full --use-cache
    """
    # Build config
    config = TestRunConfig(
        corpus=corpus if not url else "custom",
        query_filter=query_filter,
        output_dir=Path(output),
        skip_ai_queries=skip_ai_queries or use_cache,
        skip_pipeline=skip_pipeline or use_cache,
        verbose=verbose,
        dry_run=dry_run,
        site_concurrency=concurrency,
    )

    # Handle single URL mode
    if url:
        # Create a custom corpus with just this URL
        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")

        custom_site = TestSite(
            url=url,
            name=domain,
            category=SiteCategory.OWN_PROPERTY,  # Treat as own for testing
            notes="Single URL test",
        )

        # Override the corpus getter for this run
        global get_corpus
        original_get_corpus = get_corpus

        def custom_corpus_getter(name):
            if name == "custom":
                return TestCorpus(
                    sites=[custom_site], name="custom", description=f"Single URL: {url}"
                )
            return original_get_corpus(name)

        get_corpus = custom_corpus_getter

    # Run the validation
    try:
        result = asyncio.run(run_validation_async(config))
        if result.get("status") == "dry_run":
            click.echo("\nDry run complete. Use without --dry-run to execute.")
    except KeyboardInterrupt:
        click.echo("\n\nInterrupted by user.")
        sys.exit(1)
    except Exception as e:
        click.echo(f"\nError: {e}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@click.command()
@click.argument("results_file", type=click.Path(exists=True))
def import_calibration(results_file: str):
    """Import calibration samples from a validation run into the database.

    RESULTS_FILE: Path to calibration_samples.json from a validation run.
    """
    click.echo(f"Importing calibration samples from: {results_file}")
    click.echo("[Import functionality not yet implemented - Session #38]")


@click.group()
def cli():
    """Real-world test runner for Findable Score validation."""
    pass


cli.add_command(run_validation, name="run")
cli.add_command(import_calibration, name="import")


if __name__ == "__main__":
    cli()
