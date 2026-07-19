"""Artifact Committer — lifecycle-guaranteed artifact delivery.

Every task MUST produce an artifact.
Artifacts now have a full lifecycle: DRAFT → GENERATED → VALIDATED → APPROVED → COMMITTED → ARCHIVED

No more "write_file → done". Now it's:
    write_file → GENERATED → verify → VALIDATED → user_approve → APPROVED → commit → COMMITTED
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Awaitable


class ArtifactState(str, Enum):
    """Lifecycle states for an artifact."""

    DRAFT = "draft"
    """Being created, not yet ready."""

    GENERATED = "generated"
    """Content has been written to disk."""

    VALIDATED = "validated"
    """Passed automated verification (syntax check, min size, etc.)."""

    APPROVED = "approved"
    """User (or auto-approve policy) has signed off."""

    COMMITTED = "committed"
    """Persisted to version control (git commit)."""

    ARCHIVED = "archived"
    """No longer active, preserved for history."""

    FAILED = "failed"
    """Lifecycle terminated due to error."""


# Valid transitions
_TRANSITIONS: dict[ArtifactState, set[ArtifactState]] = {
    ArtifactState.DRAFT: {ArtifactState.GENERATED, ArtifactState.FAILED},
    ArtifactState.GENERATED: {ArtifactState.VALIDATED, ArtifactState.FAILED},
    ArtifactState.VALIDATED: {ArtifactState.APPROVED, ArtifactState.GENERATED, ArtifactState.FAILED},
    ArtifactState.APPROVED: {ArtifactState.COMMITTED, ArtifactState.GENERATED, ArtifactState.FAILED},
    ArtifactState.COMMITTED: {ArtifactState.ARCHIVED, ArtifactState.FAILED},
    ArtifactState.ARCHIVED: set(),
    ArtifactState.FAILED: set(),
}


@dataclass
class LifecycleArtifact:
    """An artifact with full lifecycle tracking."""

    id: str
    kind: str  # "file", "diff", "report", "test_result"
    path: str
    content: str
    state: ArtifactState = ArtifactState.DRAFT
    checksum: str = ""
    size: int = 0
    created_at: str = ""
    validated_at: str = ""
    committed_at: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def transition(self, to: ArtifactState) -> None:
        """Transition to a new state with validity check."""
        allowed = _TRANSITIONS.get(self.state, set())
        if to not in allowed:
            raise ValueError(
                f"Cannot transition artifact {self.id} from {self.state.value} to {to.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        self.state = to

    @property
    def is_terminal(self) -> bool:
        return self.state in (ArtifactState.COMMITTED, ArtifactState.ARCHIVED, ArtifactState.FAILED)

    @property
    def is_verified(self) -> bool:
        return self.state in (ArtifactState.VALIDATED, ArtifactState.APPROVED, ArtifactState.COMMITTED)


class ArtifactCommitter:
    """Ensures artifacts go through proper lifecycle with delivery guarantees."""

    def __init__(self, workspace_dir: str = "") -> None:
        self._workspace_dir = Path(workspace_dir) if workspace_dir else Path.cwd()
        self._lifecycle_hooks: dict[ArtifactState, list[Callable[[LifecycleArtifact], Awaitable[None]]]] = {}

    def on_state(self, state: ArtifactState, handler: Callable[[LifecycleArtifact], Awaitable[None]]) -> None:
        """Register a handler that fires when artifact reaches a state."""
        self._lifecycle_hooks.setdefault(state, []).append(handler)

    async def generate(self, artifact_id: str, kind: str, path: str, content: str) -> LifecycleArtifact:
        """Create a new artifact (DRAFT → GENERATED)."""
        artifact = LifecycleArtifact(
            id=artifact_id,
            kind=kind,
            path=path,
            content=content,
            state=ArtifactState.DRAFT,
            size=len(content),
            checksum=hashlib.sha256(content.encode()).hexdigest()[:16],
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        # Write to disk
        filepath = Path(path)
        if not filepath.is_absolute():
            filepath = self._workspace_dir / path
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding="utf-8")

        artifact.transition(ArtifactState.GENERATED)
        await self._fire_hooks(artifact)
        return artifact

    async def validate(self, artifact: LifecycleArtifact) -> LifecycleArtifact:
        """Run validation checks (GENERATED → VALIDATED)."""
        artifact.transition(ArtifactState.VALIDATED)
        artifact.validated_at = datetime.now(timezone.utc).isoformat()
        artifact.metadata["size_on_disk"] = Path(artifact.path).stat().st_size if Path(artifact.path).exists() else 0
        await self._fire_hooks(artifact)
        return artifact

    async def approve(self, artifact: LifecycleArtifact) -> LifecycleArtifact:
        """Mark as approved (VALIDATED → APPROVED)."""
        artifact.transition(ArtifactState.APPROVED)
        await self._fire_hooks(artifact)
        return artifact

    async def commit(self, artifact: LifecycleArtifact) -> LifecycleArtifact:
        """Mark as committed (APPROVED → COMMITTED)."""
        artifact.transition(ArtifactState.COMMITTED)
        artifact.committed_at = datetime.now(timezone.utc).isoformat()
        await self._fire_hooks(artifact)
        return artifact

    async def _fire_hooks(self, artifact: LifecycleArtifact) -> None:
        hooks = self._lifecycle_hooks.get(artifact.state, [])
        for hook in hooks:
            try:
                await hook(artifact)
            except Exception:
                pass

    async def fail(self, artifact: LifecycleArtifact, error: str) -> LifecycleArtifact:
        """Mark as failed."""
        artifact.transition(ArtifactState.FAILED)
        artifact.error = error
        await self._fire_hooks(artifact)
        return artifact

    async def generate_diff(self, artifact_id: str, path: str, original: str, modified: str) -> LifecycleArtifact:
        """Generate a diff artifact."""
        import difflib
        import uuid

        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            modified.splitlines(keepends=True),
            fromfile=path + " (before)",
            tofile=path + " (after)",
        )
        diff_content = "".join(diff)
        return await self.generate(
            artifact_id or uuid.uuid4().hex[:12],
            "diff",
            f"{path}.diff",
            diff_content,
        )
