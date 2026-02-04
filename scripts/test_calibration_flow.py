#!/usr/bin/env python
"""Test the full calibration flow end-to-end.

This script:
1. Creates a test site in the database
2. Runs the audit pipeline with observation enabled (using mock provider)
3. Verifies calibration samples were collected
4. Shows the collected samples

Usage:
    python scripts/test_calibration_flow.py [url] [max_pages]

Examples:
    python scripts/test_calibration_flow.py https://httpbin.org 3
    python scripts/test_calibration_flow.py https://example.com 5
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

# Add project root to path
sys.path.insert(0, ".")


async def test_calibration_flow(url: str, max_pages: int = 5) -> dict:
    """Run full audit with observation and verify calibration samples."""
    from sqlalchemy import func, select

    from api.config import get_settings
    from api.database import async_session_maker
    from api.models import Run, Site
    from api.models.calibration import CalibrationSample
    from worker.chunking.chunker import SemanticChunker
    from worker.crawler.crawler import crawl_site
    from worker.embeddings.embedder import Embedder
    from worker.extraction.extractor import ContentExtractor
    from worker.observation.models import ObservationRequest, ProviderType
    from worker.observation.runner import ObservationRunner, RunConfig
    from worker.questions.generator import QuestionGenerator, SiteContext
    from worker.retrieval.retriever import HybridRetriever
    from worker.simulation.runner import SimulationRunner
    from worker.tasks.calibration import collect_calibration_samples

    settings = get_settings()
    parsed = urlparse(url)
    domain = parsed.netloc
    company_name = domain.split(".")[0].title()

    print(f"\n{'='*70}")
    print("CALIBRATION FLOW TEST")
    print(f"{'='*70}")
    print(f"URL: {url}")
    print(f"Domain: {domain}")
    print(f"Company: {company_name}")
    print(f"Max Pages: {max_pages}")
    print(f"Calibration Enabled: {settings.calibration_enabled}")
    print(f"Sample Collection: {settings.calibration_sample_collection}")
    print(f"{'='*70}\n")

    results = {
        "url": url,
        "domain": domain,
        "started_at": datetime.now(UTC).isoformat(),
    }

    # =========================================================
    # Step 1: Create site and run in database
    # =========================================================
    print("[1/8] Creating site and run in database...")

    from api.models.user import User

    async with async_session_maker() as db:
        # Check if test user exists, create if not
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
            print(f"      Created test user: {user.id}")
        else:
            print(f"      Using existing test user: {user.id}")

        user_id = user.id

        # Check if site already exists
        existing = await db.execute(select(Site).where(Site.domain == domain))
        site = existing.scalar_one_or_none()

        if site:
            print(f"      Using existing site: {site.id}")
        else:
            site = Site(
                id=uuid.uuid4(),
                user_id=user_id,
                domain=domain,
                name=company_name,
            )
            db.add(site)
            await db.flush()
            print(f"      Created site: {site.id}")

        site_id = site.id

        # Create run
        run = Run(
            id=uuid.uuid4(),
            site_id=site_id,
            status="pending",
            config={"include_observation": True},  # Enable observation
        )
        db.add(run)
        await db.commit()
        run_id = run.id
        print(f"      Created run: {run_id}")

    results["site_id"] = str(site_id)
    results["run_id"] = str(run_id)

    # =========================================================
    # Step 2: Crawl
    # =========================================================
    print(f"\n[2/8] Crawling site (max {max_pages} pages)...")

    crawl_result = await crawl_site(url=url, max_pages=max_pages, max_depth=2)
    print(f"      Pages crawled: {len(crawl_result.pages)}")
    print(f"      Duration: {crawl_result.duration_seconds:.1f}s")

    results["pages_crawled"] = len(crawl_result.pages)

    # =========================================================
    # Step 3: Extract
    # =========================================================
    print("\n[3/8] Extracting content...")

    extractor = ContentExtractor()
    extraction_result = extractor.extract_crawl(crawl_result)
    print(f"      Pages extracted: {extraction_result.total_pages}")
    print(f"      Total words: {extraction_result.total_words:,}")

    results["words_extracted"] = extraction_result.total_words

    # =========================================================
    # Step 4: Chunk and Embed
    # =========================================================
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
    total_embeddings = sum(len(ep.embeddings) for ep in embedded_pages)
    print(f"      Total embeddings: {total_embeddings}")

    results["total_chunks"] = total_chunks

    # =========================================================
    # Step 5: Build Retriever
    # =========================================================
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

    # =========================================================
    # Step 6: Generate Questions and Run Simulation
    # =========================================================
    print("\n[6/8] Generating questions and running simulation...")

    # Collect context
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

    print(f"      Questions answered: {simulation_result.questions_answered}")
    print(f"      Questions partial: {simulation_result.questions_partial}")
    print(f"      Questions unanswered: {simulation_result.questions_unanswered}")
    print(f"      Overall score: {simulation_result.overall_score:.1f}")

    results["questions"] = len(questions)
    results["simulation_score"] = simulation_result.overall_score

    # =========================================================
    # Step 7: Run Observation (Mock Provider)
    # =========================================================
    print("\n[7/8] Running observation (Mock Provider)...")

    # Create observation requests
    _observation_requests = [
        ObservationRequest(
            question_id=q.id,
            question_text=q.text,
            company_name=company_name,
            domain=domain,
        )
        for q in questions
    ]

    # Use mock provider for testing
    run_config = RunConfig(
        primary_provider=ProviderType.MOCK,
        fallback_provider=ProviderType.MOCK,
        max_retries=1,
        request_timeout_seconds=30,
        concurrent_requests=5,
    )

    # Build questions list as (id, text) tuples
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

    # =========================================================
    # Step 8: Collect Calibration Samples
    # =========================================================
    print("\n[8/8] Collecting calibration samples...")

    # Build pillar scores snapshot (simplified for test)
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

    # =========================================================
    # Verify: Check samples in database
    # =========================================================
    print(f"\n{'='*70}")
    print("VERIFICATION: Checking calibration samples in database")
    print(f"{'='*70}\n")

    async with async_session_maker() as db:
        # Count samples for this run
        count_result = await db.execute(
            select(func.count(CalibrationSample.id)).where(CalibrationSample.run_id == run_id)
        )
        sample_count = count_result.scalar()
        print(f"Samples for run {run_id}: {sample_count}")

        # Get sample breakdown by outcome
        outcome_result = await db.execute(
            select(
                CalibrationSample.outcome_match,
                func.count(CalibrationSample.id),
            )
            .where(CalibrationSample.run_id == run_id)
            .group_by(CalibrationSample.outcome_match)
        )
        outcomes = dict(outcome_result.fetchall())
        print("Outcome breakdown:")
        for outcome, count in outcomes.items():
            print(f"  - {outcome}: {count}")

        # Show sample details
        samples_result = await db.execute(
            select(CalibrationSample).where(CalibrationSample.run_id == run_id).limit(5)
        )
        samples = samples_result.scalars().all()

        if samples:
            print("\nSample details (first 5):")
            print("-" * 70)
            for s in samples:
                print(f"  Q: {s.question_text[:50]}...")
                print(f"     Sim: {s.sim_answerability} (score={s.sim_score:.2f})")
                print(f"     Obs: mentioned={s.obs_mentioned}, cited={s.obs_cited}")
                print(f"     Match: {s.outcome_match}, accurate={s.prediction_accurate}")
                print()

        results["verified_sample_count"] = sample_count
        results["outcome_breakdown"] = outcomes

    # =========================================================
    # Summary
    # =========================================================
    print(f"{'='*70}")
    print("CALIBRATION FLOW TEST COMPLETE")
    print(f"{'='*70}")
    print(f"Site: {domain}")
    print(f"Run ID: {run_id}")
    print(f"Questions: {len(questions)}")
    print(f"Simulation Score: {simulation_result.overall_score:.1f}")
    print(f"Samples Collected: {samples_collected}")
    print(f"Verified in DB: {sample_count}")

    if sample_count > 0:
        print("\n[SUCCESS] Calibration samples are being collected!")
    else:
        print("\n[FAILURE] No calibration samples found")

    print(f"{'='*70}\n")

    results["success"] = sample_count > 0
    results["completed_at"] = datetime.now(UTC).isoformat()

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Default to a simple test site
        url = "https://httpbin.org"
        max_pages = 3
    else:
        url = sys.argv[1]
        max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    # Ensure URL has protocol
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    results = asyncio.run(test_calibration_flow(url, max_pages))

    if results.get("success"):
        print("Test PASSED - Calibration flow is working!")
        sys.exit(0)
    else:
        print("Test FAILED - Check the output above for errors")
        sys.exit(1)
