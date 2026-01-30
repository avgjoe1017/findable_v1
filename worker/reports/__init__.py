"""Report assembly and JSON contract.

This package provides a stable report format that combines all analysis
results into a versioned, serializable artifact.

Use explicit imports:
    from worker.reports.contract import ReportVersion, FullReport
    from worker.reports.assembler import ReportAssembler, assemble_report
"""

__all__ = [
    # Contract
    "ReportVersion",
    "ReportMetadata",
    "ScoreSection",
    "FixSection",
    "ObservationSection",
    "BenchmarkSection",
    "DivergenceSection",
    "FullReport",
    # Assembler
    "ReportAssembler",
    "ReportAssemblerConfig",
    "assemble_report",
]
