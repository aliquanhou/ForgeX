"""Stress 5: Multi-task — run multiple tasks concurrently."""

import asyncio


class TestMultiTask:
    """Run multiple tasks and verify isolation."""

    async def test_two_tasks_independent(self):
        from forge.kernel.runtime import Runtime

        results = []

        async def run_task(name):
            runtime = Runtime(round_limit=5)

            async def plan(s):
                s.add_fact(f"task_{name}_planned")

            async def implement(s):
                s.add_fact(f"task_{name}_round_{s.round}")

            async def nop(s): pass

            runtime.on_plan(plan)
            runtime.on_explore(nop)
            runtime.on_implement(implement)
            runtime.on_verify(nop)
            runtime.on_finalize(nop)

            result = await runtime.run(f"task_{name}")
            results.append((name, result.success))

        await asyncio.gather(run_task("A"), run_task("B"))

        assert len(results) == 2
        assert all(success for _, success in results)

    async def test_workspace_isolation(self):
        from forge.workspace import WorkspaceManager

        mgr = WorkspaceManager()

        s1 = mgr.create_session(env={"PROJECT": "alpha"})
        s2 = mgr.create_session(env={"PROJECT": "beta"})

        assert s1.env["PROJECT"] == "alpha"
        assert s2.env["PROJECT"] == "beta"
        assert s1.session_id != s2.session_id
        assert s1.root != s2.root

        (s1.root / "config.txt").write_text("alpha_config")
        (s2.root / "config.txt").write_text("beta_config")

        assert (s1.root / "config.txt").read_text() == "alpha_config"
        assert (s2.root / "config.txt").read_text() == "beta_config"

        mgr.destroy_all()
        assert mgr.active_sessions == 0
