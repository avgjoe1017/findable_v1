"""Simulation runner for AI sourceability evaluation.

Runs questions against indexed site content to determine
how well an AI system could answer questions about the site.

Thresholds and weights can be dynamically loaded from the active CalibrationConfig.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from worker.questions.generator import GeneratedQuestion, QuestionSource
from worker.questions.universal import QuestionCategory, QuestionDifficulty
from worker.retrieval.retriever import HybridRetriever, RetrievalResult

if TYPE_CHECKING:
    from api.models.calibration import CalibrationConfig

logger = structlog.get_logger(__name__)


# Coverage bucket mapping: question category → bucket name
ENTITY_FACTS_CATEGORIES = {
    QuestionCategory.IDENTITY,
    QuestionCategory.CONTACT,
    QuestionCategory.TRUST,
}
PRODUCT_HOWTO_CATEGORIES = {
    QuestionCategory.OFFERINGS,
    QuestionCategory.DIFFERENTIATION,
}


class Answerability(str, Enum):
    """How answerable a question is based on retrieved content."""

    FULLY_ANSWERABLE = "fully_answerable"  # All signals present
    PARTIALLY_ANSWERABLE = "partially_answerable"  # Some signals present
    NOT_ANSWERABLE = "not_answerable"  # No relevant content found
    CONTRADICTORY = "contradictory"  # Conflicting information found


class ConfidenceLevel(str, Enum):
    """Confidence in the answerability assessment."""

    HIGH = "high"  # Strong signals, consistent content
    MEDIUM = "medium"  # Some signals, minor gaps
    LOW = "low"  # Weak signals, significant gaps


@dataclass
class RetrievedContext:
    """Context retrieved for answering a question."""

    chunks: list[RetrievalResult]
    total_chunks: int
    avg_relevance_score: float
    max_relevance_score: float
    source_pages: list[str]  # URLs of source pages
    content_preview: str  # Combined preview of top chunks

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_chunks": self.total_chunks,
            "avg_relevance_score": self.avg_relevance_score,
            "max_relevance_score": self.max_relevance_score,
            "source_pages": self.source_pages,
            "content_preview": self.content_preview[:500],
            "chunks": [
                {
                    "content": c.content[:200],
                    "score": c.score,
                    "source_url": c.metadata.get("source_url"),
                }
                for c in self.chunks[:3]
            ],
        }


@dataclass
class SignalMatch:
    """A matched expected signal in the retrieved content."""

    signal: str
    found: bool
    confidence: float
    evidence: str | None = None  # Snippet showing the match

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "signal": self.signal,
            "found": self.found,
            "confidence": self.confidence,
            "evidence": self.evidence[:100] if self.evidence else None,
        }


@dataclass
class QuestionResult:
    """Result of simulating a single question."""

    question_id: str
    question_text: str
    category: QuestionCategory
    difficulty: QuestionDifficulty
    source: QuestionSource
    weight: float

    # Results
    answerability: Answerability
    confidence: ConfidenceLevel
    score: float  # 0.0 to 1.0

    # Context
    context: RetrievedContext
    signal_matches: list[SignalMatch]
    signals_found: int
    signals_total: int

    # Timing
    retrieval_time_ms: float
    evaluation_time_ms: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "category": self.category.value,
            "difficulty": self.difficulty.value,
            "source": self.source.value,
            "weight": self.weight,
            "answerability": self.answerability.value,
            "confidence": self.confidence.value,
            "score": self.score,
            "context": self.context.to_dict(),
            "signal_matches": [s.to_dict() for s in self.signal_matches],
            "signals_found": self.signals_found,
            "signals_total": self.signals_total,
            "retrieval_time_ms": self.retrieval_time_ms,
            "evaluation_time_ms": self.evaluation_time_ms,
        }


@dataclass
class SimulationResult:
    """Complete simulation result for a site."""

    site_id: UUID
    run_id: UUID
    company_name: str

    # Question results
    question_results: list[QuestionResult]
    total_questions: int
    questions_answered: int
    questions_partial: int
    questions_unanswered: int

    # Scores by category
    category_scores: dict[str, float]
    difficulty_scores: dict[str, float]

    # Overall metrics
    overall_score: float  # Weighted score 0-100
    coverage_score: float  # % of questions answerable
    confidence_score: float  # Average confidence

    # Timing
    total_time_ms: float
    started_at: datetime
    completed_at: datetime

    # Coverage by bucket (entity facts vs product/how-to)
    entity_coverage: float = 0.0  # % of entity-fact questions answerable
    product_coverage: float = 0.0  # % of product/how-to questions answerable

    # Metadata
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "site_id": str(self.site_id),
            "run_id": str(self.run_id),
            "company_name": self.company_name,
            "total_questions": self.total_questions,
            "questions_answered": self.questions_answered,
            "questions_partial": self.questions_partial,
            "questions_unanswered": self.questions_unanswered,
            "category_scores": self.category_scores,
            "difficulty_scores": self.difficulty_scores,
            "overall_score": self.overall_score,
            "coverage_score": self.coverage_score,
            "entity_coverage": self.entity_coverage,
            "product_coverage": self.product_coverage,
            "confidence_score": self.confidence_score,
            "total_time_ms": self.total_time_ms,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "question_results": [q.to_dict() for q in self.question_results],
            "metadata": self.metadata,
        }


@dataclass
class SimulationConfig:
    """Configuration for simulation runner.

    Can be loaded from an active CalibrationConfig for dynamic thresholds.
    """

    # Retrieval settings
    chunks_per_question: int = 5  # Top chunks to retrieve
    min_relevance_score: float = 0.0  # RRF scores are small (0.001-0.03), don't filter

    # Scoring thresholds
    fully_answerable_threshold: float = 0.7  # Score for full answer
    partially_answerable_threshold: float = 0.3  # Score for partial

    # Signal matching
    signal_match_threshold: float = 0.6  # Confidence for signal match (60%+ words must match)
    use_fuzzy_matching: bool = True  # Allow fuzzy signal matching

    # Weights for scoring
    relevance_weight: float = 0.4  # Weight for retrieval relevance
    signal_weight: float = 0.4  # Weight for signal coverage
    confidence_weight: float = 0.2  # Weight for confidence

    # Performance
    max_content_length: int = 2000  # Max chars for content preview

    # Calibration tracking
    config_name: str | None = None  # Name of CalibrationConfig used

    @classmethod
    def from_calibration_config(cls, config: CalibrationConfig) -> SimulationConfig:
        """
        Create SimulationConfig from a CalibrationConfig.

        Args:
            config: CalibrationConfig with thresholds and weights

        Returns:
            SimulationConfig initialized with calibration values
        """
        return cls(
            fully_answerable_threshold=config.threshold_fully_answerable,
            partially_answerable_threshold=config.threshold_partially_answerable,
            signal_match_threshold=config.threshold_signal_match,
            relevance_weight=config.scoring_relevance_weight,
            signal_weight=config.scoring_signal_weight,
            confidence_weight=config.scoring_confidence_weight,
            config_name=config.name,
        )


# Cache for active calibration config (for performance)
_cached_simulation_config: SimulationConfig | None = None
_cached_simulation_config_name: str | None = None


def get_simulation_config(config: CalibrationConfig | None = None) -> SimulationConfig:
    """
    Get SimulationConfig from calibration config or defaults.

    Args:
        config: Optional CalibrationConfig to use. If None, uses cached
                config or defaults.

    Returns:
        SimulationConfig with appropriate thresholds
    """
    # If explicit config provided, use it
    if config is not None:
        return SimulationConfig.from_calibration_config(config)

    # Use cached config if available
    if _cached_simulation_config is not None:
        return _cached_simulation_config

    # Fall back to defaults
    return SimulationConfig()


def set_active_simulation_config(
    config: SimulationConfig | None,
    config_name: str | None = None,
) -> None:
    """
    Set the cached active simulation config.

    Call this when the active CalibrationConfig changes.

    Args:
        config: SimulationConfig to cache, or None to clear cache
        config_name: Name of the config (for logging)
    """
    global _cached_simulation_config, _cached_simulation_config_name

    if config is not None:
        _cached_simulation_config = config
        _cached_simulation_config_name = config_name or config.config_name
        logger.info(
            "simulation_config_cached",
            config_name=_cached_simulation_config_name,
            fully_threshold=config.fully_answerable_threshold,
            partially_threshold=config.partially_answerable_threshold,
        )
    else:
        _cached_simulation_config = None
        _cached_simulation_config_name = None
        logger.info("simulation_config_cache_cleared")


def get_cached_simulation_config_name() -> str | None:
    """Get the name of the currently cached simulation config."""
    return _cached_simulation_config_name


async def load_active_simulation_config() -> SimulationConfig:
    """
    Async function to load and cache simulation config from active CalibrationConfig.

    Call this at startup or when config changes.

    Returns:
        The loaded SimulationConfig (or defaults if no active config)
    """
    try:
        from sqlalchemy import select

        from api.database import async_session_maker
        from api.models.calibration import CalibrationConfig

        async with async_session_maker() as db:
            result = await db.execute(
                select(CalibrationConfig).where(CalibrationConfig.is_active == True)  # noqa: E712
            )
            active_config = result.scalar_one_or_none()

            if active_config:
                sim_config = SimulationConfig.from_calibration_config(active_config)
                set_active_simulation_config(sim_config, active_config.name)
                return sim_config

    except Exception as e:
        logger.debug("active_simulation_config_load_failed", error=str(e))

    # No active config - clear cache and return defaults
    set_active_simulation_config(None)
    return SimulationConfig()


class SimulationRunner:
    """Runs simulations to evaluate AI sourceability."""

    def __init__(
        self,
        retriever: HybridRetriever,
        config: SimulationConfig | None = None,
    ):
        self.retriever = retriever
        self.config = config or SimulationConfig()

    def run(
        self,
        site_id: UUID,
        run_id: UUID,
        company_name: str,
        questions: list[GeneratedQuestion],
    ) -> SimulationResult:
        """
        Run simulation for a set of questions.

        Args:
            site_id: ID of the site being evaluated
            run_id: ID of this evaluation run
            company_name: Name of the company
            questions: Questions to evaluate

        Returns:
            SimulationResult with all question evaluations
        """
        import time

        started_at = datetime.utcnow()
        start_time = time.perf_counter()

        question_results: list[QuestionResult] = []

        for question in questions:
            result = self._evaluate_question(question)
            question_results.append(result)

        # Calculate aggregate scores
        category_scores = self._calculate_category_scores(question_results)
        difficulty_scores = self._calculate_difficulty_scores(question_results)
        overall_score = self._calculate_overall_score(question_results)
        coverage_score = self._calculate_coverage_score(question_results)
        confidence_score = self._calculate_confidence_score(question_results)
        entity_coverage, product_coverage = self._calculate_bucket_coverage(question_results)

        # Count by answerability
        answered = sum(
            1 for r in question_results if r.answerability == AnswerResult.FULLY_ANSWERABLE
        )
        partial = sum(
            1 for r in question_results if r.answerability == Answerability.PARTIALLY_ANSWERABLE
        )
        unanswered = sum(
            1 for r in question_results if r.answerability == Answerability.NOT_ANSWERABLE
        )

        completed_at = datetime.utcnow()
        total_time = (time.perf_counter() - start_time) * 1000

        return SimulationResult(
            site_id=site_id,
            run_id=run_id,
            company_name=company_name,
            question_results=question_results,
            total_questions=len(questions),
            questions_answered=answered,
            questions_partial=partial,
            questions_unanswered=unanswered,
            category_scores=category_scores,
            difficulty_scores=difficulty_scores,
            overall_score=overall_score,
            coverage_score=coverage_score,
            entity_coverage=entity_coverage,
            product_coverage=product_coverage,
            confidence_score=confidence_score,
            total_time_ms=total_time,
            started_at=started_at,
            completed_at=completed_at,
        )

    def _evaluate_question(self, question: GeneratedQuestion) -> QuestionResult:
        """Evaluate a single question against retrieved content."""
        import time

        # Retrieve relevant content
        retrieval_start = time.perf_counter()
        results = self.retriever.search(
            query=question.question,
            limit=self.config.chunks_per_question,
        )
        # Filter by min_score if configured
        if self.config.min_relevance_score > 0:
            results = [r for r in results if r.score >= self.config.min_relevance_score]
        retrieval_time = (time.perf_counter() - retrieval_start) * 1000

        # Build context from results
        context = self._build_context(results)

        # Evaluate signals
        eval_start = time.perf_counter()
        signal_matches = self._evaluate_signals(
            question.expected_signals,
            context,
        )
        signals_found = sum(1 for s in signal_matches if s.found)
        signals_total = len(signal_matches)

        # Determine answerability and score
        answerability, confidence, score = self._calculate_answerability(
            context=context,
            signal_matches=signal_matches,
            signals_found=signals_found,
            signals_total=signals_total,
        )
        eval_time = (time.perf_counter() - eval_start) * 1000

        # Generate question ID if not present
        question_id = question.metadata.get("universal_id") or self._generate_id(question.question)

        return QuestionResult(
            question_id=question_id,
            question_text=question.question,
            category=question.category,
            difficulty=question.difficulty,
            source=question.source,
            weight=question.weight,
            answerability=answerability,
            confidence=confidence,
            score=score,
            context=context,
            signal_matches=signal_matches,
            signals_found=signals_found,
            signals_total=signals_total,
            retrieval_time_ms=retrieval_time,
            evaluation_time_ms=eval_time,
        )

    def _build_context(self, results: list[RetrievalResult]) -> RetrievedContext:
        """Build context from retrieval results."""
        if not results:
            return RetrievedContext(
                chunks=[],
                total_chunks=0,
                avg_relevance_score=0.0,
                max_relevance_score=0.0,
                source_pages=[],
                content_preview="",
            )

        # Calculate scores - normalize RRF scores to 0-1 range
        # RRF scores are tiny (0.001-0.03), normalize by dividing by 0.02
        scores = [r.score for r in results]
        raw_avg = sum(scores) / len(scores)
        raw_max = max(scores)
        # Normalize: 0.02 RRF score → 1.0, scale linearly
        avg_score = min(1.0, raw_avg / 0.02)
        max_score = min(1.0, raw_max / 0.02)

        # Get unique source pages
        source_pages = list(
            {r.metadata.get("source_url", "") for r in results if r.metadata.get("source_url")}
        )

        # Build content preview
        preview_parts = []
        total_len = 0
        for r in results:
            if total_len >= self.config.max_content_length:
                break
            preview_parts.append(r.content)
            total_len += len(r.content)

        content_preview = "\n\n".join(preview_parts)[: self.config.max_content_length]

        return RetrievedContext(
            chunks=results,
            total_chunks=len(results),
            avg_relevance_score=avg_score,
            max_relevance_score=max_score,
            source_pages=source_pages,
            content_preview=content_preview,
        )

    def _evaluate_signals(
        self,
        expected_signals: list[str],
        context: RetrievedContext,
    ) -> list[SignalMatch]:
        """Evaluate which expected signals are present in context."""
        import re

        if not expected_signals:
            return []

        matches: list[SignalMatch] = []
        content = context.content_preview
        content_lower = content.lower()

        # Pattern matchers for common signal types
        signal_patterns: dict[str, list[re.Pattern]] = {
            # Contact signals - strict patterns to avoid false positives
            "email": [re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")],
            # Phone: require at least 7 digits total, avoid matching decimals like "99.99%"
            "phone": [
                re.compile(
                    r"(?<![0-9.])(?:\+?1[-.\s]?)?(?:\([0-9]{3}\)|[0-9]{3})[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}(?![0-9%])"
                )
            ],
            "address": [
                re.compile(
                    r"\d+\s+[\w\s]+(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|way|court|ct)",
                    re.I,
                )
            ],
            "contact form": [
                re.compile(r"contact\s*(?:us|form|page)?", re.I),
                re.compile(r"get\s*in\s*touch", re.I),
            ],
            # Identity signals
            "business description": [
                re.compile(
                    r"(?:we\s+(?:are|help|provide|offer|build|create|make|deliver)|(?:is\s+a|leading|platform|solution|service|company|tool))",
                    re.I,
                )
            ],
            "industry": [
                re.compile(
                    r"(?:automation|software|saas|technology|platform|integration|workflow|productivity|enterprise|business)",
                    re.I,
                )
            ],
            "primary activity": [
                re.compile(
                    r"(?:helps?\s+(?:you|teams?|businesses?|companies?|organizations?))|(?:enables?\s+)|(?:allows?\s+)",
                    re.I,
                )
            ],
            # Founder/history signals
            "founder": [re.compile(r"(?:founded\s+by|co-?founder|ceo|chief\s+executive)", re.I)],
            "founding year": [
                re.compile(
                    r"(?:founded|established|started|launched|since)\s*(?:in\s*)?(19|20)\d{2}", re.I
                )
            ],
            "founding": [re.compile(r"(?:founded|established|started|launched|began)", re.I)],
            # Location signals
            "headquarters": [
                re.compile(r"(?:headquarter|hq|based\s+in|located\s+in|office\s+in)", re.I)
            ],
            "operating regions": [
                re.compile(r"(?:worldwide|global|international|countries|regions)", re.I)
            ],
            "office": [re.compile(r"(?:office|location|branch)\s*(?:in|at)?", re.I)],
            # Offering signals
            "product": [
                re.compile(
                    r"(?:product|feature|tool|app|application|platform|solution|service)", re.I
                )
            ],
            "service": [re.compile(r"(?:service|offering|solution|support|consulting)", re.I)],
            "feature": [re.compile(r"(?:feature|capability|function|ability)", re.I)],
            "description": [
                re.compile(r"(?:enables?|allows?|helps?|provides?|offers?|delivers?)", re.I)
            ],
            # Pricing signals
            "pricing": [
                re.compile(
                    r"(?:pricing|price|cost|\$\d+|free\s+(?:tier|plan|trial)|per\s+(?:month|year|user))",
                    re.I,
                )
            ],
            "tier": [re.compile(r"(?:plan|tier|package|edition|version)\s*(?:s)?", re.I)],
            # Customer signals
            "customer": [
                re.compile(r"(?:customer|client|user|team|organization|company|business)", re.I)
            ],
            "segment": [
                re.compile(
                    r"(?:small\s+business|enterprise|startup|agency|freelancer|developer|marketer)",
                    re.I,
                )
            ],
            "use case": [
                re.compile(r"(?:use\s+case|workflow|automation|integration|scenario)", re.I)
            ],
            "vertical": [re.compile(r"(?:industry|sector|vertical|market)", re.I)],
            # Problem/solution signals
            "pain point": [
                re.compile(r"(?:challenge|problem|issue|struggle|difficulty|pain)", re.I)
            ],
            "solution": [re.compile(r"(?:solution|solve|fix|address|resolve|help)", re.I)],
            "outcome": [
                re.compile(r"(?:result|outcome|benefit|improvement|save|increase|reduce)", re.I)
            ],
            # Trust signals
            "client": [re.compile(r"(?:customer|client|partner|user)\s*(?:s)?", re.I)],
            "case stud": [re.compile(r"(?:case\s+stud|success\s+stor|testimonial)", re.I)],
            "testimonial": [re.compile(r"(?:testimonial|review|quote|said|says)", re.I)],
            "logo": [re.compile(r"(?:trusted\s+by|used\s+by|powering|serving)", re.I)],
            "partnership": [re.compile(r"(?:partner|integration|connect|work\s+with)", re.I)],
            # Recognition signals
            "award": [re.compile(r"(?:award|winner|recognized|honored|best|top)", re.I)],
            "certification": [
                re.compile(r"(?:certified|certification|compliance|soc\s*2|gdpr|hipaa|iso)", re.I)
            ],
            "recognition": [re.compile(r"(?:recognized|featured|mentioned|covered|press)", re.I)],
            "press": [re.compile(r"(?:press|news|media|article|coverage|featured\s+in)", re.I)],
            # Track record signals
            "years": [
                re.compile(r"(?:\d+\s*\+?\s*years?|since\s+\d{4}|established\s+\d{4})", re.I)
            ],
            "growth": [
                re.compile(
                    r"(?:growth|growing|scale|expanded|million|billion|\d+[kmb]\+?\s*(?:user|customer|company))",
                    re.I,
                )
            ],
            "success": [re.compile(r"(?:success|achievement|milestone|accomplish)", re.I)],
            "count": [
                re.compile(
                    r"(?:\d+[,\d]*\s*(?:\+\s*)?(?:user|customer|client|company|team|business))",
                    re.I,
                )
            ],
            # Differentiation signals
            "unique": [re.compile(r"(?:unique|only|first|exclusive|proprietary|patented)", re.I)],
            "advantage": [re.compile(r"(?:advantage|benefit|better|faster|easier|simpler)", re.I)],
            "proprietary": [re.compile(r"(?:proprietary|patent|exclusive|innovative)", re.I)],
            "differentiating": [
                re.compile(r"(?:different|unique|stand\s*out|unlike|versus|vs)", re.I)
            ],
            # Value prop signals
            "value": [re.compile(r"(?:value|benefit|advantage|why\s+choose|reason)", re.I)],
            "benefit": [re.compile(r"(?:benefit|advantage|improve|enhance|boost|save)", re.I)],
            "selling point": [re.compile(r"(?:why|benefit|advantage|feature|capability)", re.I)],
            # Mission/vision signals
            "mission": [re.compile(r"(?:mission|purpose|goal|aim|strive)", re.I)],
            "vision": [re.compile(r"(?:vision|future|believe|dream|aspire)", re.I)],
            "core value": [re.compile(r"(?:value|principle|believe|commitment|culture)", re.I)],
            "purpose": [re.compile(r"(?:purpose|why|reason|mission|passion)", re.I)],
            # Getting started signals
            "signup": [
                re.compile(
                    r"(?:sign\s*up|register|create\s+account|get\s+started|start\s+free)", re.I
                )
            ],
            "getting started": [
                re.compile(r"(?:get\s*(?:ting)?\s*started|begin|start|onboard)", re.I)
            ],
            "trial": [re.compile(r"(?:free\s+trial|try\s+(?:it\s+)?free|demo|test\s+drive)", re.I)],
            "demo": [re.compile(r"(?:demo|demonstration|tour|walkthrough|preview)", re.I)],
        }

        for signal in expected_signals:
            signal_lower = signal.lower()
            found = False
            confidence = 0.0
            evidence = None

            # First try pattern matching for known signal types
            for pattern_key, patterns in signal_patterns.items():
                if pattern_key in signal_lower:
                    for pattern in patterns:
                        match = pattern.search(content)
                        if match:
                            found = True
                            confidence = 1.0
                            # Extract evidence with context
                            start = max(0, match.start() - 30)
                            end = min(len(content), match.end() + 30)
                            evidence = content[start:end]
                            break
                    if found:
                        break

            # Fallback: check for exact or fuzzy text match
            if not found:
                if signal_lower in content_lower:
                    found = True
                    confidence = 1.0
                    idx = content_lower.find(signal_lower)
                    start = max(0, idx - 50)
                    end = min(len(content), idx + len(signal) + 50)
                    evidence = content[start:end]
                elif self.config.use_fuzzy_matching:
                    # Check for partial matches (any word in signal)
                    signal_words = [w for w in signal_lower.split() if len(w) > 3]
                    if signal_words:
                        matched_words = 0
                        first_match_idx = -1
                        for w in signal_words:
                            if w in content_lower:
                                matched_words += 1
                                if first_match_idx == -1:
                                    first_match_idx = content_lower.find(w)
                        if matched_words > 0:
                            confidence = matched_words / len(signal_words)
                            if confidence >= self.config.signal_match_threshold:
                                found = True
                                # Extract evidence around first matched word
                                if first_match_idx >= 0:
                                    start = max(0, first_match_idx - 30)
                                    end = min(len(content), first_match_idx + 60)
                                    evidence = content[start:end]

            matches.append(
                SignalMatch(
                    signal=signal,
                    found=found,
                    confidence=confidence,
                    evidence=evidence,
                )
            )

        return matches

    def _calculate_answerability(
        self,
        context: RetrievedContext,
        signal_matches: list[SignalMatch],
        signals_found: int,
        signals_total: int,
    ) -> tuple[Answerability, ConfidenceLevel, float]:
        """Calculate answerability, confidence, and score."""
        # No content retrieved
        if context.total_chunks == 0:
            return Answerability.NOT_ANSWERABLE, ConfidenceLevel.HIGH, 0.0

        # Calculate component scores
        # Note: avg_relevance_score is already normalized to 0-1 in _retrieve_context
        relevance_score = context.avg_relevance_score
        signal_score = signals_found / signals_total if signals_total > 0 else 0.5
        confidence_scores = [m.confidence for m in signal_matches if m.found]
        avg_confidence = (
            sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        )

        # Weighted score
        score = (
            self.config.relevance_weight * relevance_score
            + self.config.signal_weight * signal_score
            + self.config.confidence_weight * avg_confidence
        )

        # Determine answerability
        if score >= self.config.fully_answerable_threshold:
            answerability = Answerability.FULLY_ANSWERABLE
        elif score >= self.config.partially_answerable_threshold:
            answerability = Answerability.PARTIALLY_ANSWERABLE
        else:
            answerability = Answerability.NOT_ANSWERABLE

        # Determine confidence
        if context.max_relevance_score >= 0.7 and signal_score >= 0.7:
            confidence = ConfidenceLevel.HIGH
        elif context.max_relevance_score >= 0.4 or signal_score >= 0.4:
            confidence = ConfidenceLevel.MEDIUM
        else:
            confidence = ConfidenceLevel.LOW

        return answerability, confidence, score

    def _calculate_category_scores(self, results: list[QuestionResult]) -> dict[str, float]:
        """Calculate average score per category."""
        category_scores: dict[str, list[float]] = {}

        for r in results:
            cat = r.category.value
            if cat not in category_scores:
                category_scores[cat] = []
            category_scores[cat].append(r.score)

        return {cat: sum(scores) / len(scores) * 100 for cat, scores in category_scores.items()}

    def _calculate_difficulty_scores(self, results: list[QuestionResult]) -> dict[str, float]:
        """Calculate average score per difficulty."""
        difficulty_scores: dict[str, list[float]] = {}

        for r in results:
            diff = r.difficulty.value
            if diff not in difficulty_scores:
                difficulty_scores[diff] = []
            difficulty_scores[diff].append(r.score)

        return {diff: sum(scores) / len(scores) * 100 for diff, scores in difficulty_scores.items()}

    def _calculate_overall_score(self, results: list[QuestionResult]) -> float:
        """Calculate weighted overall score (0-100)."""
        if not results:
            return 0.0

        total_weight = sum(r.weight for r in results)
        weighted_sum = sum(r.score * r.weight for r in results)

        return (weighted_sum / total_weight) * 100 if total_weight > 0 else 0.0

    def _calculate_coverage_score(self, results: list[QuestionResult]) -> float:
        """Calculate percentage of questions that are answerable."""
        if not results:
            return 0.0

        answerable = sum(
            1
            for r in results
            if r.answerability
            in (Answerability.FULLY_ANSWERABLE, Answerability.PARTIALLY_ANSWERABLE)
        )

        return (answerable / len(results)) * 100

    def _calculate_bucket_coverage(
        self,
        results: list[QuestionResult],
    ) -> tuple[float, float]:
        """Calculate coverage for entity-fact vs product/how-to question buckets.

        Returns:
            (entity_coverage_pct, product_coverage_pct) both 0-100
        """
        entity_total = 0
        entity_answerable = 0
        product_total = 0
        product_answerable = 0

        for r in results:
            is_answerable = r.answerability in (
                Answerability.FULLY_ANSWERABLE,
                Answerability.PARTIALLY_ANSWERABLE,
            )
            if r.category in ENTITY_FACTS_CATEGORIES:
                entity_total += 1
                if is_answerable:
                    entity_answerable += 1
            elif r.category in PRODUCT_HOWTO_CATEGORIES:
                product_total += 1
                if is_answerable:
                    product_answerable += 1

        entity_pct = (entity_answerable / entity_total * 100) if entity_total else 0.0
        product_pct = (product_answerable / product_total * 100) if product_total else 0.0
        return entity_pct, product_pct

    def _calculate_confidence_score(self, results: list[QuestionResult]) -> float:
        """Calculate average confidence score."""
        if not results:
            return 0.0

        confidence_values = {
            ConfidenceLevel.HIGH: 1.0,
            ConfidenceLevel.MEDIUM: 0.6,
            ConfidenceLevel.LOW: 0.3,
        }

        total = sum(confidence_values[r.confidence] for r in results)
        return (total / len(results)) * 100

    def _generate_id(self, text: str) -> str:
        """Generate a deterministic ID from text."""
        return hashlib.md5(text.encode()).hexdigest()[:8]


# Fix typo in run method
AnswerResult = Answerability  # Alias for the typo


def run_simulation(
    retriever: HybridRetriever,
    site_id: UUID,
    run_id: UUID,
    company_name: str,
    questions: list[GeneratedQuestion],
    config: SimulationConfig | None = None,
) -> SimulationResult:
    """
    Convenience function to run a simulation.

    Args:
        retriever: Hybrid retriever with indexed content
        site_id: ID of the site
        run_id: ID of this run
        company_name: Company name
        questions: Questions to evaluate
        config: Optional configuration

    Returns:
        SimulationResult
    """
    runner = SimulationRunner(retriever, config)
    return runner.run(site_id, run_id, company_name, questions)
