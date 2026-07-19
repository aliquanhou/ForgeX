"""Runtime — the main orchestrator that drives the entire agent loop.

This is the "while not completed" loop from the architecture.
It owns the state, budget, event bus, scheduler, and delegates to planner/verifier/tools.

LLM 不是大脑，Runtime 才是大脑。
"""

from __future__ import annotations

import asyncio
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from .state import RuntimeState, TaskPhase, ToolEvidence
from .intent import IntentClassifier, IntentType
from .event_bus import Event, EventKind, event_bus
from .budget import BudgetManager, BudgetKind
from .scheduler import Scheduler, ScheduleAction, ScheduleDecision

# Map ScheduleAction -> TaskPhase for event publishing
_ACTION_PHASE_MAP: dict[ScheduleAction, TaskPhase] = {
    ScheduleAction.PLAN: TaskPhase.PLANNING,
    ScheduleAction.EXPLORE: TaskPhase.EXPLORATION,
    ScheduleAction.IMPLEMENT: TaskPhase.IMPLEMENTATION,
    ScheduleAction.VERIFY: TaskPhase.VERIFICATION,
    ScheduleAction.FINALIZE: TaskPhase.FINALIZING,
    ScheduleAction.RECOVER: TaskPhase.RECOVERY,
    ScheduleAction.STOP: TaskPhase.CANCELLED,
}


@dataclass
class RuntimeResult:
    """Final result of a runtime execution."""

    task_id: str
    success: bool
    phase: TaskPhase
    artifacts: list[dict[str, Any]]
    rounds: int
    tokens_used: int
    total_time_seconds: float
    error: str = ""


class Runtime:
    """The central runtime that drives the agent loop.

    Usage:
        runtime = Runtime()
        result = await runtime.run("fix the bug in app/main.py")
    """

    def __init__(
        self,
        token_budget: int = 100_000,
        round_limit: int = 50,
    ) -> None:
        self.state = RuntimeState()
        self.intent_classifier = IntentClassifier()
        self.budget = BudgetManager(
            token_limit=token_budget,
            round_limit=round_limit,
        )
        self.scheduler = Scheduler()

        # v0.3.3 Autonomous Control Layer — pause event (non-busy-wait)
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # default: running

        # Plugin system for extensibility
        self._plugins: dict[str, Callable[..., Any]] = {}

        # Handlers set externally by the app
        self._plan_handler: Callable[[RuntimeState], Awaitable[Any]] | None = None
        self._explore_handler: Callable[[RuntimeState], Awaitable[Any]] | None = None
        self._implement_handler: Callable[[RuntimeState], Awaitable[Any]] | None = None
        self._verify_handler: Callable[[RuntimeState], Awaitable[Any]] | None = None
        self._finalize_handler: Callable[[RuntimeState], Awaitable[Any]] | None = None
        self._recover_handler: Callable[[RuntimeState], Awaitable[Any]] | None = None

    # -- Handler registration --

    def on_plan(self, handler: Callable[[RuntimeState], Awaitable[Any]]) -> None:
        self._plan_handler = handler

    def on_explore(self, handler: Callable[[RuntimeState], Awaitable[Any]]) -> None:
        self._explore_handler = handler

    def on_implement(self, handler: Callable[[RuntimeState], Awaitable[Any]]) -> None:
        self._implement_handler = handler

    def on_verify(self, handler: Callable[[RuntimeState], Awaitable[Any]]) -> None:
        self._verify_handler = handler

    def on_finalize(self, handler: Callable[[RuntimeState], Awaitable[Any]]) -> None:
        self._finalize_handler = handler

    def on_recover(self, handler: Callable[[RuntimeState], Awaitable[Any]]) -> None:
        self._recover_handler = handler

    def plugin(self, name: str, handler: Callable[..., Any]) -> None:
        self._plugins[name] = handler

    # -- v0.3.3 Autonomous Control Layer --

    async def pause(self) -> None:
        """Pause the runtime loop at the next safe point."""
        self.state.paused = True
        self._pause_event.clear()
        await event_bus.publish(Event(
            kind=EventKind.RUNTIME_PAUSED,
            payload={"task_id": self.state.task_id},
            task_id=self.state.task_id,
        ))

    async def resume(self) -> None:
        """Resume from pause."""
        self.state.paused = False
        self._pause_event.set()
        if self.state.human_override:
            self.state.human_override = False
            await event_bus.publish(Event(
                kind=EventKind.HUMAN_OVERRIDE_ENDED,
                payload={"task_id": self.state.task_id},
                task_id=self.state.task_id,
            ))
        await event_bus.publish(Event(
            kind=EventKind.RUNTIME_RESUMED,
            payload={"task_id": self.state.task_id},
            task_id=self.state.task_id,
        ))

    async def take_over(self) -> None:
        """Human takes over control. Agent loop pauses."""
        self.state.human_override = True
        self.state.paused = True
        await event_bus.publish(Event(
            kind=EventKind.HUMAN_OVERRIDE_STARTED,
            payload={"task_id": self.state.task_id, "phase": self.state.phase.value},
            task_id=self.state.task_id,
        ))

    async def rollback(self) -> dict[str, Any]:
        """Roll back the last snapshot. Returns rollback info."""
        from forge.snapshot.snapshot import SnapshotManager
        sm = SnapshotManager()
        # Use last snapshot from state
        if not self.state.snapshot_id:
            return {"rolled_back": False, "reason": "No snapshot available"}
        try:
            # Find and restore the snapshot with matching task_id
            from pathlib import Path
            workspace = Path.home() / "forge_workspace"
            snap_dir = workspace / ".forge_snapshots"
            if snap_dir.exists():
                import json
                for f in sorted(snap_dir.glob("*.json"), reverse=True):
                    data = json.loads(f.read_text())
                    if data.get("task_id") == self.state.task_id:
                        # Restore each file in the snapshot
                        restored = []
                        for snap in data.get("snapshots", []):
                            from forge.snapshot.snapshot import Snapshot
                            s = Snapshot(**snap) if isinstance(snap, dict) else snap
                            if s.restore():
                                restored.append(s.file_path)
                        await event_bus.publish(Event(
                            kind=EventKind.ROLLBACK_COMPLETED,
                            payload={"task_id": self.state.task_id, "files_restored": restored},
                            task_id=self.state.task_id,
                        ))
                        return {"rolled_back": True, "files_restored": restored}
        except Exception as e:
            return {"rolled_back": False, "reason": str(e)}
        return {"rolled_back": False, "reason": "No snapshot found"}

    async def stop(self) -> None:
        """Stop the task immediately. Keeps stream, artifacts, snapshots intact."""
        self.state.phase = TaskPhase.CANCELLED
        self.state.paused = False
        await event_bus.publish(Event(
            kind=EventKind.RUNTIME_STOPPED,
            payload={"task_id": self.state.task_id, "phase": "cancelled"},
            task_id=self.state.task_id,
        ))

    async def set_mode(self, mode: str) -> None:
        """Switch runtime mode. Takes effect immediately."""
        from .state import RuntimeMode
        try:
            new_mode = RuntimeMode(mode)
            old_mode = self.state.mode.value
            self.state.mode = new_mode
            await event_bus.publish(Event(
                kind=EventKind.MODE_CHANGED,
                payload={"task_id": self.state.task_id, "from": old_mode, "to": new_mode.value},
                task_id=self.state.task_id,
            ))
        except ValueError:
            raise ValueError(f"Invalid mode: {mode}. Must be one of: autonomous, observe, governed")

    # -- Main loop --

    async def run(self, goal: str, session_id: str = "") -> RuntimeResult:
        """Execute a goal through the runtime loop."""
        start_time = datetime.now(timezone.utc)

        # Reuse state if task_id is already set (e.g. created via API)
        if not hasattr(self.state, 'task_id') or not self.state.task_id:
            self.state = RuntimeState()
        self.state.goal = goal
        self.state.phase = TaskPhase.INIT
        if session_id:
            self.state.session_id = session_id

        # Classify intent
        intent_result = self.intent_classifier.classify(goal)
        self.state.intent = intent_result.intent.value

        await event_bus.publish(Event(
            kind=EventKind.TASK_STARTED,
            payload={
                "task_id": self.state.task_id,
                "goal": goal,
                "intent": intent_result.intent.value,
                "confidence": intent_result.confidence,
            },
            task_id=self.state.task_id,
        ))

        await event_bus.publish(Event(
            kind=EventKind.INTENT_CLASSIFIED,
            payload={
                "intent": intent_result.intent.value,
                "confidence": intent_result.confidence,
                "reason": intent_result.reason,
            },
            task_id=self.state.task_id,
        ))

        # Main loop — THIS IS THE CORE
        try:
            while not self.state.is_terminal:
                # 0. Check pause/stop (v0.3.3 Autonomous Control Layer)
                if self.state.phase == TaskPhase.CANCELLED:
                    break
                await self._pause_event.wait()  # non-busy-wait gate

                # 1. Check budgets
                if self.budget.is_exhausted:
                    self.state.phase = TaskPhase.FAILED
                    await event_bus.publish(Event(
                        kind=EventKind.BUDGET_EXHAUSTED,
                        payload=self.budget.summary,
                        task_id=self.state.task_id,
                    ))
                    break

                # 2. Check warnings
                for warning in self.budget.check_warnings():
                    await event_bus.publish(Event(
                        kind=EventKind.BUDGET_WARNING,
                        payload={"message": warning},
                        task_id=self.state.task_id,
                    ))

                # 3. Decide next action
                decision = await self.scheduler.decide(self.state.summary)

                await event_bus.publish(Event(
                    kind=EventKind.ACTION_SELECTED,
                    payload={"action": decision.action.value, "reason": decision.reason},
                    task_id=self.state.task_id,
                ))

                # 4. Execute the action
                await self._execute_action(decision)

                # 5. Advance round
                self.state.advance_round()
                self.budget.consume_round()

            # /while

            # Finalize if completed
            if self.state.phase == TaskPhase.COMPLETED:
                pass  # Finalization happens through the loop

        except Exception as e:
            self.state.phase = TaskPhase.FAILED
            self.state.last_error = str(e)
            self.state.error_count += 1
            await event_bus.publish(Event(
                kind=EventKind.ERROR,
                payload={"error": str(e), "traceback": traceback.format_exc()},
                task_id=self.state.task_id,
            ))

        # Final event
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        await event_bus.publish(Event(
            kind=EventKind.TASK_COMPLETED if self.state.phase == TaskPhase.COMPLETED else EventKind.TASK_FAILED,
            payload={
                "phase": self.state.phase.value,
                "rounds": self.state.round,
                "tokens_used": self.state.total_tokens_used,
                "elapsed_seconds": elapsed,
            },
            task_id=self.state.task_id,
        ))

        return RuntimeResult(
            task_id=self.state.task_id,
            success=self.state.phase == TaskPhase.COMPLETED,
            phase=self.state.phase,
            artifacts=[{"kind": a.kind, "path": a.path} for a in self.state.artifacts],
            rounds=self.state.round,
            tokens_used=self.state.total_tokens_used,
            total_time_seconds=elapsed,
            error=self.state.last_error,
        )

    # Phase sequence for auto-advancement
    _PHASE_SEQUENCE: list[TaskPhase] = [
        TaskPhase.INIT,
        TaskPhase.PLANNING,
        TaskPhase.EXPLORATION,
        TaskPhase.IMPLEMENTATION,
        TaskPhase.VERIFICATION,
        TaskPhase.FINALIZING,
        TaskPhase.COMPLETED,
    ]

    def _next_phase(self) -> TaskPhase | None:
        """Return the next phase in sequence, or None if already at end."""
        try:
            idx = self._PHASE_SEQUENCE.index(self.state.phase)
            if idx < len(self._PHASE_SEQUENCE) - 1:
                return self._PHASE_SEQUENCE[idx + 1]
            return None
        except ValueError:
            return None

    async def _execute_action(self, decision: ScheduleDecision) -> None:
        """Execute a single schedule action, emitting events for each step."""
        action = decision.action
        tid = self.state.task_id
        original_phase = self.state.phase
        action_name = action.value if hasattr(action, 'value') else str(action)
        start_ts = datetime.now(timezone.utc)

        # Publish phase change
        new_phase = _ACTION_PHASE_MAP.get(action)
        if new_phase and self.state.phase != new_phase:
            prev = self.state.phase.value if hasattr(self.state.phase, 'value') else str(self.state.phase)
            self.state.phase = new_phase
            await event_bus.publish(Event(
                kind=EventKind.PHASE_CHANGED,
                payload={"from": prev, "to": new_phase.value},
                task_id=tid,
            ))

        # Publish tool started
        await event_bus.publish(Event(
            kind=EventKind.TOOL_STARTED,
            payload={"tool": action_name, "target": self.state.goal[:60], "params": {}},
            task_id=tid,
        ))

        # Execute
        error = None
        try:
            if action == ScheduleAction.PLAN:
                if self._plan_handler:
                    await self._plan_handler(self.state)
                else:
                    self.state.add_fact("No plan handler registered; using default plan.")

            elif action == ScheduleAction.EXPLORE:
                if self._explore_handler:
                    await self._explore_handler(self.state)
                else:
                    self.state.add_fact("No explore handler registered.")

            elif action == ScheduleAction.IMPLEMENT:
                if self._implement_handler:
                    await self._implement_handler(self.state)
                else:
                    self.state.add_fact("No implement handler registered.")

            elif action == ScheduleAction.VERIFY:
                if self._verify_handler:
                    await self._verify_handler(self.state)
                else:
                    self.state.phase = TaskPhase.COMPLETED

            elif action == ScheduleAction.FINALIZE:
                self.state.phase = TaskPhase.FINALIZING
                if self._finalize_handler:
                    await self._finalize_handler(self.state)
                self.state.phase = TaskPhase.COMPLETED

            elif action == ScheduleAction.ASK_USER:
                pass

            elif action == ScheduleAction.RECOVER:
                self.state.phase = TaskPhase.RECOVERY
                if self._recover_handler:
                    await self._recover_handler(self.state)

            elif action == ScheduleAction.STOP:
                if self.state.phase not in (TaskPhase.COMPLETED, TaskPhase.FAILED):
                    self.state.phase = TaskPhase.CANCELLED

            # Auto-advance phase
            if self.state.phase == original_phase and action not in (
                ScheduleAction.STOP, ScheduleAction.WAIT, ScheduleAction.ASK_USER,
            ):
                next_p = self._next_phase()
                if next_p and next_p != self.state.phase:
                    prev = self.state.phase.value if hasattr(self.state.phase, 'value') else str(self.state.phase)
                    self.state.phase = next_p
                    await event_bus.publish(Event(
                        kind=EventKind.PHASE_CHANGED,
                        payload={"from": prev, "to": next_p.value},
                        task_id=tid,
                    ))

        except Exception as e:
            error = str(e)
            await event_bus.publish(Event(
                kind=EventKind.ERROR,
                payload={"error": error, "source": action_name, "recoverable": False},
                task_id=tid,
            ))

        # Publish tool completed
        elapsed_ms = (datetime.now(timezone.utc) - start_ts).total_seconds() * 1000
        await event_bus.publish(Event(
            kind=EventKind.TOOL_COMPLETED,
            payload={
                "tool": action_name,
                "target": self.state.goal[:60],
                "duration_ms": elapsed_ms,
                "error": error or "",
                "result_summary": f"Action '{action_name}' -> phase={self.state.phase.value}",
            },
            task_id=tid,
        ))
