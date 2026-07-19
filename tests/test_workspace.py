"""Tests for Workspace Manager."""

from pathlib import Path


class TestWorkspaceManager:
    """Session-isolated workspaces."""

    def test_create_session(self):
        from forge.workspace import WorkspaceManager

        mgr = WorkspaceManager()
        session = mgr.create_session()
        assert session.session_id
        assert session.root.exists()
        assert mgr.active_sessions == 1

    def test_resolve_path(self):
        from forge.workspace import WorkspaceManager

        mgr = WorkspaceManager()
        session = mgr.create_session()

        resolved = session.resolve("test.txt")
        assert str(resolved).startswith(str(session.root))
        assert resolved.name == "test.txt"

    def test_resolve_path_traversal_blocked(self):
        from forge.workspace import WorkspaceManager

        mgr = WorkspaceManager()
        session = mgr.create_session()

        import pytest
        with pytest.raises(PermissionError, match="Path traversal"):
            session.resolve("../etc/passwd")

    def test_multiple_sessions(self):
        from forge.workspace import WorkspaceManager

        mgr = WorkspaceManager()
        s1 = mgr.create_session()
        s2 = mgr.create_session()
        assert s1.session_id != s2.session_id
        assert mgr.active_sessions == 2

    def test_destroy_session(self):
        from forge.workspace import WorkspaceManager

        mgr = WorkspaceManager()
        session = mgr.create_session()
        root = session.root
        assert root.exists()

        mgr.destroy_session(session.session_id)
        assert mgr.active_sessions == 0
        assert not root.exists()

    def test_env_vars(self):
        from forge.workspace import WorkspaceManager

        mgr = WorkspaceManager()
        session = mgr.create_session(env={"CUSTOM_VAR": "hello"})
        assert session.env.get("CUSTOM_VAR") == "hello"
        assert "FORGE_SESSION_ID" in session.env
        assert "FORGE_WORKSPACE" in session.env
