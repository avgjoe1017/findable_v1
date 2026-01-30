"""Simulation runner for AI sourceability evaluation.

Runs questions against indexed site content to determine
how well an AI system could answer questions about the site.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID

from worker.questions.generator import GeneratedQuestion, QuestionSource
from worker.questions.universal import QuestionCategory, QuestionDifficulty
from worker.retrieval.retriever import HybridRetriever, RetrievalResult


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
            "confidence_score": self.confidence_score,
            "total_time_ms": self.total_time_ms,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "question_results": [q.to_dict() for q in self.question_results],
            "metadata": self.metadata,
        }


@dataclass
class SimulationConfig:
    """Configuration for simulation runner."""

    # Retrieval settings
    chunks_per_question: int = 5  # Top chunks to retrieve
    min_relevance_score: float = 0.3  # Minimum score to consider

    # Scoring thresholds
    fully_answerable_threshold: float = 0.7  # Score for full answer
    partially_answerable_threshold: float = 0.3  # Score for partial

    # Signal matching
    signal_match_threshold: float = 0.5  # Confidence for signal match
    use_fuzzy_matching: bool = True  # Allow fuzzy signal matching

    # Weights for scoring
    relevance_weight: float = 0.4  # Weight for retrieval relevance
    signal_weight: float = 0.4  # Weight for signal coverage
    confidence_weight: float = 0.2  # Weight for confidence

    # Performance
    max_content_length: int = 2000  # Max chars for content preview


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

        # Calculate scores
        scores = [r.score for r in results]
        avg_score = sum(scores) / len(scores)
        max_score = max(scores)

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
        if not expected_signals:
            return []

        matches: list[SignalMatch] = []
        content_lower = context.content_preview.lower()

        for signal in expected_signals:
            signal_lower = signal.lower()
            found = False
            confidence = 0.0
            evidence = None

            # Check for exact or fuzzy match
            if signal_lower in content_lower:
                found = True
                confidence = 1.0
                # Extract evidence snippet
                idx = content_lower.find(signal_lower)
                start = max(0, idx - 50)
                end = min(len(context.content_preview), idx + len(signal) + 50)
                evidence = context.content_preview[start:end]
            elif self.config.use_fuzzy_matching:
                # Check for partial matches (any word in signal)
                signal_words = signal_lower.split()
                matched_words = sum(1 for w in signal_words if w in content_lower)
                if matched_words > 0:
                    confidence = matched_words / len(signal_words)
                    if confidence >= self.config.signal_match_threshold:
                        found = True

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
