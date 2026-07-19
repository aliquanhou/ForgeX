"""Behavior Diff — compare runtime behavior before vs after changes.

Answers: "Did the change break anything?"
         "What changed in the output?"
         "Are there new errors?"

Works by comparing RuntimeSnapshot pairs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .trace import RuntimeSnapshot, TraceKind


class DiffSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class BehaviorChange:
    """A single detected behavior change."""

    kind: str  # "exit_code", "stderr", "stdout", "exception"
    severity: DiffSeverity
    description: str
    before_value: str = ""
    after_value: str = ""


@dataclass
class BehaviorDiff:
    """Result of comparing two runtime snapshots."""

    before_label: str
    after_label: str
    changes: list[BehaviorChange] = field(default_factory=list)
    passed_before: bool = True
    passed_after: bool = True

    @property
    def has_regression(self) -> bool:
        """Did behavior get worse?"""
        if self.passed_before and not self.passed_after:
            return True
        return any(c.severity in (DiffSeverity.ERROR, DiffSeverity.CRITICAL) for c in self.changes)

    @property
    def has_improvement(self) -> bool:
        """Did behavior get better?"""
        if not self.passed_before and self.passed_after:
            return True
        return False

    @property
    def summary(self) -> str:
        lines = [f"Behavior diff: {self.before_label} → {self.after_label}"]
        if self.has_regression:
            lines.append("  ⚠ REGRESSION DETECTED")
        if self.has_improvement:
            lines.append("  ✓ Behavior improved")
        if not self.changes:
            lines.append("  ✓ No behavioral changes detected")
        for c in self.changes:
            emoji = {"info": "ℹ", "warning": "⚠", "error": "✗", "critical": "🔥"}.get(c.severity.value, "•")
            lines.append(f"  {emoji} [{c.kind}] {c.description}")
        return "\n".join(lines)


class BehaviorDiffer:
    """Compares runtime behavior before and after changes.

    Usage:
        differ = BehaviorDiffer()
        diff = differ.compare(before_snapshot, after_snapshot)
        print(diff.summary)
        if diff.has_regression:
            rollback()
    """

    def compare(self, before: RuntimeSnapshot, after: RuntimeSnapshot) -> BehaviorDiff:
        """Compare two runtime snapshots and find behavioral differences."""
        result = BehaviorDiff(
            before_label=before.label,
            after_label=after.label,
            passed_before=not before.has_errors,
            passed_after=not after.has_errors,
        )

        # 1. Exit code comparison
        if before.exit_code != after.exit_code:
            result.changes.append(BehaviorChange(
                kind="exit_code",
                severity=DiffSeverity.ERROR if after.exit_code != 0 else DiffSeverity.INFO,
                description=f"Exit code: {before.exit_code} → {after.exit_code}",
                before_value=str(before.exit_code),
                after_value=str(after.exit_code),
            ))

        # 2. Error comparison (new errors = regression)
        before_errors = set(t.content[:100] for t in before.captures if t.is_error)
        after_errors = set(t.content[:100] for t in after.captures if t.is_error)
        new_errors = after_errors - before_errors
        fixed_errors = before_errors - after_errors

        for err in new_errors:
            severity = DiffSeverity.CRITICAL if "traceback" in err.lower() else DiffSeverity.ERROR
            result.changes.append(BehaviorChange(
                kind="exception" if "traceback" in err.lower() or "error" in err.lower() else "stderr",
                severity=severity,
                description=f"New error: {err[:120]}",
                after_value=err,
            ))

        for err in fixed_errors:
            result.changes.append(BehaviorChange(
                kind="exception",
                severity=DiffSeverity.INFO,
                description=f"Fixed error: {err[:120]}",
                before_value=err,
            ))

        # 3. Output size comparison (drastic changes = suspicious)
        if before.stdout and after.stdout:
            before_size = len(before.stdout)
            after_size = len(after.stdout)
            if after_size == 0 and before_size > 0:
                result.changes.append(BehaviorChange(
                    kind="stdout",
                    severity=DiffSeverity.WARNING,
                    description="Output disappeared (was {before_size} chars, now 0)",
                ))
            elif before_size > 0 and after_size > 0:
                ratio = after_size / before_size
                if ratio > 2.0:
                    result.changes.append(BehaviorChange(
                        kind="stdout",
                        severity=DiffSeverity.WARNING,
                        description=f"Output size grew {ratio:.1f}x ({before_size} → {after_size} chars)",
                    ))
                elif ratio < 0.1:
                    result.changes.append(BehaviorChange(
                        kind="stdout",
                        severity=DiffSeverity.WARNING,
                        description=f"Output shrank to {ratio:.0%} of original",
                    ))

        return result

    def compare_before_after(
        self,
        before_label: str,
        after_label: str,
        trace: "LiveTrace",
    ) -> BehaviorDiff | None:
        """Convenience: compare two snapshots from a LiveTrace by label."""
        before = next((s for s in trace._history if s.label == before_label), None)  # type: ignore
        after = next((s for s in trace._history if s.label == after_label), None)  # type: ignore
        if before is None or after is None:
            return None
        return self.compare(before, after)

    def verify_change(
        self,
        before_snapshot: RuntimeSnapshot,
        after_snapshot: RuntimeSnapshot,
        require_same_exit_code: bool = True,
        allow_new_stderr: bool = False,
    ) -> tuple[bool, BehaviorDiff]:
        """Verify that a change is safe.

        Returns (is_safe, diff).
        """
        diff = self.compare(before_snapshot, after_snapshot)

        if diff.has_regression:
            return False, diff

        if require_same_exit_code and before_snapshot.exit_code != after_snapshot.exit_code:
            # Only fail if after is non-zero
            if after_snapshot.exit_code != 0:
                return False, diff

        if not allow_new_stderr:
            after_stderr = after_snapshot.stderr.strip()
            before_stderr = before_snapshot.stderr.strip()
            if after_stderr and not before_stderr:
                return False, diff

        return True, diff
