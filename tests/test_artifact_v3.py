"""Tests for Artifact Versioning v0.3."""

import tempfile
from pathlib import Path


class TestArtifactVersioning:
    """Artifact version chain and rollback."""

    async def test_version_chain(self):
        from forge.api.artifact import ArtifactCommitter

        with tempfile.TemporaryDirectory() as tmp:
            committer = ArtifactCommitter(workspace_dir=tmp)
            fp = str(Path(tmp) / "main.py")

            v1 = await committer.create_version("v1", "file", fp, "v1 content")
            assert v1.version == 1
            assert v1.parent_id == ""

            v2 = await committer.create_version("v2", "file", fp, "v2 content", original_content="v1 content")
            assert v2.version == 2
            assert v2.parent_id == v1.id
            assert v2.diff_from_parent

            history = committer.get_version_history(fp)
            assert len(history) == 2

    async def test_rollback_to_previous_version(self):
        from forge.api.artifact import ArtifactCommitter

        with tempfile.TemporaryDirectory() as tmp:
            committer = ArtifactCommitter(workspace_dir=tmp)
            fp = str(Path(tmp) / "main.py")

            v1 = await committer.create_version("v1", "file", fp, "original")
            v2 = await committer.create_version("v2", "file", fp, "modified content")

            # Rollback to v1 — creates v3 with original content
            v3 = await committer.rollback_to(fp, 1)
            assert v3 is not None
            assert v3.version == 3

    async def test_version_count(self):
        from forge.api.artifact import ArtifactCommitter

        with tempfile.TemporaryDirectory() as tmp:
            committer = ArtifactCommitter(workspace_dir=tmp)
            fp = str(Path(tmp) / "f.py")
            await committer.create_version("a", "file", fp, "a")
            await committer.create_version("b", "file", fp, "b", original_content="a")
            assert committer.total_versions == 2

    async def test_full_lifecycle_with_version(self):
        from forge.api.artifact import ArtifactCommitter, ArtifactState

        with tempfile.TemporaryDirectory() as tmp:
            committer = ArtifactCommitter(workspace_dir=tmp)
            fp = str(Path(tmp) / "test.txt")

            # Create version instead of plain generate
            artifact = await committer.create_version("x1", "file", fp, "hello world")
            assert artifact.version == 1

            artifact = await committer.validate(artifact)
            assert artifact.state == ArtifactState.VALIDATED

            artifact = await committer.approve(artifact)
            assert artifact.state == ArtifactState.APPROVED

            artifact = await committer.commit(artifact)
            assert artifact.state == ArtifactState.COMMITTED
