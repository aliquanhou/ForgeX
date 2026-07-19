"""Artifact Committer — the module that guarantees delivery.

Every task MUST produce an artifact.
The ArtifactCommitter ensures that what the agent claims to have done
actually exists on disk and meets quality criteria.

This is one of the 4 moat modules.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from forge.kernel.state import Artifact


@dataclass
class DeliveryGuarantee:
    """Quality guarantees for an artifact."""

    file_exists: bool = False
    minimum_size: bool = False
    required_sections: bool = False
    checksum_match: bool = False

    @property
    def all_met(self) -> bool:
        return all([self.file_exists, self.minimum_size])


class ArtifactCommitter:
    """Ensures artifacts are properly created and verified.

    This is what makes the "task is not done until artifact exists" principle real.
    """

    def __init__(self, workspace_dir: str = "") -> None:
        self._workspace_dir = Path(workspace_dir) if workspace_dir else Path.cwd()

    async def commit(
        self,
        artifact_type: str,
        path: str,
        content: str,
        min_size: int = 1,
        verify: bool = True,
    ) -> Artifact:
        """Create an artifact with delivery guarantees.

        Args:
            artifact_type: Type of artifact
            path: Where to write it
            content: Content to write
            min_size: Minimum size in bytes
            verify: Whether to verify after writing

        Returns:
            Artifact with verification status
        """
        filepath = Path(path)
        if not filepath.is_absolute():
            filepath = self._workspace_dir / path

        # Write
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding="utf-8")

        # Compute checksum
        checksum = hashlib.sha256(content.encode()).hexdigest()[:16]

        # Verify
        guarantee = DeliveryGuarantee()
        if verify:
            guarantee.file_exists = filepath.exists()
            guarantee.minimum_size = filepath.stat().st_size >= min_size

        artifact = Artifact(
            kind=artifact_type,
            path=str(filepath),
            checksum=checksum,
            verified=guarantee.all_met,
            metadata={
                "size": len(content),
                "min_size": min_size,
                "delivery_guarantee": {
                    "file_exists": guarantee.file_exists,
                    "minimum_size": guarantee.minimum_size,
                },
            },
        )

        return artifact

    async def commit_diff(
        self, path: str, original: str, modified: str
    ) -> Artifact:
        """Create a diff artifact from before/after content."""
        import difflib

        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            modified.splitlines(keepends=True),
            fromfile=path + " (before)",
            tofile=path + " (after)",
        )
        diff_content = "".join(diff)
        return await self.commit("diff", f"{path}.diff", diff_content, min_size=1)

    async def commit_report(
        self, path: str, content: str
    ) -> Artifact:
        """Create a report artifact."""
        return await self.commit("report", path, content, min_size=100)

    async def commit_file_change(
        self, path: str, content: str, original_content: str = ""
    ) -> list[Artifact]:
        """Create artifacts for a file change — the file itself + diff.

        Returns [file_artifact, diff_artifact] or [file_artifact] if no original.
        """
        artifacts = []
        file_artifact = await self.commit("file", path, content)
        artifacts.append(file_artifact)

        if original_content and original_content != content:
            diff_artifact = await self.commit_diff(path, original_content, content)
            artifacts.append(diff_artifact)

        return artifacts
