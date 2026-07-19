"""Tool Node — a single node in the Tool Graph DAG.

Each node wraps a tool with:
- Preconditions: what must be true BEFORE execution
- Postconditions: what becomes true AFTER execution
- Hooks: lifecycle callbacks (before, after, on_error)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable


class NodeStatus(str, Enum):
    PENDING = "pending"
    BLOCKED = "blocked"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class NodeHook(str, Enum):
    """Lifecycle hook points."""

    BEFORE = "before"
    AFTER = "after"
    ON_ERROR = "on_error"
    ON_SKIP = "on_skip"


@dataclass
class HookResult:
    """Result from a hook execution."""

    ok: bool
    message: str = ""
    data: Any = None
    abort: bool = False  # If True, stop the tool execution


# Pre/post condition: a predicate on workspace state
ConditionFn = Callable[[dict[str, Any]], bool]
HookFn = Callable[[dict[str, Any], dict[str, Any]], Awaitable[HookResult]]


@dataclass
class ToolNode:
    """A single node in the Tool Graph.

    Example:
        node = ToolNode(
            name="write_file",
            preconditions=[lambda s: s.get("snapshot_taken")],
            postconditions=[("file_written", True)],
        )
    """

    name: str
    description: str = ""

    # Dependencies: other node names that must succeed first
    depends_on: list[str] = field(default_factory=list)

    # Preconditions: all must be True for this node to be READY
    preconditions: list[ConditionFn] = field(default_factory=list)

    # Postconditions: state mutations after success
    postconditions: list[tuple[str, Any]] = field(default_factory=list)

    # Lifecycle hooks
    hooks: dict[NodeHook, list[HookFn]] = field(default_factory=lambda: {h.value: [] for h in NodeHook})

    # Current status
    status: NodeStatus = NodeStatus.PENDING

    # Whether this operation requires user approval
    requires_approval: bool = False

    def add_hook(self, hook: NodeHook, fn: HookFn) -> None:
        self.hooks.setdefault(hook, []).append(fn)

    @property
    def is_ready(self) -> bool:
        return self.status == NodeStatus.READY

    @property
    def is_done(self) -> bool:
        return self.status in (NodeStatus.SUCCEEDED, NodeStatus.FAILED, NodeStatus.SKIPPED)
