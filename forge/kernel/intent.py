"""Intent Classifier — determines what kind of task the user wants.

This runs BEFORE any planning or execution.
It's a cheap, fast classification that sets the entire downstream behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IntentType(str, Enum):
    """The type of intent Forge can handle."""

    CHAT = "chat"
    """General Q&A, no code modification needed."""

    CODE_MODIFY = "code_modify"
    """Implement a feature, fix a bug, refactor code."""

    DEBUG = "debug"
    """Investigate a failure, find root cause, propose fix."""

    RESEARCH = "research"
    """Explore the codebase to understand how something works."""

    REVIEW = "review"
    """Review code for quality, security, correctness."""

    REPORT = "report"
    """Generate a documentation or analysis report."""


# Keywords that strongly suggest an intent
_INTENT_KEYWORDS: dict[IntentType, list[str]] = {
    IntentType.CHAT: ["think", "opinion", "explain", "general"],
    IntentType.CODE_MODIFY: ["implement", "add", "create", "write code", "fix", "change", "update", "refactor"],
    IntentType.DEBUG: ["error", "bug", "crash", "fail", "not working", "wrong", "broken", "issue"],
    IntentType.RESEARCH: ["understand", "how does", "what does", "find", "locate", "search", "explore", "architecture"],
    IntentType.REVIEW: ["review", "audit", "check", "inspect", "quality"],
    IntentType.REPORT: ["document", "report", "summary", "writeup", "explain"],
}


@dataclass
class IntentResult:
    """Result of intent classification."""

    intent: IntentType
    confidence: float  # 0.0 - 1.0
    reason: str = ""
    extracted_goal: str = ""
    extracted_files: list[str] = field(default_factory=list)

    @property
    def requires_code(self) -> bool:
        """Does this intent require write access to the filesystem?"""
        return self.intent in (
            IntentType.CODE_MODIFY,
            IntentType.DEBUG,
            IntentType.REVIEW,
        )

    @property
    def requires_execution(self) -> bool:
        """Does this intent need to run commands/shell?"""
        return self.intent in (IntentType.CODE_MODIFY, IntentType.DEBUG, IntentType.REVIEW)


class IntentClassifier:
    """Classifies user input into an IntentType.

    Uses a simple keyword + heuristic approach for the initial fast path.
    The LLM-based deep classifier is in planner.py.
    """

    def classify(self, user_input: str) -> IntentResult:
        """Classify intent based on user input.

        Returns a best-guess intent. The deep planner refines this later.
        """
        text = user_input.lower().strip()

        # Score each intent type
        scores: dict[IntentType, float] = {}
        for intent, keywords in _INTENT_KEYWORDS.items():
            score = 0.0
            for kw in keywords:
                if kw in text:
                    score += 1.0
            if score > 0:
                scores[intent] = score / len(keywords)  # normalize

        if not scores:
            return IntentResult(
                intent=IntentType.CHAT,
                confidence=0.5,
                reason="No specific intent keywords found; defaulting to chat.",
                extracted_goal=user_input,
            )

        best = max(scores, key=scores.get)
        confidence = min(scores[best] + 0.3, 1.0)

        return IntentResult(
            intent=best,
            confidence=confidence,
            reason=f"Matched {len(scores)} intent patterns; best={best.value}",
            extracted_goal=user_input,
        )

    def extract_files(self, user_input: str) -> list[str]:
        """Heuristic: extract potential file paths from user input."""
        import re

        # Match paths like path/to/file.py, ./src/main.rs, etc.
        pattern = r'(?:[.\w]+/[\w./-]+\.[a-zA-Z]+)'
        return list(set(re.findall(pattern, user_input)))
