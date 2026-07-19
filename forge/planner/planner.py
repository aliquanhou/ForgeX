"""High-Level Planner — generates structured plans from user goals.

This is the first module that calls the LLM.
It produces a Plan that the rest of the system follows.
"""

from __future__ import annotations

from typing import Any

from forge.llm import LLMClient, SystemPrompts
from forge.kernel.state import RuntimeState, TaskPhase
from .types import Plan


class HighLevelPlanner:
    """Generates and manages high-level plans."""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self._llm = llm
        self.current_plan: Plan | None = None

    def set_llm(self, llm: LLMClient) -> None:
        self._llm = llm

    async def create_plan(self, state: RuntimeState) -> Plan:
        """Create a high-level plan from the current state.

        Uses the LLM if available, falls back to template-based planning.
        """
        if self._llm:
            return await self._create_plan_llm(state)
        return self._create_plan_template(state)

    async def _create_plan_llm(self, state: RuntimeState) -> Plan:
        """Use the LLM to generate a plan."""
        prompt = f"""Create a plan for the following goal:

User goal: {state.goal}
Intent: {state.intent}
Current phase: {state.phase.value}

Generate a structured plan with:
1. A clear restatement of the goal
2. Phases (exploration, implementation, verification, etc.)
3. Each phase with specific steps, files to read, and success criteria
4. Risks
5. Estimated rounds needed"""
        result = await self._llm.chat_json(
            prompt=prompt,
            system=SystemPrompts.PLANNER,
        )
        self.current_plan = Plan.from_dict(result)
        return self.current_plan

    def _create_plan_template(self, state: RuntimeState) -> Plan:
        """Template-based plan when no LLM is available."""
        from forge.kernel.intent import IntentType

        intent = IntentType(state.intent)

        if intent == IntentType.DEBUG:
            return Plan(
                goal=state.goal,
                phases=[
                    Plan.Phase("exploration", ["Reproduce the issue", "Gather error logs"]),
                    Plan.Phase("analysis", ["Identify root cause", "Check related code"]),
                    Plan.Phase("implementation", ["Implement fix", "Add tests"]),
                    Plan.Phase("verification", ["Verify fix works", "Run existing tests"]),
                ],
                risks=["May not reproduce consistently"],
            )
        elif intent == IntentType.RESEARCH:
            return Plan(
                goal=state.goal,
                phases=[
                    Plan.Phase("exploration", ["Find relevant files", "Read key functions"]),
                    Plan.Phase("analysis", ["Trace data flow", "Document findings"]),
                ],
                risks=["Key files may be hard to find"],
            )
        else:  # CODE_MODIFY and default
            return Plan(
                goal=state.goal,
                phases=[
                    Plan.Phase("exploration", ["Read relevant files", "Understand context"]),
                    Plan.Phase("implementation", ["Implement changes"]),
                    Plan.Phase("verification", ["Verify changes", "Run tests"]),
                ],
                risks=["Changes may affect other parts of the system"],
            )
