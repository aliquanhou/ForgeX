"""EVI — Evidence Intelligence Engine.

EVI measures how much useful information each tool call produces.
This is the quantitative feedback that enables the runtime to make
informed decisions about whether to continue, retry, or pivot.

A core piece of the Forge moat.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EVIResult:
    """Result of an EVI evaluation."""

    score: float  # 0.0 - 1.0
    novel_info: float  # Did we learn something new?
    progress: float  # Did we move toward the goal?
    resolution: float  # Did we answer an open question?
    quality: float  # Is the information reliable?
    reasoning: str = ""

    @property
    def low_value(self) -> bool:
        return self.score < 0.2

    @property
    def high_value(self) -> bool:
        return self.score > 0.7


class EVIEngine:
    """Evidence Intelligence Engine.

    Evaluates tool call outputs and assigns an EVI score.
    This score feeds into the budget manager and scheduler.
    """

    def __init__(self, low_gain_threshold: float = 0.15, force_finalize_streak: int = 3) -> None:
        self.low_gain_threshold = low_gain_threshold
        self.force_finalize_streak = force_finalize_streak
        self._history: list[EVIResult] = []

    def evaluate(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: Any,
        open_questions: list[str],
    ) -> EVIResult:
        """Evaluate the evidence value of a tool call.

        This is a heuristic EVI scorer. For LLM-based EVI, use evaluate_llm().

        Args:
            tool_name: Name of the tool that was called
            tool_input: Arguments passed to the tool
            tool_output: Result from the tool
            open_questions: Current open questions in the state

        Returns:
            EVIResult with scores
        """
        # Default scores
        novel = 0.0
        progress = 0.0
        resolution = 0.0
        quality = 0.5

        # Heuristic scoring per tool type
        if isinstance(tool_output, dict):
            # Check for errors — errors are useful information
            if tool_output.get("error"):
                novel = 0.7  # Error messages are valuable
                quality = 0.8
                reasoning = f"Produced diagnostic error info"
            else:
                # Search tools that return matches
                matches = tool_output.get("matches") or tool_output.get("files") or []
                count = tool_output.get("count", 0) or len(matches) if isinstance(matches, list) else 0

                if count > 0:
                    novel = min(0.3 + (count * 0.05), 0.9)
                    progress = 0.6
                    quality = 0.7
                    reasoning = f"Found {count} results"
                elif tool_output.get("content"):
                    content = tool_output["content"]
                    content_len = len(content) if isinstance(content, str) else 0
                    if content_len > 100:
                        novel = 0.6
                        progress = 0.7
                        quality = 0.8
                        reasoning = f"Read {content_len} chars of content"
                    else:
                        novel = 0.2
                        progress = 0.2
                        reasoning = "Content too short to be useful"
                else:
                    novel = 0.1
                    reasoning = "No meaningful output"

        # Tool-specific heuristics
        if tool_name == "read_file":
            novel = max(novel, 0.4)
            progress = max(progress, 0.5)

        elif tool_name in ("write_file", "edit_file"):
            novel = max(novel, 0.3)
            progress = max(progress, 0.8)
            quality = max(quality, 0.9)

        elif tool_name == "execute":
            exit_code = None
            if isinstance(tool_output, dict):
                exit_code = tool_output.get("exit_code")
            if exit_code == 0:
                progress = max(progress, 0.6)
                quality = max(quality, 0.7)
            elif exit_code is not None:
                novel = max(novel, 0.5)
                progress = max(progress, 0.3)

        # Check if any open questions were resolved
        if open_questions and isinstance(tool_output, dict):
            output_text = str(tool_output).lower()
            for q in open_questions:
                q_lower = q.lower()[:30]
                if q_lower in output_text:
                    resolution = max(resolution, 0.8)
                    break

        composite = (novel * 0.3 + progress * 0.3 + resolution * 0.2 + quality * 0.2)

        result = EVIResult(
            score=round(composite, 3),
            novel_info=round(novel, 3),
            progress=round(progress, 3),
            resolution=round(resolution, 3),
            quality=round(quality, 3),
            reasoning=reasoning or "Heuristic EVI score",
        )

        self._history.append(result)
        return result

    @property
    def recent_scores(self) -> list[float]:
        return [r.score for r in self._history[-5:]]

    @property
    def low_value_streak(self) -> int:
        """Count consecutive low-value actions."""
        streak = 0
        for r in reversed(self._history):
            if r.low_value:
                streak += 1
            else:
                break
        return streak

    @property
    def should_force_finalize(self) -> bool:
        """Should we force finalization due to sustained low value?"""
        return self.low_value_streak >= self.force_finalize_streak
