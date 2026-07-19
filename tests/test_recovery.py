"""Tests for Recovery modules."""


class TestFailureHandler:
    """Failure tracking and recovery strategies."""

    def test_record_failure(self):
        from forge.recovery import FailureHandler, FailureSeverity

        handler = FailureHandler()
        record = handler.record("file not found", FailureSeverity.WARNING)
        assert record.error == "file not found"
        assert record.severity == FailureSeverity.WARNING
        assert handler.total_count == 1

    def test_consecutive_failures(self):
        from forge.recovery import FailureHandler, FailureSeverity

        handler = FailureHandler()
        handler.record("err1", FailureSeverity.ERROR)
        handler.record("err2", FailureSeverity.ERROR)
        assert handler.consecutive_failures == 2

    def test_recovery_breaks_streak(self):
        from forge.recovery import FailureHandler, FailureSeverity

        handler = FailureHandler()
        r1 = handler.record("err1", FailureSeverity.ERROR)
        handler.record("err2", FailureSeverity.ERROR)
        handler.mark_recovered(r1)
        # consecutive should only count from end
        assert handler.consecutive_failures == 1  # only err2 counts

    def test_recovery_actions(self):
        from forge.recovery import FailureHandler, FailureSeverity

        handler = FailureHandler()
        assert handler.get_recovery_action() == "continue"

        handler.record("err", FailureSeverity.ERROR)
        assert handler.get_recovery_action() == "retry"

        handler.record("err2", FailureSeverity.ERROR)
        assert handler.get_recovery_action() == "pivot"

        handler.record("err3", FailureSeverity.ERROR)
        assert handler.get_recovery_action() == "ask_user"

    def test_should_abort(self):
        from forge.recovery import FailureHandler, FailureSeverity

        handler = FailureHandler()
        for _ in range(5):
            handler.record("fail", FailureSeverity.ERROR)
        assert handler.should_abort()


class TestRetryPolicy:
    """Retry with backoff."""

    async def test_successful_execution(self):
        from forge.recovery import RetryPolicy

        policy = RetryPolicy(max_retries=3)

        async def succeed():
            return "ok"

        result = await policy.execute(succeed)
        assert result == "ok"

    async def test_retry_then_succeed(self):
        from forge.recovery import RetryPolicy

        policy = RetryPolicy(max_retries=3)

        call_count = 0

        async def eventually_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("not yet")
            return "finally ok"

        result = await policy.execute(eventually_succeed)
        assert result == "finally ok"
        assert call_count == 2

    async def test_exhaust_retries(self):
        from forge.recovery import RetryPolicy
        import pytest

        policy = RetryPolicy(max_retries=2)

        async def always_fails():
            raise ValueError("always")

        with pytest.raises(ValueError, match="always"):
            await policy.execute(always_fails)

    def test_backoff_delay(self):
        from forge.recovery import RetryPolicy

        policy = RetryPolicy(base_delay=1.0, jitter=False)
        d1 = policy.get_delay(1)
        d2 = policy.get_delay(2)
        d3 = policy.get_delay(3)

        assert d1 == 1.0
        assert d2 == 2.0
        assert d3 == 4.0

    def test_max_delay_cap(self):
        from forge.recovery import RetryPolicy

        policy = RetryPolicy(base_delay=10.0, max_delay=15.0, jitter=False)
        d5 = policy.get_delay(5)  # would be 160s without cap
        assert d5 <= 15.0
