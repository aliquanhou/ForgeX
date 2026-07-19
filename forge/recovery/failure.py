"""Failure Handler — tracks, categorizes, and recovers from failures.

Not all errors are equal. The failure handler classifies errors by severity
and applies appropriate recovery strategies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class FailureSeverity(str, Enum):
    INFO = "info"  # Log and continue
    WARNING = "warning"  # Retry once
    ERROR = "error"  # Retry with backoff
    CRITICAL = "critical"  # Stop and ask user
    FATAL = "fatal"  # Terminate task


@dataclass
class FailureRecord:
    """A single failure occurrence."""

    error: str
    severity: FailureSeverity
    tool: str = ""
    phase: str = ""
    timestamp: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    recovered: bool = False
    recovery_action: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class FailureHandler:
    """Tracks failures and determines recovery strategy.

    Usage:
        handler = FailureHandler()
        handler.record("file not found", FailureSeverity.WARNING)
        action = handler.get_recovery_action()  # "retry" | "pivot" | "ask_user" | "abort"
    """

    MAX_HISTORY: int = 50

    def __init__(self) -> None:
        self._history: list[FailureRecord] = []
        self._recovery_count: int = 0

    def record(
        self,
        error: str,
        severity: FailureSeverity = FailureSeverity.ERROR,
        tool: str = "",
        phase: str = "",
        context: dict[str, Any] | None = None,
    ) -> FailureRecord:
        """Record a failure and return the record."""
        record = FailureRecord(
            error=error,
            severity=severity,
            tool=tool,
            phase=phase,
            context=context or {},
        )
        self._history.append(record)
        if len(self._history) > self.MAX_HISTORY:
            self._history = self._history[-self.MAX_HISTORY:]
        return record

    def mark_recovered(self, record: FailureRecord, action: str = "") -> None:
        """Mark a failure as recovered."""
        record.recovered = True
        record.recovery_action = action
        self._recovery_count += 1

    @property
    def total_count(self) -> int:
        return len(self._history)

    @property
    def recent_failures(self) -> list[FailureRecord]:
        return self._history[-5:]

    @property
    def consecutive_failures(self) -> int:
        """Count consecutive unrecovered failures."""
        count = 0
        for r in reversed(self._history):
            if not r.recovered:
                count += 1
            else:
                break
        return count

    def get_recovery_action(self) -> str:
        """Determine the appropriate recovery action based on failure history."""
        if self.consecutive_failures >= 5 or self._has_fatal():
            return "abort"

        if self.consecutive_failures >= 3:
            return "ask_user"

        if self.consecutive_failures >= 2:
            return "pivot"  # Try a different approach

        if self._has_error():
            return "retry"

        return "continue"

    def should_ask_user(self) -> bool:
        return self.consecutive_failures >= 3 or self._has_severity(FailureSeverity.CRITICAL)

    def should_abort(self) -> bool:
        return self.consecutive_failures >= 5 or self._has_fatal()

    def _has_severity(self, sev: FailureSeverity) -> bool:
        return any(r.severity == sev and not r.recovered for r in self.recent_failures)

    def _has_fatal(self) -> bool:
        return self._has_severity(FailureSeverity.FATAL)

    def _has_error(self) -> bool:
        return self._has_severity(FailureSeverity.ERROR)

    def summary(self) -> dict[str, Any]:
        return {
            "total": self.total_count,
            "recovered": self._recovery_count,
            "consecutive_failures": self.consecutive_failures,
            "recovery_action": self.get_recovery_action(),
            "recent": [
                {
                    "error": r.error[:80],
                    "severity": r.severity.value,
                    "tool": r.tool,
                    "recovered": r.recovered,
                }
                for r in self.recent_failures
            ],
        }
