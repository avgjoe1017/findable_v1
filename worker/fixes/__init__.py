"""Fix generation package for AI sourceability improvements."""

# Lazy imports to avoid requiring all dependencies at import time
# Use explicit imports when needed:
# from worker.fixes.reason_codes import ReasonCode
# from worker.fixes.templates import FixTemplate, get_template
# from worker.fixes.generator import FixGenerator, Fix, FixPlan
# from worker.fixes.impact import TierCEstimator, estimate_plan_impact
# from worker.fixes.synthetic import TierBEstimator, estimate_fix_tier_b

__all__ = [
    # Reason codes
    "ReasonCode",
    # Templates
    "FixTemplate",
    "get_template",
    # Generator
    "Fix",
    "FixPlan",
    "FixGenerator",
    # Tier C Impact
    "TierCEstimator",
    "FixImpactEstimate",
    "FixPlanImpact",
    "ImpactRange",
    "estimate_fix_impact",
    "estimate_plan_impact",
    # Tier B Impact (Synthetic Patching)
    "TierBEstimator",
    "TierBEstimate",
    "PatchedQuestionResult",
    "SyntheticChunk",
    "estimate_fix_tier_b",
    "estimate_plan_tier_b",
    # v2 Fix Generator (Action Center)
    "FixGeneratorV2",
    "FixPlanV2",
    "ActionCenter",
    "ActionItem",
    "UnifiedFix",
    "FixCategory",
    "EffortLevel",
    "ImpactLevel",
    "generate_fix_plan_v2",
]
