"""Scoring package for AI sourceability evaluation."""

# Lazy imports to avoid requiring all dependencies at import time
# Use explicit imports when needed:
# from worker.scoring.rubric import ScoringRubric
# from worker.scoring.calculator import ScoreCalculator

__all__ = [
    "ScoringRubric",
    "RubricCriterion",
    "ScoreCalculator",
    "ScoreBreakdown",
    "CategoryBreakdown",
    "calculate_score",
]
