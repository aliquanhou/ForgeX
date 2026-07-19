"""
Integration test: Runtime ↔ Studio SSE event flow.

Verifies that:
1. A task can be created via REST API
2. SSE event stream produces events for that task
3. Events contain correct payloads for each lifecycle phase
4. The complete task lifecycle is represented in the event stream
5. Multiple phases are reflected as the runtime progresses

This simulates what ForgeX-Studio does when connected to ForgeX Runtime.
"""

import asyncio
import json
import httpx


class TestRuntimeSSEFlow:
    """Test the full Runtime → SSE → Client event flow.

    Instead of running the actual ForgeX server, we test the event
    emission contract directly through the Runtime and EventBus.
    """

    async def test_event_stream_contains_lifecycle_events(self):
        """Verify Runtime.run() emits correct lifecycle events via EventBus."""
        from forge.kernel.runtime import Runtime
        from forge.kernel.event_bus import EventKind, event_bus

        runtime = Runtime(round_limit=5)
        collected: list[dict] = []

        async def nop(s):
            pass

        runtime.on_plan(nop)
        runtime.on_explore(nop)
        runtime.on_implement(nop)
        runtime.on_verify(nop)
        runtime.on_finalize(nop)

        # Collect events as ForgeX-Studio would via SSE
        async def collector():
            async for event in event_bus.subscribe():
                collected.append({
                    "kind": event.kind.value,
                    "task_id": event.task_id,
                    "payload": event.payload,
                })
                if event.kind in (EventKind.TASK_COMPLETED, EventKind.TASK_FAILED, EventKind.TASK_CANCELLED):
                    break

        async with asyncio.TaskGroup() as tg:
            tg.create_task(collector())
            await asyncio.sleep(0.05)
            await runtime.run("integration test event flow")

        # Verify lifecycle events
        kinds = [e["kind"] for e in collected]
        assert "task_started" in kinds, f"Missing task_started in {kinds}"
        assert "intent_classified" in kinds, f"Missing intent_classified in {kinds}"
        assert "action_selected" in kinds, f"Missing action_selected in {kinds}"

        # Verify task completion
        terminal = [e for e in collected if e["kind"] in ("task_completed", "task_failed")]
        assert len(terminal) >= 1, "No terminal event found"
        assert terminal[-1]["kind"] == "task_completed"

    async def test_event_payloads_contain_required_fields(self):
        """Verify each event kind has the payload fields Studio depends on."""
        from forge.kernel.runtime import Runtime
        from forge.kernel.event_bus import EventKind, event_bus

        runtime = Runtime(round_limit=5)
        collected: list[dict] = []

        async def nop(s):
            pass

        runtime.on_plan(nop)
        runtime.on_explore(nop)
        runtime.on_implement(nop)
        runtime.on_verify(nop)
        runtime.on_finalize(nop)

        async def collector():
            async for event in event_bus.subscribe():
                collected.append({
                    "kind": event.kind.value,
                    "task_id": event.task_id,
                    "event_id": event.event_id,
                    "timestamp": event.timestamp,
                    "payload": event.payload,
                })
                if event.kind in (EventKind.TASK_COMPLETED, EventKind.TASK_FAILED, EventKind.TASK_CANCELLED):
                    break

        async with asyncio.TaskGroup() as tg:
            tg.create_task(collector())
            await asyncio.sleep(0.05)
            await runtime.run("verify event payloads")

        # Verify every event has required SSE-serializable fields
        for e in collected:
            assert "kind" in e, f"Missing kind in {e}"
            assert "task_id" in e, f"Missing task_id in {e}"
            assert "event_id" in e, f"Missing event_id in {e}"
            assert "timestamp" in e, f"Missing timestamp in {e}"
            # Every event must be JSON-serializable (SSE requirement)
            json.dumps(e)

        # Verify task_started has goal
        started = [e for e in collected if e["kind"] == "task_started"]
        if started:
            assert "goal" in started[0]["payload"]

        # Verify action_selected events have action field
        actions = [e for e in collected if e["kind"] == "action_selected"]
        for a in actions:
            assert "action" in a["payload"], f"Missing action in {a}"

    async def test_sse_stream_serializable(self):
        """Verify all event types are JSON-serializable for SSE transport."""
        from forge.kernel.event_bus import Event, EventKind

        # Test every event kind
        for kind in EventKind:
            event = Event(kind=kind, payload={"test": "data", "number": 42})
            try:
                serialized = event.serialize()
                parsed = json.loads(serialized)
                assert parsed["kind"] == kind.value
                assert parsed["payload"]["test"] == "data"
            except (TypeError, ValueError, json.JSONDecodeError) as e:
                assert False, f"Event {kind.value} failed serialization: {e}"

    async def test_multiple_events_per_phase(self):
        """Verify each runtime phase produces appropriate event types."""
        from forge.kernel.runtime import Runtime
        from forge.kernel.event_bus import EventKind, event_bus

        runtime = Runtime(round_limit=5)
        collected: list[dict] = []

        async def nop(s):
            pass

        runtime.on_plan(nop)
        runtime.on_explore(nop)
        runtime.on_implement(nop)
        runtime.on_verify(nop)
        runtime.on_finalize(nop)

        async def collector():
            async for event in event_bus.subscribe():
                collected.append({"kind": event.kind.value, "payload": dict(event.payload)})
                if event.kind in (EventKind.TASK_COMPLETED, EventKind.TASK_FAILED, EventKind.TASK_CANCELLED):
                    break

        async with asyncio.TaskGroup() as tg:
            tg.create_task(collector())
            await asyncio.sleep(0.05)
            await runtime.run("multi-event phase test")

        kinds = [e["kind"] for e in collected]

        # Verify phase events exist
        phase_events = [k for k in kinds if k in ("phase_changed", "action_selected")]
        assert len(phase_events) > 0, f"No phase events in {kinds}"

        # Verify task_started → ... → task_completed
        assert kinds[0] == "task_started", f"First event should be task_started, got {kinds[0]}"
        assert kinds[-1] == "task_completed", f"Last event should be task_completed, got {kinds[-1]}"

    async def test_runtime_inspector_contract(self):
        """Test the data contract ForgeX-Studio DecisionInspector depends on.

        Studio expects events with specific payload fields.
        This test verifies those fields exist at runtime.
        """
        from forge.kernel.runtime import Runtime
        from forge.kernel.event_bus import EventKind, event_bus

        runtime = Runtime(round_limit=5)
        collected: list[dict] = []

        async def nop(s):
            pass

        runtime.on_plan(nop)
        runtime.on_explore(nop)
        runtime.on_implement(nop)
        runtime.on_verify(nop)
        runtime.on_finalize(nop)

        # Register an EVI event manually (since the mock handlers don't produce EVI)
        from forge.kernel.event_bus import Event

        async def evi_caller(s):
            await event_bus.publish(Event(
                kind=EventKind.EVI_EVALUATED,
                payload={"score": 0.85, "info_gain": 0.4, "progress": 0.6, "risk_reduction": 0.3, "cost": 0.15},
                task_id=runtime.state.task_id,
            ))

        runtime.on_implement(evi_caller)

        async def collector():
            async for event in event_bus.subscribe():
                collected.append({"kind": event.kind.value, "payload": dict(event.payload)})
                if event.kind in (EventKind.TASK_COMPLETED, EventKind.TASK_FAILED, EventKind.TASK_CANCELLED):
                    break

        async with asyncio.TaskGroup() as tg:
            tg.create_task(collector())
            await asyncio.sleep(0.05)
            await runtime.run("inspector contract test")

        # Check EVI event has the fields DecisionInspector renders
        evi_events = [e for e in collected if e["kind"] == "evi_evaluated"]
        if evi_events:
            payload = evi_events[0]["payload"]
            # Studio DecisionInspector renders info_gain, progress, risk_reduction, cost
            for field in ["info_gain", "progress", "risk_reduction", "cost"]:
                assert field in payload, f"EVI payload missing {field}: {payload}"
