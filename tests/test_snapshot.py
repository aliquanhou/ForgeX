"""Tests for snapshot/rollback module."""

import tempfile
from pathlib import Path


class TestSnapshotManager:
    """File-level state capture and restore."""

    def test_snapshot_and_restore(self):
        from forge.snapshot.snapshot import SnapshotManager

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("original content")
            name = f.name

        try:
            mgr = SnapshotManager()
            snap = mgr.snapshot_before(name)
            assert snap is not None
            assert snap.content == "original content"
            assert mgr.get_snapshot_count() == 1

            # Change the file
            Path(name).write_text("modified content")
            assert Path(name).read_text() == "modified content"

            # Rollback
            ok = mgr.rollback_file(name)
            assert ok
            assert Path(name).read_text() == "original content"

        finally:
            Path(name).unlink(missing_ok=True)

    def test_snapshot_nonexistent_file(self):
        from forge.snapshot.snapshot import SnapshotManager

        mgr = SnapshotManager()
        snap = mgr.snapshot_before("/nonexistent/file.txt")
        assert snap is None

    def test_rollback_all(self):
        from forge.snapshot.snapshot import SnapshotManager

        with (
            tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f1,
            tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f2,
        ):
            f1.write("a")
            f2.write("b")
            name1 = f1.name
            name2 = f2.name

        try:
            mgr = SnapshotManager()
            mgr.snapshot_before(name1)
            mgr.snapshot_before(name2)

            Path(name1).write_text("a2")
            Path(name2).write_text("b2")

            count = mgr.rollback_all()
            assert count == 2
            assert Path(name1).read_text() == "a"
            assert Path(name2).read_text() == "b"

        finally:
            Path(name1).unlink(missing_ok=True)
            Path(name2).unlink(missing_ok=True)
