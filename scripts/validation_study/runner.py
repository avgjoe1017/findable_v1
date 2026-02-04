#!/usr/bin/env python
"""Validation Study Runner.

Executes the full validation study:
1. Phase 1: Score all sites with Findable Score pipeline
2. Phase 2: Query AI systems for each site
3. Phase 3: Analyze correlation between scores and citations
4. Phase 4: Generate gap analysis report

Usage:
    python -m scripts.validation_study.runner --phase 1  # Score sites
    python -m scripts.validation_study.runner --phase 2  # Query AI
    python -m scripts.validation_study.runner --phase 3  # Analyze
    python -m scripts.validation_study.runner --all      # Full study
"""

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, ".")

from scripts.validation_study.corpus import (  # noqa: E402
    Quadrant,
    StudySite,
    get_all_sites,
    get_real_sites,
    get_sites_by_quadrant,
)

# Output directory
OUTPUT_DIR = Path("validation_study_results")


@dataclass
class SiteScore:
    """Findable Score results for a site."""

    site_id: str
    url: str
    name: str
    quadrant: str
    findable_score: float = 0.0
    pillar_scores: dict[str, float] = field(default_factory=dict)
    crawl_stats: dict[str, Any] = field(default_factory=dict)
    scored_at: str = ""
    error: str | None = None


@dataclass
class CitationResult:
    """Citation result from an AI query."""

    query: str
    target_site: str
    target_domain: str
    provider: str
    cited: bool = False
    mentioned: bool = False
    citation_type: str | None = None  # "direct_link", "inline", "source_list"
    position: int | None = None
    context: str | None = None
    queried_at: str = ""
    error: str | None = None


@dataclass
class StudyResults:
    """Complete study results."""

    started_at: str
    completed_at: str | None = None
    sites_scored: int = 0
    queries_executed: int = 0
    site_scores: list[SiteScore] = field(default_factory=list)
    citation_results: list[CitationResult] = field(default_factory=list)
    analysis: dict[str, Any] = field(default_factory=dict)


async def score_site(site: StudySite, max_pages: int = 20) -> SiteScore:
    """Run Findable Score pipeline on a single site."""
    from urllib.parse import urlparse

    from worker.chunking.chunker import SemanticChunker
    from worker.crawler.crawler import crawl_site
    from worker.embeddings.embedder import Embedder
    from worker.extraction.extractor import ContentExtractor
    from worker.questions.generator import QuestionGenerator, SiteContext
    from worker.retrieval.retriever import HybridRetriever
    from worker.simulation.runner import SimulationRunner

    result = SiteScore(
        site_id=site.id,
        url=site.url,
        name=site.name,
        quadrant=site.quadrant.value,
        scored_at=datetime.now(UTC).isoformat(),
    )

    try:
        parsed = urlparse(site.url)
        domain = parsed.netloc

        # Crawl
        crawl_result = await crawl_site(url=site.url, max_pages=max_pages, max_depth=2)
        result.crawl_stats = {
            "pages_crawled": len(crawl_result.pages),
            "duration_seconds": crawl_result.duration_seconds,
        }

        if not crawl_result.pages:
            result.error = "No pages crawled"
            return result

        # Extract
        extractor = ContentExtractor()
        extraction_result = extractor.extract_crawl(crawl_result)

        # Chunk and embed
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

        # Build retriever
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

        # Generate questions
        schema_types = list(set(extraction_result.schema_types_found))
        headings = {"h1": [], "h2": [], "h3": []}
        for page in extraction_result.pages:
            page_headings = page.metadata.headings or {}
            for level in ["h1", "h2", "h3"]:
                if level in page_headings:
                    headings[level].extend(page_headings[level])

        site_context = SiteContext(
            company_name=site.name,
            domain=domain,
            schema_types=schema_types,
            headings=headings,
        )

        question_generator = QuestionGenerator()
        questions = question_generator.generate(site_context)

        # Run simulation
        import uuid

        simulation_runner = SimulationRunner(retriever=retriever)
        simulation_result = simulation_runner.run(
            site_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            company_name=site.name,
            questions=questions,
        )

        result.findable_score = simulation_result.overall_score
        result.pillar_scores = {
            "technical": 70.0,  # Placeholder - need full pillar calculation
            "structure": 65.0,
            "schema": 50.0,
            "authority": 60.0,
            "retrieval": simulation_result.overall_score,
            "coverage": simulation_result.coverage_score,
        }

    except Exception as e:
        result.error = str(e)

    return result


async def query_ai_for_site(
    site: StudySite,
    queries: list[str],
    provider: str = "openrouter",
) -> list[CitationResult]:
    """Query AI system about a site and check for citations."""
    from urllib.parse import urlparse

    from api.config import get_settings
    from worker.observation.models import ProviderType
    from worker.observation.runner import ObservationRunner, RunConfig

    settings = get_settings()
    results = []

    parsed = urlparse(site.url)
    domain = parsed.netloc

    run_config = RunConfig(
        primary_provider=ProviderType.OPENROUTER,
        fallback_provider=ProviderType.OPENAI,
        openrouter_api_key=settings.openrouter_api_key,
        openai_api_key=settings.openai_api_key,
        max_retries=2,
        request_timeout_seconds=60,
        concurrent_requests=3,
    )

    runner = ObservationRunner(config=run_config)

    for query in queries:
        result = CitationResult(
            query=query,
            target_site=site.id,
            target_domain=domain,
            provider=provider,
            queried_at=datetime.now(UTC).isoformat(),
        )

        try:
            # Create observation request
            import uuid

            obs_run = await runner.run_observation(
                site_id=uuid.uuid4(),
                run_id=uuid.uuid4(),
                company_name=site.name,
                domain=domain,
                questions=[(f"q_{uuid.uuid4().hex[:8]}", query)],
            )

            if obs_run.results:
                obs_result = obs_run.results[0]
                result.cited = obs_result.url_cited
                result.mentioned = obs_result.company_mentioned

                # Determine citation type
                if obs_result.citations:
                    result.citation_type = "direct_link"
                    result.context = (
                        obs_result.response_text[:200] if obs_result.response_text else None
                    )

        except Exception as e:
            result.error = str(e)

        results.append(result)

    return results


def analyze_results(study: StudyResults) -> dict[str, Any]:
    """Analyze study results for correlation and metrics."""
    import statistics

    # Group scores by quadrant
    quadrant_scores: dict[str, list[float]] = {q.value: [] for q in Quadrant}
    for score in study.site_scores:
        if score.error is None:
            quadrant_scores[score.quadrant].append(score.findable_score)

    # Calculate citation rates per site
    site_citations: dict[str, list[bool]] = {}
    for result in study.citation_results:
        if result.target_site not in site_citations:
            site_citations[result.target_site] = []
        site_citations[result.target_site].append(result.cited)

    site_citation_rates: dict[str, float] = {}
    for site_id, citations in site_citations.items():
        if citations:
            site_citation_rates[site_id] = sum(citations) / len(citations)

    # Calculate correlation if we have data
    scores = []
    citation_rates = []
    for score in study.site_scores:
        if score.site_id in site_citation_rates and score.error is None:
            scores.append(score.findable_score)
            citation_rates.append(site_citation_rates[score.site_id])

    correlation = None
    if len(scores) >= 5:
        # Simple Pearson correlation calculation
        mean_x = statistics.mean(scores)
        mean_y = statistics.mean(citation_rates)

        numerator = sum(
            (x - mean_x) * (y - mean_y) for x, y in zip(scores, citation_rates, strict=False)
        )
        denom_x = sum((x - mean_x) ** 2 for x in scores) ** 0.5
        denom_y = sum((y - mean_y) ** 2 for y in citation_rates) ** 0.5

        if denom_x > 0 and denom_y > 0:
            correlation = numerator / (denom_x * denom_y)

    # Confusion matrix (threshold at 50 for score, 50% for citation)
    score_threshold = 50.0
    citation_threshold = 0.5

    tp = fp = fn = tn = 0
    for score in study.site_scores:
        if score.site_id in site_citation_rates and score.error is None:
            high_score = score.findable_score >= score_threshold
            cited = site_citation_rates[score.site_id] >= citation_threshold

            if high_score and cited:
                tp += 1
            elif high_score and not cited:
                fp += 1
            elif not high_score and cited:
                fn += 1
            else:
                tn += 1

    total = tp + fp + fn + tn
    accuracy = (tp + tn) / total if total > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "sample_size": len(scores),
        "correlation": correlation,
        "confusion_matrix": {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "true_negative": tn,
        },
        "metrics": {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
        },
        "quadrant_avg_scores": {
            q: statistics.mean(s) if s else 0 for q, s in quadrant_scores.items()
        },
        "site_citation_rates": site_citation_rates,
        "thresholds": {
            "score": score_threshold,
            "citation": citation_threshold,
        },
    }


async def run_phase_1(max_pages: int = 20) -> list[SiteScore]:
    """Phase 1: Score all sites."""
    sites = get_real_sites()
    print(f"Phase 1: Scoring {len(sites)} sites...")

    results = []
    for i, site in enumerate(sites):
        print(f"  [{i+1}/{len(sites)}] Scoring {site.name} ({site.url})...")
        try:
            score = await score_site(site, max_pages=max_pages)
            results.append(score)
            print(f"    Score: {score.findable_score:.1f}")
        except Exception as e:
            print(f"    Error: {e}")
            results.append(
                SiteScore(
                    site_id=site.id,
                    url=site.url,
                    name=site.name,
                    quadrant=site.quadrant.value,
                    error=str(e),
                    scored_at=datetime.now(UTC).isoformat(),
                )
            )

    return results


async def run_phase_2(site_scores: list[SiteScore]) -> list[CitationResult]:
    """Phase 2: Query AI for each site."""
    sites = get_real_sites()
    site_map = {s.id: s for s in sites}

    print(f"Phase 2: Querying AI for {len(sites)} sites...")

    results = []
    for i, score in enumerate(site_scores):
        if score.site_id not in site_map:
            continue

        site = site_map[score.site_id]
        queries = site.expected_queries[:5]  # Max 5 queries per site

        print(f"  [{i+1}/{len(site_scores)}] Querying {site.name} ({len(queries)} queries)...")

        try:
            citation_results = await query_ai_for_site(site, queries)
            results.extend(citation_results)

            cited_count = sum(1 for r in citation_results if r.cited)
            print(f"    Citations: {cited_count}/{len(queries)}")
        except Exception as e:
            print(f"    Error: {e}")

    return results


def save_results(study: StudyResults) -> None:
    """Save study results to files."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Save scores
    scores_file = OUTPUT_DIR / "site_scores.json"
    with open(scores_file, "w") as f:
        json.dump([asdict(s) for s in study.site_scores], f, indent=2)

    # Save citations
    citations_file = OUTPUT_DIR / "citation_results.json"
    with open(citations_file, "w") as f:
        json.dump([asdict(c) for c in study.citation_results], f, indent=2)

    # Save analysis
    analysis_file = OUTPUT_DIR / "analysis.json"
    with open(analysis_file, "w") as f:
        json.dump(study.analysis, f, indent=2)

    # Save summary
    summary_file = OUTPUT_DIR / "summary.json"
    with open(summary_file, "w") as f:
        json.dump(
            {
                "started_at": study.started_at,
                "completed_at": study.completed_at,
                "sites_scored": study.sites_scored,
                "queries_executed": study.queries_executed,
                "correlation": study.analysis.get("correlation"),
                "accuracy": study.analysis.get("metrics", {}).get("accuracy"),
                "f1_score": study.analysis.get("metrics", {}).get("f1_score"),
            },
            f,
            indent=2,
        )

    print(f"\nResults saved to {OUTPUT_DIR}/")


async def run_full_study(max_pages: int = 20) -> StudyResults:
    """Run the complete validation study."""
    study = StudyResults(started_at=datetime.now(UTC).isoformat())

    # Phase 1: Score sites
    print("\n" + "=" * 70)
    print("PHASE 1: SITE SCORING")
    print("=" * 70)
    study.site_scores = await run_phase_1(max_pages=max_pages)
    study.sites_scored = len([s for s in study.site_scores if s.error is None])

    # Phase 2: Query AI
    print("\n" + "=" * 70)
    print("PHASE 2: AI CITATION TESTING")
    print("=" * 70)
    study.citation_results = await run_phase_2(study.site_scores)
    study.queries_executed = len(study.citation_results)

    # Phase 3: Analyze
    print("\n" + "=" * 70)
    print("PHASE 3: ANALYSIS")
    print("=" * 70)
    study.analysis = analyze_results(study)

    study.completed_at = datetime.now(UTC).isoformat()

    # Print summary
    print("\n" + "=" * 70)
    print("STUDY COMPLETE")
    print("=" * 70)
    print(f"Sites scored: {study.sites_scored}")
    print(f"Queries executed: {study.queries_executed}")
    print(f"Correlation: {study.analysis.get('correlation', 'N/A')}")
    print(f"Accuracy: {study.analysis.get('metrics', {}).get('accuracy', 0):.1%}")
    print(f"F1 Score: {study.analysis.get('metrics', {}).get('f1_score', 0):.1%}")

    # Save results
    save_results(study)

    return study


def main():
    parser = argparse.ArgumentParser(description="Run validation study")
    parser.add_argument("--phase", type=int, choices=[1, 2, 3], help="Run specific phase")
    parser.add_argument("--all", action="store_true", help="Run full study")
    parser.add_argument("--max-pages", type=int, default=20, help="Max pages to crawl per site")
    parser.add_argument("--list-sites", action="store_true", help="List all study sites")

    args = parser.parse_args()

    if args.list_sites:
        sites = get_all_sites()
        real_sites = get_real_sites()
        print(f"Total sites: {len(sites)}")
        print(f"Real sites (not placeholders): {len(real_sites)}")
        print("\nBy quadrant:")
        for q in Quadrant:
            q_sites = get_sites_by_quadrant(q)
            real_count = len([s for s in q_sites if not s.url.startswith("https://example-")])
            print(f"  {q.value}: {len(q_sites)} ({real_count} real)")
        return

    if args.all:
        asyncio.run(run_full_study(max_pages=args.max_pages))
    elif args.phase == 1:
        results = asyncio.run(run_phase_1(max_pages=args.max_pages))
        print(f"\nScored {len(results)} sites")
    else:
        print("Use --all to run full study or --phase 1/2/3")


if __name__ == "__main__":
    main()
