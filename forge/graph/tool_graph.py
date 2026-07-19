"""Tool Graph v2 — Adaptive DAG with dynamic node insertion.

v0.3: From Static DAG → Adaptive Graph.
When tests fail → auto-insert debug_node.
When verify fails → auto-insert fix_node.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

from .node import ToolNode, NodeStatus, NodeHook, HookResult


class ToolGraph:
    """Adaptive DAG of tool nodes.

    v0.3 upgrades:
    - Dynamic node insertion on failure
    - Auto-repair paths
    - Execution history tracking
    """

    def __init__(self) -> None:
        self._nodes: dict[str, ToolNode] = {}
        self._state: dict[str, Any] = {
            "snapshot_taken": False,
            "file_backed_up": False,
            "changes_verified": False,
            "tested": False,
            "committed": False,
        }
        self._execution_history: list[dict[str, Any]] = []
        self._adaptive_hooks: list[Callable[[str, dict[str, Any]], list[ToolNode]]] = []

    def add_node(self, node: ToolNode) -> ToolNode:
        self._nodes[node.name] = node
        return node

    def get_node(self, name: str) -> ToolNode | None:
        return self._nodes.get(name)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def on_failure(self, hook: Callable[[str, dict[str, Any]], list[ToolNode]]) -> None:
        """Register a hook that fires when a node fails.

        The hook receives (failed_node_name, state) and can return
        new nodes to dynamically insert (e.g., debug node).
        """
        self._adaptive_hooks.append(hook)

    def record_failure(self, node_name: str, error: str) -> list[ToolNode]:
        """Called when a node fails. Triggers adaptive hooks."""
        self._state["last_error"] = error
        self._execution_history.append({
            "node": node_name,
            "status": "failed",
            "error": error,
        })

        inserted: list[ToolNode] = []
        for hook in self._adaptive_hooks:
            new_nodes = hook(node_name, self._state)
            for n in new_nodes:
                self.add_node(n)
                inserted.append(n)
        return inserted

    def record_success(self, node_name: str, result: Any = None) -> None:
        self._execution_history.append({
            "node": node_name,
            "status": "succeeded",
        })
        node = self._nodes.get(node_name)
        if node:
            node.status = NodeStatus.SUCCEEDED
            for key, value in node.postconditions:
                self._state[key] = value

    def resolve_order(self) -> list[str]:
        """Topological sort with adaptive path support."""
        in_degree: dict[str, int] = {name: 0 for name in self._nodes}
        adjacency: dict[str, list[str]] = {name: [] for name in self._nodes}

        for name, node in self._nodes.items():
            for dep in node.depends_on:
                if dep in self._nodes:
                    adjacency[dep].append(name)
                    in_degree[name] = in_degree.get(name, 0) + 1

        queue = deque([name for name, deg in in_degree.items() if deg == 0])
        order: list[str] = []

        while queue:
            name = queue.popleft()
            order.append(name)
            for neighbor in adjacency[name]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self._nodes):
            raise ValueError("Cycle detected")
        return order

    def check_preconditions(self, node_name: str) -> list[str]:
        node = self._nodes.get(node_name)
        if node is None:
            return [f"Unknown node: {node_name}"]

        failures = []
        for i, pred in enumerate(node.preconditions):
            try:
                if not pred(self._state):
                    failures.append(f"Precondition {i} failed for {node_name}")
            except Exception as e:
                failures.append(f"Precondition {i} error: {e}")

        for dep_name in node.depends_on:
            dep = self._nodes.get(dep_name)
            if dep and dep.status != NodeStatus.SUCCEEDED:
                failures.append(f"Dependency {dep_name} not succeeded")

        return failures

    def update_state(self, key: str, value: Any) -> None:
        self._state[key] = value

    def get_state(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def reset(self) -> None:
        for node in self._nodes.values():
            node.status = NodeStatus.PENDING
        self._state = {
            "snapshot_taken": False,
            "file_backed_up": False,
            "changes_verified": False,
            "tested": False,
            "committed": False,
        }
        self._execution_history.clear()

    @property
    def history(self) -> list[dict[str, Any]]:
        return list(self._execution_history)

    def summary(self) -> dict[str, Any]:
        return {
            "total_nodes": len(self._nodes),
            "node_statuses": {n: nd.status.value for n, nd in self._nodes.items()},
            "executed": len(self._execution_history),
            "state": dict(self._state),
        }

    def to_dot(self) -> str:
        lines = ['digraph ToolGraph {', '  rankdir="LR";']
        for name, node in self._nodes.items():
            color = {"pending": "gray", "running": "blue", "succeeded": "green",
                     "failed": "red", "skipped": "orange"}.get(node.status.value, "gray")
            lines.append(f'  "{name}" [label="{name}\\n{node.status.value}", color="{color}"];')
            for dep in node.depends_on:
                lines.append(f'  "{dep}" -> "{name}";')
        lines.append("}")
        return "\n".join(lines)
