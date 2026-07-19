"""Event Protocol v1 — typed schemas for all Runtime → Studio events.

Every event has:
- type: string like "task.started" (dot-separated namespace)
- timestamp: ISO 8601
- task_id: string
- payload: typed per event

Studio UI components map directly to event types:
  DecisionInspector  ← "decision.selected"
  RuntimeTimeline    ← "task.*", "phase.*"
  WorldModelViewer   ← "world.*", "fact.*"
  MemoryConsole      ← "memory.*"
  ToolExecutionPanel ← "tool.*"
  ArtifactDiffViewer ← "artifact.*"
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Lifecycle events
# ---------------------------------------------------------------------------

@dataclass
class TaskStartedEvent:
    type: str = "task.started"
    task_id: str = ""
    timestamp: str = ""
    payload: dict = field(default_factory=lambda: {
        "goal": "",
        "intent": "",
        "intent_confidence": 0.0,
    })

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = _now()
        if not self.task_id:
            self.task_id = _id()

    def to_event_bus(self):
        from forge.kernel.event_bus import Event, EventKind
        return Event(kind=EventKind.TASK_STARTED, payload=self.payload, task_id=self.task_id, timestamp=self.timestamp)


@dataclass
class TaskCompletedEvent:
    type: str = "task.completed"
    task_id: str = ""
    timestamp: str = ""
    payload: dict = field(default_factory=lambda: {
        "rounds": 0,
        "tokens_used": 0,
        "elapsed_seconds": 0.0,
        "phase": "completed",
    })

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = _now()

    def to_event_bus(self):
        from forge.kernel.event_bus import Event, EventKind
        return Event(kind=EventKind.TASK_COMPLETED, payload=self.payload, task_id=self.task_id, timestamp=self.timestamp)


@dataclass
class TaskFailedEvent:
    type: str = "task.failed"
    task_id: str = ""
    timestamp: str = ""
    payload: dict = field(default_factory=lambda: {
        "error": "",
        "rounds": 0,
        "phase": "failed",
    })

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = _now()

    def to_event_bus(self):
        from forge.kernel.event_bus import Event, EventKind
        return Event(kind=EventKind.TASK_FAILED, payload=self.payload, task_id=self.task_id, timestamp=self.timestamp)


# ---------------------------------------------------------------------------
# Intent events
# ---------------------------------------------------------------------------

@dataclass
class IntentClassifiedEvent:
    type: str = "intent.classified"
    task_id: str = ""
    timestamp: str = ""
    payload: dict = field(default_factory=lambda: {
        "intent": "",
        "confidence": 0.0,
        "reason": "",
    })

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = _now()

    def to_event_bus(self):
        from forge.kernel.event_bus import Event, EventKind
        return Event(kind=EventKind.INTENT_CLASSIFIED, payload=self.payload, task_id=self.task_id, timestamp=self.timestamp)


# ---------------------------------------------------------------------------
# Decision events
# ---------------------------------------------------------------------------

@dataclass
class DecisionSelectedEvent:
    type: str = "decision.selected"
    task_id: str = ""
    timestamp: str = ""
    payload: dict = field(default_factory=lambda: {
        "action": "",
        "reason": "",
        "confidence": 0.0,
        "evi_score": 0.0,
        "knowledge_coverage": 0.0,
        "uncertainty_entropy": 0.0,
        "alternatives": [],
    })

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = _now()

    def to_event_bus(self):
        from forge.kernel.event_bus import Event, EventKind
        return Event(kind=EventKind.ACTION_SELECTED, payload=self.payload, task_id=self.task_id, timestamp=self.timestamp)


# ---------------------------------------------------------------------------
# Tool events
# ---------------------------------------------------------------------------

@dataclass
class ToolStartedEvent:
    type: str = "tool.started"
    task_id: str = ""
    timestamp: str = ""
    payload: dict = field(default_factory=lambda: {
        "tool": "",
        "target": "",
        "params": {},
    })

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = _now()

    def to_event_bus(self):
        from forge.kernel.event_bus import Event, EventKind
        return Event(kind=EventKind.TOOL_STARTED, payload=self.payload, task_id=self.task_id, timestamp=self.timestamp)


@dataclass
class ToolCompletedEvent:
    type: str = "tool.completed"
    task_id: str = ""
    timestamp: str = ""
    payload: dict = field(default_factory=lambda: {
        "tool": "",
        "target": "",
        "evi_score": 0.0,
        "duration_ms": 0.0,
        "result_summary": "",
    })

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = _now()

    def to_event_bus(self):
        from forge.kernel.event_bus import Event, EventKind
        return Event(kind=EventKind.TOOL_COMPLETED, payload=self.payload, task_id=self.task_id, timestamp=self.timestamp)


@dataclass
class ToolFailedEvent:
    type: str = "tool.failed"
    task_id: str = ""
    timestamp: str = ""
    payload: dict = field(default_factory=lambda: {
        "tool": "",
        "target": "",
        "error": "",
    })

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = _now()

    def to_event_bus(self):
        from forge.kernel.event_bus import Event, EventKind
        return Event(kind=EventKind.TOOL_FAILED, payload=self.payload, task_id=self.task_id, timestamp=self.timestamp)


@dataclass
class ToolRejectedEvent:
    type: str = "tool.rejected"
    task_id: str = ""
    timestamp: str = ""
    payload: dict = field(default_factory=lambda: {
        "tool": "",
        "reason": "",
    })

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = _now()

    def to_event_bus(self):
        from forge.kernel.event_bus import Event, EventKind
        return Event(kind=EventKind.TOOL_REJECTED, payload=self.payload, task_id=self.task_id, timestamp=self.timestamp)


# ---------------------------------------------------------------------------
# World Model events
# ---------------------------------------------------------------------------

@dataclass
class FactConfirmedEvent:
    type: str = "fact.confirmed"
    task_id: str = ""
    timestamp: str = ""
    payload: dict = field(default_factory=lambda: {
        "fact": "",
        "source": "",
        "confidence": 1.0,
    })

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = _now()

    def to_event_bus(self):
        from forge.kernel.event_bus import Event, EventKind
        return Event(kind=EventKind.FACT_CONFIRMED, payload=self.payload, task_id=self.task_id, timestamp=self.timestamp)


@dataclass
class WorldUpdatedEvent:
    type: str = "world.updated"
    task_id: str = ""
    timestamp: str = ""
    payload: dict = field(default_factory=lambda: {
        "entity": "",
        "change_type": "",
        "details": {},
        "impact": [],
    })

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = _now()

    def to_event_bus(self):
        from forge.kernel.event_bus import Event, EventKind
        return Event(kind=EventKind.FACT_CONFIRMED, payload=self.payload, task_id=self.task_id, timestamp=self.timestamp)


# ---------------------------------------------------------------------------
# EVI events
# ---------------------------------------------------------------------------

@dataclass
class EVIEvaluatedEvent:
    type: str = "evi.evaluated"
    task_id: str = ""
    timestamp: str = ""
    payload: dict = field(default_factory=lambda: {
        "score": 0.0,
        "info_gain": 0.0,
        "progress": 0.0,
        "risk_reduction": 0.0,
        "cost": 0.0,
        "tool": "",
        "cost_effective": False,
    })

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = _now()

    def to_event_bus(self):
        from forge.kernel.event_bus import Event, EventKind
        return Event(kind=EventKind.EVI_EVALUATED, payload=self.payload, task_id=self.task_id, timestamp=self.timestamp)


# ---------------------------------------------------------------------------
# Artifact events
# ---------------------------------------------------------------------------

@dataclass
class ArtifactCreatedEvent:
    type: str = "artifact.created"
    task_id: str = ""
    timestamp: str = ""
    payload: dict = field(default_factory=lambda: {
        "id": "",
        "kind": "",
        "path": "",
        "state": "generated",
        "size": 0,
        "version": 1,
    })

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = _now()

    def to_event_bus(self):
        from forge.kernel.event_bus import Event, EventKind
        return Event(kind=EventKind.ARTIFACT_CREATED, payload=self.payload, task_id=self.task_id, timestamp=self.timestamp)


@dataclass
class ArtifactStateChangedEvent:
    type: str = "artifact.state_changed"
    task_id: str = ""
    timestamp: str = ""
    payload: dict = field(default_factory=lambda: {
        "id": "",
        "kind": "",
        "path": "",
        "from_state": "",
        "to_state": "",
        "version": 1,
    })

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = _now()

    def to_event_bus(self):
        from forge.kernel.event_bus import Event, EventKind
        return Event(kind=EventKind.ARTIFACT_CREATED, payload=self.payload, task_id=self.task_id, timestamp=self.timestamp)


# ---------------------------------------------------------------------------
# Phase events
# ---------------------------------------------------------------------------

@dataclass
class PhaseChangedEvent:
    type: str = "phase.changed"
    task_id: str = ""
    timestamp: str = ""
    payload: dict = field(default_factory=lambda: {
        "from": "",
        "to": "",
    })

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = _now()

    def to_event_bus(self):
        from forge.kernel.event_bus import Event, EventKind
        return Event(kind=EventKind.PHASE_CHANGED, payload=self.payload, task_id=self.task_id, timestamp=self.timestamp)


# ---------------------------------------------------------------------------
# Error / Budget events
# ---------------------------------------------------------------------------

@dataclass
class ErrorEvent:
    type: str = "error"
    task_id: str = ""
    timestamp: str = ""
    payload: dict = field(default_factory=lambda: {
        "error": "",
        "source": "",
        "recoverable": False,
    })

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = _now()

    def to_event_bus(self):
        from forge.kernel.event_bus import Event, EventKind
        return Event(kind=EventKind.ERROR, payload=self.payload, task_id=self.task_id, timestamp=self.timestamp)


@dataclass
class BudgetWarningEvent:
    type: str = "budget.warning"
    task_id: str = ""
    timestamp: str = ""
    payload: dict = field(default_factory=lambda: {
        "dimension": "",
        "used": 0,
        "limit": 0,
        "pct": 0.0,
    })

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = _now()

    def to_event_bus(self):
        from forge.kernel.event_bus import Event, EventKind
        return Event(kind=EventKind.BUDGET_WARNING, payload=self.payload, task_id=self.task_id, timestamp=self.timestamp)


@dataclass
class BudgetExhaustedEvent:
    type: str = "budget.exhausted"
    task_id: str = ""
    timestamp: str = ""
    payload: dict = field(default_factory=lambda: {
        "dimension": "",
        "used": 0,
        "limit": 0,
    })

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = _now()

    def to_event_bus(self):
        from forge.kernel.event_bus import Event, EventKind
        return Event(kind=EventKind.BUDGET_EXHAUSTED, payload=self.payload, task_id=self.task_id, timestamp=self.timestamp)
