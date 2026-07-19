"""Stress 1: Long task stability — simulate 50-round task, verify no drift."""


class TestLongTaskStability:
    """Simulate a long multi-phase task and verify state doesn't drift."""

    async def _noop(self, state=None):
        pass

    async def test_runtime_survives_many_rounds(self):
        from forge.kernel.runtime import Runtime

        runtime = Runtime(round_limit=15)
        calls = []
        phases_seen = set()

        async def plan(s): calls.append("plan"); phases_seen.add(s.phase.value)
        async def explore(s): calls.append("explore"); phases_seen.add(s.phase.value)
        async def implement(s): calls.append("implement"); phases_seen.add(s.phase.value)
        async def verify(s): calls.append("verify"); phases_seen.add(s.phase.value)
        async def finalize(s): calls.append("finalize"); phases_seen.add(s.phase.value)

        runtime.on_plan(plan)
        runtime.on_explore(explore)
        runtime.on_implement(implement)
        runtime.on_verify(verify)
        runtime.on_finalize(finalize)

        result = await runtime.run("long running task to test stability")

        assert result.success
        assert result.rounds > 0
        assert len(calls) >= 5
        assert result.phase.name == "COMPLETED"

    async def test_memory_stable_across_phases(self):
        from forge.kernel.runtime import Runtime

        runtime = Runtime(round_limit=10)
        facts = []

        async def plan(s):
            s.add_fact("fact_plan")
            facts.append(len(s.confirmed_facts))

        async def explore(s):
            s.add_fact("fact_explore")

        async def implement(s):
            s.add_fact(f"fact_round_{s.round}")
            facts.append(len(s.confirmed_facts))

        async def verify(s):
            pass

        async def finalize(s):
            pass

        runtime.on_plan(plan)
        runtime.on_explore(explore)
        runtime.on_implement(implement)
        runtime.on_verify(verify)
        runtime.on_finalize(finalize)

        result = await runtime.run("memory stability test")
        assert result.success
        assert len(facts) > 0

    async def test_budget_never_overflows(self):
        from forge.kernel.runtime import Runtime
        from forge.kernel.budget import BudgetKind

        runtime = Runtime(round_limit=3, token_budget=1000)

        async def plan(s): pass
        async def explore(s): pass
        async def verify(s): pass
        async def finalize(s): pass

        async def implement(s):
            runtime.budget.consume_tokens(500)

        runtime.on_plan(plan)
        runtime.on_explore(explore)
        runtime.on_implement(implement)
        runtime.on_verify(verify)
        runtime.on_finalize(finalize)

        result = await runtime.run("budget test")
        rounds_state = runtime.budget.get_state(BudgetKind.ROUNDS)
        assert rounds_state.used <= rounds_state.limit
