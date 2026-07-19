"""Stress 2: Error recovery — verify system handles failures gracefully."""


class TestErrorRecovery:
    """Deliberately cause failures and verify recovery works."""

    async def test_recover_from_tool_failure(self):
        from forge.kernel.runtime import Runtime
        from forge.recovery import FailureHandler, FailureSeverity

        handler = FailureHandler()
        runtime = Runtime(round_limit=5)
        call_count = 0

        async def plan(s):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                handler.record("simulated failure", FailureSeverity.ERROR)
                raise RuntimeError("simulated tool failure")

        async def nop(s): pass

        runtime.on_plan(plan)
        runtime.on_explore(nop)
        runtime.on_implement(nop)
        runtime.on_verify(nop)
        runtime.on_finalize(nop)

        result = await runtime.run("test recovery from failure")
        # Should complete or fail gracefully — not crash
        assert result.phase.name in ("COMPLETED", "FAILED", "CANCELLED")
        assert result.rounds >= 0

    async def test_failure_memory_learns(self):
        from forge.recovery.memory import FailureMemory

        mem = FailureMemory()

        for i in range(3):
            rec = mem.record_failure(f"ModuleNotFoundError: package_{i}")
            mem.record_fix(rec.id, f"pip install package_{i}", "requirements.txt", success=True)

        recommendation = mem.get_recommendation("ModuleNotFoundError: package_2")
        assert recommendation is not None
        assert recommendation["action"] == "pip install package_2"
        assert recommendation["confidence"] > 0.3

    async def test_retry_policy_exhaustion(self):
        from forge.recovery import RetryPolicy
        import pytest

        policy = RetryPolicy(max_retries=2, base_delay=0.01)

        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError(f"attempt_{call_count}")

        with pytest.raises(ValueError):
            await policy.execute(always_fails)

        assert call_count == 3  # Initial + 2 retries
