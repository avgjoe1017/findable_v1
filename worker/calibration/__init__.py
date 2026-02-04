"""Calibration module for learning from observation outcomes.

This module provides:
- Weight optimization via grid search
- Threshold optimization for answerability
- A/B experiment infrastructure
- Analysis utilities for calibration data
"""

from worker.calibration.experiment import (
    ExperimentArm,
    ExperimentAssignment,
    ExperimentResults,
    analyze_experiment,
    assign_to_experiment,
    conclude_experiment,
    get_active_experiment,
    get_experiment_arm,
    start_experiment,
)
from worker.calibration.optimizer import (
    OptimizationResult,
    optimize_answerability_thresholds,
    optimize_pillar_weights,
    validate_config_improvement,
)

__all__ = [
    # Optimizer
    "OptimizationResult",
    "optimize_pillar_weights",
    "optimize_answerability_thresholds",
    "validate_config_improvement",
    # Experiment
    "ExperimentArm",
    "ExperimentAssignment",
    "ExperimentResults",
    "get_experiment_arm",
    "get_active_experiment",
    "assign_to_experiment",
    "analyze_experiment",
    "conclude_experiment",
    "start_experiment",
]
