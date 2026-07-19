#!/usr/bin/env python3
"""ACL-01 quick direct test — single assertion: round advances after resume."""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from forge.kernel.runtime import Runtime
from forge.kernel.event_bus import EventKind, event_bus

PASS = 0
FAIL = 0

def check(name, ok, detail=""):
    global PASS, FAIL
    if ok: PASS += 1; print(f"  [PASS] {name}")
    else:  FAIL += 1; print(f"  [FAIL] {name} -- {detail}")

async def test():
    rt = Runtime(token_budget=50000, round_limit=20)
    key_events = []

    async def collector():
        async for ev in event_bus.subscribe():
            k = ev.kind.value if hasattr(ev.kind, 'value') else str(ev.kind)
            key_events.append(k)
            if ev.kind in (EventKind.TASK_COMPLETED, EventKind.TASK_FAILED):
                break

    async def med(state):
        for i in range(8):
            await asyncio.sleep(0.15)
            state.add_fact(f'step_{i}')

    rt.on_plan(med); rt.on_explore(med); rt.on_implement(med)
    rt.on_verify(lambda s: s.add_fact('v_done'))
    rt.on_finalize(lambda s: s.add_fact('f_done'))

    c = asyncio.create_task(collector())
    t = asyncio.create_task(rt.run('acl01 direct'))

    await asyncio.sleep(0.4)
    pre_round = rt.state.round
    await rt.pause()

    check("state.paused after pause", rt.state.paused is True)
    check("pause_event NOT set", rt._pause_event.is_set() is False)

    await asyncio.sleep(1)
    still_round = rt.state.round
    delta = still_round - pre_round
    check(f"round stalled during pause (delta={delta})", delta <= 1,
          f"round grew {delta}: {pre_round} -> {still_round}")

    await rt.resume()

    check("state.paused after resume", rt.state.paused is False)
    check("pause_event IS set", rt._pause_event.is_set() is True)

    await asyncio.sleep(4)
    post_round = rt.state.round
    check(f"round advanced after resume ({still_round} -> {post_round})",
          post_round > still_round)

    await t; await c

    check("runtime_paused event", "runtime_paused" in key_events)
    check("runtime_resumed event", "runtime_resumed" in key_events)

    print(f"\nKey events: {key_events}")
    print(f"\nACL-01: {PASS}/{PASS+FAIL} passed")
    return FAIL == 0

if __name__ == "__main__":
    asyncio.run(test())
    sys.exit(0 if FAIL == 0 else 1)
