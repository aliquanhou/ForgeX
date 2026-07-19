"""Event Bus — real-time progress streaming via async pub/sub.

Every significant step in the runtime loop produces an Event.
Clients consume these via SSE or WebSocket for live progress.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator


class EventKind(str, Enum):
    """Every event kind the system can emit."""

    # Lifecycle
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"

    # Phase transitions
    PHASE_CHANGED = "phase_changed"

    # Decisions
    INTENT_CLASSIFIED = "intent_classified"
    INTENT_DETECTED = "intent_detected"
    PLAN_CREATED = "plan_created"
    ACTION_SELECTED = "action_selected"

    # Tool execution
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    TOOL_REJECTED = "tool_rejected"

    # State
    STATE_COMPRESSED = "state_compressed"
    FACT_CONFIRMED = "fact_confirmed"
    EVI_EVALUATED = "evi_evaluated"

    # Verification
    VERIFY_STARTED = "verify_started"
    VERIFY_COMPLETED = "verify_completed"
    VERIFY_FAILED = "verify_failed"

    # Artifact
    ARTIFACT_CREATED = "artifact_created"

    # User interaction
    ASK_APPROVAL = "ask_approval"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"

    # Budget / control
    BUDGET_WARNING = "budget_warning"
    BUDGET_EXHAUSTED = "budget_exhausted"
    FORCE_FINALIZE = "force_finalize"

    # Runtime control (v0.3.3 Autonomous Control Layer)
    RUNTIME_PAUSED = "runtime_paused"
    RUNTIME_RESUMED = "runtime_resumed"
    HUMAN_OVERRIDE_STARTED = "human_override_started"
    HUMAN_OVERRIDE_ENDED = "human_override_ended"
    ROLLBACK_COMPLETED = "rollback_completed"
    RUNTIME_STOPPED = "runtime_stopped"
    MODE_CHANGED = "mode_changed"

    # Log
    LOG = "log"
    ERROR = "error"


@dataclass
class Event:
    """A single event emitted by the system."""

    kind: EventKind
    payload: dict[str, Any] = field(default_factory=dict)
    task_id: str = ""
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def serialize(self) -> str:
        data = asdict(self)
        data["kind"] = data["kind"].value
        return json.dumps(data, default=str)


class EventBus:
    """Async pub/sub event bus using asyncio.Queue.

    Producers call publish(). Consumers call subscribe() to get an async iterator.
    Each subscriber gets its own queue; events are broadcast to all.
    """

    def __init__(self, maxsize: int = 256) -> None:
        self._maxsize = maxsize
        self._subscribers: set[asyncio.Queue[Event]] = set()

    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        dead: list[asyncio.Queue[Event]] = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.discard(q)

    def subscribe(self) -> AsyncIterator[Event]:
        """Return an async iterator over all future events."""

        async def _iterate() -> AsyncIterator[Event]:
            q: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._maxsize)
            self._subscribers.add(q)
            try:
                while True:
                    try:
                        event = await q.get()
                    except asyncio.CancelledError:
                        break
                    yield event
                    q.task_done()
                    if event.kind in (
                        EventKind.TASK_COMPLETED,
                        EventKind.TASK_FAILED,
                        EventKind.TASK_CANCELLED,
                    ):
                        break
            finally:
                self._subscribers.discard(q)

        return _iterate()

    async def aclose(self) -> None:
        """Close the event bus."""
        self._subscribers.clear()


# Global event bus singleton
event_bus = EventBus()
