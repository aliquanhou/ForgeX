"""Budget Manager — tracks and enforces resource limits.

The budget is a HARD ceiling, not a suggestion.
When exhausted, the runtime must finalize or fail gracefully.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BudgetKind(str, Enum):
    TOKENS = "tokens"
    ROUNDS = "rounds"
    READS = "reads"
    EXECUTIONS = "executions"
    TIME = "time"


@dataclass
class BudgetState:
    """Current state of a single budget dimension."""

    limit: int
    used: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    @property
    def exhausted(self) -> bool:
        return self.used >= self.limit

    @property
    def pct(self) -> float:
        return self.used / self.limit if self.limit > 0 else 0.0


class BudgetManager:
    """Manages all budget dimensions for a task."""

    def __init__(
        self,
        token_limit: int = 100_000,
        round_limit: int = 50,
        read_limit: int = 200,
        execution_limit: int = 100,
        time_limit_seconds: int = 600,
    ) -> None:
        self._budgets: dict[BudgetKind, BudgetState] = {
            BudgetKind.TOKENS: BudgetState(limit=token_limit),
            BudgetKind.ROUNDS: BudgetState(limit=round_limit),
            BudgetKind.READS: BudgetState(limit=read_limit),
            BudgetKind.EXECUTIONS: BudgetState(limit=execution_limit),
            BudgetKind.TIME: BudgetState(limit=time_limit_seconds),
        }
        self._warnings_emitted: set[str] = set()

    # -- Consumption --

    def consume_tokens(self, count: int) -> None:
        self._budgets[BudgetKind.TOKENS].used += count

    def consume_round(self) -> None:
        self._budgets[BudgetKind.ROUNDS].used += 1

    def consume_read(self) -> None:
        self._budgets[BudgetKind.READS].used += 1

    def consume_execution(self) -> None:
        self._budgets[BudgetKind.EXECUTIONS].used += 1

    # -- Status queries --

    @property
    def is_exhausted(self) -> bool:
        """Return True if ANY budget is exhausted."""
        return any(b.exhausted for b in self._budgets.values())

    @property
    def summary(self) -> dict[str, dict]:
        return {
            k.value: {
                "limit": b.limit,
                "used": b.used,
                "remaining": b.remaining,
                "pct": round(b.pct, 3),
            }
            for k, b in self._budgets.items()
        }

    def get_state(self, kind: BudgetKind) -> BudgetState:
        return self._budgets[kind]

    # -- Warning system --

    def check_warnings(self) -> list[str]:
        """Return warning messages for budgets that are near exhaustion."""
        warnings: list[str] = []
        warning_config = {
            BudgetKind.TOKENS: (0.85, "Token budget at {pct}%"),
            BudgetKind.ROUNDS: (0.80, "Round limit at {pct}%"),
        }
        for kind, (threshold, msg) in warning_config.items():
            b = self._budgets[kind]
            if b.pct >= threshold and kind.value not in self._warnings_emitted:
                self._warnings_emitted.add(kind.value)
                warnings.append(msg.format(pct=round(b.pct * 100)))
        return warnings
