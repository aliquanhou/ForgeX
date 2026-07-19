"""Live Execution Intelligence — runtime behavior observability.

Captures what actually happens when code runs:
- stdout/stderr traces
- Exception traces
- HTTP request/response traces
- Command execution traces

Enables the agent to compare behavior before vs after changes.
"""

from __future__ import annotations

from .trace import LiveTrace, TraceCapture, RuntimeSnapshot, TraceKind
from .behavior_diff import BehaviorDiff, BehaviorChange, DiffSeverity, BehaviorDiffer
from .coverage import ExecutionCoverage, CoverageResult, CoverageLine

__all__ = [
    "LiveTrace", "TraceCapture", "RuntimeSnapshot", "TraceKind",
    "BehaviorDiff", "BehaviorChange", "DiffSeverity", "BehaviorDiffer",
    "ExecutionCoverage", "CoverageResult", "CoverageLine",
]
