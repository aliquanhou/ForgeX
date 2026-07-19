"""Plan types — structured representation of a task plan."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PlanStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    SUPERSEDED = "superseded"


@dataclass
class PlanPhase:
    """A single phase within a plan."""

    name: str  # exploration, implementation, verification, etc.
    steps: list[str] = field(default_factory=list)
    files_to_read: list[str] = field(default_factory=list)
    files_to_modify: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    completed: bool = False


@dataclass
class Plan:
    """A complete high-level plan for a task."""

    goal: str
    phases: list[PlanPhase] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    estimated_rounds: int = 5
    status: PlanStatus = PlanStatus.DRAFT

    @property
    def current_phase(self) -> PlanPhase | None:
        """Return the first incomplete phase, or None if all done."""
        for phase in self.phases:
            if not phase.completed:
                return phase
        return None

    @property
    def progress(self) -> float:
        """Return progress as 0.0-1.0."""
        if not self.phases:
            return 0.0
        return sum(1 for p in self.phases if p.completed) / len(self.phases)

    @property
    def summary(self) -> dict[str, Any]:
        current = self.current_phase
        return {
            "goal": self.goal,
            "total_phases": len(self.phases),
            "completed_phases": sum(1 for p in self.phases if p.completed),
            "current_phase": current.name if current else "all_done",
            "risks": self.risks,
            "progress": self.progress,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Plan:
        """Create a Plan from a dict (e.g. from LLM JSON output)."""
        phases = []
        for pdata in data.get("phases", []):
            phases.append(PlanPhase(
                name=pdata.get("name", "unknown"),
                steps=pdata.get("steps", []),
                files_to_read=pdata.get("files_to_read", []),
                files_to_modify=pdata.get("files_to_modify", []),
                success_criteria=pdata.get("success_criteria", []),
            ))
        return cls(
            goal=data.get("goal", ""),
            phases=phases,
            risks=data.get("risks", []),
            estimated_rounds=data.get("estimated_rounds", 5),
        )
