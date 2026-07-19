"""Episodic Memory — cross-session task experience storage.

Stores complete task episodes with:
- Goal, phases, key decisions
- Problems encountered and solutions found
- Artifacts produced
- Success/failure outcome

Enables similarity-based retrieval: "Has this task been done before?"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass
class EpisodeDecision:
    """A key decision made during the episode."""
    round: int
    action: str
    reason: str
    evi_score: float
    outcome: str


@dataclass
class EpisodeArtifact:
    """Artifact produced during the episode."""
    kind: str
    path: str
    verified: bool


@dataclass
class Episode:
    """A complete record of a task execution episode."""

    id: str
    goal: str
    intent: str
    success: bool
    total_rounds: int
    started_at: str
    finished_at: str = ""
    phases: list[str] = field(default_factory=list)
    key_files: list[str] = field(default_factory=list)
    decisions: list[EpisodeDecision] = field(default_factory=list)
    artifacts: list[EpisodeArtifact] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @classmethod
    def create(cls, goal: str, intent: str = "") -> Episode:
        return cls(
            id=uuid.uuid4().hex[:12],
            goal=goal,
            intent=intent,
            success=False,
            total_rounds=0,
            started_at=datetime.now(timezone.utc).isoformat(),
        )


@dataclass
class EpisodeQuery:
    """Query for retrieving similar episodes."""
    goal_keywords: list[str] = field(default_factory=list)
    intent: str = ""
    max_results: int = 3
    min_similarity: float = 0.3


class EpisodicMemory:
    """Cross-session memory of task episodes.

    Stores, indexes, and retrieves task experiences.
    Enables the agent to learn from past successes and failures.
    """

    def __init__(self) -> None:
        self._episodes: list[Episode] = []
        self._max_episodes: int = 100

    def record(self, episode: Episode) -> None:
        """Store an episode."""
        if not episode.finished_at:
            episode.finished_at = datetime.now(timezone.utc).isoformat()
        self._episodes.append(episode)
        if len(self._episodes) > self._max_episodes:
            self._episodes = self._episodes[-self._max_episodes:]

    def search(self, query: EpisodeQuery) -> list[Episode]:
        """Find similar episodes by keyword overlap."""
        scored: list[tuple[float, Episode]] = []

        for ep in self._episodes:
            score = self._similarity(ep, query)
            if score >= query.min_similarity:
                scored.append((score, ep))

        scored.sort(key=lambda x: -x[0])
        return [ep for _, ep in scored[:query.max_results]]

    def find_by_error(self, error_text: str) -> list[Episode]:
        """Find episodes containing a specific error."""
        error_lower = error_text.lower()
        matches = []
        for ep in self._episodes:
            for err in ep.errors:
                if error_lower in err.lower():
                    matches.append(ep)
                    break
        return matches[:5]

    def find_by_file(self, file_path: str) -> list[Episode]:
        """Find episodes that touched a specific file."""
        path_lower = file_path.lower()
        matches = []
        for ep in self._episodes:
            if any(path_lower in f.lower() for f in ep.key_files):
                matches.append(ep)
        return matches[:5]

    @property
    def total_episodes(self) -> int:
        return len(self._episodes)

    @property
    def success_rate(self) -> float:
        if not self._episodes:
            return 0.0
        return sum(1 for e in self._episodes if e.success) / len(self._episodes)

    @property
    def common_errors(self) -> list[tuple[str, int]]:
        """Return most common error patterns with counts."""
        from collections import Counter
        all_errors = [e.strip()[:60] for ep in self._episodes for e in ep.errors]
        return Counter(all_errors).most_common(5)

    def _similarity(self, episode: Episode, query: EpisodeQuery) -> float:
        """Compute keyword-based similarity between episode and query."""
        if not query.goal_keywords:
            return 0.0

        ep_text = (episode.goal + " " + " ".join(episode.tags)).lower()
        matches = sum(1 for kw in query.goal_keywords if kw.lower() in ep_text)
        score = matches / len(query.goal_keywords)

        # Bonus for matching intent
        if query.intent and query.intent == episode.intent:
            score += 0.2

        return min(1.0, score)

    def summary(self) -> dict[str, Any]:
        return {
            "total_episodes": self.total_episodes,
            "success_rate": round(self.success_rate, 3),
            "common_errors": self.common_errors[:3],
        }
