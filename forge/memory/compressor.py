"""State Compressor — transforms verbose state into a compact LLM context.

This is the module that prevents "long task drift".
Instead of dumping the entire conversation history into the LLM context,
we maintain a compressed, curated state.

This is one of the 4 moat modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from forge.kernel.state import RuntimeState


@dataclass
class CompressedState:
    """The compressed state — what actually goes into the LLM context.

    Designed to fit in ~500 tokens.
    """

    goal: str = ""
    phase: str = ""
    round: int = 0
    confirmed_facts: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    critical_files: list[str] = field(default_factory=list)
    recent_changes: list[str] = field(default_factory=list)
    next_action: str = ""

    def to_prompt(self) -> str:
        """Format as a compact prompt string."""
        parts = [f"Goal: {self.goal}", f"Phase: {self.phase} (round {self.round})"]

        if self.confirmed_facts:
            parts.append("Known:")
            for f in self.confirmed_facts[:5]:
                parts.append(f"  • {f}")

        if self.open_questions:
            parts.append("Questions:")
            for q in self.open_questions[:3]:
                parts.append(f"  ? {q}")

        if self.critical_files:
            parts.append("Files:")
            for f in self.critical_files[:5]:
                parts.append(f"  📄 {f}")

        if self.recent_changes:
            parts.append("Recent:")
            for c in self.recent_changes[-3:]:
                parts.append(f"  ~ {c}")

        if self.next_action:
            parts.append(f"Next: {self.next_action}")

        return "\n".join(parts)

    def token_estimate(self) -> int:
        """Rough token estimate (chars / 4)."""
        return len(self.to_prompt()) // 4


class StateCompressor:
    """Compresses RuntimeState into a compact form for LLM consumption.

    The goal is to preserve all decision-relevant information
    while discarding redundancy and historical detail.
    """

    MAX_FACTS: int = 10
    MAX_QUESTIONS: int = 5
    MAX_CHANGES: int = 5
    MAX_FILES: int = 10
    MAX_TOKENS: int = 500

    def __init__(self, max_tokens: int = 500) -> None:
        self.max_tokens = max_tokens

    def compress(self, state: RuntimeState) -> CompressedState:
        """Compress a full RuntimeState into a compact representation.

        This is lossy by design. We keep only what the LLM needs
        to make the next decision.
        """
        # Merge similar facts
        facts = self._deduplicate_and_prune(state.confirmed_facts, self.MAX_FACTS)

        # Keep highest-priority open questions
        questions = state.open_questions[:self.MAX_QUESTIONS]

        # Keep only critical files
        files = state.critical_files[:self.MAX_FILES]

        # Keep only recent changes
        changes = state.recent_changes[-self.MAX_CHANGES:]

        compressed = CompressedState(
            goal=state.goal[:200],  # Truncate very long goals
            phase=state.phase.value,
            round=state.round,
            confirmed_facts=facts,
            open_questions=questions,
            critical_files=files,
            recent_changes=changes,
            next_action=state.next_best_action,
        )

        # If still over token budget, aggressively prune
        while compressed.token_estimate() > self.max_tokens:
            if len(compressed.confirmed_facts) > 3:
                compressed.confirmed_facts = compressed.confirmed_facts[:3]
            elif len(compressed.critical_files) > 3:
                compressed.critical_files = compressed.critical_files[:3]
            elif len(compressed.open_questions) > 2:
                compressed.open_questions = compressed.open_questions[:2]
            elif len(compressed.recent_changes) > 2:
                compressed.recent_changes = compressed.recent_changes[:2]
            elif len(compressed.goal) > 100:
                compressed.goal = compressed.goal[:100]
            else:
                break

        return compressed

    def _deduplicate_and_prune(self, items: list[str], max_count: int) -> list[str]:
        """Remove near-duplicate facts and keep the most recent."""
        seen: set[str] = set()
        result: list[str] = []
        for item in reversed(items):
            # Simple dedup: normalize and compare
            key = item.lower().strip()
            if key not in seen:
                seen.add(key)
                result.append(item)
            if len(result) >= max_count:
                break
        return list(reversed(result))
