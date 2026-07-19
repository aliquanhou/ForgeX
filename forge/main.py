"""Forge Agent OS — Main entry point.

Usage:
    python -m forge.main              Start the API server
    python -m forge.main run --task   Run a single task via CLI
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from forge.config import config
from forge.kernel.event_bus import Event, EventKind, event_bus
from forge.kernel.runtime import Runtime
from forge.kernel.state import TaskPhase


# --- FastAPI App ---

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager — replaces deprecated on_event."""
    _register_tools()
    print(f"  Forge Agent OS v0.1.0")
    print(f"  LLM: {config.llm_model} @ {config.llm_base_url}")
    print(f"  Workspace: {config.workspace_root}")
    yield
    await event_bus.aclose()
    print("  Forge Agent OS shut down.")


app = FastAPI(
    title="Forge Agent OS",
    version="0.1.0",
    description="Runtime-Driven Autonomous Engineering System",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _register_tools() -> None:
    """Register all tools with the global registry."""
    from forge.tools import search, file_tools, execute, git_tools
    loop = asyncio.get_event_loop()
    loop.create_task(search._register())
    loop.create_task(file_tools._register())
    loop.create_task(execute._register())
    loop.create_task(git_tools._register())


# --- Mount API routes ---

from forge.api.routes import router
app.include_router(router)


# --- CLI handler ---

def cli_run(args: argparse.Namespace) -> None:
    """Run a single task from the CLI."""
    goal = args.task
    if not goal:
        print("Error: --task <goal> is required")
        sys.exit(1)

    async def _run() -> None:
        runtime = Runtime(round_limit=10)  # Safety limit

        # Register handlers
        async def plan_handler(state):
            state.add_fact(f"Planning for: {state.goal}")
            print(f"  [Plan] Goal: {state.goal}")
            print(f"  [Plan] Intent: {state.intent}")

        async def explore_handler(state):
            print(f"  [Explore] Round {state.round}: gathering info...")
            state.add_fact(f"Explored codebase in round {state.round}")
            state.add_change(f"Explored: {state.goal}")

        async def implement_handler(state):
            print(f"  [Execute] Round {state.round}: working on '{state.goal[:60]}'")
            state.add_fact(f"Executing round {state.round}")
            state.add_change(f"Implementation round {state.round}")

        async def verify_handler(state):
            print(f"  [Verify] Checking results...")
            state.add_change("Verification completed")

        async def finalize_handler(state):
            print(f"  [Finalize] Delivering results...")
            print(f"  [Finalize] {len(state.artifacts)} artifacts produced")

        runtime.on_plan(plan_handler)
        runtime.on_explore(explore_handler)
        runtime.on_implement(implement_handler)
        runtime.on_verify(verify_handler)
        runtime.on_finalize(finalize_handler)

        # Subscribe to events (in background, cancelled when runtime finishes)
        async def print_events():
            try:
                async for event in event_bus.subscribe():
                    if event.kind in (EventKind.ACTION_SELECTED, EventKind.PHASE_CHANGED, EventKind.ERROR, EventKind.TASK_COMPLETED, EventKind.TASK_FAILED):
                        print(f"  [{event.kind.value}] {event.payload}")
            except asyncio.CancelledError:
                pass

        monitor_task = asyncio.create_task(print_events())
        try:
            runtime_result = await runtime.run(goal)
        finally:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
        if isinstance(runtime_result, Exception):
            print(f"\n  [Error] {runtime_result}")
        else:
            print(f"\n{'='*50}")
            print(f"  Task:    {runtime_result.task_id}")
            print(f"  Success: {runtime_result.success}")
            print(f"  Rounds:  {runtime_result.rounds}")
            print(f"  Phase:   {runtime_result.phase}")
            print(f"  Time:    {runtime_result.total_time_seconds:.2f}s")
            print(f"  Tokens:  {runtime_result.tokens_used}")
            if runtime_result.artifacts:
                for a in runtime_result.artifacts:
                    print(f"  Artifact: [{a['kind']}] {a['path']}")

    asyncio.run(_run())


def cli_server() -> None:
    """Start the Forge API server."""
    uvicorn.run(
        "forge.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level="info" if not config.debug else "debug",
    )


def main() -> None:
    """Forge CLI entry point."""
    parser = argparse.ArgumentParser(description="Forge Agent OS")
    parser.add_argument("command", nargs="?", default="server", help="run | server")
    parser.add_argument("--task", "-t", help="Run a single task")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)

    args = parser.parse_args()

    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port

    if args.command == "run" and args.task:
        cli_run(args)
    else:
        cli_server()


if __name__ == "__main__":
    main()
