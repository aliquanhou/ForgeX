"""Decision Engine — the intelligent action selector.

This replaces the old phase→action if-else scheduler.
It uses state + EVI + budget + goal progress to make real decisions.

Scheduler was "flow control". Decision Engine is "intelligence control".
"""

from .engine import DecisionEngine, Decision, DecisionKind, DecisionContext, DecisionStrategy

__all__ = [
    "DecisionEngine",
    "Decision",
    "DecisionKind",
    "DecisionContext",
    "DecisionStrategy",
]
