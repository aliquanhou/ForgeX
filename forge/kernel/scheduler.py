"""Scheduler — the core loop orchestrator.

This is the "while not completed" loop from the architecture.
It decides WHAT to do next based on the current state, delegates execution,
then evaluates the result.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Awaitable


class ScheduleAction(str, Enum):
    """Actions the scheduler can take in each iteration."""

    PLAN = "plan"
    """Generate or refine the high-level plan."""

    EXPLORE = "explore"
    """Search/read the codebase to gather information."""

    IMPLEMENT = "implement"
    """Make code changes."""

    VERIFY = "verify"
    """Run tests, checks, or verification."""

    ASK_USER = "ask_user"
    """Pause for user input/approval."""

    FINALIZE = "finalize"
    """Wrap up and produce artifacts."""

    WAIT = "wait"
    """Await external event."""

    STOP = "stop"
    """End the loop."""

    RECOVER = "recover"
    """Attempt recovery from an error."""


@dataclass
class ScheduleDecision:
    """What the scheduler decided to do next."""

    action: ScheduleAction
    reason: str = ""
    params: dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.params is None:
            self.params = {}


ActionHandler = Callable[[ScheduleDecision], Awaitable[Any]]


class Scheduler:
    """Main loop scheduler.

    The scheduler decides the NEXT action based on the current state.
    It does NOT execute the action — that is the Runtime's job.
    """

    def __init__(self) -> None:
        self._handlers: dict[ScheduleAction, ActionHandler] = {}

    def register(self, action: ScheduleAction, handler: ActionHandler) -> None:
        """Register a handler for a given action type."""
        self._handlers[action] = handler

    async def decide(self, state_summary: dict[str, Any]) -> ScheduleDecision:
        """Decide what to do next based on the state summary.

        Maps each phase to exactly one action. Simple rule-based routing.
        """
        phase = state_summary.get("phase", "init")
        round_num = state_summary.get("round", 0)

        # Phase → Action mapping (complete, no fallthrough)
        ROUTES: dict[str, ScheduleAction] = {
            "init": ScheduleAction.PLAN,
            "planning": ScheduleAction.EXPLORE,
            "exploration": ScheduleAction.IMPLEMENT,
            "implementation": ScheduleAction.VERIFY,
            "verification": ScheduleAction.FINALIZE,
            "finalizing": ScheduleAction.FINALIZE,
            "completed": ScheduleAction.STOP,
            "failed": ScheduleAction.STOP,
            "cancelled": ScheduleAction.STOP,
            "recovery": ScheduleAction.RECOVER,
        }

        action = ROUTES.get(phase, ScheduleAction.IMPLEMENT)
        return ScheduleDecision(action, f"Phase: {phase} → {action.value}")

    async def dispatch(self, decision: ScheduleDecision) -> Any:
        """Dispatch a decision to its registered handler."""
        handler = self._handlers.get(decision.action)
        if handler is None:
            raise ValueError(f"No handler registered for action: {decision.action}")
        return await handler(decision)
