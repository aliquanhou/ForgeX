"""FastAPI REST routes for Forge.

Provides the external API for creating tasks, monitoring progress,
and retrieving artifacts.
"""

from __future__ import annotations

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
    """Create a new task and start execution."""
    runtime = Runtime(
        token_budget=request.token_budget,
        round_limit=request.round_limit,
    )

    _tasks[request.goal] = runtime  # key by goal for dedup, use task_id later

    return TaskResponse(
        task_id=runtime.state.task_id,
        status="created",
        goal=request.goal,
        message="Task created. Use GET /api/tasks/{task_id}/stream to follow progress.",
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
    """SSE endpoint: stream events for a task in real-time."""
    async def event_generator() -> AsyncIterator[str]:
        async for event in event_bus.subscribe():
            if event.task_id and event.task_id != task_id:
                continue
            yield f"event: {event.kind.value}\ndata: {event.serialize()}\n\n"
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
