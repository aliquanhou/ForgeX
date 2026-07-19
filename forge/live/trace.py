"""Live Trace — runtime behavior capture.

Captures stdout, stderr, exceptions, and exit codes from execution.
Each capture is a timestamped snapshot of what happened.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TraceKind(str, Enum):
    STDOUT = "stdout"
    STDERR = "stderr"
    EXCEPTION = "exception"
    EXIT_CODE = "exit_code"
    HTTP_REQUEST = "http_request"
    HTTP_RESPONSE = "http_response"
    DB_QUERY = "db_query"
    CUSTOM = "custom"


@dataclass
class TraceCapture:
    """A single captured trace event."""

    kind: TraceKind
    content: str
    timestamp: str = ""
    source: str = ""  # e.g., "pytest", "curl", "python"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    @property
    def is_error(self) -> bool:
        return self.kind in (TraceKind.STDERR, TraceKind.EXCEPTION)


@dataclass
class RuntimeSnapshot:
    """A snapshot of runtime behavior after executing something.

    Before/after comparison works by comparing two snapshots.
    """

    label: str  # e.g., "before_change", "after_change"
    captures: list[TraceCapture] = field(default_factory=list)
    exit_code: int = 0
    duration_ms: float = 0.0

    @property
    def has_errors(self) -> bool:
        return any(t.is_error for t in self.captures) or self.exit_code != 0

    @property
    def stderr(self) -> str:
        return "\n".join(t.content for t in self.captures if t.kind == TraceKind.STDERR)

    @property
    def stdout(self) -> str:
        return "\n".join(t.content for t in self.captures if t.kind == TraceKind.STDOUT)

    @property
    def exceptions(self) -> list[str]:
        return [t.content for t in self.captures if t.kind == TraceKind.EXCEPTION]


class LiveTrace:
    """Captures runtime execution traces for before/after comparison.

    Usage:
        trace = LiveTrace()
        snapshot = trace.capture("test_suite", lambda: run_tests())
        print(snapshot.has_errors)
    """

    def __init__(self) -> None:
        self._history: list[RuntimeSnapshot] = []

    def capture(self, label: str, executable: str, args: list[str] | None = None,
                cwd: str = "", timeout: float = 30.0) -> RuntimeSnapshot:
        """Execute a command and capture its runtime trace.

        Args:
            label: Label for this snapshot (e.g., "before_fix")
            executable: Command to run (e.g., "python", "pytest")
            args: Command arguments
            cwd: Working directory
            timeout: Timeout in seconds

        Returns:
            RuntimeSnapshot with captured traces
        """
        import asyncio
        import subprocess
        import time

        start = time.time()
        captures: list[TraceCapture] = []

        cmd = [executable]
        if args:
            cmd.extend(args)

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=cwd or None,
                timeout=timeout,
            )

            if proc.stdout:
                captures.append(TraceCapture(
                    kind=TraceKind.STDOUT,
                    content=proc.stdout[:50000],
                    source=executable,
                ))

            if proc.stderr:
                captures.append(TraceCapture(
                    kind=TraceKind.STDERR,
                    content=proc.stderr[:50000],
                    source=executable,
                ))

            exit_code = proc.returncode

        except subprocess.TimeoutExpired:
            captures.append(TraceCapture(
                kind=TraceKind.EXCEPTION,
                content=f"Command timed out after {timeout}s",
                source=executable,
            ))
            exit_code = -1
        except FileNotFoundError:
            captures.append(TraceCapture(
                kind=TraceKind.EXCEPTION,
                content=f"Command not found: {executable}",
                source=executable,
            ))
            exit_code = -1
        except Exception as e:
            captures.append(TraceCapture(
                kind=TraceKind.EXCEPTION,
                content=str(e),
                source=executable,
            ))
            exit_code = -1

        duration = (time.time() - start) * 1000

        snapshot = RuntimeSnapshot(
            label=label,
            captures=captures,
            exit_code=exit_code,
            duration_ms=round(duration, 2),
        )
        self._history.append(snapshot)
        return snapshot

    def capture_python(self, label: str, code: str) -> RuntimeSnapshot:
        """Execute a Python snippet and capture its trace."""
        return self.capture(label, "python", ["-c", code])

    def capture_test(self, label: str, test_path: str, cwd: str = "") -> RuntimeSnapshot:
        """Run pytest and capture the trace."""
        return self.capture(label, "python", ["-m", "pytest", test_path, "-v", "--tb=short"], cwd=cwd)

    def compare(self, before: str, after: str) -> RuntimeSnapshot | None:
        """Compare two snapshots by label. Returns None if either not found."""
        snapshots = {s.label: s for s in self._history}
        before_snap = snapshots.get(before)
        after_snap = snapshots.get(after)
        if before_snap is None or after_snap is None:
            return None

        # Return the after snapshot for behavior diff
        return after_snap

    @property
    def last_snapshot(self) -> RuntimeSnapshot | None:
        return self._history[-1] if self._history else None
