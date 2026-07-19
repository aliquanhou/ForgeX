"""Procedural Memory — success patterns and reusable templates.

Stores:
- Successful operation sequences ("when you need to do X, do Y then Z")
- Common fix patterns ("error E → fix F")
- Parameterized templates for recurring tasks

Built from successful episodes and verified by the verifier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass
class ProcedureStep:
    """A single step in a procedure."""
    action: str
    target: str
    params: dict[str, Any] = field(default_factory=dict)
    notes: str = ""


@dataclass
class Procedure:
    """A reusable procedure for a common task pattern."""

    id: str
    name: str
    description: str
    trigger_pattern: str  # e.g., "implement new API endpoint"
    steps: list[ProcedureStep] = field(default_factory=list)
    expected_outcome: str = ""
    prerequisites: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    success_count: int = 0
    fail_count: int = 0
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    @property
    def confidence(self) -> float:
        total = self.success_count + self.fail_count
        if total == 0:
            return 0.5
        return self.success_count / total


@dataclass
class ProcedurePattern:
    """A reusable fix pattern — "error X → do Y"."""

    error_pattern: str  # regex or keyword pattern
    fix_action: str
    fix_target: str
    success_rate: float = 0.0
    times_used: int = 0


class ProceduralMemory:
    """Library of reusable procedures and fix patterns.

    Enables the agent to recognize common situations and apply known solutions.
    """

    def __init__(self) -> None:
        self._procedures: dict[str, Procedure] = {}
        self._patterns: list[ProcedurePattern] = []

    def add_procedure(self, procedure: Procedure) -> None:
        """Store a procedure."""
        self._procedures[procedure.id] = procedure

    def find_procedure(self, goal: str, intent: str = "") -> Procedure | None:
        """Find a matching procedure by goal or intent keywords."""
        goal_lower = goal.lower()
        best_match: tuple[float, Procedure] = (0.0, None)

        for proc in self._procedures.values():
            score = 0.0
            # Match trigger pattern
            trigger_words = proc.trigger_pattern.lower().split()
            matches = sum(1 for w in trigger_words if w in goal_lower)
            score += matches / max(len(trigger_words), 1) * 0.6

            # Match tags
            tag_matches = sum(1 for t in proc.tags if t.lower() in goal_lower)
            score += tag_matches * 0.1

            # Confidence bonus
            score += proc.confidence * 0.2

            if score > best_match[0]:
                best_match = (score, proc)

        return best_match[1] if best_match[0] > 0.3 else None

    def record_success(self, procedure_id: str) -> None:
        proc = self._procedures.get(procedure_id)
        if proc:
            proc.success_count += 1

    def record_failure(self, procedure_id: str) -> None:
        proc = self._procedures.get(procedure_id)
        if proc:
            proc.fail_count += 1

    def add_pattern(self, pattern: ProcedurePattern) -> None:
        """Add or update a fix pattern."""
        # Check if pattern already exists
        for i, existing in enumerate(self._patterns):
            if existing.error_pattern == pattern.error_pattern:
                self._patterns[i] = pattern
                return
        self._patterns.append(pattern)

    def find_pattern(self, error_text: str) -> ProcedurePattern | None:
        """Find a fix pattern matching the error."""
        error_lower = error_text.lower()
        best_match: tuple[float, ProcedurePattern] = (0.0, None)

        for pattern in self._patterns:
            if pattern.error_pattern.lower() in error_lower:
                score = pattern.success_rate * pattern.times_used / max(pattern.times_used, 1)
                if score > best_match[0]:
                    best_match = (score, pattern)

        return best_match[1] if best_match[0] > 0 else None

    def learn_from_episode(
        self,
        goal: str,
        steps: list[tuple[str, str]],
        success: bool,
    ) -> Procedure | None:
        """Create a procedure from a successful episode."""
        if not success:
            return None
        if not steps:
            return None

        procedure = Procedure(
            id=uuid.uuid4().hex[:12],
            name=f"Procedure from: {goal[:50]}",
            description=f"Learned from successful task: {goal}",
            trigger_pattern=goal[:100],
            steps=[
                ProcedureStep(action=action, target=target)
                for action, target in steps[:10]
            ],
            success_count=1,
            tags=[goal.split()[0].lower()] if goal.split() else [],
        )
        self.add_procedure(procedure)
        return procedure

    @property
    def procedure_count(self) -> int:
        return len(self._procedures)

    @property
    def pattern_count(self) -> int:
        return len(self._patterns)

    def summary(self) -> dict[str, Any]:
        return {
            "procedures": self.procedure_count,
            "patterns": self.pattern_count,
            "top_patterns": [p.error_pattern for p in self._patterns[:3]],
        }
