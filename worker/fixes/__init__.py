"""Fix generation package for AI sourceability improvements."""

# Lazy imports to avoid requiring all dependencies at import time
# Use explicit imports when needed:
# from worker.fixes.reason_codes import ReasonCode
# from worker.fixes.templates import FixTemplate, get_template
# from worker.fixes.generator import FixGenerator, Fix, FixPlan

__all__ = [
    "ReasonCode",
    "FixTemplate",
    "Fix",
    "FixPlan",
    "FixGenerator",
    "get_template",
]
