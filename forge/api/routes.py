"""FastAPI REST routes for Forge.

Provides the external API for creating tasks, monitoring progress,
and retrieving artifacts.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from forge.kernel.event_bus import Event, EventKind, event_bus
from forge.kernel.runtime import Runtime, RuntimeResult

router = APIRouter(prefix="/api", tags=["forge"])

# In-memory task store (replace with PostgreSQL later)
_tasks: dict[str, Runtime] = {}
_task_results: dict[str, RuntimeResult] = {}
_pending_runs: dict[str, asyncio.Task] = {}


# --- Request/Response models ---

class TaskRequest(BaseModel):
    goal: str
    session_id: str = ""
    token_budget: int = 100_000
    round_limit: int = 50


class TaskResponse(BaseModel):
    task_id: str
    status: str
    goal: str
    intent: str = ""
    message: str = ""


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    phase: str
    round: int
    goal: str
    is_running: bool


class TaskListResponse(BaseModel):
    tasks: list[TaskStatusResponse]


# --- Routes ---

@router.post("/tasks", response_model=TaskResponse)
async def create_task(request: TaskRequest) -> TaskResponse:
    """Create and start a task. Execution begins immediately in background."""
    runtime = Runtime(
        token_budget=request.token_budget,
        round_limit=request.round_limit,
    )
    task_id = runtime.state.task_id
    _tasks[request.goal] = runtime

    # ── Register default handlers so tasks produce meaningful output ──
    from forge.llm.client import LLMClient
    from forge.config import config
    from forge.kernel.event_bus import Event, EventKind
    llm = LLMClient(
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
        default_model=config.llm_model,
    )
    llm_response: dict[str, str] = {}

    async def publish(kind: EventKind, payload: dict):
        await event_bus.publish(Event(kind=kind, payload=payload, task_id=task_id))

    def track_tokens(resp):
        """Record LLM token usage into runtime state and budget."""
        tokens = (resp.tokens_in or 0) + (resp.tokens_out or 0)
        if tokens:
            runtime.state.total_tokens_used += tokens
            runtime.budget.consume_tokens(tokens)

    async def plan_handler(state):
        goal = state.goal
        state.current_plan = "1. Understand request\n2. Analyze context\n3. Generate response"
        await publish(EventKind.FACT_CONFIRMED, {"fact": f"Planning for: {goal}", "source": "scheduler", "confidence": 1.0})
        state.add_fact(f"Plan: analyze and respond to: {goal[:80]}")

    async def explore_handler(state):
        await publish(EventKind.FACT_CONFIRMED, {"fact": f"Analyzing: {state.goal[:80]}", "source": "scheduler", "confidence": 1.0})
        state.add_fact(f"Exploring request: {state.goal[:80]}")

    async def implement_handler(state):
        """Single LLM call — generate the actual response."""
        try:
            resp = await llm.chat(
                f"User request: {state.goal}\n\nProvide a complete, helpful response. Be concise and direct.",
                system="You are ForgeX Agent OS, an AI engineering assistant. Be concise, practical, and thorough.",
                max_tokens=1000,
            )
            track_tokens(resp)
            llm_response["result"] = resp.content
            state.add_fact(f"Result: {resp.content[:300]}")
            await publish(EventKind.FACT_CONFIRMED, {"fact": resp.content[:2000], "source": "llm", "confidence": 1.0, "is_final": True})
        except Exception as e:
            await publish(EventKind.FACT_CONFIRMED, {"fact": "Processing request... (LLM unavailable)", "source": "default", "confidence": 0.5})

    async def verify_handler(state):
        if "result" in llm_response:
            state.add_fact("Response generated successfully")
            await publish(EventKind.FACT_CONFIRMED, {"fact": "Response generated successfully", "source": "verifier", "confidence": 1.0})
        else:
            state.add_fact("Task completed")

    runtime.on_plan(plan_handler)
    runtime.on_explore(explore_handler)
    runtime.on_implement(implement_handler)
    runtime.on_verify(verify_handler)

    # Start execution in background -- events flow via EventBus -> SSE
    async def _run():
        try:
            result = await runtime.run(request.goal, request.session_id)
            _task_results[task_id] = result
        except Exception as e:
            print(f"  [Runtime] Task {task_id} failed: {e}")
        finally:
            _pending_runs.pop(task_id, None)

    _pending_runs[task_id] = asyncio.create_task(_run())

    return TaskResponse(
        task_id=task_id,
        status="running",
        goal=request.goal,
        message="Task started. Connect SSE to follow progress.",
    )


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks() -> TaskListResponse:
    """List all tasks."""
    tasks_list = []
    for goal, runtime in _tasks.items():
        s = runtime.state
        tasks_list.append(TaskStatusResponse(
            task_id=s.task_id,
            status=s.phase.value,
            phase=s.phase.value,
            round=s.round,
            goal=goal,
            is_running=not s.is_terminal,
        ))
    return TaskListResponse(tasks=tasks_list)


@router.get("/tasks/events")
async def stream_all_events():
    """SSE endpoint: stream ALL events in real-time (no task_id filter)."""
    async def event_generator() -> AsyncIterator[str]:
        async for event in event_bus.subscribe():
            yield f"data: {event.serialize()}\n\n"
            if event.kind in (EventKind.TASK_COMPLETED, EventKind.TASK_FAILED, EventKind.TASK_CANCELLED):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task(task_id: str) -> TaskStatusResponse:
    """Get task status by ID."""
    for goal, runtime in _tasks.items():
        if runtime.state.task_id == task_id:
            s = runtime.state
            return TaskStatusResponse(
                task_id=s.task_id,
                status=s.phase.value,
                phase=s.phase.value,
                round=s.round,
                goal=goal,
                is_running=not s.is_terminal,
            )
    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")


@router.get("/tasks/{task_id}/events")
async def stream_task_events(task_id: str):
    """SSE endpoint: stream events for a specific task."""
    async def event_generator() -> AsyncIterator[str]:
        async for event in event_bus.subscribe():
            if event.task_id and event.task_id != task_id:
                continue
            yield f"data: {event.serialize()}\n\n"
            if event.kind in (EventKind.TASK_COMPLETED, EventKind.TASK_FAILED, EventKind.TASK_CANCELLED):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/tasks/{task_id}/approve")
async def approve_action(task_id: str, approved: bool = True) -> dict[str, Any]:
    """Approve or reject a pending action."""
    await event_bus.publish(Event(
        kind=EventKind.APPROVAL_GRANTED if approved else EventKind.APPROVAL_DENIED,
        payload={"task_id": task_id, "approved": approved},
        task_id=task_id,
    ))
    return {"task_id": task_id, "approved": approved}


_demo_task: asyncio.Task | None = None


@router.post("/demo")
async def trigger_demo() -> dict[str, Any]:
    """Trigger the event replay demo in-process so SSE subscribers see the events."""
    global _demo_task
    if _demo_task and not _demo_task.done():
        raise HTTPException(status_code=409, detail="Demo is already running")

    from forge.demo.event_demo import replay_demo

    async def _run():
        try:
            await replay_demo()
        except Exception as e:
            print(f"  [demo] Error: {e}")

    _demo_task = asyncio.create_task(_run())
    return {"status": "started", "message": "Demo replay started. Connect SSE to watch."}


# ── v0.3.3 Autonomous Control Layer ──────────────────────────


def _find_runtime(task_id: str) -> Runtime:
    """Find a running Runtime by task_id."""
    for goal, runtime in _tasks.items():
        if runtime.state.task_id == task_id:
            if runtime.state.is_terminal:
                raise HTTPException(status_code=400, detail=f"Task {task_id} has already terminated")
            return runtime
    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")


class ModeRequest(BaseModel):
    mode: str


@router.post("/tasks/{task_id}/pause")
async def pause_task(task_id: str) -> dict[str, Any]:
    """Pause the runtime loop."""
    runtime = _find_runtime(task_id)
    await runtime.pause()
    return {"task_id": task_id, "status": "paused"}


@router.post("/tasks/{task_id}/resume")
async def resume_task(task_id: str) -> dict[str, Any]:
    """Resume from pause / end human override."""
    runtime = _find_runtime(task_id)
    await runtime.resume()
    return {"task_id": task_id, "status": "resumed"}


@router.post("/tasks/{task_id}/takeover")
async def takeover_task(task_id: str) -> dict[str, Any]:
    """Human takes over control from the agent."""
    runtime = _find_runtime(task_id)
    await runtime.take_over()
    return {"task_id": task_id, "status": "human_override"}


@router.post("/tasks/{task_id}/rollback")
async def rollback_task(task_id: str) -> dict[str, Any]:
    """Roll back the last snapshot."""
    runtime = _find_runtime(task_id)
    result = await runtime.rollback()
    return {"task_id": task_id, **result}


@router.post("/tasks/{task_id}/stop")
async def stop_task(task_id: str) -> dict[str, Any]:
    """Cancel the task immediately."""
    runtime = _find_runtime(task_id)
    await runtime.stop()
    return {"task_id": task_id, "status": "stopped"}


@router.post("/tasks/{task_id}/mode")
async def set_task_mode(task_id: str, req: ModeRequest) -> dict[str, Any]:
    """Switch runtime mode: autonomous | observe | governed."""
    runtime = _find_runtime(task_id)
    try:
        await runtime.set_mode(req.mode)
        return {"task_id": task_id, "mode": req.mode}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tasks/{task_id}/status")
async def task_status(task_id: str) -> dict[str, Any]:
    """Get full task status including control state."""
    for goal, runtime in _tasks.items():
        if runtime.state.task_id == task_id:
            s = runtime.state
            return {
                "task_id": task_id,
                "goal": s.goal,
                "phase": s.phase.value,
                "round": s.round,
                "mode": s.mode.value,
                "paused": s.paused,
                "human_override": s.human_override,
                "is_running": not s.is_terminal,
                "tokens_used": s.total_tokens_used,
            }
    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")


# ── Health ─────────────────────────────────────────────


@router.get("/health")
async def health() -> dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "forge-agent-os",
        "tasks_running": sum(1 for r in _tasks.values() if not r.state.is_terminal),
    }


@router.get("/tools", response_model=list[dict[str, Any]])
async def list_tools() -> list[dict[str, Any]]:
    """List all registered tools."""
    from forge.tools.registry import registry
    return registry.summary()
