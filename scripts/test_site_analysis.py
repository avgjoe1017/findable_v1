#!/usr/bin/env python
"""
Standalone script to test the full analysis pipeline for a site.

Usage:
    python scripts/test_site_analysis.py etonline.com
    python scripts/test_site_analysis.py https://www.etonline.com
"""

import asyncio
import json
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set minimal environment
os.environ.setdefault("ENV", "development")
os.environ.setdefault("JWT_SECRET", "dev-secret")


async def analyze_site(domain: str, max_pages: int = 10):
    """Run full analysis pipeline on a site."""
    from worker.chunking.chunker import SemanticChunker
    from worker.crawler.crawler import crawl_site
    from worker.embeddings.embedder import Embedder
    from worker.extraction.extractor import ContentExtractor
    from worker.extraction.images import analyze_images
    from worker.extraction.js_detection import detect_js_dependency
    from worker.extraction.paragraphs import analyze_paragraphs

    # New modules from gap analysis
    from worker.extraction.topic_clusters import analyze_topic_clusters
    from worker.fixes.generator_v2 import FixGeneratorV2
    from worker.questions.generator import QuestionGenerator, SiteContext
    from worker.retrieval.retriever import HybridRetriever
    from worker.scoring.calculator import calculate_score

    # v2 calculator
    from worker.scoring.calculator_v2 import calculate_findable_score_v2
    from worker.scoring.technical import calculate_technical_score
    from worker.simulation.runner import SimulationRunner
    from worker.tasks.authority_check import aggregate_authority_scores, run_authority_checks_sync
    from worker.tasks.schema_check import aggregate_schema_scores, run_schema_checks_sync
    from worker.tasks.structure_check import aggregate_structure_scores, run_structure_checks_sync

    # v2 scoring modules
    from worker.tasks.technical_check import run_technical_checks_parallel

    # Normalize domain
    if domain.startswith("http"):
        from urllib.parse import urlparse

        parsed = urlparse(domain)
        domain = parsed.netloc
    domain = domain.replace("www.", "")

    start_url = f"https://{domain}"
    print(f"\n{'='*60}")
    print(f"FINDABLE SCORE ANALYSIS: {domain}")
    print(f"{'='*60}")
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Max pages: {max_pages}")
    print()

    # =========================================================
    # Step 0: Technical Readiness Check
    # =========================================================
    print("[1/12] Technical Readiness Check...")
    try:
        technical_score = await run_technical_checks_parallel(
            url=start_url,
            html=None,
            timeout=15.0,
        )
        print(f"       Score: {technical_score.total_score:.1f}/100 ({technical_score.level})")
        if technical_score.critical_issues:
            for issue in technical_score.critical_issues[:3]:
                print(f"       CRITICAL: {issue}")
    except Exception as e:
        print(f"       Failed: {e}")
        technical_score = None

    # =========================================================
    # Step 1: Crawling
    # =========================================================
    print(f"\n[2/12] Crawling {domain}...")
    crawl_result = await crawl_site(
        url=start_url,
        max_pages=max_pages,
        max_depth=3,
    )
    print(f"       Pages crawled: {len(crawl_result.pages)}")
    print(f"       URLs discovered: {crawl_result.urls_discovered}")
    print(f"       Duration: {crawl_result.duration_seconds:.1f}s")

    # =========================================================
    # Step 2: Extraction
    # =========================================================
    print("\n[3/12] Extracting content...")
    extractor = ContentExtractor()
    extraction_result = extractor.extract_crawl(crawl_result)
    print(f"       Pages extracted: {extraction_result.total_pages}")
    print(f"       Total words: {extraction_result.total_words:,}")

    # =========================================================
    # Step 2.5: Update Technical with JS Detection
    # =========================================================
    if technical_score and crawl_result.pages:
        homepage_html = crawl_result.pages[0].html if crawl_result.pages else None
        if homepage_html:
            try:
                js_result = detect_js_dependency(homepage_html, start_url)
                technical_score = calculate_technical_score(
                    robots_result=technical_score.robots_result,
                    ttfb_result=technical_score.ttfb_result,
                    llms_txt_result=technical_score.llms_txt_result,
                    js_result=js_result,
                    is_https=technical_score.is_https,
                )
                print(
                    f"\n[3.5/12] JS Detection: {'JS-dependent' if js_result.likely_js_dependent else 'Static OK'}"
                )
                if js_result.framework_detected:
                    print(f"         Framework: {js_result.framework_detected}")
            except Exception as e:
                print(f"         JS detection failed: {e}")

    # =========================================================
    # Step 3: Structure Analysis
    # =========================================================
    print("\n[4/12] Structure Quality Analysis...")
    page_structure_scores = []
    for i, page in enumerate(crawl_result.pages):
        if page.html and i < len(extraction_result.pages):
            extracted = extraction_result.pages[i]
            score = run_structure_checks_sync(
                html=page.html,
                url=page.url,
                main_content=extracted.main_content,
                word_count=extracted.word_count,
            )
            page_structure_scores.append(score)

    structure_score = (
        aggregate_structure_scores(page_structure_scores) if page_structure_scores else None
    )
    if structure_score:
        print(f"       Score: {structure_score.total_score:.1f}/100 ({structure_score.level})")

    # =========================================================
    # Step 4: Schema Analysis
    # =========================================================
    print("\n[5/12] Schema Richness Analysis...")
    page_schema_scores = []
    for page in crawl_result.pages:
        if page.html:
            score = run_schema_checks_sync(html=page.html, url=page.url)
            page_schema_scores.append(score)

    schema_score = aggregate_schema_scores(page_schema_scores) if page_schema_scores else None
    if schema_score:
        print(f"       Score: {schema_score.total_score:.1f}/100 ({schema_score.level})")
        # Get schema types from analysis
        schema_types = []
        if schema_score.schema_analysis:
            schema_types = [s.schema_type for s in schema_score.schema_analysis.schemas]
        if schema_types:
            print(f"       Schema types: {', '.join(set(schema_types)[:5])}")

    # =========================================================
    # Step 5: Authority Analysis
    # =========================================================
    print("\n[6/12] Authority Signals Analysis...")
    page_authority_scores = []
    for i, page in enumerate(crawl_result.pages):
        if page.html and i < len(extraction_result.pages):
            extracted = extraction_result.pages[i]
            score = run_authority_checks_sync(
                html=page.html,
                url=page.url,
                main_content=extracted.main_content,
            )
            page_authority_scores.append(score)

    authority_score = (
        aggregate_authority_scores(page_authority_scores) if page_authority_scores else None
    )
    if authority_score:
        print(f"       Score: {authority_score.total_score:.1f}/100 ({authority_score.level})")

    # =========================================================
    # Step 6: NEW - Topic Cluster Analysis
    # =========================================================
    print("\n[7/12] Topic Cluster Analysis (NEW)...")
    cluster_pages_data = []
    for i, page in enumerate(crawl_result.pages):
        if i < len(extraction_result.pages):
            extracted = extraction_result.pages[i]
            # Get internal links from page
            from urllib.parse import urljoin, urlparse

            from bs4 import BeautifulSoup

            internal_links = []
            if page.html:
                soup = BeautifulSoup(page.html, "html.parser")
                page_domain = urlparse(page.url).netloc.lower()
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    full_url = urljoin(page.url, href)
                    link_domain = urlparse(full_url).netloc.lower()
                    if link_domain == page_domain:
                        internal_links.append(full_url.split("#")[0].split("?")[0])

            cluster_pages_data.append(
                {
                    "url": page.url,
                    "word_count": extracted.word_count,
                    "title": extracted.title or "",
                    "internal_links": internal_links,
                }
            )

    cluster_analysis = analyze_topic_clusters(cluster_pages_data)
    print(f"       Clusters found: {cluster_analysis.cluster_count}")
    print(f"       Pillar pages: {len(cluster_analysis.pillar_pages)}")
    print(f"       Orphan pages: {len(cluster_analysis.orphan_pages)}")
    print(f"       Bidirectional ratio: {cluster_analysis.bidirectional_ratio:.0%}")
    print(f"       Score: {cluster_analysis.total_score:.1f}/100 ({cluster_analysis.level})")

    # =========================================================
    # Step 7: NEW - Image Alt Text Analysis
    # =========================================================
    print("\n[8/12] Image Alt Text Analysis (NEW)...")
    total_images = 0
    total_missing_alt = 0
    total_poor_alt = 0
    total_good_alt = 0

    for page in crawl_result.pages:
        if page.html:
            img_analysis = analyze_images(page.html, page.url)
            total_images += img_analysis.total_images
            total_missing_alt += img_analysis.images_missing_alt
            total_poor_alt += img_analysis.images_poor_alt
            total_good_alt += img_analysis.images_good_alt

    print(f"       Total images: {total_images}")
    print(f"       Missing alt: {total_missing_alt}")
    print(f"       Poor alt: {total_poor_alt}")
    print(f"       Good alt: {total_good_alt}")
    if total_images > 0:
        quality_ratio = total_good_alt / total_images
        print(f"       Quality ratio: {quality_ratio:.0%}")

    # =========================================================
    # Step 8: NEW - Paragraph Analysis
    # =========================================================
    print("\n[9/12] Paragraph Length Analysis (NEW)...")
    total_paragraphs = 0
    total_long_paragraphs = 0
    total_optimal_paragraphs = 0

    for page in crawl_result.pages:
        if page.html:
            para_analysis = analyze_paragraphs(page.html)
            total_paragraphs += para_analysis.total_paragraphs
            total_long_paragraphs += para_analysis.long_paragraphs
            total_optimal_paragraphs += para_analysis.optimal_paragraphs

    print(f"       Total paragraphs: {total_paragraphs}")
    print(f"       Optimal (<=4 sentences): {total_optimal_paragraphs}")
    print(f"       Too long (>4 sentences): {total_long_paragraphs}")
    if total_paragraphs > 0:
        optimal_ratio = total_optimal_paragraphs / total_paragraphs
        print(f"       Optimal ratio: {optimal_ratio:.0%}")

    # =========================================================
    # Step 9: Chunking
    # =========================================================
    print("\n[10/12] Chunking content...")
    chunker = SemanticChunker()
    chunked_pages = []
    total_chunks = 0
    for page in extraction_result.pages:
        chunked = chunker.chunk_text(
            text=page.main_content,
            url=page.url,
            title=page.title,
        )
        chunked_pages.append(chunked)
        total_chunks += chunked.total_chunks
    print(f"        Total chunks: {total_chunks}")

    # =========================================================
    # Step 10: Embedding + Retrieval
    # =========================================================
    print("\n[11/12] Embedding and indexing...")
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
    print(f"        Documents indexed: {len(retriever._documents)}")

    # =========================================================
    # Step 11: Questions + Simulation
    # =========================================================
    print("\n[12/12] Running simulation...")
    import uuid

    schema_types = list(set(extraction_result.schema_types_found))
    headings = {"h1": [], "h2": [], "h3": []}
    for page in extraction_result.pages:
        page_headings = page.metadata.headings or {}
        for level in ["h1", "h2", "h3"]:
            if level in page_headings:
                headings[level].extend(page_headings[level])

    site_context = SiteContext(
        company_name=domain.split(".")[0].upper(),
        domain=domain,
        schema_types=schema_types,
        headings=headings,
    )

    question_generator = QuestionGenerator()
    questions = question_generator.generate(site_context)
    print(f"        Questions generated: {len(questions)}")

    simulation_runner = SimulationRunner(retriever=retriever)
    simulation_result = simulation_runner.run(
        site_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        company_name=site_context.company_name,
        questions=questions,
    )
    print(f"        Questions answered: {simulation_result.questions_answered}/{len(questions)}")
    print(f"        Questions partial: {simulation_result.questions_partial}")

    # =========================================================
    # Calculate v2 Score
    # =========================================================
    print("\n" + "=" * 60)
    print("FINDABLE SCORE v2 RESULTS")
    print("=" * 60)

    # Convert simulation result to score breakdown
    simulation_breakdown = calculate_score(simulation_result)
    print(
        f"Simulation Score (v1): {simulation_breakdown.total_score:.1f}/100 ({simulation_breakdown.grade})"
    )

    v2_score = calculate_findable_score_v2(
        technical_score=technical_score,
        structure_score=structure_score,
        schema_score=schema_score,
        authority_score=authority_score,
        simulation_breakdown=simulation_breakdown,
    )

    print(f"\nTOTAL SCORE: {v2_score.total_score:.1f}/100")
    print(f"LEVEL: {v2_score.level_label}")
    print(f"SUMMARY: {v2_score.level_summary}")

    if v2_score.next_milestone:
        print(
            f"\nNext milestone: {v2_score.next_milestone} ({v2_score.points_to_milestone:.1f} points needed)"
        )

    print("\nPILLAR BREAKDOWN:")
    print("-" * 60)
    for pillar in v2_score.pillars:
        icon = "+" if pillar.level == "good" else "!" if pillar.level == "warning" else "X"
        print(
            f"[{icon}] {pillar.display_name}: {pillar.raw_score:.1f}/100 -> {pillar.points_earned:.1f}/{pillar.max_points} pts"
        )

    good = sum(1 for p in v2_score.pillars if p.level == "good")
    warning = sum(1 for p in v2_score.pillars if p.level == "warning")
    critical = sum(1 for p in v2_score.pillars if p.level == "critical")
    print(f"\nPillar health: {good} good, {warning} warning, {critical} critical")

    # =========================================================
    # Generate Fixes
    # =========================================================
    print("\n" + "=" * 60)
    print("TOP FIXES")
    print("=" * 60)

    fix_generator = FixGeneratorV2()
    fix_plan = fix_generator.generate(
        site_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        company_name=site_context.company_name,
        technical_score=technical_score,
        structure_score=structure_score,
        schema_score=schema_score,
        authority_score=authority_score,
    )
    fixes = fix_plan.action_center.all_fixes

    for i, action_item in enumerate(fixes[:10], 1):
        fix = action_item.fix
        print(f"\n{i}. [{fix.impact_level.value.upper()}] {fix.title}")
        print(f"   Category: {fix.category.value}")
        print(
            f"   Impact: +{fix.estimated_points:.1f} total pts, +{fix.impact_points:.1f} pillar pts"
        )
        print(f"   Effort: {fix.effort_level.value}")
        print(f"   Pillar: {fix.affected_pillar}")

    # =========================================================
    # New Analysis Summary
    # =========================================================
    print("\n" + "=" * 60)
    print("NEW ANALYSIS MODULES SUMMARY")
    print("=" * 60)

    print("\nTopic Clusters:")
    print(f"  - Clusters detected: {cluster_analysis.cluster_count}")
    print(f"  - Pillar pages: {len(cluster_analysis.pillar_pages)}")
    print(f"  - Orphan pages: {len(cluster_analysis.orphan_pages)}")
    print(f"  - Bidirectional link ratio: {cluster_analysis.bidirectional_ratio:.0%}")
    if cluster_analysis.issues:
        print(f"  - Issues: {cluster_analysis.issues[0]}")

    print("\nImage Accessibility:")
    print(f"  - Total images: {total_images}")
    print(f"  - Missing alt text: {total_missing_alt}")
    print(f"  - Poor alt text: {total_poor_alt}")

    print("\nParagraph Readability:")
    print(f"  - Total paragraphs: {total_paragraphs}")
    print(f"  - Too long (>4 sentences): {total_long_paragraphs}")
    if total_paragraphs > 0:
        print(f"  - Optimal ratio: {total_optimal_paragraphs/total_paragraphs:.0%}")

    print("\n" + "=" * 60)
    print(f"Analysis complete: {datetime.now().isoformat()}")
    print("=" * 60)

    return {
        "domain": domain,
        "total_score": v2_score.total_score,
        "level": v2_score.level,
        "level_label": v2_score.level_label,
        "pillars": {p.name: p.raw_score for p in v2_score.pillars},
        "cluster_analysis": cluster_analysis.to_dict(),
        "fixes_count": len(fixes),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_site_analysis.py <domain>")
        print("Example: python scripts/test_site_analysis.py etonline.com")
        sys.exit(1)

    domain = sys.argv[1]
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    result = asyncio.run(analyze_site(domain, max_pages))

    print("\n\nJSON Result:")
    print(json.dumps(result, indent=2, default=str))
