"""Tests for the Event Protocol v1 — schema validation and serialization."""

import json


class TestEventProtocol:
    """Validate every event type in the protocol layer."""

    EVENT_TYPES = [
        "task.started", "task.completed", "task.failed",
        "intent.classified",
        "decision.selected",
        "tool.started", "tool.completed", "tool.failed", "tool.rejected",
        "fact.confirmed", "world.updated",
        "evi.evaluated",
        "artifact.created", "artifact.state_changed",
        "phase.changed",
        "error",
        "budget.warning", "budget.exhausted",
    ]

    def test_all_events_have_type_field(self):
        """Every event must have a 'type' field registered in EVENT_TYPES."""
        from forge.events import (
            TaskStartedEvent, TaskCompletedEvent, TaskFailedEvent,
            IntentClassifiedEvent,
            DecisionSelectedEvent,
            ToolStartedEvent, ToolCompletedEvent, ToolFailedEvent, ToolRejectedEvent,
            FactConfirmedEvent, WorldUpdatedEvent,
            EVIEvaluatedEvent,
            ArtifactCreatedEvent, ArtifactStateChangedEvent,
            PhaseChangedEvent,
            ErrorEvent,
            BudgetWarningEvent, BudgetExhaustedEvent,
        )

        instances = [
            TaskStartedEvent(), TaskCompletedEvent(), TaskFailedEvent(),
            IntentClassifiedEvent(),
            DecisionSelectedEvent(),
            ToolStartedEvent(), ToolCompletedEvent(), ToolFailedEvent(), ToolRejectedEvent(),
            FactConfirmedEvent(), WorldUpdatedEvent(),
            EVIEvaluatedEvent(),
            ArtifactCreatedEvent(), ArtifactStateChangedEvent(),
            PhaseChangedEvent(),
            ErrorEvent(),
            BudgetWarningEvent(), BudgetExhaustedEvent(),
        ]

        for inst in instances:
            assert inst.type in self.EVENT_TYPES, f"Unknown event type for {type(inst).__name__}: {inst.type}"

    def test_all_events_serializable(self):
        """Every event must be JSON-serializable (SSE requirement)."""
        from forge.events import (
            TaskStartedEvent, TaskCompletedEvent, TaskFailedEvent,
            IntentClassifiedEvent,
            DecisionSelectedEvent,
            ToolStartedEvent, ToolCompletedEvent, ToolFailedEvent, ToolRejectedEvent,
            FactConfirmedEvent, WorldUpdatedEvent,
            EVIEvaluatedEvent,
            ArtifactCreatedEvent, ArtifactStateChangedEvent,
            PhaseChangedEvent,
            ErrorEvent,
            BudgetWarningEvent, BudgetExhaustedEvent,
        )

        instances = [
            TaskStartedEvent(payload={"goal": "test", "intent": "code_modify", "intent_confidence": 0.9}),
            TaskCompletedEvent(payload={"rounds": 5, "tokens_used": 1000, "elapsed_seconds": 3.2, "phase": "completed"}),
            TaskFailedEvent(payload={"error": "timeout", "rounds": 3, "phase": "failed"}),
            IntentClassifiedEvent(payload={"intent": "code_modify", "confidence": 0.85, "reason": "keyword match"}),
            DecisionSelectedEvent(payload={"action": "read_file", "reason": "need context", "confidence": 0.8,
                                            "evi_score": 0.72, "knowledge_coverage": 0.6, "uncertainty_entropy": 0.3, "alternatives": []}),
            ToolStartedEvent(payload={"tool": "read_file", "target": "app.py", "params": {}}),
            ToolCompletedEvent(payload={"tool": "read_file", "target": "app.py", "evi_score": 0.6, "duration_ms": 45.0, "result_summary": "235 lines"}),
            ToolFailedEvent(payload={"tool": "execute", "target": "pytest", "error": "ModuleNotFoundError"}),
            ToolRejectedEvent(payload={"tool": "execute", "reason": "command not in whitelist"}),
            FactConfirmedEvent(payload={"fact": "User model in user.py", "source": "read_file", "confidence": 1.0}),
            WorldUpdatedEvent(payload={"entity": "UserModel", "change_type": "entity_added", "details": {}, "impact": []}),
            EVIEvaluatedEvent(payload={"score": 0.85, "info_gain": 0.4, "progress": 0.6, "risk_reduction": 0.3, "cost": 0.15, "tool": "read_file", "cost_effective": True}),
            ArtifactCreatedEvent(payload={"id": "a1", "kind": "file", "path": "app.py", "state": "generated", "size": 500, "version": 1}),
            ArtifactStateChangedEvent(payload={"id": "a1", "kind": "file", "path": "app.py", "from_state": "generated", "to_state": "validated", "version": 1}),
            PhaseChangedEvent(payload={"from": "exploration", "to": "implementation"}),
            ErrorEvent(payload={"error": "disk full", "source": "tool.execute", "recoverable": True}),
            BudgetWarningEvent(payload={"dimension": "tokens", "used": 85000, "limit": 100000, "pct": 0.85}),
            BudgetExhaustedEvent(payload={"dimension": "rounds", "used": 50, "limit": 50}),
        ]

        for inst in instances:
            as_dict = {
                "type": inst.type,
                "task_id": inst.task_id,
                "timestamp": inst.timestamp,
                "payload": inst.payload,
            }
            try:
                serialized = json.dumps(as_dict)
                parsed = json.loads(serialized)
                assert parsed["type"] == inst.type
            except (TypeError, ValueError, json.JSONDecodeError) as e:
                assert False, f"{type(inst).__name__} failed serialization: {e}"

    def test_event_has_task_id(self):
        """Every event must be associated with a task."""
        from forge.events import (
            TaskStartedEvent
        )
        event = TaskStartedEvent(task_id="task-001")
        assert event.task_id == "task-001"

    def test_event_to_eventbus(self):
        """Every event must be convertible to the internal EventBus Event."""
        from forge.events import (
            TaskStartedEvent, TaskCompletedEvent,
            DecisionSelectedEvent,
            ToolStartedEvent, ToolCompletedEvent,
            FactConfirmedEvent,
            ErrorEvent,
        )
        from forge.kernel.event_bus import EventKind

        events = [
            (TaskStartedEvent(task_id="t1"), EventKind.TASK_STARTED),
            (TaskCompletedEvent(task_id="t1"), EventKind.TASK_COMPLETED),
            (DecisionSelectedEvent(task_id="t1"), EventKind.ACTION_SELECTED),
            (ToolStartedEvent(task_id="t1"), EventKind.TOOL_STARTED),
            (ToolCompletedEvent(task_id="t1"), EventKind.TOOL_COMPLETED),
            (FactConfirmedEvent(task_id="t1"), EventKind.FACT_CONFIRMED),
            (ErrorEvent(task_id="t1"), EventKind.ERROR),
        ]

        for event, expected_kind in events:
            bus_event = event.to_event_bus()
            assert bus_event.kind == expected_kind
            assert bus_event.task_id == "t1"

    def test_studio_event_types_are_documented(self):
        """All event types Studio depends on must exist in the protocol."""
        # These are the mappings Studio v0.1 uses
        studio_consumes = {
            "task.started": "RuntimeTimeline renders this",
            "task.completed": "RuntimeTimeline shows completion",
            "task.failed": "RuntimeTimeline shows failure",
            "intent.classified": "DecisionInspector shows intent",
            "decision.selected": "DecisionInspector shows action + reason",
            "evi.evaluated": "DecisionInspector shows EVI metrics",
            "tool.started": "ToolExecutionPanel shows running tool",
            "tool.completed": "ToolExecutionPanel shows result",
            "tool.failed": "ToolExecutionPanel shows error",
            "fact.confirmed": "WorldModelViewer shows facts",
            "artifact.created": "ArtifactDiffViewer shows pipeline",
            "phase.changed": "RuntimeTimeline shows phase transition",
            "error": "All panels show error state",
        }

        from forge.events import (
            TaskStartedEvent, TaskCompletedEvent, TaskFailedEvent,
            IntentClassifiedEvent,
            DecisionSelectedEvent,
            EVIEvaluatedEvent,
            ToolStartedEvent, ToolCompletedEvent, ToolFailedEvent,
            FactConfirmedEvent,
            ArtifactCreatedEvent,
            PhaseChangedEvent,
            ErrorEvent,
        )

        available = {
            "task.started": TaskStartedEvent,
            "task.completed": TaskCompletedEvent,
            "task.failed": TaskFailedEvent,
            "intent.classified": IntentClassifiedEvent,
            "decision.selected": DecisionSelectedEvent,
            "evi.evaluated": EVIEvaluatedEvent,
            "tool.started": ToolStartedEvent,
            "tool.completed": ToolCompletedEvent,
            "tool.failed": ToolFailedEvent,
            "fact.confirmed": FactConfirmedEvent,
            "artifact.created": ArtifactCreatedEvent,
            "phase.changed": PhaseChangedEvent,
            "error": ErrorEvent,
        }

        for event_type, purpose in studio_consumes.items():
            assert event_type in available, f"Studio needs {event_type} ({purpose}) but it's not in the protocol"
            assert available[event_type] is not None

        # All 13 event types Studio v0.1 depends on are present
        assert len(studio_consumes) == len(available) == 13
