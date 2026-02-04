"""Background task definitions."""

from worker.tasks.audit import run_audit, run_audit_sync
from worker.tasks.authority_check import (
    aggregate_authority_scores,
    generate_authority_fixes,
    run_authority_checks,
    run_authority_checks_sync,
)
from worker.tasks.schema_check import (
    aggregate_schema_scores,
    generate_schema_fixes,
    run_schema_checks,
    run_schema_checks_sync,
)
from worker.tasks.structure_check import (
    aggregate_structure_scores,
    generate_structure_fixes,
    run_structure_checks,
    run_structure_checks_sync,
)
from worker.tasks.technical_check import (
    generate_technical_fixes,
    run_technical_checks,
    run_technical_checks_parallel,
)

__all__ = [
    "run_audit",
    "run_audit_sync",
    # Technical checks (v2)
    "run_technical_checks",
    "run_technical_checks_parallel",
    "generate_technical_fixes",
    # Structure checks (v2)
    "run_structure_checks",
    "run_structure_checks_sync",
    "aggregate_structure_scores",
    "generate_structure_fixes",
    # Schema checks (v2)
    "run_schema_checks",
    "run_schema_checks_sync",
    "aggregate_schema_scores",
    "generate_schema_fixes",
    # Authority checks (v2)
    "run_authority_checks",
    "run_authority_checks_sync",
    "aggregate_authority_scores",
    "generate_authority_fixes",
]
