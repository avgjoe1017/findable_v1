"""Scoring package for AI sourceability evaluation."""

# Lazy imports to avoid requiring all dependencies at import time
# Use explicit imports when needed:
# from worker.scoring.rubric import ScoringRubric
# from worker.scoring.calculator import ScoreCalculator
# from worker.scoring.technical import calculate_technical_score
# from worker.scoring.structure import calculate_structure_score
# from worker.scoring.schema import calculate_schema_score

__all__ = [
    "ScoringRubric",
    "RubricCriterion",
    "ScoreCalculator",
    "ScoreBreakdown",
    "CategoryBreakdown",
    "calculate_score",
    # Technical Readiness (v2)
    "TechnicalScoreCalculator",
    "TechnicalReadinessScore",
    "TechnicalComponent",
    "calculate_technical_score",
    # Structure Quality (v2)
    "StructureScoreCalculator",
    "StructureQualityScore",
    "StructureComponent",
    "calculate_structure_score",
    # Schema Richness (v2)
    "SchemaScoreCalculator",
    "SchemaRichnessScore",
    "SchemaComponent",
    "calculate_schema_score",
    # Authority Signals (v2)
    "AuthorityScoreCalculator",
    "AuthoritySignalsScore",
    "AuthorityComponent",
    "calculate_authority_score",
    # Unified v2 Score
    "FindableScoreCalculatorV2",
    "FindableScoreV2",
    "PillarScore",
    "MilestoneInfo",
    "PathAction",
    "FINDABILITY_LEVELS",
    "MILESTONES",
    "calculate_findable_score_v2",
    # Delta Comparison (run-over-run)
    "ScoreDeltaCalculator",
    "ScoreDelta",
    "PillarDelta",
    "ChangeDirection",
    "ChangeSignificance",
    "ScoreTrend",
    "ScoreTrendSummary",
    "compare_scores",
    "build_trend_data",
]
