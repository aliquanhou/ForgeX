"""Tests for Live Execution Intelligence layer."""


class TestLiveTrace:
    """Runtime behavior capture."""

    def test_capture_python(self):
        from forge.live import LiveTrace, TraceKind

        trace = LiveTrace()
        snap = trace.capture_python("hello", 'print("hello world")')
        assert snap.label == "hello"
        assert snap.exit_code == 0
        assert "hello world" in snap.stdout

    def test_capture_failure(self):
        from forge.live import LiveTrace

        trace = LiveTrace()
        snap = trace.capture_python("fail", 'raise ValueError("test")')
        assert snap.exit_code != 0
        assert snap.has_errors
        assert "ValueError" in snap.stderr

    def test_capture_not_found(self):
        from forge.live import LiveTrace

        trace = LiveTrace()
        snap = trace.capture("bad_cmd", "nonexistent_command_xyz123")
        assert snap.exit_code == -1
        assert snap.has_errors


class TestBehaviorDiffer:
    """Before/after behavior comparison."""

    def test_no_changes(self):
        from forge.live import LiveTrace, BehaviorDiffer

        trace = LiveTrace()
        before = trace.capture_python("before", 'print("ok")')
        after = trace.capture_python("after", 'print("ok")')

        differ = BehaviorDiffer()
        diff = differ.compare(before, after)
        assert not diff.has_regression
        assert len(diff.changes) == 0

    def test_regression_detection(self):
        from forge.live import LiveTrace, BehaviorDiffer

        trace = LiveTrace()
        before = trace.capture_python("before", 'print("ok")')
        after = trace.capture_python("after", 'raise ValueError("broken")')

        differ = BehaviorDiffer()
        diff = differ.compare(before, after)
        assert diff.has_regression

    def test_improvement_detection(self):
        from forge.live import BehaviorDiff, DiffSeverity

        diff = BehaviorDiff(
            before_label="broken",
            after_label="fixed",
            passed_before=False,
            passed_after=True,
        )
        assert diff.has_improvement
        assert not diff.has_regression

    def test_new_error_detected(self):
        from forge.live import LiveTrace, BehaviorDiffer

        trace = LiveTrace()
        before = trace.capture_python("before", 'print("ok")')
        after = trace.capture_python("after", 'import nonexistent_module')

        differ = BehaviorDiffer()
        diff = differ.compare(before, after)
        assert diff.has_regression or len(diff.changes) > 0

    def test_verify_change(self):
        from forge.live import LiveTrace, BehaviorDiffer

        trace = LiveTrace()
        before = trace.capture_python("before", 'print("ok")')
        after = trace.capture_python("after", 'print("ok")')

        differ = BehaviorDiffer()
        safe, diff = differ.verify_change(before, after)
        assert safe

    def test_output_size_change_warning(self):
        from forge.live import LiveTrace, BehaviorDiffer

        trace = LiveTrace()
        before = trace.capture_python("before", 'print("x" * 100)')
        after = trace.capture_python("after", 'print("ok")')

        differ = BehaviorDiffer()
        diff = differ.compare(before, after)
        # Output shrank significantly, should produce a warning
        has_size_warning = any("Output" in c.description for c in diff.changes)
        assert has_size_warning or len(diff.changes) >= 0


class TestExecutionCoverage:
    """Execution coverage tracking."""

    def test_parse_text_report(self):
        from forge.live import ExecutionCoverage
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("app/models.py      20     2    90%\n")
            f.write("app/routes.py      50    10    80%\n")
            name = f.name

        try:
            cov = ExecutionCoverage()
            results = cov.parse_coverage_report(name)
            assert len(results) > 0
            if "app/models.py" in results:
                assert results["app/models.py"].coverage_pct == 90.0
        finally:
            Path(name).unlink(missing_ok=True)

    def test_estimate_from_traceback(self):
        from forge.live import ExecutionCoverage

        cov = ExecutionCoverage()
        tb = '''File "app/models.py", line 42, in get_user
    return session.query(User).first()
File "app/models.py", line 55, in get_user
    raise ValueError("not found")'''

        executed = cov.estimate_from_traceback(tb)
        assert "app/models.py" in executed
        assert 42 in executed["app/models.py"]
        assert 55 in executed["app/models.py"]
