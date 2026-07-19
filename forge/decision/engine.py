"""Decision Engine v2 — with LLM Judge fallback + Uncertainty Entropy.

v0.3 upgrades:
- 90% cases: rule-based (fast, cheap)
- 10% hard cases: LLM Judge (slow, smart)
- Uncertainty Entropy in decision context
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable


class DecisionKind(str, Enum):
    CONTINUE_EXPLORE = "continue_explore"
    DEEP_READ = "deep_read"
    SEARCH_SYMBOL = "search_symbol"
    WRITE_CODE = "write_code"
    EDIT_CODE = "edit_code"
    CREATE_FILE = "create_file"
    RUN_TEST = "run_test"
    VERIFY_FILE = "verify_file"
    SYNTAX_CHECK = "syntax_check"
    ASK_USER = "ask_user"
    ROLLBACK = "rollback"
    FINALIZE = "finalize"
    STOP = "stop"
    RECOVER = "recover"
    RECOMPUTE = "recompute"


@dataclass
class Decision:
    kind: DecisionKind
    confidence: float
    reason: str
    params: dict[str, Any] = field(default_factory=dict)
    alternatives: list[tuple[DecisionKind, float]] = field(default_factory=list)
    from_judge: bool = False  # True if LLM Judge made this call

    @property
    def is_certain(self) -> bool:
        return self.confidence >= 0.8

    @property
    def is_uncertain(self) -> bool:
        return self.confidence < 0.5


@dataclass
class DecisionContext:
    phase: str
    round: int
    goal: str
    intent: str

    open_questions: int = 0
    confirmed_facts: int = 0
    critical_files_known: int = 0

    last_evi_score: float = 0.0
    last_evi_tool: str = ""
    evi_trend: list[float] = field(default_factory=list)
    low_evi_streak: int = 0

    # v0.3: Uncertainty Entropy
    uncertainty_entropy: float = 0.0  # 0.0 = certain, 1.0 = completely uncertain
    knowledge_coverage: float = 0.0  # 0.0-1.0: how much do we know about the goal?

    rounds_remaining: int = 50
    tokens_pct: float = 0.0
    current_phase_steps: int = 0
    phases_completed: int = 0
    phases_total: int = 0
    last_error: str = ""
    error_count: int = 0


class DecisionStrategy(str, Enum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


class DecisionEngine:
    """Decision Engine v2 with LLM Judge fallback.

    Flow:
    1. Fast rules handle 90% of cases
    2. If confidence < threshold → call LLM Judge
    3. LLM Judge return used as override
    """

    def __init__(self, strategy: DecisionStrategy = DecisionStrategy.BALANCED) -> None:
        self.strategy = strategy
        self._llm_judge: Callable[[DecisionContext], Awaitable[Decision]] | None = None
        self._stats: dict[str, Any] = {
            "decisions_made": 0,
            "judge_called": 0,
            "judge_overruled": 0,
        }

    def set_judge(self, judge_fn: Callable[[DecisionContext], Awaitable[Decision]]) -> None:
        """Set the LLM Judge callback for hard cases."""
        self._llm_judge = judge_fn

    async def decide(self, ctx: DecisionContext) -> Decision:
        """Make a decision. Calls LLM Judge for uncertain cases."""
        self._stats["decisions_made"] += 1

        # --- Fast rule-based path ---
        decision = self._rule_decide(ctx)

        # --- If uncertain and judge is available → LLM Judge ---
        if decision.is_uncertain and self._llm_judge and self.strategy != DecisionStrategy.AGGRESSIVE:
            self._stats["judge_called"] += 1
            judge_decision = await self._llm_judge(ctx)
            judge_decision.from_judge = True
            if judge_decision.confidence > decision.confidence:
                self._stats["judge_overruled"] += 1
                return judge_decision

        return decision

    def _rule_decide(self, ctx: DecisionContext) -> Decision:
        """Rule-based decision (90% of cases)."""
        # --- Stop conditions ---
        if ctx.phase in ("completed", "failed", "cancelled"):
            return Decision(DecisionKind.STOP, 1.0, "Task is terminal")
        if ctx.rounds_remaining <= 0:
            return Decision(DecisionKind.FINALIZE, 0.9, "Budget exhausted")

        # --- Recovery ---
        if ctx.error_count > 0 and ctx.last_error:
            if ctx.error_count >= 3:
                return Decision(DecisionKind.ASK_USER, 0.7, f"Failed {ctx.error_count}x")
            return Decision(DecisionKind.RECOVER, 0.8, f"Recovering: {ctx.last_error[:80]}")

        # --- EVI-based pivoting ---
        if ctx.low_evi_streak >= 3:
            if ctx.phase == "exploration":
                return Decision(DecisionKind.WRITE_CODE, 0.65, f"EVI low ×{ctx.low_evi_streak}, stop exploring")
            elif ctx.phase == "implementation":
                return Decision(DecisionKind.ROLLBACK, 0.7, f"EVI low ×{ctx.low_evi_streak}, rollback")
            return Decision(DecisionKind.FINALIZE, 0.6, "Force finalize")

        if ctx.last_evi_score < 0.15 and ctx.low_evi_streak >= 1:
            alt = self._suggest_alternative(ctx)
            return Decision(alt.kind, alt.confidence * 0.95, f"EVI low, pivot: {alt.reason}")

        # --- Uncertainty-aware phase routing ---
        if ctx.uncertainty_entropy > 0.7:
            # High uncertainty → explore more before deciding
            if ctx.phase == "implementation":
                return Decision(DecisionKind.CONTINUE_EXPLORE, 0.55,
                                f"High uncertainty ({ctx.uncertainty_entropy:.2f}), explore more first")

        if ctx.knowledge_coverage < 0.3 and ctx.phase != "exploration":
            return Decision(DecisionKind.CONTINUE_EXPLORE, 0.6,
                            f"Low knowledge coverage ({ctx.knowledge_coverage:.2f}), need more context")

        # --- Phase routing ---
        if ctx.phase == "planning":
            return Decision(DecisionKind.WRITE_CODE, 0.8, "Plan ready → implement")
        if ctx.phase == "exploration":
            return self._decide_explore(ctx)
        if ctx.phase == "implementation":
            return self._decide_implement(ctx)
        if ctx.phase == "verification":
            return self._decide_verify(ctx)
        if ctx.phase == "finalizing":
            return Decision(DecisionKind.FINALIZE, 0.9, "Finalizing")

        return Decision(DecisionKind.CONTINUE_EXPLORE, 0.5, f"Default phase={ctx.phase}")

    def _decide_explore(self, ctx: DecisionContext) -> Decision:
        if ctx.open_questions == 0 and ctx.confirmed_facts >= 3:
            return Decision(DecisionKind.WRITE_CODE, 0.85, "Ready to implement")
        if ctx.critical_files_known > ctx.open_questions:
            return Decision(DecisionKind.DEEP_READ, 0.75, "Deep read phase")
        if ctx.critical_files_known < 3:
            return Decision(DecisionKind.SEARCH_SYMBOL, 0.7, "Need more files")
        return Decision(DecisionKind.CONTINUE_EXPLORE, 0.6, "Exploring more")

    def _decide_implement(self, ctx: DecisionContext) -> Decision:
        if ctx.last_error:
            return Decision(DecisionKind.SYNTAX_CHECK, 0.8, "Check syntax first")
        if ctx.last_evi_score > 0.7 and self.strategy != DecisionStrategy.CONSERVATIVE:
            return Decision(DecisionKind.WRITE_CODE, 0.85, "High confidence → write")
        if ctx.open_questions > 0:
            return Decision(DecisionKind.EDIT_CODE, 0.65, "Questions open → edit")
        return Decision(DecisionKind.WRITE_CODE, 0.7, f"Implement round {ctx.round}")

    def _decide_verify(self, ctx: DecisionContext) -> Decision:
        if ctx.last_evi_tool in ("write_file", "edit_file"):
            return Decision(DecisionKind.VERIFY_FILE, 0.9, "Modified → verify")
        if ctx.phases_completed >= ctx.phases_total - 1:
            return Decision(DecisionKind.FINALIZE, 0.85, "All phases done")
        return Decision(DecisionKind.RUN_TEST, 0.75, "Verify")

    def _suggest_alternative(self, ctx: DecisionContext) -> Decision:
        if ctx.last_evi_tool in ("grep", "glob", "read_file"):
            return Decision(DecisionKind.SEARCH_SYMBOL, 0.6, "Search strategy pivot")
        return Decision(
            DecisionKind.ASK_USER if self.strategy == DecisionStrategy.CONSERVATIVE
            else DecisionKind.CONTINUE_EXPLORE, 0.5, "Pivoting"
        )

    @property
    def stats(self) -> dict[str, Any]:
        return dict(self._stats)


# Helper: compute uncertainty entropy from state signals
def compute_uncertainty_entropy(
    open_questions: int,
    critical_files_known: int,
    evi_trend: list[float],
    low_evi_streak: int,
) -> float:
    """Compute uncertainty entropy (0.0 = certain, 1.0 = completely uncertain).

    Higher values mean the agent has less confidence in what to do next.
    """
    entropy = 0.0

    # More open questions = more uncertainty
    q_factor = min(1.0, open_questions / 5.0)
    entropy += q_factor * 0.3

    # Fewer known files = more uncertainty
    f_factor = max(0.0, 1.0 - critical_files_known / 5.0)
    entropy += f_factor * 0.2

    # Low/inconsistent EVI = more uncertainty
    if evi_trend:
        avg_evi = sum(evi_trend) / len(evi_trend)
        entropy += (1.0 - avg_evi) * 0.3

    # Low EVI streak = sharp uncertainty spike
    entropy += min(1.0, low_evi_streak / 5.0) * 0.2

    return min(1.0, entropy)


# Helper: compute knowledge coverage
def compute_knowledge_coverage(
    confirmed_facts: int,
    open_questions: int,
    critical_files_known: int,
) -> float:
    """Compute how much we know relative to what we need (0.0-1.0)."""
    if confirmed_facts == 0 and open_questions == 0:
        return 0.0
    if confirmed_facts + open_questions == 0:
        return 0.5
    fact_ratio = confirmed_facts / max(confirmed_facts + open_questions, 1)
    file_coverage = min(1.0, critical_files_known / 3.0)
    return (fact_ratio * 0.6 + file_coverage * 0.4)
