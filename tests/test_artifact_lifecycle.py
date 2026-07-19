"""Tests for Artifact Lifecycle."""

import tempfile
from pathlib import Path


class TestArtifactLifecycle:
    """Artifact DRAFT→GENERATED→VALIDATED→APPROVED→COMMITTED→ARCHIVED."""

    async def test_full_lifecycle(self):
        from forge.api.artifact import ArtifactCommitter, ArtifactState

        with tempfile.TemporaryDirectory() as tmp:
            committer = ArtifactCommitter(workspace_dir=tmp)
            file_path = str(Path(tmp) / "output.txt")

            # DRAFT → GENERATED
            artifact = await committer.generate("a1", "file", file_path, "hello world")
            assert artifact.state == ArtifactState.GENERATED
            assert artifact.checksum
            assert Path(file_path).exists()

            # GENERATED → VALIDATED
            artifact = await committer.validate(artifact)
            assert artifact.state == ArtifactState.VALIDATED

            # VALIDATED → APPROVED
            artifact = await committer.approve(artifact)
            assert artifact.state == ArtifactState.APPROVED

            # APPROVED → COMMITTED
            artifact = await committer.commit(artifact)
            assert artifact.state == ArtifactState.COMMITTED
            assert artifact.committed_at

    async def test_invalid_transition(self):
        from forge.api.artifact import ArtifactCommitter, ArtifactState
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            committer = ArtifactCommitter(workspace_dir=tmp)
            file_path = str(Path(tmp) / "test.txt")

            artifact = await committer.generate("a2", "file", file_path, "data")

            # Can't go from GENERATED to COMMITTED (skip APPROVED)
            import pytest
            with pytest.raises(ValueError, match="Cannot transition"):
                await committer.commit(artifact)

    async def test_fail(self):
        from forge.api.artifact import ArtifactCommitter, ArtifactState
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            committer = ArtifactCommitter(workspace_dir=tmp)
            file_path = str(Path(tmp) / "test.txt")

            artifact = await committer.generate("a3", "file", file_path, "data")
            artifact = await committer.fail(artifact, "something broke")
            assert artifact.state == ArtifactState.FAILED
            assert artifact.error == "something broke"

    async def test_diff_generation(self):
        from forge.api.artifact import ArtifactCommitter, ArtifactState
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            committer = ArtifactCommitter(workspace_dir=tmp)
            artifact = await committer.generate_diff("d1", "main.py", "old code", "new code")
            assert artifact.state == ArtifactState.GENERATED
            assert artifact.kind == "diff"
            assert "old code" in artifact.content or "new code" in artifact.content
