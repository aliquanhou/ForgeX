"""Change Explanation — structured, human-readable explanations of why changes are needed.

Answers the question every reviewer asks: "Why is this change necessary?"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChangeExplanation:
    """A structured explanation of a change."""

    what: str  # What is being changed (one line)
    why: str  # Why this change is needed
    how: str  # How the change works
    impact: str  # What the impact will be
    alternatives: list[str] = field(default_factory=list)  # What else was considered
    risks: list[str] = field(default_factory=list)  # Known risks
    evidence: list[str] = field(default_factory=list)  # Evidence supporting this change

    def to_text(self) -> str:
        """Format as a human-readable explanation."""
        parts = [
            f"## {self.what}",
            f"\n**Why:** {self.why}",
            f"\n**How:** {self.how}",
            f"\n**Impact:** {self.impact}",
        ]
        if self.alternatives:
            parts.append(f"\n**Alternatives considered:**")
            for a in self.alternatives:
                parts.append(f"- {a}")
        if self.risks:
            parts.append(f"\n**Risks:**")
            for r in self.risks:
                parts.append(f"- {r}")
        if self.evidence:
            parts.append(f"\n**Evidence:**")
            for e in self.evidence:
                parts.append(f"- {e}")
        return "\n".join(parts)

    def to_markdown(self) -> str:
        """Same as to_text but with full markdown formatting."""
        lines = self.to_text().split("\n")
        return "\n".join(lines)


class Explainer:
    """Generates structured explanations for code changes.

    Explains why Forge made the decisions it did.
    """

    def explain_edit(self, path: str, search: str, replace: str, reason: str) -> ChangeExplanation:
        """Explain a file edit change."""
        import difflib
        diff = "".join(difflib.unified_diff(
            search.splitlines(keepends=True),
            replace.splitlines(keepends=True),
            fromfile=path + " (before)",
            tofile=path + " (after)",
        ))

        return ChangeExplanation(
            what=f"Modify {path}",
            why=reason,
            how=self._infer_how(search, replace),
            impact=f"Changes {len(diff.splitlines())} lines in {path}",
            evidence=[f"Diff:\n```diff\n{diff[:500]}\n```"],
        )

    def explain_create(self, path: str, content: str, reason: str) -> ChangeExplanation:
        """Explain a file creation."""
        lines = content.splitlines()
        return ChangeExplanation(
            what=f"Create {path}",
            why=reason,
            how=f"New file with {len(lines)} lines",
            impact=f"Adds {path} to the project",
            evidence=[f"First line: `{lines[0][:80]}`" if lines else "Empty file"],
        )

    def explain_execute(self, command: str, reason: str, output: str = "") -> ChangeExplanation:
        """Explain a command execution."""
        return ChangeExplanation(
            what=f"Run: {command[:100]}",
            why=reason,
            how="Shell command execution",
            impact="May modify system state or produce output",
            evidence=[f"Output ({len(output)} chars)"] if output else [],
        )

    def _infer_how(self, search: str, replace: str) -> str:
        """Infer a natural language description of what changed."""
        if search == replace:
            return "No actual change (search == replace)"

        if search.strip() == "":
            return "Inserting new content"

        if replace.strip() == "":
            return "Removing existing content"

        search_lines = search.splitlines()
        replace_lines = replace.splitlines()

        if len(search_lines) == len(replace_lines):
            return f"Modified {len(search_lines)} line(s) in place"
        elif len(replace_lines) > len(search_lines):
            return f"Replaced {len(search_lines)} line(s) with {len(replace_lines)} line(s) (expansion)"
        else:
            return f"Replaced {len(search_lines)} line(s) with {len(replace_lines)} line(s) (contraction)"
