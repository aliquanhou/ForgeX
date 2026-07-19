"""Tests for Forge kernel modules."""

import asyncio


class TestRuntimeState:
    """RuntimeState is the central data structure."""

    def test_create_state(self):
        from forge.kernel.state import RuntimeState, TaskPhase

        state = RuntimeState()
        assert state.task_id
        assert state.phase == TaskPhase.INIT
        assert state.round == 0
        assert state.confirmed_facts == []

    def test_add_fact(self):
        from forge.kernel.state import RuntimeState

        state = RuntimeState()
        state.add_fact("The sky is blue")
        assert "The sky is blue" in state.confirmed_facts

    def test_dedup_facts(self):
        from forge.kernel.state import RuntimeState

        state = RuntimeState()
        state.add_fact("fact")
        state.add_fact("fact")
        assert len(state.confirmed_facts) == 1

    def test_phase_transitions(self):
        from forge.kernel.state import RuntimeState, TaskPhase

        state = RuntimeState()
        state.phase = TaskPhase.PLANNING
        assert state.phase == TaskPhase.PLANNING
        assert not state.is_terminal

        state.phase = TaskPhase.COMPLETED
        assert state.is_terminal

    def test_summary_contains_key_fields(self):
        from forge.kernel.state import RuntimeState

        state = RuntimeState()
        state.goal = "test goal"
        s = state.summary
        assert s["goal"] == "test goal"
        assert "phase" in s
        assert "round" in s
        assert "confirmed_facts" in s


class TestIntentClassifier:
    """IntentClassifier determines what the user wants."""

    def test_classify_code_modify(self):
        from forge.kernel.intent import IntentClassifier, IntentType

        c = IntentClassifier()
        r = c.classify("implement a new feature in app.py")
        assert r.intent == IntentType.CODE_MODIFY
        assert r.confidence > 0.4

    def test_classify_debug(self):
        from forge.kernel.intent import IntentClassifier, IntentType

        c = IntentClassifier()
        r = c.classify("fix the bug where the app crashes on startup")
        assert r.intent == IntentType.DEBUG

    def test_classify_chat(self):
        from forge.kernel.intent import IntentClassifier, IntentType

        c = IntentClassifier()
        r = c.classify("what do you think about the weather?")
        assert r.intent == IntentType.CHAT

    def test_classify_research(self):
        from forge.kernel.intent import IntentClassifier, IntentType

        c = IntentClassifier()
        r = c.classify("understand how the authentication system works")
        assert r.intent == IntentType.RESEARCH

    def test_requires_code(self):
        from forge.kernel.intent import IntentType, IntentResult

        r = IntentResult(intent=IntentType.CODE_MODIFY, confidence=0.9)
        assert r.requires_code

        r = IntentResult(intent=IntentType.CHAT, confidence=0.9)
        assert not r.requires_code


class TestBudgetManager:
    """BudgetManager tracks and enforces resource limits."""

    def test_budget_starts_empty(self):
        from forge.kernel.budget import BudgetManager, BudgetKind

        b = BudgetManager()
        assert not b.is_exhausted
        assert b.get_state(BudgetKind.ROUNDS).used == 0

    def test_rounds_exhausted(self):
        from forge.kernel.budget import BudgetManager

        b = BudgetManager(round_limit=3)
        for _ in range(3):
            b.consume_round()
        assert b.is_exhausted

    def test_summary(self):
        from forge.kernel.budget import BudgetManager

        b = BudgetManager(token_limit=1000)
        b.consume_tokens(500)
        s = b.summary
        assert s["tokens"]["remaining"] == 500
        assert s["tokens"]["pct"] == 0.5

    def test_check_warnings(self):
        from forge.kernel.budget import BudgetManager

        b = BudgetManager(token_limit=100, round_limit=100)
        b.consume_tokens(90)
        warnings = b.check_warnings()
        assert len(warnings) > 0


class TestEventBus:
    """EventBus provides async pub/sub."""

    async def test_publish_subscribe(self):
        from forge.kernel.event_bus import EventBus, Event, EventKind

        bus = EventBus()
        received = []

        async def consumer():
            async for event in bus.subscribe():
                received.append(event.kind.value)
                if event.kind == EventKind.TASK_COMPLETED:
                    break

        async def producer():
            await bus.publish(Event(kind=EventKind.LOG))
            await bus.publish(Event(kind=EventKind.TASK_STARTED))
            await bus.publish(Event(kind=EventKind.TASK_COMPLETED))

        async with asyncio.TaskGroup() as tg:
            tg.create_task(consumer())
            await asyncio.sleep(0.05)
            tg.create_task(producer())

        assert len(received) == 3
        assert received[0] == "log"
        assert received[-1] == "task_completed"

    def test_event_serialization(self):
        from forge.kernel.event_bus import Event, EventKind

        e = Event(kind=EventKind.TASK_STARTED, payload={"key": "val"})
        s = e.serialize()
        assert '"kind": "task_started"' in s
        assert '"key": "val"' in s
        assert '"event_id"' in s


class TestScheduler:
    """Scheduler decides what action to take."""

    async def test_init_phase_plans(self):
        from forge.kernel.scheduler import Scheduler, ScheduleAction

        s = Scheduler()
        d = await s.decide({"phase": "init"})
        assert d.action == ScheduleAction.PLAN

    async def test_planning_phase_explores(self):
        from forge.kernel.scheduler import Scheduler, ScheduleAction

        s = Scheduler()
        d = await s.decide({"phase": "planning"})
        assert d.action == ScheduleAction.EXPLORE

    async def test_completed_stops(self):
        from forge.kernel.scheduler import Scheduler, ScheduleAction

        s = Scheduler()
        d = await s.decide({"phase": "completed"})
        assert d.action == ScheduleAction.STOP


class TestRuntime:
    """Runtime integration — the main loop."""

    async def test_runtime_loop_completes(self):
        from forge.kernel.runtime import Runtime

        runtime = Runtime(round_limit=10)

        calls = []

        async def plan_handler(state):
            calls.append("plan")

        async def explore_handler(state):
            calls.append("explore")

        async def implement_handler(state):
            calls.append("implement")

        async def verify_handler(state):
            calls.append("verify")

        async def finalize_handler(state):
            calls.append("finalize")

        runtime.on_plan(plan_handler)
        runtime.on_explore(explore_handler)
        runtime.on_implement(implement_handler)
        runtime.on_verify(verify_handler)
        runtime.on_finalize(finalize_handler)

        result = await runtime.run("integration test")

        assert result.success
        assert result.phase.name == "COMPLETED"
        assert result.rounds > 0
        assert len(calls) == 5
        assert calls == ["plan", "explore", "implement", "verify", "finalize"]
