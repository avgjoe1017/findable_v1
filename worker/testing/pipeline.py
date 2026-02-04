"""Pipeline executor for test site validation.

Runs the Findable Score pipeline on test corpus sites and returns
structured results for comparison with ground truth.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from worker.chunking.chunker import SemanticChunker
from worker.crawler.crawler import crawl_site
from worker.embeddings.embedder import Embedder
from worker.extraction.extractor import ContentExtractor
from worker.questions.generator import QuestionGenerator, SiteContext
from worker.retrieval.retriever import HybridRetriever
from worker.simulation.runner import SimulationRunner
from worker.testing.config import PipelineConfig

logger = structlog.get_logger(__name__)


@dataclass
class PillarScores:
    """Individual pillar scores from the pipeline."""

    technical: float | None = None
    structure: float | None = None
    schema: float | None = None
    authority: float | None = None
    retrieval: float | None = None
    coverage: float | None = None

    def to_dict(self) -> dict[str, float | None]:
        """Convert to dictionary."""
        return {
            "technical": self.technical,
            "structure": self.structure,
            "schema": self.schema,
            "authority": self.authority,
            "retrieval": self.retrieval,
            "coverage": self.coverage,
        }


@dataclass
class QuestionResult:
    """Result for a single question from simulation."""

    question_id: str
    question_text: str
    category: str
    answerability: str  # "fully", "partially", "not"
    score: float
    confidence: float
    chunks_found: int
    top_chunk_relevance: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "category": self.category,
            "answerability": self.answerability,
            "score": self.score,
            "confidence": self.confidence,
            "chunks_found": self.chunks_found,
            "top_chunk_relevance": self.top_chunk_relevance,
        }


@dataclass
class PipelineResult:
    """Complete result from running the pipeline on a site."""

    url: str
    domain: str
    status: str  # "success", "failed", "cached"
    overall_score: float
    pillar_scores: PillarScores
    question_results: list[QuestionResult] = field(default_factory=list)
    questions_answered: int = 0
    questions_partial: int = 0
    questions_unanswered: int = 0
    pages_crawled: int = 0
    chunks_created: int = 0
    duration_seconds: float = 0.0
    error_message: str | None = None
    cached_at: str | None = None
    executed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "domain": self.domain,
            "status": self.status,
            "overall_score": self.overall_score,
            "pillar_scores": self.pillar_scores.to_dict(),
            "question_results": [q.to_dict() for q in self.question_results],
            "questions_answered": self.questions_answered,
            "questions_partial": self.questions_partial,
            "questions_unanswered": self.questions_unanswered,
            "pages_crawled": self.pages_crawled,
            "chunks_created": self.chunks_created,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
            "cached_at": self.cached_at,
            "executed_at": self.executed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PipelineResult":
        """Create from dictionary."""
        pillar_data = data.get("pillar_scores", {})
        pillar_scores = PillarScores(
            technical=pillar_data.get("technical"),
            structure=pillar_data.get("structure"),
            schema=pillar_data.get("schema"),
            authority=pillar_data.get("authority"),
            retrieval=pillar_data.get("retrieval"),
            coverage=pillar_data.get("coverage"),
        )

        question_results = []
        for q in data.get("question_results", []):
            question_results.append(
                QuestionResult(
                    question_id=q["question_id"],
                    question_text=q["question_text"],
                    category=q["category"],
                    answerability=q["answerability"],
                    score=q["score"],
                    confidence=q["confidence"],
                    chunks_found=q["chunks_found"],
                    top_chunk_relevance=q.get("top_chunk_relevance"),
                )
            )

        return cls(
            url=data["url"],
            domain=data["domain"],
            status=data["status"],
            overall_score=data["overall_score"],
            pillar_scores=pillar_scores,
            question_results=question_results,
            questions_answered=data.get("questions_answered", 0),
            questions_partial=data.get("questions_partial", 0),
            questions_unanswered=data.get("questions_unanswered", 0),
            pages_crawled=data.get("pages_crawled", 0),
            chunks_created=data.get("chunks_created", 0),
            duration_seconds=data.get("duration_seconds", 0.0),
            error_message=data.get("error_message"),
            cached_at=data.get("cached_at"),
            executed_at=data.get("executed_at", datetime.now(UTC).isoformat()),
        )


def get_cache_key(url: str, config: PipelineConfig) -> str:
    """Generate a cache key for a pipeline run."""
    key_data = f"{url}:{config.max_pages}:{config.max_depth}"
    return hashlib.sha256(key_data.encode()).hexdigest()[:16]


def load_cached_result(url: str, config: PipelineConfig, cache_dir: Path) -> PipelineResult | None:
    """Load cached pipeline result if available and not expired."""
    cache_key = get_cache_key(url, config)
    cache_file = cache_dir / f"pipeline_{cache_key}.json"

    if not cache_file.exists():
        return None

    try:
        with open(cache_file) as f:
            data = json.load(f)

        # Check cache TTL
        cached_at = datetime.fromisoformat(data.get("cached_at", ""))
        age_hours = (datetime.now(UTC) - cached_at).total_seconds() / 3600

        if age_hours > config.cache_ttl_hours:
            logger.debug("cache_expired", url=url, age_hours=age_hours)
            return None

        result = PipelineResult.from_dict(data)
        result.status = "cached"
        logger.info("cache_hit", url=url, cached_at=result.cached_at)
        return result

    except Exception as e:
        logger.warning("cache_load_failed", url=url, error=str(e))
        return None


def save_cached_result(result: PipelineResult, config: PipelineConfig, cache_dir: Path) -> None:
    """Save pipeline result to cache."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = get_cache_key(result.url, config)
    cache_file = cache_dir / f"pipeline_{cache_key}.json"

    try:
        result.cached_at = datetime.now(UTC).isoformat()
        with open(cache_file, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        logger.debug("cache_saved", url=result.url, file=str(cache_file))
    except Exception as e:
        logger.warning("cache_save_failed", url=result.url, error=str(e))


async def run_pipeline(
    url: str,
    config: PipelineConfig | None = None,
    cache_dir: Path | None = None,
    use_cache: bool = True,
) -> PipelineResult:
    """
    Run the scoring pipeline on a URL.

    Args:
        url: The URL to analyze
        config: Pipeline configuration (uses defaults if not provided)
        cache_dir: Directory for caching results
        use_cache: Whether to use cached results

    Returns:
        PipelineResult with scores and question results
    """
    config = config or PipelineConfig()
    cache_dir = cache_dir or Path("results/cache/pipeline")

    # Extract domain from URL
    from urllib.parse import urlparse

    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")

    # Check cache first
    if use_cache:
        cached = load_cached_result(url, config, cache_dir)
        if cached:
            return cached

    start_time = datetime.now(UTC)

    logger.info("pipeline_starting", url=url, domain=domain)

    try:
        # Initialize result with defaults
        pillar_scores = PillarScores()
        question_results: list[QuestionResult] = []

        # =========================================================
        # Step 1: Crawl
        # =========================================================
        logger.info("crawl_starting", url=url, max_pages=config.max_pages)

        crawl_result = await crawl_site(
            url=url,
            max_pages=config.max_pages,
            max_depth=config.max_depth,
        )

        pages_crawled = len(crawl_result.pages)
        logger.info("crawl_completed", pages=pages_crawled)

        if pages_crawled == 0:
            return PipelineResult(
                url=url,
                domain=domain,
                status="failed",
                overall_score=0.0,
                pillar_scores=pillar_scores,
                error_message="No pages crawled",
                duration_seconds=(datetime.now(UTC) - start_time).total_seconds(),
            )

        # =========================================================
        # Step 2: Extract
        # =========================================================
        logger.info("extraction_starting", pages=pages_crawled)

        extractor = ContentExtractor()
        extraction_result = extractor.extract_crawl(crawl_result)

        logger.info(
            "extraction_completed",
            pages=extraction_result.total_pages,
            words=extraction_result.total_words,
        )

        # =========================================================
        # Step 3: Technical Score
        # =========================================================
        from worker.tasks.technical_check import run_technical_checks_parallel

        try:
            technical_score = await run_technical_checks_parallel(
                url=url,
                html=crawl_result.pages[0].html if crawl_result.pages else None,
                timeout=10.0,
            )
            pillar_scores.technical = technical_score.total_score
            logger.info("technical_score", score=technical_score.total_score)
        except Exception as e:
            logger.warning("technical_check_failed", error=str(e))

        # =========================================================
        # Step 4: Structure Score
        # =========================================================
        from worker.tasks.structure_check import (
            aggregate_structure_scores,
            run_structure_checks_sync,
        )

        try:
            structure_page_scores = []
            for i, page in enumerate(crawl_result.pages):
                if page.html and i < len(extraction_result.pages):
                    extracted = extraction_result.pages[i]
                    page_score = run_structure_checks_sync(
                        html=page.html,
                        url=page.url,
                        main_content=extracted.main_content,
                        word_count=extracted.word_count,
                    )
                    structure_page_scores.append(page_score)

            if structure_page_scores:
                structure_score = aggregate_structure_scores(structure_page_scores)
                pillar_scores.structure = structure_score.total_score
                logger.info("structure_score", score=structure_score.total_score)
        except Exception as e:
            logger.warning("structure_check_failed", error=str(e))

        # =========================================================
        # Step 5: Schema Score
        # =========================================================
        from worker.tasks.schema_check import (
            aggregate_schema_scores,
            run_schema_checks_sync,
        )

        try:
            schema_page_scores = []
            for page in crawl_result.pages:
                if page.html:
                    page_schema_score = run_schema_checks_sync(
                        html=page.html,
                        url=page.url,
                    )
                    schema_page_scores.append(page_schema_score)

            if schema_page_scores:
                schema_score = aggregate_schema_scores(schema_page_scores)
                pillar_scores.schema = schema_score.total_score
                logger.info("schema_score", score=schema_score.total_score)
        except Exception as e:
            logger.warning("schema_check_failed", error=str(e))

        # =========================================================
        # Step 6: Authority Score
        # =========================================================
        from worker.tasks.authority_check import (
            aggregate_authority_scores,
            run_authority_checks_sync,
        )

        try:
            authority_page_scores = []
            for i, page in enumerate(crawl_result.pages):
                if page.html and i < len(extraction_result.pages):
                    extracted = extraction_result.pages[i]
                    page_authority_score = run_authority_checks_sync(
                        html=page.html,
                        url=page.url,
                        main_content=extracted.main_content,
                    )
                    authority_page_scores.append(page_authority_score)

            if authority_page_scores:
                authority_score = aggregate_authority_scores(authority_page_scores)
                pillar_scores.authority = authority_score.total_score
                logger.info("authority_score", score=authority_score.total_score)
        except Exception as e:
            logger.warning("authority_check_failed", error=str(e))

        # =========================================================
        # Step 7: Chunking & Embedding
        # =========================================================
        logger.info("chunking_starting")

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

        logger.info("chunking_completed", chunks=total_chunks)

        # Embed chunks
        logger.info("embedding_starting")

        embedder = Embedder()
        embedded_pages = embedder.embed_pages(chunked_pages)

        # Build retriever index
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

        logger.info("embedding_completed", documents=len(retriever._documents))

        # =========================================================
        # Step 8: Generate Questions
        # =========================================================
        logger.info("question_generation_starting")

        # Collect schema types and headings
        schema_types = list(set(extraction_result.schema_types_found))
        headings: dict[str, list[str]] = {"h1": [], "h2": [], "h3": []}
        for page in extraction_result.pages:
            page_headings = page.metadata.headings or {}
            for level in ["h1", "h2", "h3"]:
                if level in page_headings:
                    headings[level].extend(page_headings[level])

        site_context = SiteContext(
            company_name=domain.split(".")[0].title(),
            domain=domain,
            schema_types=schema_types,
            headings=headings,
        )

        question_generator = QuestionGenerator()
        questions = question_generator.generate(site_context)

        logger.info("question_generation_completed", questions=len(questions))

        # =========================================================
        # Step 9: Simulation
        # =========================================================
        logger.info("simulation_starting", questions=len(questions))

        # Create synthetic IDs for standalone run
        site_id = uuid.uuid5(uuid.NAMESPACE_URL, url)
        run_id = uuid.uuid4()

        simulation_runner = SimulationRunner(retriever=retriever)
        simulation_result = simulation_runner.run(
            site_id=site_id,
            run_id=run_id,
            company_name=domain.split(".")[0].title(),
            questions=questions,
        )

        logger.info(
            "simulation_completed",
            overall_score=simulation_result.overall_score,
            answered=simulation_result.questions_answered,
            partial=simulation_result.questions_partial,
            unanswered=simulation_result.questions_unanswered,
        )

        # Extract retrieval and coverage from simulation
        pillar_scores.coverage = simulation_result.coverage_score
        pillar_scores.retrieval = simulation_result.overall_score

        # Convert simulation results to question results
        # Map confidence levels to numeric values
        confidence_values = {"high": 1.0, "medium": 0.6, "low": 0.3}

        for sim_q in simulation_result.question_results:
            # Get confidence as float
            conf_val = (
                sim_q.confidence.value
                if hasattr(sim_q.confidence, "value")
                else str(sim_q.confidence)
            )
            confidence_float = confidence_values.get(conf_val.lower(), 0.5)

            # Get category as string
            category_str = (
                sim_q.category.value if hasattr(sim_q.category, "value") else str(sim_q.category)
            )

            question_results.append(
                QuestionResult(
                    question_id=str(sim_q.question_id),
                    question_text=sim_q.question_text,
                    category=category_str,
                    answerability=(
                        sim_q.answerability.value
                        if hasattr(sim_q.answerability, "value")
                        else str(sim_q.answerability)
                    ),
                    score=sim_q.score,
                    confidence=confidence_float,
                    chunks_found=sim_q.context.total_chunks,
                    top_chunk_relevance=(
                        sim_q.context.max_relevance_score
                        if sim_q.context.total_chunks > 0
                        else None
                    ),
                )
            )

        # Calculate overall score
        overall_score = simulation_result.overall_score

        duration = (datetime.now(UTC) - start_time).total_seconds()

        result = PipelineResult(
            url=url,
            domain=domain,
            status="success",
            overall_score=overall_score,
            pillar_scores=pillar_scores,
            question_results=question_results,
            questions_answered=simulation_result.questions_answered,
            questions_partial=simulation_result.questions_partial,
            questions_unanswered=simulation_result.questions_unanswered,
            pages_crawled=pages_crawled,
            chunks_created=total_chunks,
            duration_seconds=duration,
        )

        # Save to cache
        if use_cache:
            save_cached_result(result, config, cache_dir)

        logger.info(
            "pipeline_completed",
            url=url,
            overall_score=overall_score,
            duration=duration,
        )

        return result

    except Exception as e:
        logger.exception("pipeline_failed", url=url, error=str(e))

        duration = (datetime.now(UTC) - start_time).total_seconds()

        return PipelineResult(
            url=url,
            domain=domain,
            status="failed",
            overall_score=0.0,
            pillar_scores=PillarScores(),
            error_message=str(e),
            duration_seconds=duration,
        )


async def run_pipeline_batch(
    urls: list[str],
    config: PipelineConfig | None = None,
    cache_dir: Path | None = None,
    use_cache: bool = True,
    concurrency: int = 3,
) -> list[PipelineResult]:
    """
    Run the pipeline on multiple URLs with concurrency control.

    Args:
        urls: List of URLs to analyze
        config: Pipeline configuration
        cache_dir: Directory for caching results
        use_cache: Whether to use cached results
        concurrency: Maximum concurrent pipeline runs

    Returns:
        List of PipelineResult objects
    """
    import asyncio

    config = config or PipelineConfig()
    cache_dir = cache_dir or Path("results/cache/pipeline")

    semaphore = asyncio.Semaphore(concurrency)

    async def run_with_semaphore(url: str) -> PipelineResult:
        async with semaphore:
            return await run_pipeline(url, config, cache_dir, use_cache)

    tasks = [run_with_semaphore(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert exceptions to failed results
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            from urllib.parse import urlparse

            parsed = urlparse(urls[i])
            domain = parsed.netloc.replace("www.", "")

            processed_results.append(
                PipelineResult(
                    url=urls[i],
                    domain=domain,
                    status="failed",
                    overall_score=0.0,
                    pillar_scores=PillarScores(),
                    error_message=str(result),
                )
            )
        else:
            processed_results.append(result)

    return processed_results
