"""Tier B impact estimator using synthetic patching.

Patches fix scaffolds into content in-memory and re-scores
only affected questions for more accurate impact estimates
without full re-crawl.
"""

from dataclasses import dataclass, field
from datetime import datetime

from worker.fixes.generator import Fix, FixPlan
from worker.fixes.impact import (
    ConfidenceLevel,
    FixImpactEstimate,
    FixPlanImpact,
    ImpactRange,
    ImpactTier,
)
from worker.fixes.reason_codes import ReasonCode
from worker.questions.universal import QuestionCategory
from worker.simulation.runner import (
    Answerability,
    QuestionResult,
    SimulationResult,
)
from worker.simulation.runner import (
    ConfidenceLevel as SimConfidence,
)


@dataclass
class SyntheticChunk:
    """A synthetic content chunk for patching."""

    content: str
    source_url: str
    relevance_boost: float  # How much to boost relevance score
    signals_added: list[str]  # Signals this chunk adds

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "content": self.content[:200] + "..." if len(self.content) > 200 else self.content,
            "source_url": self.source_url,
            "relevance_boost": self.relevance_boost,
            "signals_added": self.signals_added,
        }


@dataclass
class PatchedQuestionResult:
    """Result of re-scoring a question with patched content."""

    question_id: str
    original_score: float
    patched_score: float
    score_delta: float

    original_answerability: Answerability
    patched_answerability: Answerability

    original_signals_found: int
    patched_signals_found: int
    signals_total: int

    new_signals_matched: list[str]
    explanation: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "question_id": self.question_id,
            "original_score": round(self.original_score, 3),
            "patched_score": round(self.patched_score, 3),
            "score_delta": round(self.score_delta, 3),
            "original_answerability": self.original_answerability.value,
            "patched_answerability": self.patched_answerability.value,
            "original_signals_found": self.original_signals_found,
            "patched_signals_found": self.patched_signals_found,
            "signals_total": self.signals_total,
            "new_signals_matched": self.new_signals_matched,
            "explanation": self.explanation,
        }


@dataclass
class TierBEstimate:
    """Tier B impact estimate with synthetic patching details."""

    fix_id: str
    reason_code: ReasonCode
    impact_range: ImpactRange

    # Patched results
    patched_questions: list[PatchedQuestionResult]
    total_score_improvement: float
    questions_improved: int
    questions_unchanged: int

    # Synthetic chunks used
    synthetic_chunks: list[SyntheticChunk]

    # Comparison to Tier C
    tier_c_expected: float
    tier_b_expected: float
    estimation_difference: float

    # Metadata
    computation_time_ms: float
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "fix_id": self.fix_id,
            "reason_code": self.reason_code.value,
            "impact_range": self.impact_range.to_dict(),
            "patched_questions": [p.to_dict() for p in self.patched_questions],
            "total_score_improvement": round(self.total_score_improvement, 2),
            "questions_improved": self.questions_improved,
            "questions_unchanged": self.questions_unchanged,
            "synthetic_chunks": [c.to_dict() for c in self.synthetic_chunks],
            "tier_c_expected": round(self.tier_c_expected, 2),
            "tier_b_expected": round(self.tier_b_expected, 2),
            "estimation_difference": round(self.estimation_difference, 2),
            "computation_time_ms": round(self.computation_time_ms, 2),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class TierBConfig:
    """Configuration for Tier B estimation."""

    # Scoring thresholds
    fully_answerable_threshold: float = 0.7
    partially_answerable_threshold: float = 0.3

    # Relevance boost for patched content
    base_relevance_boost: float = 0.3
    max_relevance_score: float = 0.95

    # Signal matching
    signal_confidence: float = 0.9  # Confidence for newly matched signals

    # Weights (same as simulation)
    relevance_weight: float = 0.4
    signal_weight: float = 0.4
    confidence_weight: float = 0.2


class TierBEstimator:
    """Tier B impact estimator using synthetic content patching."""

    def __init__(self, config: TierBConfig | None = None):
        self.config = config or TierBConfig()

    def estimate_fix(
        self,
        fix: Fix,
        simulation: SimulationResult,
        tier_c_expected: float = 0.0,
    ) -> TierBEstimate:
        """
        Estimate impact for a fix using synthetic patching.

        Args:
            fix: The fix to estimate
            simulation: Original simulation result
            tier_c_expected: Tier C estimate for comparison

        Returns:
            TierBEstimate with detailed results
        """
        import time
        start_time = time.perf_counter()

        # Get affected questions from simulation
        affected_questions = self._get_affected_questions(
            fix.affected_question_ids,
            simulation.question_results,
        )

        # Create synthetic chunks from fix scaffold
        synthetic_chunks = self._create_synthetic_chunks(fix)

        # Re-score affected questions with patched content
        patched_results: list[PatchedQuestionResult] = []
        for question in affected_questions:
            patched = self._rescore_question(question, synthetic_chunks, fix)
            patched_results.append(patched)

        # Calculate total improvement
        total_improvement = sum(p.score_delta for p in patched_results)
        questions_improved = sum(1 for p in patched_results if p.score_delta > 0.01)
        questions_unchanged = len(patched_results) - questions_improved

        # Scale to 100-point score
        # Each question contributes based on its weight in the total
        num_questions = simulation.total_questions or 1
        scaled_improvement = (total_improvement / num_questions) * 100

        # Calculate impact range (Tier B has tighter bounds)
        min_points = scaled_improvement * 0.8
        max_points = scaled_improvement * 1.2
        expected_points = scaled_improvement

        # Determine confidence
        confidence = self._determine_confidence(patched_results)

        computation_time = (time.perf_counter() - start_time) * 1000

        return TierBEstimate(
            fix_id=str(fix.id),
            reason_code=fix.reason_code,
            impact_range=ImpactRange(
                min_points=max(0, min_points),
                max_points=max_points,
                expected_points=max(0, expected_points),
                confidence=confidence,
                tier=ImpactTier.TIER_B,
            ),
            patched_questions=patched_results,
            total_score_improvement=scaled_improvement,
            questions_improved=questions_improved,
            questions_unchanged=questions_unchanged,
            synthetic_chunks=synthetic_chunks,
            tier_c_expected=tier_c_expected,
            tier_b_expected=expected_points,
            estimation_difference=expected_points - tier_c_expected,
            computation_time_ms=computation_time,
        )

    def estimate_plan(
        self,
        plan: FixPlan,
        simulation: SimulationResult,
        tier_c_impact: FixPlanImpact | None = None,
        top_n: int = 5,
    ) -> FixPlanImpact:
        """
        Estimate impact for a fix plan using Tier B.

        Args:
            plan: The fix plan
            simulation: Original simulation result
            tier_c_impact: Optional Tier C impact for comparison
            top_n: Number of top fixes to process with Tier B

        Returns:
            FixPlanImpact with Tier B estimates
        """
        estimates: list[FixImpactEstimate] = []

        # Get top fixes to estimate (limit to top_n for performance)
        top_fixes = plan.get_top_fixes(top_n)

        # Get Tier C estimates for comparison
        tier_c_map: dict[str, float] = {}
        if tier_c_impact:
            for e in tier_c_impact.estimates:
                tier_c_map[e.fix_id] = e.impact_range.expected_points

        for fix in top_fixes:
            tier_c_expected = tier_c_map.get(str(fix.id), 0.0)
            tier_b_estimate = self.estimate_fix(fix, simulation, tier_c_expected)

            # Convert to FixImpactEstimate for consistency
            estimate = FixImpactEstimate(
                fix_id=tier_b_estimate.fix_id,
                reason_code=tier_b_estimate.reason_code,
                impact_range=tier_b_estimate.impact_range,
                affected_questions=len(tier_b_estimate.patched_questions),
                affected_categories=fix.affected_categories,
                base_impact=tier_b_estimate.tier_b_expected,
                question_multiplier=1.0,
                category_multiplier=1.0,
                explanation=self._build_explanation(tier_b_estimate),
                assumptions=self._build_assumptions(tier_b_estimate),
            )
            estimates.append(estimate)

        # Sort by expected impact
        estimates.sort(key=lambda e: -e.impact_range.expected_points)

        # Calculate totals
        total_min = sum(e.impact_range.min_points for e in estimates)
        total_max = sum(e.impact_range.max_points for e in estimates)
        total_expected = sum(e.impact_range.expected_points for e in estimates)

        # Get all categories
        all_categories: set[QuestionCategory] = set()
        for e in estimates:
            all_categories.update(e.affected_categories)

        # Determine overall confidence
        if not estimates:
            overall_confidence = ConfidenceLevel.LOW
        else:
            high_count = sum(
                1 for e in estimates
                if e.impact_range.confidence == ConfidenceLevel.HIGH
            )
            if high_count > len(estimates) / 2:
                overall_confidence = ConfidenceLevel.HIGH
            else:
                overall_confidence = ConfidenceLevel.MEDIUM

        notes = [
            f"Tier B estimates based on synthetic patching of {len(top_fixes)} fixes",
            "More accurate than Tier C but does not account for all content interactions",
        ]

        return FixPlanImpact(
            plan_id=str(plan.id),
            estimates=estimates,
            total_min_points=total_min,
            total_max_points=total_max,
            total_expected_points=total_expected,
            top_impact_fixes=[e.fix_id for e in estimates],
            categories_impacted=list(all_categories),
            overall_confidence=overall_confidence,
            tier=ImpactTier.TIER_B,
            notes=notes,
        )

    def _get_affected_questions(
        self,
        question_ids: list[str],
        all_results: list[QuestionResult],
    ) -> list[QuestionResult]:
        """Get question results for affected questions."""
        id_set = set(question_ids)
        return [r for r in all_results if r.question_id in id_set]

    def _create_synthetic_chunks(self, fix: Fix) -> list[SyntheticChunk]:
        """Create synthetic content chunks from fix scaffold."""
        chunks: list[SyntheticChunk] = []

        # Extract signals this fix would add
        signals_added = self._extract_signals_from_scaffold(
            fix.scaffold,
            fix.reason_code,
        )

        # Create main chunk from scaffold
        main_chunk = SyntheticChunk(
            content=fix.scaffold,
            source_url=fix.target_url or "/",
            relevance_boost=self.config.base_relevance_boost,
            signals_added=signals_added,
        )
        chunks.append(main_chunk)

        return chunks

    def _extract_signals_from_scaffold(
        self,
        scaffold: str,
        reason_code: ReasonCode,
    ) -> list[str]:
        """Extract expected signals that the scaffold would add."""
        signals: list[str] = []
        scaffold_lower = scaffold.lower()

        # Common signals by reason code
        signal_patterns = {
            ReasonCode.MISSING_DEFINITION: [
                "company description", "business type", "value proposition",
                "what we do", "who we are",
            ],
            ReasonCode.MISSING_PRICING: [
                "pricing", "price", "cost", "plan", "subscription",
                "free trial", "per month", "per year",
            ],
            ReasonCode.MISSING_CONTACT: [
                "email", "phone", "contact", "address", "hours",
                "get in touch",
            ],
            ReasonCode.MISSING_LOCATION: [
                "location", "address", "headquarters", "service area",
                "serving", "located",
            ],
            ReasonCode.MISSING_FEATURES: [
                "feature", "capability", "functionality", "includes",
                "supports",
            ],
            ReasonCode.MISSING_SOCIAL_PROOF: [
                "testimonial", "review", "case study", "customer",
                "client", "results",
            ],
            ReasonCode.TRUST_GAP: [
                "certified", "award", "recognition", "featured in",
                "trusted by",
            ],
        }

        patterns = signal_patterns.get(reason_code, [])
        for pattern in patterns:
            if pattern in scaffold_lower:
                signals.append(pattern)

        # If no specific signals found, add generic ones
        if not signals:
            signals = ["content added", "information provided"]

        return signals[:5]  # Limit to 5 signals

    def _rescore_question(
        self,
        question: QuestionResult,
        synthetic_chunks: list[SyntheticChunk],
        _fix: Fix,
    ) -> PatchedQuestionResult:
        """Re-score a question with synthetic patched content."""
        # Get original metrics
        original_score = question.score
        original_relevance = question.context.avg_relevance_score
        original_signals = question.signals_found
        signals_total = question.signals_total

        # Calculate patched relevance (boosted)
        relevance_boost = sum(c.relevance_boost for c in synthetic_chunks)
        patched_relevance = min(
            self.config.max_relevance_score,
            original_relevance + relevance_boost,
        )

        # Calculate new signal matches
        new_signals: list[str] = []
        for chunk in synthetic_chunks:
            for signal in chunk.signals_added:
                # Check if this signal was missing
                was_missing = not any(
                    m.found and m.signal.lower() == signal.lower()
                    for m in question.signal_matches
                )
                if was_missing:
                    new_signals.append(signal)

        # Calculate patched signals found
        patched_signals = min(signals_total, original_signals + len(new_signals))
        signal_ratio = patched_signals / signals_total if signals_total > 0 else 0.5

        # Calculate patched confidence
        patched_confidence = self._calculate_patched_confidence(
            original_confidence=question.confidence,
            relevance_improved=(patched_relevance > original_relevance),
            signals_improved=(patched_signals > original_signals),
        )

        # Calculate patched score
        patched_score = (
            self.config.relevance_weight * patched_relevance +
            self.config.signal_weight * signal_ratio +
            self.config.confidence_weight * patched_confidence
        )

        # Determine patched answerability
        if patched_score >= self.config.fully_answerable_threshold:
            patched_answerability = Answerability.FULLY_ANSWERABLE
        elif patched_score >= self.config.partially_answerable_threshold:
            patched_answerability = Answerability.PARTIALLY_ANSWERABLE
        else:
            patched_answerability = Answerability.NOT_ANSWERABLE

        # Build explanation
        explanation = self._build_question_explanation(
            question,
            original_score,
            patched_score,
            new_signals,
        )

        return PatchedQuestionResult(
            question_id=question.question_id,
            original_score=original_score,
            patched_score=patched_score,
            score_delta=patched_score - original_score,
            original_answerability=question.answerability,
            patched_answerability=patched_answerability,
            original_signals_found=original_signals,
            patched_signals_found=patched_signals,
            signals_total=signals_total,
            new_signals_matched=new_signals,
            explanation=explanation,
        )

    def _calculate_patched_confidence(
        self,
        original_confidence: SimConfidence,
        relevance_improved: bool,
        signals_improved: bool,
    ) -> float:
        """Calculate confidence score for patched content."""
        base_confidence = {
            SimConfidence.HIGH: 1.0,
            SimConfidence.MEDIUM: 0.6,
            SimConfidence.LOW: 0.3,
        }.get(original_confidence, 0.5)

        # Improve confidence if metrics improved
        if relevance_improved and signals_improved:
            return min(1.0, base_confidence + 0.3)
        elif relevance_improved or signals_improved:
            return min(1.0, base_confidence + 0.15)

        return base_confidence

    def _build_question_explanation(
        self,
        _question: QuestionResult,
        original_score: float,
        patched_score: float,
        new_signals: list[str],
    ) -> str:
        """Build explanation for question re-scoring."""
        delta = patched_score - original_score
        if delta > 0.1:
            impact = "significant improvement"
        elif delta > 0.01:
            impact = "moderate improvement"
        else:
            impact = "minimal change"

        signals_str = ", ".join(new_signals[:3]) if new_signals else "none"

        return (
            f"{impact.capitalize()} expected. Score: {original_score:.2f} → "
            f"{patched_score:.2f} (+{delta:.2f}). New signals: {signals_str}."
        )

    def _determine_confidence(
        self,
        patched_results: list[PatchedQuestionResult],
    ) -> ConfidenceLevel:
        """Determine confidence level for the estimate."""
        if not patched_results:
            return ConfidenceLevel.LOW

        # High confidence if most questions improved
        improved = sum(1 for p in patched_results if p.score_delta > 0.05)
        if improved > len(patched_results) * 0.7:
            return ConfidenceLevel.HIGH
        elif improved > len(patched_results) * 0.3:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def _build_explanation(self, estimate: TierBEstimate) -> str:
        """Build explanation for Tier B estimate."""
        return (
            f"Tier B synthetic patching shows ~{estimate.tier_b_expected:.1f} point "
            f"improvement. {estimate.questions_improved} of "
            f"{len(estimate.patched_questions)} affected questions would improve."
        )

    def _build_assumptions(self, estimate: TierBEstimate) -> list[str]:
        """Build assumptions list for Tier B estimate."""
        assumptions = [
            "Based on Tier B synthetic content patching",
            "Assumes fix scaffold accurately represents final content",
            "Signal matching based on keyword presence",
        ]

        if estimate.estimation_difference > 2:
            assumptions.append(
                f"Tier B estimate is {estimate.estimation_difference:.1f}pts higher "
                "than Tier C - actual impact may vary"
            )
        elif estimate.estimation_difference < -2:
            assumptions.append(
                f"Tier B estimate is {-estimate.estimation_difference:.1f}pts lower "
                "than Tier C - fix may have less impact than initially estimated"
            )

        return assumptions


def estimate_fix_tier_b(
    fix: Fix,
    simulation: SimulationResult,
    tier_c_expected: float = 0.0,
) -> TierBEstimate:
    """
    Convenience function to estimate fix impact with Tier B.

    Args:
        fix: The fix to estimate
        simulation: Original simulation result
        tier_c_expected: Tier C estimate for comparison

    Returns:
        TierBEstimate
    """
    estimator = TierBEstimator()
    return estimator.estimate_fix(fix, simulation, tier_c_expected)


def estimate_plan_tier_b(
    plan: FixPlan,
    simulation: SimulationResult,
    tier_c_impact: FixPlanImpact | None = None,
    top_n: int = 5,
) -> FixPlanImpact:
    """
    Convenience function to estimate plan impact with Tier B.

    Args:
        plan: The fix plan
        simulation: Original simulation result
        tier_c_impact: Optional Tier C impact for comparison
        top_n: Number of top fixes to process

    Returns:
        FixPlanImpact with Tier B estimates
    """
    estimator = TierBEstimator()
    return estimator.estimate_plan(plan, simulation, tier_c_impact, top_n)
