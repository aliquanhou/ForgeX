"""Failure Memory — experience-driven fault recovery.

Records failure patterns + solutions + success rates.
Next time a similar failure occurs, the system can recommend
the known fix without trial and error.

Built on top of recovery/failure.py and memory/episodic.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass
class FailureRecord:
    """A recorded failure with context and resolution."""

    id: str
    error_text: str
    error_type: str  # "syntax", "import", "runtime", "test", "timeout", "permission"
    tool: str
    phase: str
    fix_action: str = ""
    fix_target: str = ""
    success: bool = False
    times_encountered: int = 1
    created_at: str = ""
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    @property
    def confidence(self) -> float:
        """Confidence in this fix based on track record."""
        return min(0.95, 0.3 + self.times_encountered * 0.1 + (0.2 if self.success else 0.0))


class FailureMemory:
    """Experience-driven failure memory.

    Learns from past failures and recommends fixes.
    Integrates with recovery/retry.py for automatic fix application.
    """

    def __init__(self) -> None:
        self._records: dict[str, FailureRecord] = {}  # id → record
        self._error_index: dict[str, list[str]] = {}  # error keyword → record ids

    def record_failure(
        self,
        error_text: str,
        tool: str = "",
        phase: str = "",
    ) -> FailureRecord:
        """Record a failure and check if similar to past failures.

        Returns the record (new or existing if duplicate).
        """
        # Check for duplicate
        existing = self.find_similar(error_text)
        if existing and existing.error_text.lower() in error_text.lower():
            existing.times_encountered += 1
            return existing

        # Extract error type
        error_type = self._classify_error(error_text)

        record = FailureRecord(
            id=uuid.uuid4().hex[:12],
            error_text=error_text[:200],
            error_type=error_type,
            tool=tool,
            phase=phase,
        )
        self._records[record.id] = record

        # Index keywords
        self._index_error(record)
        return record

    def record_fix(
        self,
        failure_id: str,
        fix_action: str,
        fix_target: str,
        success: bool,
    ) -> None:
        """Record a fix that was applied to a failure."""
        record = self._records.get(failure_id)
        if record:
            record.fix_action = fix_action
            record.fix_target = fix_target
            record.success = success

    def find_similar(self, error_text: str) -> FailureRecord | None:
        """Find a similar failure in memory."""
        error_lower = error_text.lower()

        # Direct match
        for record in self._records.values():
            if record.error_text.lower() in error_lower or error_lower in record.error_text.lower():
                return record

        # Keyword match: find records sharing 2+ keywords
        error_words = set(w for w in error_lower.split() if len(w) > 4)
        best: tuple[int, FailureRecord | None] = (0, None)
        for record in self._records.values():
            record_words = set(w for w in record.error_text.lower().split() if len(w) > 4)
            overlap = len(error_words & record_words)
            if overlap > best[0]:
                best = (overlap, record)

        return best[1] if best[0] >= 2 else None

    def get_recommendation(self, error_text: str) -> dict[str, Any] | None:
        """Get a fix recommendation for an error.

        Returns {"action": str, "target": str, "confidence": float} or None.
        """
        similar = self.find_similar(error_text)
        if similar and similar.fix_action:
            return {
                "action": similar.fix_action,
                "target": similar.fix_target,
                "confidence": similar.confidence,
                "record_id": similar.id,
            }
        return None

    def _classify_error(self, error_text: str) -> str:
        """Classify error by type."""
        text = error_text.lower()
        if "syntax" in text or "parse" in text:
            return "syntax"
        if "import" in text or "module" in text or "not found" in text:
            return "import"
        if "typeerror" in text or "valueerror" in text or "keyerror" in text:
            return "runtime"
        if "assert" in text or "test" in text or "failed" in text:
            return "test"
        if "timeout" in text or "timed out" in text:
            return "timeout"
        if "permission" in text or "access" in text:
            return "permission"
        return "unknown"

    def _index_error(self, record: FailureRecord) -> None:
        """Index error by keywords for fast retrieval."""
        words = set(w for w in record.error_text.lower().split() if len(w) > 3)
        for word in words:
            if word not in self._error_index:
                self._error_index[word] = []
            self._error_index[word].append(record.id)

    @property
    def total_failures(self) -> int:
        return len(self._records)

    @property
    def success_rate(self) -> float:
        if not self._records:
            return 0.0
        resolved = [r for r in self._records.values() if r.fix_action]
        if not resolved:
            return 0.0
        return sum(1 for r in resolved if r.success) / len(resolved)

    def summary(self) -> dict[str, Any]:
        return {
            "total_failures": self.total_failures,
            "with_fixes": sum(1 for r in self._records.values() if r.fix_action),
            "success_rate": round(self.success_rate, 3),
            "common_types": self._common_error_types(),
        }

    def _common_error_types(self) -> list[tuple[str, int]]:
        from collections import Counter
        counts = Counter(r.error_type for r in self._records.values())
        return counts.most_common(5)
