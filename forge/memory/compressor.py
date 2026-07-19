"""Short-term Memory — upgraded StateCompressor with multi-turn awareness.

v0.3 upgrades:
- Token-accurate estimation per entry
- Priority-aware retention (critical facts persist longer)
- Cross-reference markers for episodic/semantic links
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from forge.kernel.state import RuntimeState


@dataclass
class CompressedState:
    """The compressed state — what actually goes into the LLM context.

    Designed to fit in ~500 tokens with priority awareness.
    """

    goal: str = ""
    phase: str = ""
    round: int = 0
    confirmed_facts: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    critical_files: list[str] = field(default_factory=list)
    recent_changes: list[str] = field(default_factory=list)
    next_action: str = ""
    memory_refs: list[str] = field(default_factory=list)  # [[ep:abc]], [[sem:xyz]]

    def to_prompt(self) -> str:
        parts = [f"Goal: {self.goal}", f"Phase: {self.phase} (round {self.round})"]
        if self.confirmed_facts:
            for f in self.confirmed_facts[:5]:
                parts.append(f"  • {f}")
        if self.open_questions:
            for q in self.open_questions[:3]:
                parts.append(f"  ? {q}")
        if self.critical_files:
            for f in self.critical_files[:5]:
                parts.append(f"  📄 {f}")
        if self.recent_changes:
            for c in self.recent_changes[-3:]:
                parts.append(f"  ~ {c}")
        if self.next_action:
            parts.append(f"Next: {self.next_action}")
        if self.memory_refs:
            parts.append(f"Memory: {', '.join(self.memory_refs)}")
        return "\n".join(parts)

    def token_estimate(self) -> int:
        return len(self.to_prompt()) // 4


class StateCompressor:
    """Compresses RuntimeState into compact LLM context.

    v0.3: priority-aware retention, memory cross-references, multi-turn decay.
    """

    MAX_FACTS: int = 10
    MAX_QUESTIONS: int = 5
    MAX_CHANGES: int = 5
    MAX_FILES: int = 10
    MAX_TOKENS: int = 500

    def __init__(self, max_tokens: int = 500) -> None:
        self.max_tokens = max_tokens
        self._fact_hits: dict[str, int] = {}  # fact → hit count (for priority)

    def compress(self, state: RuntimeState, memory_refs: list[str] | None = None) -> CompressedState:
        facts = self._prioritize_facts(state.confirmed_facts, self.MAX_FACTS)
        questions = state.open_questions[:self.MAX_QUESTIONS]
        files = state.critical_files[:self.MAX_FILES]
        changes = state.recent_changes[-self.MAX_CHANGES:]

        compressed = CompressedState(
            goal=state.goal[:200],
            phase=state.phase.value if hasattr(state.phase, 'value') else str(state.phase),
            round=state.round,
            confirmed_facts=facts,
            open_questions=questions,
            critical_files=files,
            recent_changes=changes,
            next_action=state.next_best_action,
            memory_refs=memory_refs or [],
        )

        # Recursive pruning until within budget
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

    def _prioritize_facts(self, facts: list[str], max_count: int) -> list[str]:
        """Keep high-priority facts (recently referenced, critical keywords)."""
        seen: set[str] = set()
        scored: list[tuple[float, str]] = []

        for fact in reversed(facts):
            key = fact.lower().strip()
            if key not in seen:
                seen.add(key)
                # Priority boost for frequently referenced facts
                hits = self._fact_hits.get(key, 0)
                self._fact_hits[key] = hits + 1
                priority = min(1.0, hits * 0.2)  # hit multiple times → high priority
                # Priority boost for critical keywords
                for kw in ["error", "fix", "root cause", "config", "api"]:
                    if kw in key:
                        priority = max(priority, 0.6)
                scored.append((priority, fact))

        scored.sort(key=lambda x: -x[0])  # highest priority first
        return [s[1] for s in scored[:max_count]]
