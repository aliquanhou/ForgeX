"""Test Intent Router — conversation should short-circuit engineering pipeline."""
import asyncio, httpx, json, sys
sys.path.insert(0, "D:\\claude\\forge")
# Avoid GBK crashes on emoji in event payloads
_orig_print = print
def safeprint(*args, **kw):
    kw.setdefault("file", sys.stdout)
    kw.pop("flush", None)
    _orig_print(*args, **kw, flush=True)
print = safeprint

BASE = "http://localhost:5173/api"

async def test_conversation():
    events = []
    sse_ready = asyncio.Event()
    task_done = asyncio.Event()

    async def sse():
        async with httpx.AsyncClient(timeout=30) as c:
            async with c.stream("GET", f"{BASE}/tasks/events", timeout=30) as resp:
                sse_ready.set()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        ev = json.loads(line[6:])
                        events.append(ev)
                        if ev["kind"] in ("task_completed","task_failed","runtime_stopped"):
                            task_done.set()
                            return

    sse_task = asyncio.create_task(sse())
    await asyncio.wait_for(sse_ready.wait(), timeout=10)

    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/tasks", json={"goal":"你好", "token_budget":5000, "round_limit":3})
        tid = r.json()["task_id"]
        print(f"Task: {tid}")

    await asyncio.wait_for(task_done.wait(), timeout=30)
    await sse_task

    kinds = [e["kind"] for e in events]
    print(f"Events ({len(events)}):")
    for i, e in enumerate(events):
        k = e["kind"]
        p = json.dumps(e.get("payload",{}), ensure_ascii=False)[:100]
        print(f"  [{i:2d}] {k:25s} {p}")

    has_implement_phase = any(
        e["kind"] == "phase_changed" and e.get("payload",{}).get("to") == "implementation"
        for e in events)
    has_verify_phase = any(
        e["kind"] == "phase_changed" and e.get("payload",{}).get("to") == "verification"
        for e in events)
    has_phase = any(e["kind"] == "phase_changed" for e in events)
    has_intent = any(e["kind"] == "intent_detected" for e in events)
    rounds = next((e["payload"].get("rounds", 0) for e in events if e["kind"] == "task_completed"), 0)

    print(f"intent_detected: {has_intent}")
    print(f"phase_changed: {has_phase}")
    print(f"implement phase: {has_implement_phase}")
    print(f"verify phase: {has_verify_phase}")
    print(f"rounds: {rounds}")

    # Conversation: has intent_detected, 1 round, NO implement/verify phases
    passed = has_intent and rounds <= 2 and not has_implement_phase
    if passed:
        print("\n=== INTENT ROUTER: PASS (conversation short-circuited) ===")
    else:
        print("\n=== INTENT ROUTER: FAIL ===")
    return passed

async def test_engineering_task():
    events = []
    sse_ready = asyncio.Event()
    task_done = asyncio.Event()

    async def sse():
        async with httpx.AsyncClient(timeout=30) as c:
            async with c.stream("GET", f"{BASE}/tasks/events", timeout=30) as resp:
                sse_ready.set()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        ev = json.loads(line[6:])
                        events.append(ev)
                        if ev["kind"] in ("task_completed","task_failed","runtime_stopped"):
                            task_done.set()
                            return

    sse_task = asyncio.create_task(sse())
    await asyncio.wait_for(sse_ready.wait(), timeout=10)

    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/tasks", json={"goal":"分析项目架构并生成优化建议","token_budget":30000,"round_limit":6})
        tid = r.json()["task_id"]
        print(f"Engineering Task: {tid}")

    await asyncio.wait_for(task_done.wait(), timeout=60)
    await sse_task

    kinds = [e["kind"] for e in events]
    print(f"Events ({len(events)}): {kinds}")

    has_intent = any(e["kind"] == "intent_detected" for e in events)
    has_implement = any(
        e["kind"] == "phase_changed" and e.get("payload",{}).get("to") == "implementation"
        for e in events)
    has_verify = any(
        e["kind"] == "phase_changed" and e.get("payload",{}).get("to") == "verification"
        for e in events)
    rounds = next((e["payload"].get("rounds", 0) for e in events if e["kind"] == "task_completed"), 0)

    print(f"intent_detected: {has_intent}")
    print(f"implement phase: {has_implement}")
    print(f"verify phase: {has_verify}")
    print(f"rounds: {rounds}")

    # Engineering: has intent_detected, 4+ rounds (plan→explore→implement→verify)
    passed = has_intent and has_implement and rounds >= 4
    if passed:
        print("\n=== INTENT ROUTER: PASS (engineering pipeline active) ===")
    else:
        print("\n=== INTENT ROUTER: FAIL ===")
    return passed

if __name__ == "__main__":
    print("=" * 50)
    print("Test 1: Conversation '你好'")
    print("=" * 50)
    r1 = asyncio.run(test_conversation())
    print()
    print("=" * 50)
    print("Test 2: Engineering '分析项目结构'")
    print("=" * 50)
    r2 = asyncio.run(test_engineering_task())
    print(f"\nOverall: {'PASS' if r1 and r2 else 'FAIL'}")
