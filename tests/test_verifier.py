"""Tests for verification and EVI modules."""

import tempfile
from pathlib import Path


class TestIndependentVerifier:
    """Independent artifact verification."""

    async def test_verify_nonexistent_file(self):
        from forge.verifier.verifier import IndependentVerifier, Verdict

        v = IndependentVerifier()
        result = await v.verify_file("/nonexistent/path.py")
        assert result.verdict == Verdict.FAIL
        assert "does not exist" in result.issues[0]

    async def test_verify_valid_python(self):
        from forge.verifier.verifier import IndependentVerifier, Verdict

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1\ny = x + 1\nprint(y)")
            name = f.name

        try:
            v = IndependentVerifier()
            result = await v.verify_file(name)
            assert result.verdict == Verdict.PASS
        finally:
            Path(name).unlink(missing_ok=True)

    async def test_verify_invalid_python(self):
        from forge.verifier.verifier import IndependentVerifier, Verdict

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def broken(")
            name = f.name

        try:
            v = IndependentVerifier()
            result = await v.verify_file(name)
            assert result.verdict == Verdict.FAIL
            assert any("syntax" in issue.lower() for issue in result.issues)
        finally:
            Path(name).unlink(missing_ok=True)

    async def test_verify_json(self):
        from forge.verifier.verifier import IndependentVerifier, Verdict

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"key": "value"}')
            name = f.name

        try:
            v = IndependentVerifier()
            result = await v.verify_file(name)
            assert result.verdict == Verdict.PASS
        finally:
            Path(name).unlink(missing_ok=True)


class TestEVIEngine:
    """Evidence Intelligence engine."""

    def test_high_value_read(self):
        from forge.verifier.evi import EVIEngine

        evi = EVIEngine()
        result = evi.evaluate(
            "read_file",
            {"path": "file.py"},
            {"content": "def foo():\n    pass\n" * 10},
            [],
        )
        assert result.score > 0.3
        assert not result.low_value

    def test_low_value_empty(self):
        from forge.verifier.evi import EVIEngine

        evi = EVIEngine()
        result = evi.evaluate(
            "some_tool",
            {},
            {},
            [],
        )
        assert result.score < 0.2
        assert result.low_value

    def test_low_value_streak(self):
        from forge.verifier.evi import EVIEngine

        evi = EVIEngine()
        for _ in range(3):
            evi.evaluate("tool", {}, {}, [])
        assert evi.low_value_streak >= 3
        assert evi.should_force_finalize
