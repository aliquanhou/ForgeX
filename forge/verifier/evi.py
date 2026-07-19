"""EVI — Evidence Intelligence Engine (v2).

Formula: EVI = ΔInfo + ΔProgress + ΔRiskReduction - α·Cost

This is the quantitative feedback that enables the runtime to make
informed decisions about whether to continue, retry, or pivot.

V2 upgrades:
- Cost dimension: every tool call has a cost (tokens, time, risk)
- Risk reduction: did the action reduce uncertainty?
- Better heuristics per tool type
- Normalized scoring (0.0 - 1.0)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


# Cost constants (approximate, in "EVI points")
COST_READ_SMALL = 0.05   # < 1KB file
COST_READ_LARGE = 0.30   # > 100KB file
COST_WRITE = 0.15        # file write
COST_EXECUTE = 0.25      # shell command
COST_GREP = 0.10         # search
COST_GLOB = 0.05         # file listing
COST_GIT = 0.10          # git operation
COST_SEARCH_SYMBOL = 0.08

# Alpha: how much cost penalizes the score
COST_PENALTY_ALPHA = 1.0  # 1.0 = cost subtracted directly


@dataclass
class EVIResult:
    """Result of an EVI evaluation."""

    score: float  # 0.0 - 1.0 (composite)
    info_gain: float  # How much new information?
    progress: float  # How much closer to goal?
    risk_reduction: float  # How much uncertainty reduced?
    cost: float  # How expensive was this action?
    reasoning: str = ""
    breakdown: dict[str, float] = field(default_factory=dict)

    @property
    def low_value(self) -> bool:
        return self.score < 0.2

    @property
    def high_value(self) -> bool:
        return self.score > 0.7

    @property
    def cost_effective(self) -> bool:
        """Was the info gained worth the cost?"""
        benefit = self.info_gain + self.progress + self.risk_reduction
        return benefit > self.cost


class EVIEngine:
    """Evidence Intelligence Engine v2.

    Formula: EVI = ΔInfo + ΔProgress + ΔRiskReduction - α·Cost

    Evaluates tool call outputs and assigns an EVI score.
    This score feeds into the Decision Engine and Budget Manager.
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

        Args:
            tool_name: Name of the tool that was called
            tool_input: Arguments passed to the tool
            tool_output: Result from the tool
            open_questions: Current open questions in the state

        Returns:
            EVIResult with new 4-dimension scoring
        """
        # Score each dimension
        info_gain, progress, risk_reduction = self._score_dimensions(
            tool_name, tool_input, tool_output, open_questions
        )
        cost = self._estimate_cost(tool_name, tool_input, tool_output)

        # Composite: benefit - penalty
        benefit = info_gain + progress + risk_reduction
        raw_score = benefit - (COST_PENALTY_ALPHA * cost)

        # Clamp to [0.0, 1.0]
        score = max(0.0, min(1.0, raw_score))

        result = EVIResult(
            score=round(score, 3),
            info_gain=round(info_gain, 3),
            progress=round(progress, 3),
            risk_reduction=round(risk_reduction, 3),
            cost=round(cost, 3),
            reasoning=self._build_reasoning(tool_name, score, info_gain, progress, risk_reduction, cost),
            breakdown={
                "info_gain": round(info_gain, 3),
                "progress": round(progress, 3),
                "risk_reduction": round(risk_reduction, 3),
                "cost": round(cost, 3),
                "benefit": round(benefit, 3),
                "raw_score": round(raw_score, 3),
                "cost_effective": benefit > cost,
            },
        )

        self._history.append(result)
        return result

    def _score_dimensions(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: Any,
        open_questions: list[str],
    ) -> tuple[float, float, float]:
        """Score the three benefit dimensions."""
        output_dict = tool_output if isinstance(tool_output, dict) else {}
        error = output_dict.get("error", "")

        info_gain = 0.0
        progress = 0.0
        risk_reduction = 0.0

        # ---- Errors ----
        if error:
            info_gain = 0.6  # Error messages have high info value
            progress = 0.0   # But don't move forward
            risk_reduction = 0.0
            return (info_gain, progress, risk_reduction)

        # ---- Tool-specific scoring ----
        if tool_name == "read_file":
            content = output_dict.get("content", "")
            size = len(content) if isinstance(content, str) else 0
            total_lines = output_dict.get("total_lines", 0)

            if total_lines == 0:
                info_gain = 0.0
                progress = 0.0
            elif total_lines > 500:
                info_gain = max(0.1, 0.4 - (total_lines / 5000 * 0.3))  # diminishing returns
                progress = 0.3
            else:
                info_gain = min(0.6, total_lines / 100 * 0.15)
                progress = 0.5

            # Check if any open question text appears in content
            if open_questions and content:
                content_lower = content.lower()
                for q in open_questions:
                    keywords = q.lower().split()[:3]
                    if any(kw in content_lower for kw in keywords):
                        risk_reduction = max(risk_reduction, 0.7)

        elif tool_name in ("grep", "search"):
            matches = output_dict.get("matches", []) if isinstance(output_dict.get("matches"), list) else []
            count = len(matches)

            if count == 0:
                info_gain = 0.1  # Knowing something is NOT found is still info
                progress = 0.2
            elif count <= 3:
                info_gain = 0.8  # Precise matches are highly informative
                progress = 0.7
                risk_reduction = 0.6
            elif count <= 20:
                info_gain = 0.5  # Some matches, still useful
                progress = 0.5
            else:
                info_gain = 0.3  # Too many matches = noise
                progress = 0.3

        elif tool_name in ("write_file", "create_file"):
            bytes_written = output_dict.get("bytes", 0) if isinstance(output_dict.get("bytes"), (int, float)) else 0
            info_gain = 0.2  # Writing doesn't generate new info
            progress = 0.8   # But makes significant progress
            risk_reduction = 0.3

            if bytes_written == 0:
                progress = 0.0

        elif tool_name == "edit_file":
            modified = output_dict.get("modified", False) if isinstance(output_dict.get("modified"), bool) else False
            if modified:
                info_gain = 0.2
                progress = 0.7
                risk_reduction = 0.2
            else:
                info_gain = 0.3  # "nothing changed" is useful info
                progress = 0.0

        elif tool_name == "execute":
            exit_code = output_dict.get("exit_code") if isinstance(output_dict.get("exit_code"), int) else None
            stdout = output_dict.get("stdout", "")
            stderr = output_dict.get("stderr", "")

            if exit_code == 0:
                info_gain = min(0.6, len(stdout) / 5000 * 0.3) if stdout else 0.2
                progress = 0.7
                risk_reduction = 0.4
            elif exit_code is not None:
                info_gain = 0.7  # Errors are informative
                progress = 0.1
                risk_reduction = 0.2
            else:
                info_gain = 0.0

        elif tool_name in ("git_status", "git_diff", "git_log"):
            info_gain = 0.5
            progress = 0.3
            risk_reduction = 0.6

        elif tool_name == "git_commit":
            commit_hash = output_dict.get("hash", "")
            info_gain = 0.1
            progress = 0.9
            risk_reduction = 0.8  # Commit = safe checkpoint

        elif tool_name in ("glob", "list_dir"):
            entries = output_dict.get("entries") or output_dict.get("files") or []
            count = len(entries) if isinstance(entries, list) else 0
            info_gain = min(0.4, count * 0.05)
            progress = 0.3
            risk_reduction = 0.2

        elif tool_name == "find_symbol":
            definitions = output_dict.get("definitions", []) if isinstance(output_dict.get("definitions"), list) else []
            count = len(definitions)
            if count > 0:
                info_gain = 0.7
                progress = 0.6
                risk_reduction = 0.5
            else:
                info_gain = 0.1

        else:
            # Unknown tool — conservative estimate
            info_gain = 0.2
            progress = 0.2
            risk_reduction = 0.1

        return (info_gain, progress, risk_reduction)

    def _estimate_cost(self, tool_name: str, tool_input: dict[str, Any], tool_output: Any) -> float:
        """Estimate the cost of a tool call.

        Cost includes: tokens spent on context, time, risk of side effects.
        """
        base_costs = {
            "read_file": COST_READ_SMALL,
            "write_file": COST_WRITE,
            "create_file": COST_WRITE,
            "edit_file": COST_WRITE,
            "execute": COST_EXECUTE,
            "grep": COST_GREP,
            "glob": COST_GLOB,
            "list_dir": COST_GLOB,
            "find_symbol": COST_SEARCH_SYMBOL,
            "git_status": COST_GIT,
            "git_diff": COST_GIT,
            "git_log": COST_GIT,
            "git_commit": COST_GIT,
        }

        base = base_costs.get(tool_name, 0.15)

        # Scale by output size (larger output = more tokens = higher cost)
        if isinstance(tool_output, dict):
            content = tool_output.get("content", "")
            if isinstance(content, str) and len(content) > 10000:
                base += 0.2  # Large output penalty

            stdout = tool_output.get("stdout", "")
            if isinstance(stdout, str) and len(stdout) > 10000:
                base += 0.2

        # Risk premium for write operations
        if tool_name in ("write_file", "edit_file", "create_file"):
            base += 0.1  # Risk of breaking things

        # Risk premium for git operations that modify history
        if tool_name == "git_commit":
            base += 0.05

        return min(1.0, base)  # Cap at 1.0

    def _build_reasoning(
        self, tool_name: str, score: float,
        info: float, progress: float, risk: float, cost: float
    ) -> str:
        benefit = info + progress + risk
        cost_effectiveness = "cost-effective" if benefit > cost else "cost-inefficient"
        return (
            f"{tool_name}: info={info:.2f} progress={progress:.2f} risk={risk:.2f} cost={cost:.2f} "
            f"→ score={score:.2f} ({cost_effectiveness})"
        )

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
