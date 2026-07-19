"""Stress 10: Stability — repeated execution without degradation."""


class TestLongRunningStability:
    """Run the runtime loop many times and verify consistent behavior."""

    async def test_repeated_execution_consistent(self):
        from forge.kernel.runtime import Runtime

        async def nop(s): pass

        results = []
        for i in range(10):
            runtime = Runtime(round_limit=5)

            async def plan(s): s.add_fact(f"plan_{i}")
            async def implement(s): s.add_fact(f"impl_{i}")

            runtime.on_plan(plan)
            runtime.on_explore(nop)
            runtime.on_implement(implement)
            runtime.on_verify(nop)
            runtime.on_finalize(nop)

            result = await runtime.run(f"iteration_{i}")
            results.append(result)

        assert all(r.success for r in results)
        assert all(r.phase.name == "COMPLETED" for r in results)

    async def test_memory_between_tasks(self):
        from forge.memory import EpisodicMemory, Episode

        mem = EpisodicMemory()

        for i in range(5):
            ep = Episode.create(f"task_{i}", "stress")
            ep.success = True
            mem.record(ep)

        assert mem.total_episodes == 5
        assert mem.success_rate == 1.0

    async def test_runtime_state_resets_between_runs(self):
        from forge.kernel.runtime import Runtime

        async def nop(s): pass

        async def run_once(label):
            r = Runtime(round_limit=5)
            r.on_plan(nop)
            r.on_explore(nop)
            r.on_implement(nop)
            r.on_verify(nop)
            r.on_finalize(nop)
            return await r.run(label)

        result1 = await run_once("first")
        result2 = await run_once("second")

        assert result1.success
        assert result2.success
