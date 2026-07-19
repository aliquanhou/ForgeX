"""Decision Engine — the intelligence layer.

Replaces the old phase→action scheduler with a context-aware decision maker.
Scheduler was "flow control". Decision Engine is "intelligence control".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DecisionKind(str, Enum):
    """Every decision the engine can make."""

    # Exploration
    CONTINUE_EXPLORE = "continue_explore"
    DEEP_READ = "deep_read"
    SEARCH_SYMBOL = "search_symbol"

    # Implementation
    WRITE_CODE = "write_code"
    EDIT_CODE = "edit_code"
    CREATE_FILE = "create_file"

    # Verification
    RUN_TEST = "run_test"
    VERIFY_FILE = "verify_file"
    SYNTAX_CHECK = "syntax_check"

    # Control
    ASK_USER = "ask_user"
    ROLLBACK = "rollback"
    FINALIZE = "finalize"
    STOP = "stop"
    RECOVER = "recover"

    # Meta
    RECOMPUTE = "recompute"


@dataclass
class Decision:
    """A decision produced by the Decision Engine."""

    kind: DecisionKind
    confidence: float  # 0.0 - 1.0
    reason: str
    params: dict[str, Any] = field(default_factory=dict)
    alternatives: list[tuple[DecisionKind, float]] = field(default_factory=list)

    @property
    def is_certain(self) -> bool:
        return self.confidence >= 0.8

    @property
    def is_uncertain(self) -> bool:
        return self.confidence < 0.5


@dataclass
class DecisionContext:
    """Full context the Decision Engine uses to make a decision."""

    # State summary
    phase: str
    round: int
    goal: str
    intent: str

    # Knowledge gaps
    open_questions: int = 0
    confirmed_facts: int = 0
    critical_files_known: int = 0

    # EVI signals
    last_evi_score: float = 0.0
    last_evi_tool: str = ""
    evi_trend: list[float] = field(default_factory=list)
    low_evi_streak: int = 0

    # Budget
    rounds_remaining: int = 50
    tokens_pct: float = 0.0

    # Phase progress
    current_phase_steps: int = 0
    phases_completed: int = 0
    phases_total: int = 0

    # Error
    last_error: str = ""
    error_count: int = 0


class DecisionStrategy(str, Enum):
    """Strategy profile — conservative vs aggressive vs balanced."""

    CONSERVATIVE = "conservative"
    """Ask user before any write operation. Verify everything."""

    BALANCED = "balanced"
    """Default. Auto-write low-risk changes. Ask for high-risk."""

    AGGRESSIVE = "aggressive"
    """Auto-write everything. Minimal user interruption."""


class DecisionEngine:
    """The brain of the agent — decides WHAT to do next.

    Decision flow:
    1. Check if task is done (stop conditions)
    2. Check if recovery needed (errors)
    3. Evaluate EVI trend (is current approach working?)
    4. Decide next action based on gaps + budget + strategy
    """

    def __init__(self, strategy: DecisionStrategy = DecisionStrategy.BALANCED) -> None:
        self.strategy = strategy
        self._stats: dict[str, Any] = {"decisions_made": 0, "overruled": 0}

    def decide(self, ctx: DecisionContext) -> Decision:
        """Make a decision based on full context."""
        self._stats["decisions_made"] += 1

        # --- Priority 1: Stop conditions ---
        if ctx.phase in ("completed", "failed", "cancelled"):
            return Decision(DecisionKind.STOP, 1.0, "Task is terminal")

        if ctx.rounds_remaining <= 0:
            return Decision(DecisionKind.FINALIZE, 0.9, "Round budget exhausted, must finalize")

        # --- Priority 2: Recovery ---
        if ctx.error_count > 0 and ctx.last_error:
            if ctx.error_count >= 3:
                return Decision(
                    DecisionKind.ASK_USER, 0.7,
                    f"Failed {ctx.error_count}x: {ctx.last_error[:80]}",
                )
            return Decision(DecisionKind.RECOVER, 0.8, f"Recover from: {ctx.last_error[:80]}")

        # --- Priority 3: EVI-based pivoting ---
        if ctx.low_evi_streak >= 3:
            if ctx.phase == "exploration":
                return Decision(
                    DecisionKind.WRITE_CODE, 0.65,
                    f"Exploration stale (EVI<0.2×{ctx.low_evi_streak}), → implement",
                )
            elif ctx.phase == "implementation":
                return Decision(
                    DecisionKind.ROLLBACK, 0.7,
                    f"Implementation stale (EVI<0.2×{ctx.low_evi_streak}), rollback",
                )
            return Decision(
                DecisionKind.FINALIZE, 0.6,
                f"Phase={ctx.phase} stale, force finalize",
            )

        if ctx.last_evi_score < 0.15 and ctx.low_evi_streak >= 1:
            alt = self._suggest_alternative(ctx)
            return Decision(
                alt.kind, alt.confidence * 0.95,
                f"EVI={ctx.last_evi_score}, pivot: {alt.reason}",
                params=alt.params,
            )

        # --- Priority 4: Phase-based routing with EVI awareness ---
        if ctx.phase == "planning":
            return Decision(DecisionKind.WRITE_CODE, 0.8, "Planning → implement")

        if ctx.phase == "exploration":
            return self._decide_explore(ctx)

        if ctx.phase == "implementation":
            return self._decide_implement(ctx)

        if ctx.phase == "verification":
            return self._decide_verify(ctx)

        if ctx.phase == "finalizing":
            return Decision(DecisionKind.FINALIZE, 0.9, "Finalizing")

        return Decision(DecisionKind.CONTINUE_EXPLORE, 0.5, f"Default for phase={ctx.phase}")

    def _decide_explore(self, ctx: DecisionContext) -> Decision:
        if ctx.open_questions == 0 and ctx.confirmed_facts >= 3:
            return Decision(
                DecisionKind.WRITE_CODE, 0.85,
                f"0 questions, {ctx.confirmed_facts} facts — ready",
            )
        if ctx.critical_files_known > ctx.open_questions:
            return Decision(
                DecisionKind.DEEP_READ, 0.75,
                f"{ctx.open_questions} questions, {ctx.critical_files_known} files",
            )
        if ctx.critical_files_known < 3:
            return Decision(
                DecisionKind.SEARCH_SYMBOL, 0.7,
                f"Only {ctx.critical_files_known} files found",
            )
        return Decision(
            DecisionKind.CONTINUE_EXPLORE, 0.6,
            f"Explore (Q={ctx.open_questions}, F={ctx.critical_files_known})",
        )

    def _decide_implement(self, ctx: DecisionContext) -> Decision:
        if ctx.last_error:
            return Decision(DecisionKind.SYNTAX_CHECK, 0.8, "Error → check syntax")
        if ctx.last_evi_score > 0.7 and self.strategy != DecisionStrategy.CONSERVATIVE:
            return Decision(DecisionKind.WRITE_CODE, 0.85, f"EVI={ctx.last_evi_score}, write")
        if ctx.open_questions > 0:
            return Decision(DecisionKind.EDIT_CODE, 0.65, f"{ctx.open_questions} questions → edit")
        return Decision(DecisionKind.WRITE_CODE, 0.7, f"Implement round {ctx.round}")

    def _decide_verify(self, ctx: DecisionContext) -> Decision:
        if ctx.last_evi_tool in ("write_file", "edit_file"):
            return Decision(DecisionKind.VERIFY_FILE, 0.9, "Modified → verify")
        if ctx.phases_completed >= ctx.phases_total - 1:
            return Decision(DecisionKind.FINALIZE, 0.85, "All phases done")
        return Decision(DecisionKind.RUN_TEST, 0.75, "Verify changes")

    def _suggest_alternative(self, ctx: DecisionContext) -> Decision:
        if ctx.last_evi_tool in ("grep", "glob", "read_file"):
            return Decision(DecisionKind.SEARCH_SYMBOL, 0.6, "Content search stale → symbol search")
        if ctx.last_evi_tool == "read_file":
            return Decision(DecisionKind.SEARCH_SYMBOL, 0.55, "Deep read low EVI → symbol search")
        return Decision(
            DecisionKind.ASK_USER if self.strategy == DecisionStrategy.CONSERVATIVE
            else DecisionKind.CONTINUE_EXPLORE,
            0.5,
            f"{ctx.last_evi_tool} EVI={ctx.last_evi_score}, pivoting",
        )
