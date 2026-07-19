#!/usr/bin/env python3
"""ACL-01: Pause/Resume 稳定性测试 — Runtime 直接测试版

直接在 Runtime 对象上测试 pause/resume 机制，避免 API 时序竞态。
验证：
  - pause 立即挂起执行循环
  - resume 恢复执行
  - pause 期间无 action 执行
  - 事件序列正确
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from forge.kernel.runtime import Runtime
from forge.kernel.event_bus import Event, EventKind, event_bus

PASS = 0
FAIL = 0
events = []


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} -- {detail}")


async def test_acl01_direct():
    global events
    print("=" * 60)
    print("ACL-01 (Direct): Pause/Resume Stability")
    print("=" * 60)

    # ── Create a Runtime with a slow handler ─────────────
    print("\n--- Setup: Runtime with slow explore handler ---")
    rt = Runtime(token_budget=50000, round_limit=10)

    # Handler that takes time — gives us a chance to pause
    async def slow_plan(state):
        state.add_fact("Planning started")
        for i in range(3):
            await asyncio.sleep(0.3)
            state.add_fact(f"Plan step {i + 1}")
        print("  Plan done (slow)")

    async def slow_explore(state):
        state.add_fact("Exploring...")
        for i in range(5):
            await asyncio.sleep(0.3)
            state.add_fact(f"Discovery {i + 1}")
        print("  Explore done (slow)")

    async def slow_implement(state):
        for i in range(3):
            await asyncio.sleep(0.3)
            state.add_change(f"Change {i + 1}")
        print("  Implement done (slow)")

    async def auto_complete(state):
        state.add_fact("Task complete")
        print("  Verify/finalize done")

    rt.on_plan(slow_plan)
    rt.on_explore(slow_explore)
    rt.on_implement(slow_implement)
    rt.on_verify(auto_complete)
    rt.on_finalize(auto_complete)

    # Collect events
    events = []

    async def collect():
        async for ev in event_bus.subscribe():
            events.append(ev)
            if ev.kind in (EventKind.TASK_COMPLETED, EventKind.TASK_FAILED):
                break

    collector = asyncio.create_task(collect())

    # ── Start the runtime in background ──────────────────
    print("\n--- Start Runtime ---")
    run_task = asyncio.create_task(rt.run("test pause/resume with slow handlers"))

    # Wait for runtime to start and produce some events
    await asyncio.sleep(1.5)
    print(f"  Events so far: {len(events)}")

    # ── PAUSE ────────────────────────────────────────────
    print("\n--- PAUSE ---")
    pre_pause_count = len(events)
    await rt.pause()
    check("runtime.state.paused is True", rt.state.paused is True)

    # Wait 4 seconds — count new events
    await asyncio.sleep(4)
    during_pause = len(events) - pre_pause_count
    print(f"  Events during 4s pause: {during_pause}")

    # Check for phase_changed or tool_started during pause (forbidden)
    paused_events = events[pre_pause_count:]
    forbidden = {EventKind.PHASE_CHANGED, EventKind.TOOL_STARTED,
                 EventKind.TOOL_COMPLETED, EventKind.ACTION_SELECTED}
    bad = [e for e in paused_events if e.kind in forbidden]
    check("no phase/tool/action events during pause", len(bad) == 0,
          f"Found {len(bad)} forbidden events: {[e.kind.value for e in bad[:5]]}")

    # Check runtime_paused event
    has_pause_ev = any(e.kind == EventKind.RUNTIME_PAUSED for e in events)
    check("runtime_paused event emitted", has_pause_ev)

    # ── RESUME ────────────────────────────────────────────
    print("\n--- RESUME ---")
    resume_mark = len(events)
    await rt.resume()
    check("runtime.state.paused is False after resume", rt.state.paused is False)

    has_resume_ev = any(e.kind == EventKind.RUNTIME_RESUMED for e in events)
    check("runtime_resumed event emitted", has_resume_ev)

    # Wait for execution to resume and produce more events
    await asyncio.sleep(3)
    after_resume = len(events)
    check("new events appear after resume", after_resume > resume_mark,
          f"No new events: {resume_mark} → {after_resume}")

    after_events = events[resume_mark:]
    has_work = any(
        e.kind in {EventKind.ACTION_SELECTED, EventKind.TOOL_STARTED, EventKind.TOOL_COMPLETED}
        for e in after_events
    )
    check("execution resumes (new actions/tools after resume)", has_work)

    # ── Wait for completion ──────────────────────────────
    print("\n--- Wait for completion ---")
    await asyncio.wait_for(run_task, timeout=60)
    await collector

    # ── Validate event sequence ──────────────────────────
    print("\n--- Event Sequence Validation ---")
    kinds = [e.kind.value for e in events]

    for required in ["task_started", "runtime_paused", "runtime_resumed", "task_completed"]:
        check(f"{required} in sequence", required in kinds)

    # Pause-resume gap check
    if "runtime_paused" in kinds and "runtime_resumed" in kinds:
        p_idx = kinds.index("runtime_paused")
        r_idx = kinds.index("runtime_resumed")
        gap = kinds[p_idx + 1:r_idx]
        gap_forbidden = [k for k in gap if k in {
            "phase_changed", "action_selected", "tool_started", "tool_completed"
        }]
        check("no execution events between pause and resume",
              len(gap_forbidden) == 0,
              f"Found: {gap_forbidden}")
        print(f"  Gap between pause/resume: {gap}")

    # Timeline
    print("\nTimeline:")
    show_kinds = {"task_started", "phase_changed", "action_selected",
                  "runtime_paused", "runtime_resumed",
                  "task_completed", "task_failed"}
    for i, ev in enumerate(events):
        k = ev.kind.value if hasattr(ev.kind, 'value') else str(ev.kind)
        if k in show_kinds:
            msg = json.dumps(ev.payload, ensure_ascii=False)[:60]
            print(f"  [{i:3d}] {k:25s} {msg}")

    print(f"\n  Total events: {len(events)}")

    # Result
    print("\n" + "=" * 60)
    print(f"ACL-01 RESULT: {PASS} passed / {FAIL} failed")
    print("=" * 60)
    return FAIL == 0


if __name__ == "__main__":
    import json
    result = asyncio.run(test_acl01_direct())
    sys.exit(0 if result else 1)
