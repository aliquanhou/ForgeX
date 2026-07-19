"""Tool Graph — DAG-based tool orchestration.

Manages tool dependencies, execution ordering, and state transitions.
Tools don't just "run" — they traverse a lifecycle with pre/post conditions.

This is the foundation for:
- Safe execution ordering (snapshot before write)
- Dependency resolution (test depends on build)
- Rollback chains (rollback in reverse order)
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

from .node import ToolNode, NodeStatus, NodeHook, HookResult


class ToolGraph:
    """DAG of tool nodes with dependency resolution.

    Usage:
        graph = ToolGraph()
        graph.add_node(read_node)
        graph.add_node(write_node, depends_on=["read_file"])
        graph.add_node(test_node, depends_on=["write_file"])

        order = graph.resolve_order()  # Topological sort
        await graph.execute("write_file")  # Auto-checks preconditions
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

    def add_node(self, node: ToolNode) -> ToolNode:
        """Add a node to the graph."""
        self._nodes[node.name] = node
        return node

    def get_node(self, name: str) -> ToolNode | None:
        return self._nodes.get(name)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def resolve_order(self) -> list[str]:
        """Topological sort of node names based on depends_on.

        Returns execution order. Raises ValueError on cycles.
        """
        # Build in-degree map
        in_degree: dict[str, int] = {name: 0 for name in self._nodes}
        adjacency: dict[str, list[str]] = {name: [] for name in self._nodes}

        for name, node in self._nodes.items():
            for dep in node.depends_on:
                if dep in self._nodes:
                    adjacency[dep].append(name)
                    in_degree[name] = in_degree.get(name, 0) + 1

        # Kahn's algorithm
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
            raise ValueError("Cycle detected in tool graph dependencies")

        return order

    def check_preconditions(self, node_name: str) -> list[str]:
        """Check preconditions for a node. Returns list of failures."""
        node = self._nodes.get(node_name)
        if node is None:
            return [f"Unknown node: {node_name}"]

        failures = []
        for i, pred in enumerate(node.preconditions):
            try:
                if not pred(self._state):
                    failures.append(f"Precondition {i} failed for {node_name}")
            except Exception as e:
                failures.append(f"Precondition {i} error for {node_name}: {e}")

        # Check dependency statuses
        for dep_name in node.depends_on:
            dep = self._nodes.get(dep_name)
            if dep and dep.status != NodeStatus.SUCCEEDED:
                failures.append(f"Dependency {dep_name} not yet succeeded (status={dep.status.value})")

        return failures

    def update_state(self, key: str, value: Any) -> None:
        """Update graph state (applies postconditions)."""
        self._state[key] = value

    def get_state(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def reset(self) -> None:
        """Reset all nodes to PENDING and clear state."""
        for node in self._nodes.values():
            node.status = NodeStatus.PENDING
        self._state = {
            "snapshot_taken": False,
            "file_backed_up": False,
            "changes_verified": False,
            "tested": False,
            "committed": False,
        }

    def summary(self) -> dict[str, Any]:
        return {
            "total_nodes": len(self._nodes),
            "node_statuses": {n: nd.status.value for n, nd in self._nodes.items()},
            "state": self._state,
        }

    def to_dot(self) -> str:
        """Generate DOT graph for visualization (Graphviz)."""
        lines = ["digraph ToolGraph {", '  rankdir="LR";']
        for name, node in self._nodes.items():
            lines.append(f'  "{name}" [label="{name}\\n{node.status.value}"];')
            for dep in node.depends_on:
                lines.append(f'  "{dep}" -> "{name}";')
        lines.append("}")
        return "\n".join(lines)
