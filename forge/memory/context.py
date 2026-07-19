"""Context Window — multi-turn sliding window over compressed states.

The LLM doesn't see one state. It sees the last N states,
with older states decaying in detail.

v0.3: multi-turn context management with priority decay.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .compressor import CompressedState


class ContextPriority(str, Enum):
    CRITICAL = "critical"  # Never decays (e.g., user's original goal)
    HIGH = "high"  # Decays slowly (e.g., confirmed architecture decisions)
    NORMAL = "normal"  # Standard decay
    LOW = "low"  # Fast decay (e.g., temporary exploration results)


@dataclass
class ContextEntry:
    """A single entry in the context window."""

    state: CompressedState
    priority: ContextPriority = ContextPriority.NORMAL
    round: int = 0
    age: int = 0  # rounds since last access
    sources: list[str] = field(default_factory=list)

    @property
    def decayed(self) -> bool:
        """Should this entry be evicted?"""
        decay_limits = {
            ContextPriority.CRITICAL: 100,
            ContextPriority.HIGH: 20,
            ContextPriority.NORMAL: 10,
            ContextPriority.LOW: 3,
        }
        return self.age >= decay_limits.get(self.priority, 10)


class ContextWindow:
    """Sliding window over compressed states.

    Maintains an ordered list of context entries.
    Older entries decay and eventually get evicted.
    """

    MAX_ENTRIES: int = 10

    def __init__(self, max_entries: int = 10) -> None:
        self.max_entries = max_entries
        self._entries: list[ContextEntry] = []

    def add(self, state: CompressedState, priority: ContextPriority = ContextPriority.NORMAL,
            sources: list[str] | None = None) -> None:
        """Add a compressed state to the context window."""
        self._entries.append(ContextEntry(
            state=state,
            priority=priority,
            round=state.round,
            sources=sources or [],
        ))
        self._garbage_collect()

    def _garbage_collect(self) -> None:
        """Evict old/low-priority entries when over limit."""
        if len(self._entries) <= self.max_entries:
            return

        # Age everything
        for entry in self._entries:
            entry.age += 1

        # Sort by priority (critical first) then age (younger first)
        priority_order = {
            ContextPriority.CRITICAL: 0,
            ContextPriority.HIGH: 1,
            ContextPriority.NORMAL: 2,
            ContextPriority.LOW: 3,
        }
        self._entries.sort(key=lambda e: (priority_order.get(e.priority, 3), e.age))

        # Keep only the top N
        self._entries = self._entries[:self.max_entries]

    def get_snapshot(self, max_tokens: int = 1500) -> str:
        """Build a consolidated prompt from the context window.

        Higher priority entries get more token budget.
        """
        if not self._entries:
            return ""

        # Allocate token budget per entry by priority weight
        weights = {
            ContextPriority.CRITICAL: 0.4,
            ContextPriority.HIGH: 0.3,
            ContextPriority.NORMAL: 0.2,
            ContextPriority.LOW: 0.1,
        }
        total_weight = sum(weights.get(e.priority, 0.2) for e in self._entries)
        parts: list[str] = []

        for entry in reversed(self._entries):  # most recent first
            # Only include if not fully decayed
            if entry.decayed and entry.priority == ContextPriority.LOW:
                continue

            prompt = entry.state.to_prompt()
            # Estimate proportional token budget
            share = weights.get(entry.priority, 0.2) / total_weight
            budget = max(100, int(max_tokens * share))
            if len(prompt) // 4 > budget:
                lines = prompt.split("\n")
                prompt = "\n".join(lines[:max(2, budget // 20)])

            parts.append(prompt)

        return "\n\n".join(parts)

    def find_fact(self, keyword: str) -> list[str]:
        """Search through context window for a fact by keyword."""
        results = []
        for entry in self._entries:
            prompt = entry.state.to_prompt()
            if keyword.lower() in prompt.lower():
                for line in prompt.split("\n"):
                    if keyword.lower() in line.lower():
                        results.append(line.strip())
        return results

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def current_goal(self) -> str:
        return self._entries[-1].state.goal if self._entries else ""
