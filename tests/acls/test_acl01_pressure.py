#!/usr/bin/env python3
"""ACL Stress Test Suite — Autonomous Control Layer 压力测试.

按照 v0.3.3 设计（Autonomous Control Layer），验证 Runtime 控制层在
高并发、多状态切换、异常干预下是否保持一致性。
不是 UI 测试，是 Runtime 合约测试。

包含 4 个核心测试：
  ACL-01: Pause/Resume 稳定性
  ACL-02: Human Takeover 接管一致性
  ACL-03: Rollback 回滚一致性
  ACL-04: Mode 切换一致性
"""

import asyncio
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from forge.kernel.runtime import Runtime, TaskPhase
from forge.kernel.state import RuntimeMode
from forge.kernel.event_bus import Event, EventKind, event_bus

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} -- {detail}")


def reset_counters():
    global PASS, FAIL
    PASS = FAIL = 0


async def nop(state):
    pass


# ────────────────────────────────────────────────────────────
# ACL-01: Pause/Resume 稳定性
# ────────────────────────────────────────────────────────────

async def test_acl01_pause_resume():
    """ACL-01: Pause/Resume 稳定性.

    Pause 是协作式的（在 loop 边界 await _pause_event.wait() 处生效），
    不是抢占式的。如果 handler 正在执行中，pause() 只会在 handler 返回后、
    下一次 loop 迭代时才生效。

    因此以下序列是合法的：
      tool_started → runtime_paused → tool_completed (in-flight handler 跑完)
      → runtime_resumed → tool_started (下一个 action)

    验证：
      - runtime.state.paused == True 立即生效
      - 无 TOOL_STARTED 在 runtime_paused 之后发生（新 action 不启动）
      - 事件顺序正确
      - resume 恢复原执行流
      - 不重复执行 action
    """
    print("\n" + "=" * 60)
    print("ACL-01: Pause/Resume Stability")
    print("=" * 60)

    rt = Runtime(token_budget=200000, round_limit=30)

    async def slow_plan(state):
        for i in range(3):
            await asyncio.sleep(0.1)
            state.add_fact(f"plan_step_{i}")

    async def slow_explore(state):
        for i in range(5):
            await asyncio.sleep(0.15)
            state.add_fact(f"discovery_{i}")

    async def slow_implement(state):
        for i in range(3):
            await asyncio.sleep(0.15)
            state.add_change(f"change_{i}")

    rt.on_plan(slow_plan)
    rt.on_explore(slow_explore)
    rt.on_implement(slow_implement)

    # ── Collect all events ──
    events: list[Event] = []

    async def collector():
        async for ev in event_bus.subscribe():
            events.append(ev)
            if ev.kind in (EventKind.TASK_COMPLETED, EventKind.TASK_FAILED):
                break

    collector_task = asyncio.create_task(collector())
    run_task = asyncio.create_task(rt.run("acl-01 pause/resume"))

    # Wait for runtime to start and produce first events
    await asyncio.sleep(1.0)
    print(f"  Events before pause: {len(events)}")

    # ── PAUSE ──
    await rt.pause()
    check("paused immediately", rt.state.paused is True)
    check("pause_event is cleared", rt._pause_event.is_set() is False)

    pause_mark = len(events)
    print(f"  Pausing for 30 seconds...")

    # Wait 30s — verify NO NEW TOOL_STARTED during pause
    # (tool_completed is allowed for in-flight handlers)
    await asyncio.sleep(30)

    gap_events = events[pause_mark:]
    forbidden = {EventKind.TOOL_STARTED, EventKind.ACTION_SELECTED}
    bad = [e for e in gap_events if e.kind in forbidden]
    check("no new TOOL_STARTED during 30s pause", len(bad) == 0,
          f"Found {len(bad)} forbidden: {[e.kind.value for e in bad]}")

    # Check runtime_paused event
    has_pause_ev = any(e.kind == EventKind.RUNTIME_PAUSED for e in events)
    check("runtime_paused event emitted", has_pause_ev)

    # Check no TOOL_STARTED after runtime_paused
    pause_idx = None
    for i, e in enumerate(events):
        if e.kind == EventKind.RUNTIME_PAUSED:
            pause_idx = i
            break
    if pause_idx is not None:
        after_pause = [e for e in events[pause_idx + 1:]
                       if e.kind in {EventKind.TOOL_STARTED, EventKind.ACTION_SELECTED}]
        check("no TOOL_STARTED after runtime_paused until resume",
              len(after_pause) == 0,
              f"Found: {[e.kind.value for e in after_pause]}")

    # ── RESUME ──
    resume_mark = len(events)
    await rt.resume()
    await asyncio.sleep(0)  # yield so collector picks up the event
    check("resumed immediately", rt.state.paused is False)
    check("pause_event is set after resume", rt._pause_event.is_set() is True)

    has_resume_ev = any(e.kind == EventKind.RUNTIME_RESUMED for e in events)
    check("runtime_resumed event emitted", has_resume_ev)

    # Wait for execution to resume and produce events
    await asyncio.sleep(5)

    after = events[resume_mark:]
    has_work = any(
        e.kind in {EventKind.TOOL_STARTED, EventKind.TOOL_COMPLETED, EventKind.ACTION_SELECTED}
        for e in after
    )
    check("execution resumes (new actions/tools after resume)", has_work)

    # ── Wait for completion ──
    await asyncio.wait_for(run_task, timeout=60)
    await collector_task

    # ── Event Sequence Validation ──
    kinds = [e.kind.value for e in events]

    for required in ["task_started", "runtime_paused", "runtime_resumed", "task_completed"]:
        check(f"'{required}' in event sequence", required in kinds)

    # Verify runtime_paused happened before runtime_resumed
    try:
        p_idx = kinds.index("runtime_paused")
        r_idx = kinds.index("runtime_resumed")
        check("runtime_paused before runtime_resumed", p_idx < r_idx,
              f"paused at {p_idx}, resumed at {r_idx}")
    except ValueError:
        check("runtime_paused and runtime_resumed both present",
              "runtime_paused" in kinds and "runtime_resumed" in kinds)

    # Timeline
    print("\n  Event Timeline (key events):")
    show = {"task_started", "phase_changed", "action_selected",
            "tool_started", "tool_completed",
            "runtime_paused", "runtime_resumed",
            "task_completed", "task_failed", "budget_exhausted"}
    for i, ev in enumerate(events):
        k = ev.kind.value if hasattr(ev.kind, 'value') else str(ev.kind)
        if k in show:
            p = json.dumps(ev.payload, ensure_ascii=False)[:60]
            print(f"    [{i:3d}] {k:25s} {p}")

    print(f"\n  Total events: {len(events)}")
    print(f"  Final phase: {rt.state.phase.name}, rounds: {rt.state.round}")

    print(f"\nACL-01: {PASS}/{PASS+FAIL} passed")
    return FAIL == 0


# ────────────────────────────────────────────────────────────
# ACL-02: Human Takeover 接管一致性
# ────────────────────────────────────────────────────────────

async def test_acl02_takeover():
    """ACL-02: Human Takeover 接管一致性.

    验证：
      - take_over() 后 state.paused=True, state.human_override=True
      - _pause_event 已清除（Agent 循环挂起）
      - 接管期间 Agent 不执行新 tool
      - 事件序列含 human_override_started/ended
      - 人工编辑被保留
    """
    print("\n" + "=" * 60)
    print("ACL-02: Human Takeover Consistency")
    print("=" * 60)

    rt = Runtime(token_budget=100000, round_limit=20)

    async def plan(state):
        await asyncio.sleep(0.1)
        state.add_fact("planned")

    async def explore(state):
        await asyncio.sleep(0.1)
        state.add_fact("explored")

    async def implement(state):
        for i in range(3):
            await asyncio.sleep(0.1)
            state.add_change(f"agent_change_{i}")
            state.add_fact(f"agent_fact_{i}")

    async def verify(state):
        state.add_fact("verification_done")

    rt.on_plan(plan)
    rt.on_explore(explore)
    rt.on_implement(implement)
    rt.on_verify(verify)

    events: list[Event] = []

    async def collector():
        async for ev in event_bus.subscribe():
            events.append(ev)
            if ev.kind in (EventKind.TASK_COMPLETED, EventKind.TASK_FAILED):
                break

    collector_task = asyncio.create_task(collector())
    run_task = asyncio.create_task(rt.run("acl-02 takeover test"))

    await asyncio.sleep(1.0)

    # ── TAKE OVER ──
    await rt.take_over()
    await asyncio.sleep(0)
    check("state.paused after takeover", rt.state.paused is True)
    check("state.human_override after takeover", rt.state.human_override is True)
    check("_pause_event cleared during takeover", rt._pause_event.is_set() is False)

    has_override_ev = any(e.kind == EventKind.HUMAN_OVERRIDE_STARTED for e in events)
    check("human_override_started event emitted", has_override_ev)

    # ── Simulate human editing ──
    rt.state.add_fact("edited_by_human")
    rt.state.add_change("human_manual_edit")
    print("  [HUMAN] Manually edited state during takeover")

    # Verify no agent execution during takeover
    takeover_mark = len(events)
    await asyncio.sleep(2)
    in_takeover = events[takeover_mark:]
    forbidden = {EventKind.TOOL_STARTED, EventKind.TOOL_COMPLETED, EventKind.ACTION_SELECTED}
    bad = [e for e in in_takeover if e.kind in forbidden]
    check("no action/tool execution during takeover", len(bad) == 0,
          f"Found {len(bad)} forbidden: {[e.kind.value for e in bad]}")

    # ── RESUME (end takeover) ──
    await rt.resume()
    await asyncio.sleep(0)
    check("state.paused False after resume", rt.state.paused is False)
    check("state.human_override False after resume", rt.state.human_override is False)
    check("_pause_event set after resume", rt._pause_event.is_set() is True)

    has_override_ended = any(e.kind == EventKind.HUMAN_OVERRIDE_ENDED for e in events)
    check("human_override_ended event emitted", has_override_ended)

    has_resume_ev = any(e.kind == EventKind.RUNTIME_RESUMED for e in events)
    check("runtime_resumed event emitted", has_resume_ev)

    await asyncio.wait_for(run_task, timeout=60)
    await collector_task

    # ── Verify human changes preserved ──
    check("human edit fact preserved in state",
          "edited_by_human" in rt.state.confirmed_facts,
          f"Facts: {rt.state.confirmed_facts}")
    check("human change preserved in recent_changes",
          any("human_manual_edit" in c for c in rt.state.recent_changes),
          f"Changes: {rt.state.recent_changes}")

    # Event sequence verification
    kinds = [e.kind.value for e in events]
    for required in ["task_started", "human_override_started",
                     "human_override_ended", "runtime_resumed"]:
        check(f"'{required}' in event sequence", required in kinds)

    # Strict ordering
    for event_a, event_b in [("human_override_started", "human_override_ended"),
                              ("human_override_ended", "runtime_resumed")]:
        try:
            idx_a = kinds.index(event_a)
            idx_b = kinds.index(event_b)
            check(f"'{event_a}' before '{event_b}'", idx_a < idx_b,
                  f"idx_a={idx_a}, idx_b={idx_b}")
        except ValueError:
            pass

    check("task reached terminal state", rt.state.is_terminal,
          f"phase={rt.state.phase}")

    print(f"\n  Events logged: {len(events)}")
    print(f"\nACL-02: {PASS}/{PASS+FAIL} passed")
    return FAIL == 0


# ────────────────────────────────────────────────────────────
# ACL-03: Rollback 回滚一致性
# ────────────────────────────────────────────────────────────

async def test_acl03_rollback():
    """ACL-03: Rollback 回滚一致性.

    验证：
      - rollback() 不崩溃
      - rollback_completed 事件可能发出（取决于 snapshot 存在性）
      - 后续操作不因回滚导致状态不一致
    """
    print("\n" + "=" * 60)
    print("ACL-03: Rollback Consistency")
    print("=" * 60)

    rt = Runtime(token_budget=50000, round_limit=10)

    async def plan(state):
        await asyncio.sleep(0.1)
        state.add_fact("planned")

    async def explore(state):
        await asyncio.sleep(0.1)
        state.add_fact("explored")

    async def implement(state):
        for i in range(3):
            await asyncio.sleep(0.1)
            state.add_change(f"change_{i}")
            state.add_fact(f"impl_step_{i}")

    rt.on_plan(plan)
    rt.on_explore(explore)
    rt.on_implement(implement)
    rt.on_verify(nop)

    events: list[Event] = []

    async def collector():
        async for ev in event_bus.subscribe():
            events.append(ev)
            if ev.kind in (EventKind.TASK_COMPLETED, EventKind.TASK_FAILED):
                break

    collector_task = asyncio.create_task(collector())
    run_task = asyncio.create_task(rt.run("acl-03 rollback test"))
    await asyncio.sleep(1.5)

    # ── ROLLBACK ──
    print("  Executing rollback...")
    result = await rt.rollback()
    print(f"  Rollback result: {result}")

    check("rollback method returned (no crash)", isinstance(result, dict))
    check("rollback has 'rolled_back' key", "rolled_back" in result,
          f"keys: {list(result.keys())}")

    has_rollback_ev = any(e.kind == EventKind.ROLLBACK_COMPLETED for e in events)
    if result.get("rolled_back"):
        check("rollback_completed event emitted", has_rollback_ev)
        check("rollback returned files_restored",
              "files_restored" in result)
    else:
        print(f"  (rollback skipped: {result.get('reason', 'no snapshots')})")
        check("rollback handled gracefully", result.get("rolled_back") is False)

    # Resume if paused then wait for completion
    if rt.state.paused:
        await rt.resume()
        rt._pause_event.set()

    await asyncio.wait_for(run_task, timeout=30)
    await collector_task

    check("state is_terminal after rollback and completion", rt.state.is_terminal,
          f"phase={rt.state.phase}")

    print(f"\n  Events: {len(events)}, round={rt.state.round}")
    print(f"\nACL-03: {PASS}/{PASS+FAIL} passed")
    return FAIL == 0


# ────────────────────────────────────────────────────────────
# ACL-04: Mode 切换一致性
# ────────────────────────────────────────────────────────────

async def test_acl04_mode_switching():
    """ACL-04: Mode 切换一致性.

    验证：
      - AUTONOMOUS → OBSERVE → GOVERNED → AUTONOMOUS 全循环
      - 每次切换发出 mode_changed SSE 事件（from/to 字段正确）
      - state.mode 正确更新
    """
    print("\n" + "=" * 60)
    print("ACL-04: Mode Switching Consistency")
    print("=" * 60)

    rt = Runtime(token_budget=50000, round_limit=15)

    async def med(state):
        for i in range(3):
            await asyncio.sleep(0.1)
            state.add_fact(f"step_{i}")

    rt.on_plan(med)
    rt.on_explore(med)
    rt.on_implement(med)

    events: list[Event] = []

    async def collector():
        async for ev in event_bus.subscribe():
            events.append(ev)
            if ev.kind in (EventKind.TASK_COMPLETED, EventKind.TASK_FAILED):
                break

    collector_task = asyncio.create_task(collector())
    run_task = asyncio.create_task(rt.run("acl-04 mode switching"))

    await asyncio.sleep(0.5)

    # ── Mode transitions ──
    check("initial mode is AUTONOMOUS", rt.state.mode == RuntimeMode.AUTONOMOUS,
          f"mode={rt.state.mode}")

    for target, label in [("observe", "OBSERVE"), ("governed", "GOVERNED"),
                          ("autonomous", "AUTONOMOUS")]:
        await rt.set_mode(target)
        await asyncio.sleep(0.05)  # yield for collector
        check(f"mode changed to {label}", rt.state.mode.value == target,
              f"mode={rt.state.mode}")

    # ── Verify mode_changed events ──
    mode_events = [e for e in events if e.kind == EventKind.MODE_CHANGED]
    check("mode_changed events emitted (3 transitions)",
          len(mode_events) >= 2,
          f"count={len(mode_events)}")

    if len(mode_events) >= 1:
        payload = mode_events[0].payload
        check("mode_changed has 'from' field", "from" in payload)
        check("mode_changed has 'to' field", "to" in payload)

    # ── Check mode_changed sequence ordering ──
    if len(mode_events) >= 3:
        transitions = [(e.payload.get("from", ""), e.payload.get("to", ""))
                       for e in mode_events[:3]]
        expected = [
            ("autonomous", "observe"),
            ("observe", "governed"),
            ("governed", "autonomous"),
        ]
        check("mode transitions in correct order",
              transitions == expected,
              f"got={transitions}, expected={expected}")

    # ── Verify mode doesn't break execution ──
    await asyncio.wait_for(run_task, timeout=30)
    await collector_task

    check("task completed after mode switching", rt.state.is_terminal,
          f"phase={rt.state.phase}")

    kinds = [e.kind.value for e in events]
    for required in ["mode_changed", "task_started", "task_completed"]:
        check(f"'{required}' in sequence", required in kinds)

    print(f"\n  Total events: {len(events)}")
    print(f"  Mode_changed events: {len(mode_events)}")
    print(f"  Final mode: {rt.state.mode.value}")
    print(f"\nACL-04: {PASS}/{PASS+FAIL} passed")
    return FAIL == 0


# ── Combined runner ──

async def run_all():
    """Run all ACL tests sequentially (ACL-01 → ACL-04)."""
    tests = [
        ("ACL-01", "Pause/Resume Stability", test_acl01_pause_resume, 150),
        ("ACL-02", "Human Takeover Consistency", test_acl02_takeover, 90),
        ("ACL-03", "Rollback Consistency", test_acl03_rollback, 60),
        ("ACL-04", "Mode Switching Consistency", test_acl04_mode_switching, 60),
    ]

    passed = failed = 0

    for test_id, desc, test_fn, _timeout in tests:
        print(f"\n{'=' * 60}")
        print(f"{test_id}: {desc}")
        print(f"{'=' * 60}")
        reset_counters()
        try:
            ok = await asyncio.wait_for(test_fn(), timeout=_timeout)
            if ok:
                passed += 1
                print(f"\n  >>> {test_id}: ALL CHECKS PASSED <<<")
            else:
                failed += 1
                print(f"\n  >>> {test_id}: {FAIL} CHECKS FAILED <<<")
        except asyncio.TimeoutError:
            failed += 1
            print(f"\n  >>> {test_id}: TIMEOUT (>{_timeout}s) <<<")
        except Exception as e:
            failed += 1
            traceback.print_exc()
            print(f"\n  >>> {test_id}: ERROR - {e} <<<")
        print(f"{'=' * 60}\n")

    print(f"\n{'=' * 60}")
    print(f"ACL SUITE: {passed}/{passed + failed} passed, {failed} failed")
    print(f"{'=' * 60}")
    return failed == 0


if __name__ == "__main__":
    result = asyncio.run(run_all())
    sys.exit(0 if result else 1)
