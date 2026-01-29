"""Simulation package for AI sourceability evaluation."""

# Lazy imports to avoid requiring all dependencies at import time
# Use explicit imports when needed:
# from worker.simulation.runner import SimulationRunner
# from worker.simulation.results import SimulationResult

__all__ = [
    "SimulationRunner",
    "SimulationConfig",
    "SimulationResult",
    "QuestionResult",
    "run_simulation",
]
