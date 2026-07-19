"""Tool Registry — the central catalog of all available tools.

Every tool has a spec that defines:
- What it does
- What arguments it accepts
- Whether it requires approval
- How its output is validated
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable


class ToolStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    REJECTED = "rejected"
    ERROR = "error"


class ToolKind(str, Enum):
    SEARCH = "search"
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    GIT = "git"
    NETWORK = "network"
    ANALYSIS = "analysis"
    SYSTEM = "system"


@dataclass
class ToolResult:
    """Result of executing a tool."""

    status: ToolStatus
    data: Any = None
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == ToolStatus.SUCCESS


@dataclass
class ToolSpec:
    """Specification of a tool."""

    name: str
    description: str
    kind: ToolKind
    parameters: dict[str, Any]  # JSON Schema
    requires_approval: bool = False
    handler: Callable[..., Awaitable[ToolResult]] | None = None


class ToolRegistry:
    """Registry of all available tools.

    Tools are registered by name and can be looked up by kind.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> ToolSpec:
        """Register a tool spec."""
        self._tools[spec.name] = spec
        return spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list_by_kind(self, kind: ToolKind) -> list[ToolSpec]:
        return [t for t in self._tools.values() if t.kind == kind]

    def list_all(self) -> list[ToolSpec]:
        return list(self._tools.values())

    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool by name."""
        spec = self.get(name)
        if spec is None:
            return ToolResult(ToolStatus.ERROR, error=f"Unknown tool: {name}")
        if spec.handler is None:
            return ToolResult(ToolStatus.ERROR, error=f"No handler for tool: {name}")
        try:
            return await spec.handler(**kwargs)
        except Exception as e:
            return ToolResult(ToolStatus.ERROR, error=str(e))

    def summary(self) -> list[dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "kind": spec.kind.value,
                "description": spec.description,
                "requires_approval": spec.requires_approval,
            }
            for spec in self._tools.values()
        ]


# Global registry
registry = ToolRegistry()
