"""Workspace Manager — session-isolated workspaces for each task.

Every task gets its own:
- Working directory
- Environment variables
- File system sandbox
- Snapshot context

This prevents cross-task contamination and enables safe parallel execution.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class WorkspaceSession:
    """A single session with isolated workspace."""

    session_id: str
    root: Path
    env: dict[str, str]
    created_at: str = ""

    def resolve(self, path: str) -> Path:
        """Resolve a path within this workspace.

        Path traversal attacks: prevents access outside root.
        """
        p = (self.root / path).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise PermissionError(f"Path traversal blocked: {path} resolves outside workspace")
        return p

    def cleanup(self) -> None:
        """Remove the workspace directory."""
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)


class WorkspaceManager:
    """Manages isolated workspaces per session.

    Usage:
        mgr = WorkspaceManager(base_dir="/tmp/forge_workspaces")
        session = mgr.create_session()
        file_path = session.resolve("src/main.py")
        # All operations stay within session.root
    """

    def __init__(self, base_dir: str | None = None) -> None:
        self._base_dir = Path(base_dir) if base_dir else Path(tempfile.gettempdir()) / "forge_workspaces"
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, WorkspaceSession] = {}

    def create_session(self, env: dict[str, str] | None = None) -> WorkspaceSession:
        """Create a new isolated workspace session."""
        session_id = uuid.uuid4().hex[:12]
        session_dir = self._base_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # Copy current env + add session-specific vars
        session_env = os.environ.copy()
        session_env["FORGE_SESSION_ID"] = session_id
        session_env["FORGE_WORKSPACE"] = str(session_dir)
        if env:
            session_env.update(env)

        from datetime import datetime, timezone
        session = WorkspaceSession(
            session_id=session_id,
            root=session_dir,
            env=session_env,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> WorkspaceSession | None:
        return self._sessions.get(session_id)

    def destroy_session(self, session_id: str) -> None:
        """Clean up a session's workspace."""
        session = self._sessions.pop(session_id, None)
        if session:
            session.cleanup()

    def destroy_all(self) -> None:
        """Clean up all sessions."""
        for session_id in list(self._sessions.keys()):
            self.destroy_session(session_id)

    @property
    def active_sessions(self) -> int:
        return len(self._sessions)

    @property
    def base_dir(self) -> str:
        return str(self._base_dir)
