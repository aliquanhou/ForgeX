"""Plugin SDK — extension framework for ForgeX.

From v0.5 LTS onward, all new capabilities go through the Plugin system.
The kernel is frozen. Extensions live here.

Plugin types:
- Language plugins (python, java, go, ...)
- Domain plugins (web, trading, cad, ...)
- Model plugins (deepseek, claude, qwen, local, ...)
- Tool plugins (docker, k8s, aws, db, ...)
- Memory plugins (software, trading, design, ...)
"""

from .sdk import ForgePlugin, PluginSpec, PluginHook, PluginCapability
from .registry import PluginRegistry

__all__ = [
    "ForgePlugin", "PluginSpec", "PluginHook", "PluginCapability",
    "PluginRegistry",
]
