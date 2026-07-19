"""Plugin SDK — the contract between plugins and the ForgeX kernel.

Every plugin implements ForgePlugin.
The kernel only depends on this interface, never on plugin internals.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable


class PluginHook(str, Enum):
    """Lifecycle hooks a plugin can register."""

    # Tool hooks
    BEFORE_TOOL = "before_tool"
    AFTER_TOOL = "after_tool"
    TOOL_REGISTER = "tool_register"

    # Execution hooks
    BEFORE_EXECUTE = "before_execute"
    AFTER_EXECUTE = "after_execute"

    # Decision hooks
    DECISION_ADVISE = "decision_advise"

    # Verification hooks
    VERIFY_ARTIFACT = "verify_artifact"

    # Event hooks
    ON_EVENT = "on_event"


class PluginCapability(str, Enum):
    """What a plugin can do."""

    TOOLS = "tools"  # Provides additional tools
    LANGUAGE = "language"  # Language-specific analysis (AST, lint, test)
    MODEL = "model"  # Alternative model provider
    MEMORY = "memory"  # Custom memory storage
    VERIFIER = "verifier"  # Custom verification
    ANALYZER = "analyzer"  # Custom code analysis
    HOOKS = "hooks"  # Lifecycle hooks only


@dataclass
class PluginSpec:
    """Plugin metadata — declared by every plugin."""

    name: str
    version: str
    description: str = ""
    author: str = ""
    capabilities: list[PluginCapability] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # other plugin names
    min_kernel_version: str = "0.5.0"


class ForgePlugin(ABC):
    """Base class for all ForgeX plugins.

    Usage:
        class MyPlugin(ForgePlugin):
            spec = PluginSpec(name="my-plugin", version="1.0.0", ...)

            async def initialize(self, runtime):
                # Register tools, hooks, etc.
                pass

            async def tools(self):
                return [my_tool_spec]

            async def hooks(self):
                return {PluginHook.AFTER_TOOL: [my_hook_fn]}
    """

    spec: PluginSpec

    @abstractmethod
    async def initialize(self, runtime: Any) -> None:
        """Called when the plugin is loaded.

        Args:
            runtime: ForgeRuntime instance for registering tools/hooks
        """
        ...

    async def tools(self) -> list[Any]:
        """Return additional tools this plugin provides."""
        return []

    async def hooks(self) -> dict[PluginHook, list[Callable[..., Awaitable[Any]]]]:
        """Return lifecycle hooks this plugin registers."""
        return {}

    async def shutdown(self) -> None:
        """Called when the plugin is unloaded."""
        pass

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def version(self) -> str:
        return self.spec.version
