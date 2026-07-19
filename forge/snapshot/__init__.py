"""Snapshot — file-level state capture and rollback."""

from .snapshot import SnapshotManager, Snapshot

__all__ = ["SnapshotManager", "Snapshot"]
