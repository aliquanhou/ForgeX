#!/usr/bin/env python3
"""ACL-02 真实场景：Human Takeover 期间手工改文件后恢复.

场景：
  1. Agent 在 workspace 中创建并修改文件
  2. 人工接管 (take_over)
  3. 人在磁盘上直接编辑文件（不同的内容）
  4. Agent 恢复 (resume)，继续工作
  5. 验证：Agent 不暴力覆盖人工修改

这个测试涉及真实文件系统操作，不是 state.facts 模拟。
"""

import asyncio
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from forge.kernel.runtime import Runtime
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


async def test_acl02_real_takeover():
    """ACL-02 真实文件接管测试.

    Agent 在 temp workspace 中改文件 → 人接管 → 人改文件 → resume.
    """
    print("\n" + "=" * 64)
    print("ACL-02 (Real): Human Takeover — 真实文件接管")
    print("=" * 64)

    # ── 1. Setup: temp workspace with a file ──
    workspace = Path(tempfile.mkdtemp(prefix="acl02_ws_"))
    target_file = workspace / "app.py"
    AGENT_CONTENT = """# app.py — 由 Agent 生成
def hello():
    print("hello from agent")

if __name__ == "__main__":
    hello()
"""

    HUMAN_CONTENT = """# app.py — 人工修改版
def hello():
    print("hello from human — this must survive!")

if __name__ == "__main__":
    hello()
    print("human edit: added debug line")
"""
    # 初始内容由 agent 创建
    target_file.write_text(AGENT_CONTENT, encoding="utf-8")
    print(f"\n  [Setup] Workspace: {workspace}")
    print(f"  [Setup] File: {target_file}")
    print(f"  [Setup] Agent initial content written ({len(AGENT_CONTENT)} chars)")

    # ── 2. Start Runtime with file-modifying handlers ──
    rt = Runtime(token_budget=100000, round_limit=20)

    async def plan(state):
        for i in range(3):
            await asyncio.sleep(0.2)
            state.add_fact(f"planned_step_{i}")

    async def explore(state):
        for i in range(3):
            await asyncio.sleep(0.2)
            state.add_fact(f"explored_{i}")

    async def implement(state):
        """Agent modifies the file: appends a function."""
        await asyncio.sleep(0.1)
        content = target_file.read_text(encoding="utf-8")
        state.add_fact(f"agent_read_file: {len(content)} chars")

        # Agent appends its work
        with target_file.open("a", encoding="utf-8") as f:
            f.write(f"\n# Agent round {state.round}\n")
            f.write("def agent_func():\n")
            f.write("    return 'agent_work'\n")

        state.add_change(f"agent_modified_file: round_{state.round}")
        state.add_fact(f"agent_wrote_round_{state.round}")

    rt.on_plan(plan)
    rt.on_explore(explore)
    rt.on_implement(implement)
    rt.on_verify(lambda s: s.add_fact("verified"))

    # ── 3. Collect events ──
    events: list[Event] = []

    async def collector():
        async for ev in event_bus.subscribe():
            events.append(ev)
            if ev.kind in (EventKind.TASK_COMPLETED, EventKind.TASK_FAILED):
                break

    collector_task = asyncio.create_task(collector())
    run_task = asyncio.create_task(rt.run("acl-02 real takeover"))

    # Wait for agent to do at least one implement round
    await asyncio.sleep(0.5)
    print(f"\n  [Event] task started, events={len(events)}")

    # Let agent do first round of file modifications
    await asyncio.sleep(2.0)

    # Snapshot file state before takeover
    pre_takeover_content = target_file.read_text(encoding="utf-8")
    pre_takeover_size = len(pre_takeover_content)
    print(f"\n  [Agent] File after agent work ({pre_takeover_size} chars):")
    for line in pre_takeover_content.splitlines():
        print(f"    | {line}")

    # ── 4. HUMAN TAKE OVER ──
    print(f"\n  >>> HUMAN TAKES OVER <<<")
    await rt.take_over()
    await asyncio.sleep(0)
    check("state.paused after takeover", rt.state.paused is True)
    check("state.human_override after takeover", rt.state.human_override is True)

    # ── 5. Human manually edits the file ──
    print(f"\n  [Human] Manually overwriting {target_file}...")
    target_file.write_text(HUMAN_CONTENT, encoding="utf-8")
    post_human_content = target_file.read_text(encoding="utf-8")
    print(f"  [Human] File now ({len(post_human_content)} chars):")
    for line in post_human_content.splitlines():
        print(f"    | {line}")

    # Wait a bit — agent should NOT modify file during takeover
    await asyncio.sleep(2.0)
    current_content = target_file.read_text(encoding="utf-8")
    check("human content preserved during takeover",
          current_content == HUMAN_CONTENT,
          f"Expected human content, got {len(current_content)} chars")

    # Verify no new tool/action events during takeover
    takeover_events = [e for e in events if e.kind in {
        EventKind.TOOL_STARTED, EventKind.ACTION_SELECTED} and
        events.index(e) > events.index(
            next(e2 for e2 in reversed(events) if e2.kind == EventKind.HUMAN_OVERRIDE_STARTED))]
    check("no new action/tool during takeover",
          len(takeover_events) <= 0,
          f"Found {len(takeover_events)} events during takeover")

    # ── 6. RESUME ──
    print(f"\n  >>> RESUME <<<")
    await rt.resume()
    await asyncio.sleep(0)
    check("state.paused False after resume", rt.state.paused is False)
    check("state.human_override False after resume", rt.state.human_override is False)

    # Wait for agent to do at least one more implement round
    await asyncio.sleep(4.0)

    # ── 7. Wait for completion ──
    await asyncio.wait_for(run_task, timeout=60)
    await collector_task

    # ── 8. FINAL VERIFICATION ──
    final_content = target_file.read_text(encoding="utf-8")
    print(f"\n  [Final] File content ({len(final_content)} chars):")
    for line in final_content.splitlines():
        print(f"    | {line}")

    # CRITICAL: Human's edits must be preserved
    check("human edit line survives in final file",
          "human edit: added debug line" in final_content,
          f"Human line missing!")
    check("human function signature preserved",
          "def hello():" in final_content,
          f"Human function missing!")
    check("human print message preserved",
          'print("hello from human' in final_content,
          f"Human print missing!")

    # Agent should have appended its work (not overwritten)
    check("agent added new work (didn't overwrite)",
          "agent_modified_file" in str(rt.state.recent_changes) or
          any("agent_func" in line for line in final_content.splitlines()),
          f"Agent didn't add content: changes={rt.state.recent_changes}")

    # Event validation
    kinds = [e.kind.value for e in events]
    for required in ["task_started", "human_override_started",
                     "human_override_ended", "runtime_resumed",
                     "task_completed"]:
        check(f"'{required}' in event sequence", required in kinds)

    # Ordered validation
    order_ok = True
    try:
        start = kinds.index("human_override_started")
        end = kinds.index("human_override_ended")
        check("human_override_started before human_override_ended", start < end)
    except ValueError:
        order_ok = False

    print(f"\n  [Summary] Events: {len(events)}")
    print(f"  [Summary] File: {pre_takeover_size} -> {len(post_human_content)} (human) "
          f"-> {len(final_content)} chars (final)")
    print(f"\nACL-02 (Real): {PASS}/{PASS+FAIL} passed")

    # Cleanup
    import shutil
    shutil.rmtree(workspace, ignore_errors=True)

    return FAIL == 0


if __name__ == "__main__":
    result = asyncio.run(test_acl02_real_takeover())
    sys.exit(0 if result else 1)
