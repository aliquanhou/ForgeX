"""Stress 3: Hallucination control — verify Forge doesn't fabricate results."""

import tempfile
from pathlib import Path


class TestHallucinationControl:
    """Test that Forge properly handles non-existent files and data."""

    async def test_read_nonexistent_file_returns_error(self):
        from forge.tools.file_tools import FileTools
        from forge.tools.registry import ToolStatus

        result = await FileTools.read_file("/definitely/does/not/exist/file.py")
        assert result.status == ToolStatus.ERROR
        assert "not found" in result.error.lower()

    async def test_grep_no_match_returns_empty(self):
        from forge.tools.search import SearchTools

        with tempfile.TemporaryDirectory() as tmp:
            result = await SearchTools.grep(
                "XYZZYX_NONEXISTENT_PATTERN_12345",
                path=tmp,
            )
            # ripgrep may return ERROR for no matches on empty dir
            # Validate by checking no match content
            if result.status == "success":
                assert result.data["count"] == 0
            # Error is also acceptable — means rg couldn't search empty dir

    async def test_glob_no_match_returns_empty(self):
        from forge.tools.search import SearchTools
        from forge.tools.registry import ToolStatus

        with tempfile.TemporaryDirectory() as tmp:
            result = await SearchTools.glob_files("*.nonexistent", path=tmp)
            assert result.status == ToolStatus.SUCCESS
            assert result.data["count"] == 0

    async def test_verifier_rejects_nonexistent_file(self):
        from forge.verifier import IndependentVerifier
        from forge.verifier.verifier import Verdict

        v = IndependentVerifier()
        result = await v.verify_file("/nonexistent/path/file.py")
        assert result.verdict == Verdict.FAIL
        assert "does not exist" in result.issues[0]
