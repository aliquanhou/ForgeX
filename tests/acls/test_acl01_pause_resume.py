#!/usr/bin/env python3
"""ACL-01: Pause/Resume 稳定性测试

验证 Runtime 控制层的 pause/resume 契约：
  - pause 立即生效，执行循环挂起
  - resume 恢复原执行流
  - pause 期间无 tool/action 事件
  - 事件序列严格：task_started → ... → runtime_paused → (gap) → runtime_resumed → ... → task_completed

策略：SSE 事件流驱动。一旦看到 action_selected 或 phase_changed，
立即 pause，此时任务仍在执行中。
"""

import asyncio
import json
import httpx
import sys
import time

BASE = "http://localhost:5173/api"
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


async def test_acl01():
    print("=" * 60)
    print("ACL-01: Pause/Resume Stability")
    print("=" * 60)

    # 1. Health check
    print("\n--- [1/6] Health Check ---")
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/health")
        assert r.status_code == 200
        print(f"  Runtime online: {r.json()['status']}")

    # 2. SSE collector — starts BEFORE task creation
    print("\n--- [2/6] Start SSE Collector ---")
    events = []
    sse_ready = asyncio.Event()
    task_done = asyncio.Event()
    got_action = asyncio.Event()
    task_id = None
    collector_error = None

    async def collect_events():
        nonlocal task_id, collector_error
        try:
            async with httpx.AsyncClient(timeout=60) as c:
                async with c.stream("GET", f"{BASE}/tasks/events", timeout=60) as resp:
                    sse_ready.set()
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            ev = json.loads(line[6:])
                            events.append(ev)
                            kind = ev.get("kind", "")
                            if task_id is None and kind == "task_started":
                                task_id = ev["task_id"]
                            if kind in {"action_selected", "phase_changed", "tool_started"}:
                                got_action.set()
                            if kind in {"task_completed", "task_failed", "runtime_stopped"}:
                                task_done.set()
                                return
        except Exception as e:
            collector_error = e
        finally:
            sse_ready.set()

    collector = asyncio.create_task(collect_events())
    await asyncio.wait_for(sse_ready.wait(), timeout=10)
    print("  SSE collector ready")

    # 3. Create task with enough rounds to allow interruption
    print("\n--- [3/6] Create Task ---")
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/tasks", json={
            "goal": "scan and analyze all Python source files for class definitions and function signatures",
            "token_budget": 200000,
            "round_limit": 30,
        })
        assert r.status_code == 200
        print(f"  Task created: {r.json()['task_id']} / {r.json()['status']}")

    # 4. Wait for the first action or task to become active
    print("\n--- [4/6] Await First Action ---")
    try:
        await asyncio.wait_for(got_action.wait(), timeout=15)
        print(f"  First action detected after {len(events)} events")
    except asyncio.TimeoutError:
        print("  WARNING: No action detected within timeout, will attempt pause anyway")
        if collector_error:
            print(f"  Collector error: {collector_error}")

    # 5. PAUSE — issue immediately
    print("\n--- [5/6] PAUSE / RESUME ---")
    pause_mark = len(events)
    print(f"  Events before pause: {pause_mark}")

    if task_id:
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{BASE}/tasks/{task_id}/pause")
            print(f"  pause: {r.status_code} {r.json()}")
            if r.status_code != 200:
                # Task already done — can still test but limited
                check("task still running for pause",
                      False, f"Task finished before pause: {r.json()}")
                # Try to verify what we can
                await asyncio.sleep(0.5)
                await collector
                print("\n--- Summary (limited — task completed before pause) ---")
                print(f"  Total events: {len(events)}")
                return FAIL == 0

            # Verify runtime_paused event
            await asyncio.sleep(1)
            has_paused = any(e.get("kind") == "runtime_paused" for e in events)
            check("runtime_paused event emitted", has_paused)

            # Wait 5s — verify zero tool/action events in this window
            await asyncio.sleep(5)
            gap_events = events[pause_mark:]
            forbidden = {"tool_started", "tool_completed", "action_selected"}
            bad = [e.get("kind") for e in gap_events if e.get("kind") in forbidden]
            check("no tool/action during pause",
                  len(bad) == 0,
                  f"Found during pause: {bad[:5]}")
            print(f"  Events during 5s pause window: {[e.get('kind') for e in gap_events[:10]]}")

            # RESUME
            resume_mark = len(events)
            r = await c.post(f"{BASE}/tasks/{task_id}/resume")
            print(f"  resume: {r.status_code} {r.json()}")
            assert r.status_code == 200

            await asyncio.sleep(1)
            has_resumed = any(e.get("kind") == "runtime_resumed" for e in events)
            check("runtime_resumed event emitted", has_resumed)

            # Wait for execution to continue
            await asyncio.sleep(5)
            after = events[resume_mark:]
            has_work = any(
                e.get("kind") in {"tool_started", "tool_completed", "action_selected"}
                for e in after
            )
            check("execution resumes after pause (new actions)", has_work)
            if after:
                print(f"  Events after resume: {[e.get('kind') for e in after[:8]]}")

    else:
        print("  No task_id captured — aborting")
        await collector
        return False

    # 6. Wait for natural completion
    print("\n--- [6/6] Wait for Completion ---")
    try:
        await asyncio.wait_for(task_done.wait(), timeout=60)
        print("  Task completed naturally")
    except asyncio.TimeoutError:
        if task_id:
            async with httpx.AsyncClient() as c:
                await c.post(f"{BASE}/tasks/{task_id}/stop")
            print("  Task stopped (timeout)")

    if collector:
        await asyncio.sleep(0.5)

    # Event sequence validation
    print("\n--- Event Sequence Validation ---")
    kinds = [e.get("kind") for e in events]

    for required in ["task_started", "runtime_paused", "runtime_resumed"]:
        check(f"{required} in sequence", required in kinds)

    # Timeline
    print("\nTimeline (key events):")
    show = {"task_started", "phase_changed", "action_selected",
            "tool_started", "tool_completed",
            "runtime_paused", "runtime_resumed",
            "task_completed", "task_failed", "runtime_stopped"}
    for i, ev in enumerate(events):
        k = ev.get("kind", "")
        if k in show:
            p = json.dumps(ev.get("payload", {}), ensure_ascii=False)[:60]
            print(f"  [{i:3d}] {k:25s} {p}")

    print(f"\n  Total events: {len(events)}")

    # Final result
    print("\n" + "=" * 60)
    print(f"ACL-01 RESULT: {PASS} passed / {FAIL} failed")
    print("=" * 60)
    return FAIL == 0


if __name__ == "__main__":
    result = asyncio.run(test_acl01())
    sys.exit(0 if result else 1)
