"""Event Demo — replay a full task lifecycle for ForgeX-Studio testing.

Simulates all 18 event types from the Event Protocol v1,
replaying them through the EventBus so Studio receives them via SSE.

Usage:
    # Start ForgeX Runtime in one terminal:
    python -m forge.main

    # In another terminal, replay the demo:
    python -m forge.demo.event_demo

    # Studio at http://localhost:5173 will show the full timeline.
"""

import asyncio
import time

from forge.events.protocol import (
    TaskStartedEvent,
    IntentClassifiedEvent,
    DecisionSelectedEvent,
    PhaseChangedEvent,
    ToolStartedEvent,
    ToolCompletedEvent,
    FactConfirmedEvent,
    EVIEvaluatedEvent,
    ArtifactCreatedEvent,
    ArtifactStateChangedEvent,
    TaskCompletedEvent,
)


async def replay_demo(task_id: str = "demo-001", goal: str = "Analyze project plugin system"):
    """Replay a realistic task lifecycle through the EventBus.

    Studio panels will update in real-time as events fire.
    """
    from forge.kernel.event_bus import event_bus

    print(f"  [demo] Starting replay: '{goal}' (task={task_id})")
    print(f"  [demo] Open ForgeX-Studio at http://localhost:5173 to watch\n")

    # ── Phase 1: Task Start ──────────────────────────────────
    await event_bus.publish(TaskStartedEvent(
        task_id=task_id,
        payload={"goal": goal, "intent": "research", "intent_confidence": 0.92},
    ).to_event_bus())
    print("  task.started")
    await asyncio.sleep(0.8)

    await event_bus.publish(IntentClassifiedEvent(
        task_id=task_id,
        payload={"intent": "research", "confidence": 0.92, "reason": "Keyword 'analyze' detected"},
    ).to_event_bus())
    print("  intent.classified → research (0.92)")
    await asyncio.sleep(0.5)

    # ── Phase 2: Planning ────────────────────────────────────
    await event_bus.publish(PhaseChangedEvent(
        task_id=task_id,
        payload={"from": "init", "to": "planning"},
    ).to_event_bus())
    print("  phase.changed: init → planning")
    await asyncio.sleep(0.3)

    await event_bus.publish(DecisionSelectedEvent(
        task_id=task_id,
        payload={
            "action": "search_symbol",
            "reason": "Need to find plugin entry point in codebase",
            "confidence": 0.88,
            "evi_score": 0.72,
            "knowledge_coverage": 0.15,
            "uncertainty_entropy": 0.68,
            "alternatives": ["read_file", "grep"],
        },
    ).to_event_bus())
    print("  decision.selected → search_symbol")
    await asyncio.sleep(0.4)

    # ── Phase 3: Exploration ─────────────────────────────────
    await event_bus.publish(PhaseChangedEvent(
        task_id=task_id,
        payload={"from": "planning", "to": "exploration"},
    ).to_event_bus())
    print("  phase.changed: planning → exploration")
    await asyncio.sleep(0.3)

    # Tool: grep
    await event_bus.publish(ToolStartedEvent(
        task_id=task_id,
        payload={"tool": "grep", "target": "\"class.*Plugin\"", "params": {"pattern": "class.*Plugin", "path": "."}},
    ).to_event_bus())
    print("  tool.started → grep 'class.*Plugin'")
    await asyncio.sleep(0.6)

    await event_bus.publish(ToolCompletedEvent(
        task_id=task_id,
        payload={"tool": "grep", "target": "\"class.*Plugin\"", "evi_score": 0.65, "duration_ms": 320.0, "result_summary": "3 matches found"},
    ).to_event_bus())
    print("  tool.completed → 3 matches")
    await asyncio.sleep(0.3)

    # EVI
    await event_bus.publish(EVIEvaluatedEvent(
        task_id=task_id,
        payload={"score": 0.65, "info_gain": 0.5, "progress": 0.4, "risk_reduction": 0.2, "cost": 0.15, "tool": "grep", "cost_effective": True},
    ).to_event_bus())
    print("  evi.evaluated → 0.65")

    # Tool: find_symbol
    await event_bus.publish(ToolStartedEvent(
        task_id=task_id,
        payload={"tool": "find_symbol", "target": "PluginManager", "params": {"name": "PluginManager", "path": "."}},
    ).to_event_bus())
    print("  tool.started → find_symbol 'PluginManager'")
    await asyncio.sleep(0.5)

    await event_bus.publish(ToolCompletedEvent(
        task_id=task_id,
        payload={"tool": "find_symbol", "target": "PluginManager", "evi_score": 0.91, "duration_ms": 150.0, "result_summary": "Found in plugin_manager.py:42"},
    ).to_event_bus())
    print("  tool.completed → plugin_manager.py:42")
    await asyncio.sleep(0.3)

    # World model update
    await event_bus.publish(FactConfirmedEvent(
        task_id=task_id,
        payload={"fact": "PluginManager class defined in plugin_manager.py line 42", "source": "find_symbol", "confidence": 1.0},
    ).to_event_bus())
    print("  fact.confirmed → PluginManager@plugin_manager.py:42")
    await asyncio.sleep(0.3)

    await event_bus.publish(EVIEvaluatedEvent(
        task_id=task_id,
        payload={"score": 0.91, "info_gain": 0.8, "progress": 0.6, "risk_reduction": 0.5, "cost": 0.08, "tool": "find_symbol", "cost_effective": True},
    ).to_event_bus())
    print("  evi.evaluated → 0.91")

    # ── Phase 4: Deep Read ───────────────────────────────────
    await event_bus.publish(DecisionSelectedEvent(
        task_id=task_id,
        payload={
            "action": "deep_read",
            "reason": "PluginManager found — read its implementation to understand lifecycle",
            "confidence": 0.85,
            "evi_score": 0.82,
            "knowledge_coverage": 0.35,
            "uncertainty_entropy": 0.45,
            "alternatives": [],
        },
    ).to_event_bus())
    print("  decision.selected → deep_read")
    await asyncio.sleep(0.3)

    await event_bus.publish(ToolStartedEvent(
        task_id=task_id,
        payload={"tool": "read_file", "target": "plugin_manager.py", "params": {"path": "plugin_manager.py"}},
    ).to_event_bus())
    print("  tool.started → read_file 'plugin_manager.py'")
    await asyncio.sleep(0.7)

    await event_bus.publish(ToolCompletedEvent(
        task_id=task_id,
        payload={"tool": "read_file", "target": "plugin_manager.py", "evi_score": 0.78, "duration_ms": 45.0, "result_summary": "342 lines read"},
    ).to_event_bus())
    print("  tool.completed → 342 lines")
    await asyncio.sleep(0.3)

    # More facts
    await event_bus.publish(FactConfirmedEvent(
        task_id=task_id,
        payload={"fact": "PluginManager has methods: load_plugin, unload_plugin, reload_plugin", "source": "read_file", "confidence": 1.0},
    ).to_event_bus())
    print("  fact.confirmed → PluginManager methods discovered")

    await event_bus.publish(FactConfirmedEvent(
        task_id=task_id,
        payload={"fact": "Plugin lifecycle: register → validate → load → init → ready", "source": "read_file", "confidence": 0.9},
    ).to_event_bus())
    print("  fact.confirmed → Plugin lifecycle documented")

    await event_bus.publish(EVIEvaluatedEvent(
        task_id=task_id,
        payload={"score": 0.78, "info_gain": 0.6, "progress": 0.5, "risk_reduction": 0.4, "cost": 0.05, "tool": "read_file", "cost_effective": True},
    ).to_event_bus())
    print("  evi.evaluated → 0.78")
    await asyncio.sleep(0.4)

    # ── Phase 5: Generate Report ─────────────────────────────
    await event_bus.publish(DecisionSelectedEvent(
        task_id=task_id,
        payload={
            "action": "finalize",
            "reason": "Sufficient information gathered, generating report",
            "confidence": 0.92,
            "evi_score": 0.85,
            "knowledge_coverage": 0.82,
            "uncertainty_entropy": 0.12,
            "alternatives": [],
        },
    ).to_event_bus())
    print("  decision.selected → finalize")
    await asyncio.sleep(0.4)

    # Phase
    await event_bus.publish(PhaseChangedEvent(
        task_id=task_id,
        payload={"from": "exploration", "to": "finalizing"},
    ).to_event_bus())
    print("  phase.changed: exploration → finalizing")

    # Artifact created
    await event_bus.publish(ArtifactCreatedEvent(
        task_id=task_id,
        payload={
            "id": "artifact-001",
            "kind": "report",
            "path": "analysis/plugin-system-report.md",
            "state": "generated",
            "size": 2450,
            "version": 1,
        },
    ).to_event_bus())
    print("  artifact.created → analysis/plugin-system-report.md")
    await asyncio.sleep(0.3)

    await event_bus.publish(ArtifactStateChangedEvent(
        task_id=task_id,
        payload={
            "id": "artifact-001",
            "kind": "report",
            "path": "analysis/plugin-system-report.md",
            "from_state": "generated",
            "to_state": "validated",
            "version": 1,
        },
    ).to_event_bus())
    print("  artifact.state_changed → validated")

    # ── Phase 6: Complete ────────────────────────────────────
    await event_bus.publish(TaskCompletedEvent(
        task_id=task_id,
        payload={
            "rounds": 7,
            "tokens_used": 4250,
            "elapsed_seconds": 4.8,
            "phase": "completed",
        },
    ).to_event_bus())
    print("  task.completed [OK]")

    print(f"\n  [demo] Replay complete — {goal}")
    print(f"  [demo] 18 events sent via EventBus → SSE → Studio\n")


if __name__ == "__main__":
    asyncio.run(replay_demo())
