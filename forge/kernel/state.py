"""RuntimeState — the compressed, structured state that drives all decisions.

This is THE single source of truth for the entire agent.
It is NOT the chat history. It is a distilled, actionable snapshot.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskPhase(str, Enum):
    """The current phase of a task. Only one at a time."""

    INIT = "init"
    PLANNING = "planning"
    EXPLORATION = "exploration"
    IMPLEMENTATION = "implementation"
    VERIFICATION = "verification"
    RECOVERY = "recovery"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ToolEvidence:
    """Evidence of what a tool call produced — used by EVI."""

    tool: str
    target: str
    evi_score: float  # 0.0 = nothing useful, 1.0 = definitive
    summary: str = ""
    artifacts: list[str] = field(default_factory=list)


@dataclass
class Artifact:
    """An artifact produced by the agent — the only real measure of progress."""

    kind: str  # "file", "diff", "report", "commit", "test_result"
    path: str
    checksum: str = ""
    verified: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeState:
    """Compressed runtime state — what gets fed to the LLM for decision-making.

    This is designed to stay under 500 tokens after compression.
    """

    # Identity
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    # Goal
    goal: str = ""  # The original user request, summarized
    phase: TaskPhase = TaskPhase.INIT
    intent: str = ""  # The classified intent type

    # Knowledge
    confirmed_facts: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    critical_files: list[str] = field(default_factory=list)

    # Progress
    current_plan: str = ""  # Short description of current plan step
    recent_changes: list[str] = field(default_factory=list)  # last 5 changes
    next_best_action: str = ""  # What the LLM suggested as next step

    # Evidence trail — last N pieces of evidence
    evidence_log: list[ToolEvidence] = field(default_factory=list)
    max_evidence_log: int = 10

    # Artifacts
    artifacts: list[Artifact] = field(default_factory=list)

    # Budget / control
    round: int = 0
    total_tokens_used: int = 0
    low_evi_streak: int = 0  # consecutive low-evidence steps

    # Error tracking
    last_error: str = ""
    error_count: int = 0

    # Snapshot
    snapshot_id: str = ""

    # --- Derived / computed helpers ---

    @property
    def is_terminal(self) -> bool:
        return self.phase in (TaskPhase.COMPLETED, TaskPhase.FAILED, TaskPhase.CANCELLED)

    @property
    def summary(self) -> dict[str, Any]:
        """Return a dict suitable for LLM context — compressed view."""
        return {
            "goal": self.goal,
            "phase": self.phase.value,
            "intent": self.intent,
            "confirmed_facts": self.confirmed_facts[-5:],
            "open_questions": self.open_questions[:3],
            "critical_files": self.critical_files[:5],
            "recent_changes": self.recent_changes[-5:],
            "next_best_action": self.next_best_action,
            "round": self.round,
        }

    def add_evidence(self, evidence: ToolEvidence) -> None:
        self.evidence_log.append(evidence)
        if len(self.evidence_log) > self.max_evidence_log:
            self.evidence_log = self.evidence_log[-self.max_evidence_log:]

    def add_artifact(self, artifact: Artifact) -> None:
        self.artifacts.append(artifact)

    def add_fact(self, fact: str) -> None:
        if fact not in self.confirmed_facts:
            self.confirmed_facts.append(fact)

    def add_change(self, change: str) -> None:
        self.recent_changes.append(change)
        if len(self.recent_changes) > 10:
            self.recent_changes = self.recent_changes[-10:]

    def with_phase(self, phase: TaskPhase) -> RuntimeState:
        self.phase = phase
        return self

    def advance_round(self) -> None:
        self.round += 1
