#!/usr/bin/env python
"""Run real AI observations on sites to collect ground truth calibration samples.

This script uses actual AI providers (OpenRouter/OpenAI) instead of mock data.
Requires OPENROUTER_API_KEY or OPENAI_API_KEY to be set.

Usage:
    python scripts/run_real_observation.py [url] [max_pages]

Examples:
    python scripts/run_real_observation.py https://anthropic.com 5
    python scripts/run_real_observation.py https://stripe.com 10
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

# Add project root to path
sys.path.insert(0, ".")


async def run_real_observation(url: str, max_pages: int = 5) -> dict:
    """Run full audit with real AI observation."""
    from sqlalchemy import func, select

    from api.config import get_settings
    from api.database import async_session_maker
    from api.models import Run, Site
    from api.models.calibration import CalibrationSample
    from api.models.user import User
    from worker.chunking.chunker import SemanticChunker
    from worker.crawler.crawler import crawl_site
    from worker.embeddings.embedder import Embedder
    from worker.extraction.extractor import ContentExtractor
    from worker.observation.models import ProviderType
    from worker.observation.runner import ObservationRunner, RunConfig
    from worker.questions.generator import QuestionGenerator, SiteContext
    from worker.retrieval.retriever import HybridRetriever
    from worker.simulation.runner import SimulationRunner
    from worker.tasks.calibration import collect_calibration_samples

    settings = get_settings()
    parsed = urlparse(url)
    domain = parsed.netloc
    company_name = domain.split(".")[0].title()
    if company_name.lower() == "www":
        company_name = domain.split(".")[1].title()

    # Check API keys
    has_openrouter = bool(settings.openrouter_api_key)
    has_openai = bool(settings.openai_api_key)

    if not has_openrouter and not has_openai:
        print("ERROR: No API keys configured!")
        print("Set OPENROUTER_API_KEY or OPENAI_API_KEY in .env")
        return {"success": False, "error": "No API keys"}

    # Select provider
    if has_openrouter:
        provider = ProviderType.OPENROUTER
        print("Using OpenRouter provider")
    else:
        provider = ProviderType.OPENAI
        print("Using OpenAI provider")

    print(f"\n{'='*70}")
    print("REAL AI OBSERVATION RUN")
    print(f"{'='*70}")
    print(f"URL: {url}")
    print(f"Domain: {domain}")
    print(f"Company: {company_name}")
    print(f"Max Pages: {max_pages}")
    print(f"Provider: {provider.value}")
    print(f"{'='*70}\n")

    results = {
        "url": url,
        "domain": domain,
        "provider": provider.value,
        "started_at": datetime.now(UTC).isoformat(),
    }

    # Step 1: Create site and run
    print("[1/8] Creating site and run in database...")

    async with async_session_maker() as db:
        # Get or create test user
        user_result = await db.execute(select(User).where(User.email == "test@calibration.local"))
        user = user_result.scalar_one_or_none()

        if not user:
            user = User(
                id=uuid.uuid4(),
                email="test@calibration.local",
                hashed_password="test_not_for_login",
                is_active=True,
            )
            db.add(user)
            await db.flush()

        user_id = user.id

        # Get or create site
        existing = await db.execute(select(Site).where(Site.domain == domain))
        site = existing.scalar_one_or_none()

        if not site:
            site = Site(
                id=uuid.uuid4(),
                user_id=user_id,
                domain=domain,
                name=company_name,
            )
            db.add(site)
            await db.flush()
            print(f"      Created site: {site.id}")
        else:
            print(f"      Using existing site: {site.id}")

        site_id = site.id

        # Create run
        run = Run(
            id=uuid.uuid4(),
            site_id=site_id,
            status="pending",
            config={"include_observation": True, "provider": provider.value},
        )
        db.add(run)
        await db.commit()
        run_id = run.id
        print(f"      Created run: {run_id}")

    results["site_id"] = str(site_id)
    results["run_id"] = str(run_id)

    # Step 2: Crawl
    print(f"\n[2/8] Crawling site (max {max_pages} pages)...")
    crawl_result = await crawl_site(url=url, max_pages=max_pages, max_depth=2)
    print(f"      Pages crawled: {len(crawl_result.pages)}")
    results["pages_crawled"] = len(crawl_result.pages)

    # Step 3: Extract
    print("\n[3/8] Extracting content...")
    extractor = ContentExtractor()
    extraction_result = extractor.extract_crawl(crawl_result)
    print(f"      Pages extracted: {extraction_result.total_pages}")
    print(f"      Total words: {extraction_result.total_words:,}")
    results["words_extracted"] = extraction_result.total_words

    # Step 4: Chunk and Embed
    print("\n[4/8] Chunking and embedding...")
    chunker = SemanticChunker()
    chunked_pages = []
    total_chunks = 0

    for page in extraction_result.pages:
        chunked_page = chunker.chunk_text(
            text=page.main_content,
            url=page.url,
            title=page.title,
        )
        chunked_pages.append(chunked_page)
        total_chunks += chunked_page.total_chunks

    print(f"      Total chunks: {total_chunks}")

    embedder = Embedder()
    embedded_pages = embedder.embed_pages(chunked_pages)
    print(f"      Total embeddings: {sum(len(ep.embeddings) for ep in embedded_pages)}")

    # Step 5: Build Retriever
    print("\n[5/8] Building retriever index...")
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

    print(f"      Documents indexed: {len(retriever._documents)}")

    # Step 6: Generate Questions and Run Simulation
    print("\n[6/8] Generating questions and running simulation...")

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
    print(f"      Questions generated: {len(questions)}")

    simulation_runner = SimulationRunner(retriever=retriever)
    simulation_result = simulation_runner.run(
        site_id=site_id,
        run_id=run_id,
        company_name=company_name,
        questions=questions,
    )

    print(f"      Simulation score: {simulation_result.overall_score:.1f}")
    results["simulation_score"] = simulation_result.overall_score

    # Step 7: Run REAL Observation
    print(f"\n[7/8] Running REAL AI observation ({provider.value})...")
    print("      This may take 30-60 seconds...")

    run_config = RunConfig(
        primary_provider=provider,
        fallback_provider=ProviderType.OPENAI if has_openai else provider,
        max_retries=2,
        request_timeout_seconds=60,
        concurrent_requests=3,
        openrouter_api_key=settings.openrouter_api_key,
        openai_api_key=settings.openai_api_key,
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

    print(f"      Status: {observation_run.status.value}")
    print(f"      Mention rate: {observation_run.company_mention_rate:.1%}")
    print(f"      Citation rate: {observation_run.citation_rate:.1%}")
    print(f"      Results: {len(observation_run.results)}")

    results["observation_mention_rate"] = observation_run.company_mention_rate
    results["observation_citation_rate"] = observation_run.citation_rate

    # Step 8: Collect Calibration Samples
    print("\n[8/8] Collecting calibration samples...")

    pillar_scores = {
        "technical": 70.0,
        "structure": 65.0,
        "schema": 50.0,
        "authority": 60.0,
        "retrieval": simulation_result.overall_score,
        "coverage": simulation_result.coverage_score,
    }

    samples_collected = await collect_calibration_samples(
        run_id=run_id,
        simulation_result=simulation_result,
        observation_run=observation_run,
        pillar_scores=pillar_scores,
    )

    print(f"      Samples collected: {samples_collected}")
    results["samples_collected"] = samples_collected

    # Verification
    print(f"\n{'='*70}")
    print("VERIFICATION")
    print(f"{'='*70}")

    async with async_session_maker() as db:
        count_result = await db.execute(
            select(func.count(CalibrationSample.id)).where(CalibrationSample.run_id == run_id)
        )
        sample_count = count_result.scalar()

        outcome_result = await db.execute(
            select(
                CalibrationSample.outcome_match,
                func.count(CalibrationSample.id),
            )
            .where(CalibrationSample.run_id == run_id)
            .group_by(CalibrationSample.outcome_match)
        )
        outcomes = dict(outcome_result.fetchall())

        print(f"Samples in DB: {sample_count}")
        print(f"Outcomes: {outcomes}")

        results["verified_samples"] = sample_count
        results["outcomes"] = outcomes

    # Summary
    print(f"\n{'='*70}")
    print("REAL OBSERVATION COMPLETE")
    print(f"{'='*70}")
    print(f"Site: {domain}")
    print(f"Provider: {provider.value}")
    print(f"Simulation Score: {simulation_result.overall_score:.1f}")
    print(f"Mention Rate: {observation_run.company_mention_rate:.1%}")
    print(f"Citation Rate: {observation_run.citation_rate:.1%}")
    print(f"Samples: {samples_collected}")

    if samples_collected > 0:
        print("\n[SUCCESS] Real calibration samples collected!")
    else:
        print("\n[WARNING] No samples collected")

    print(f"{'='*70}\n")

    results["success"] = samples_collected > 0
    results["completed_at"] = datetime.now(UTC).isoformat()

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_real_observation.py <url> [max_pages]")
        print("Example: python scripts/run_real_observation.py https://anthropic.com 5")
        sys.exit(1)

    url = sys.argv[1]
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    results = asyncio.run(run_real_observation(url, max_pages))

    if results.get("success"):
        print("Run completed successfully!")
        sys.exit(0)
    else:
        print(f"Run failed: {results.get('error', 'Unknown error')}")
        sys.exit(1)
