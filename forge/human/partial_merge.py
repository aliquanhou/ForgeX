"""Partial Merge — apply only approved parts of a change set.

Enables the human to say: "Approve the bugfix, reject the refactor."
Without this, the only options are "accept all" or "reject all".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class MergeDecision(str, Enum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    MODIFY = "modify"


@dataclass
class MergeChunk:
    """A single contiguous chunk of a diff that can be independently accepted."""

    file_path: str
    start_line: int
    end_line: int
    content: str  # the code
    decision: MergeDecision = MergeDecision.INCLUDE
    label: str = ""  # human-readable label for this chunk
    reason: str = ""  # why this chunk exists

    @property
    def is_selected(self) -> bool:
        return self.decision == MergeDecision.INCLUDE


@dataclass
class PartialMergeResult:
    """Result of a partial merge operation."""

    original_file: str
    output_file: str
    included_chunks: int = 0
    excluded_chunks: int = 0
    has_conflicts: bool = False
    warnings: list[str] = field(default_factory=list)


class PartialMerge:
    """Applies only selected chunks of a change set.

    Usage:
        merger = PartialMerge()
        chunks = merger.chunk_diff(diff_text, "app/models.py")
        # User marks chunk[1] as EXCLUDE
        result = merger.apply_chunks("app/models.py", chunks, output_path="app/models.py.new")
    """

    def chunk_diff(self, diff_text: str, file_path: str) -> list[MergeChunk]:
        """Split a unified diff into independently selectable chunks.

        Each hunk in the diff becomes a MergeChunk.
        """
        import re

        chunks: list[MergeChunk] = []
        current_lines: list[str] = []
        current_start = 0
        current_end = 0

        for line in diff_text.splitlines(keepends=True):
            # Hunk header: @@ -a,b +c,d @@
            hunk_match = re.match(r'^@@ -(\d+),?\d* \+(\d+),?\d* @@(.*)', line)
            if hunk_match:
                # Save previous chunk
                if current_lines and current_start > 0:
                    chunks.append(MergeChunk(
                        file_path=file_path,
                        start_line=current_start,
                        end_line=current_end,
                        content="".join(current_lines),
                        label=f"Lines {current_start}-{current_end}",
                    ))

                current_lines = [line]
                current_start = int(hunk_match.group(2))  # new file line number
                current_end = current_start
            elif current_lines:
                current_lines.append(line)
                if line.startswith("+") or line.startswith(" "):
                    current_end += 1

        # Last chunk
        if current_lines and current_start > 0:
            chunks.append(MergeChunk(
                file_path=file_path,
                start_line=current_start,
                end_line=current_end,
                content="".join(current_lines),
                label=f"Lines {current_start}-{current_end}",
            ))

        return chunks

    def apply_chunks(
        self,
        file_path: str,
        chunks: list[MergeChunk],
        output_path: str = "",
        dry_run: bool = False,
    ) -> PartialMergeResult:
        """Apply only selected chunks to a file.

        Args:
            file_path: Original file to modify
            chunks: Chunks with decisions
            output_path: Where to write the result (defaults to original file)
            dry_run: If True, don't write, only compute result

        Returns:
            PartialMergeResult with stats
        """
        path = Path(file_path)
        if not path.exists():
            return PartialMergeResult(
                original_file=file_path,
                output_file=output_path or file_path,
                warnings=[f"File not found: {file_path}"],
            )

        result = PartialMergeResult(
            original_file=file_path,
            output_file=output_path or file_path,
        )

        included = [c for c in chunks if c.decision == MergeDecision.INCLUDE]
        excluded = [c for c in chunks if c.decision == MergeDecision.EXCLUDE]
        result.included_chunks = len(included)
        result.excluded_chunks = len(excluded)

        if not included:
            result.warnings.append("No chunks selected — file will not be modified")
            return result

        if dry_run:
            return result

        # Read original content
        original = path.read_text(encoding="utf-8", errors="replace")
        lines = original.splitlines(keepends=True)

        # Apply included chunks in reverse order (to preserve line numbers)
        for chunk in sorted(included, key=lambda c: -c.start_line):
            # Parse the chunk to find what to replace
            new_lines = self._extract_new_content(chunk.content)
            if new_lines:
                old_start = chunk.start_line - 1  # 0-indexed
                old_end = chunk.end_line - 1
                lines[old_start:old_end] = new_lines

        output = Path(result.output_file)
        output.write_text("".join(lines), encoding="utf-8")
        return result

    def _extract_new_content(self, hunk_text: str) -> list[str] | None:
        """Extract the new file content from a diff hunk.

        Lines starting with '+' are additions.
        Lines starting with ' ' are context (included).
        Lines starting with '-' are removals (skipped).
        """
        new_lines: list[str] = []
        has_content = False

        for line in hunk_text.splitlines(keepends=True):
            if line.startswith("+") and not line.startswith("+++"):
                new_lines.append(line[1:])  # Added line
                has_content = True
            elif line.startswith(" ") and not line.startswith("@@ "):
                new_lines.append(line[1:])  # Context line
                has_content = True
            # '-' lines are simply omitted

        return new_lines if has_content else None
