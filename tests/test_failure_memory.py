"""Tests for Failure Memory — experience-driven fault recovery."""


class TestFailureMemory:
    """Records, indexes, and recommends fixes for failures."""

    def test_record_failure(self):
        from forge.recovery.memory import FailureMemory

        mem = FailureMemory()
        rec = mem.record_failure("ModuleNotFoundError: No module named 'flask'", "execute", "test")
        assert rec.error_type == "import"
        assert mem.total_failures == 1

    def test_find_similar(self):
        from forge.recovery.memory import FailureMemory

        mem = FailureMemory()
        mem.record_failure("Connection refused to database", "execute", "impl")
        found = mem.find_similar("Connection refused error when connecting to db")
        assert found is not None

    def test_get_recommendation(self):
        from forge.recovery.memory import FailureMemory

        mem = FailureMemory()
        rec = mem.record_failure("ModuleNotFoundError: No module named 'requests'")
        mem.record_fix(rec.id, "pip install requests", "requirements.txt", success=True)

        recommendation = mem.get_recommendation("ModuleNotFoundError: No module named 'requests'")
        assert recommendation is not None
        assert recommendation["action"] == "pip install requests"

    def test_no_recommendation_for_unknown(self):
        from forge.recovery.memory import FailureMemory

        mem = FailureMemory()
        rec = mem.get_recommendation("something completely new")
        assert rec is None

    def test_error_classification(self):
        from forge.recovery.memory import FailureMemory

        mem = FailureMemory()
        r1 = mem.record_failure("SyntaxError: invalid syntax")
        assert r1.error_type == "syntax"

        r2 = mem.record_failure("TimeoutError: operation timed out")
        assert r2.error_type == "timeout"

        r3 = mem.record_failure("Permission denied: /etc")
        assert r3.error_type == "permission"

    def test_duplicate_detection(self):
        from forge.recovery.memory import FailureMemory

        mem = FailureMemory()
        r1 = mem.record_failure("disk full")
        r2 = mem.record_failure("disk full")
        assert r2.id == r1.id  # Same record
        assert r2.times_encountered == 2  # Counter incremented
