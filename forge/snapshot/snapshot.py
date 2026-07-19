"""Snapshot Manager — file-level state capture before any modification.

Every time the agent is about to modify a file, we snapshot it first.
This enables function-call-level rollback — not just git-level.

This is one of the 4 moat modules.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Snapshot:
    """A single snapshot — the state of a file at a point in time."""

    id: str
    file_path: str
    content: str
    checksum: str
    timestamp: float
    task_id: str = ""

    @classmethod
    def capture(cls, file_path: str, task_id: str = "") -> Snapshot | None:
        """Capture a snapshot of a file.

        Returns None if the file doesn't exist.
        """
        path = Path(file_path)
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8", errors="replace")
        return cls(
            id=uuid.uuid4().hex[:12],
            file_path=str(path.resolve()),
            content=content,
            checksum=hashlib.sha256(content.encode()).hexdigest()[:16],
            timestamp=os.times().elapsed if hasattr(os, 'times') else 0.0,
            task_id=task_id,
        )

    def restore(self) -> bool:
        """Restore the file to this snapshot's state.

        Returns True if successful.
        """
        try:
            path = Path(self.file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.content, encoding="utf-8")
            return True
        except Exception:
            return False


class SnapshotManager:
    """Manages snapshots for a task session.

    Every file modification should be preceded by a snapshot.
    This makes rollback trivial and safe.
    """

    def __init__(self, workspace_dir: str | None = None) -> None:
        self._snapshots: list[Snapshot] = []
        self._file_index: dict[str, list[Snapshot]] = {}  # file_path -> snapshots
        self._snapshot_dir: Path | None = None
        if workspace_dir:
            self._snapshot_dir = Path(workspace_dir) / ".forge_snapshots"
            self._snapshot_dir.mkdir(parents=True, exist_ok=True)

    def snapshot_before(self, file_path: str, task_id: str = "") -> Snapshot | None:
        """Capture a snapshot of a file before modification.

        Safe to call even if the file doesn't exist yet.
        """
        snap = Snapshot.capture(file_path, task_id)
        if snap is None:
            return None

        self._snapshots.append(snap)
        resolved = str(Path(file_path).resolve())
        if resolved not in self._file_index:
            self._file_index[resolved] = []
        self._file_index[resolved].append(snap)

        # Persist to disk if snapshot dir is configured
        if self._snapshot_dir:
            snap_file = self._snapshot_dir / f"{snap.id}.snap"
            snap_file.write_text(snap.content, encoding="utf-8")

        return snap

    def rollback_file(self, file_path: str) -> bool:
        """Rollback a single file to its most recent snapshot.

        Returns True if rollback succeeded.
        """
        resolved = str(Path(file_path).resolve())
        if resolved not in self._file_index or not self._file_index[resolved]:
            return False
        snap = self._file_index[resolved][-1]
        return snap.restore()

    def rollback_all(self) -> int:
        """Rollback ALL files to their most recent snapshot.

        Returns the number of files restored.
        """
        count = 0
        for resolved, snapshots in self._file_index.items():
            if snapshots:
                if snapshots[-1].restore():
                    count += 1
        return count

    def get_snapshot_count(self) -> int:
        return len(self._snapshots)

    def get_last_snapshot(self, file_path: str) -> Snapshot | None:
        resolved = str(Path(file_path).resolve())
        snaps = self._file_index.get(resolved, [])
        return snaps[-1] if snaps else None

    def clear(self) -> None:
        self._snapshots.clear()
        self._file_index.clear()
