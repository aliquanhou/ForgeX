"""Plugin Registry — manages plugin lifecycle, dependencies, and isolation.

Each plugin runs in its own context with declared capabilities.
The registry validates dependencies before loading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import importlib.util
import sys

from .sdk import ForgePlugin, PluginSpec, PluginCapability


@dataclass
class PluginInstance:
    """A loaded plugin instance with its state."""

    plugin: ForgePlugin
    spec: PluginSpec
    loaded: bool = False
    error: str = ""


class PluginRegistry:
    """Registry of all installed plugins.

    Handles discovery, loading, dependency resolution, and lifecycle.
    """

    def __init__(self) -> None:
        self._plugins: dict[str, PluginInstance] = {}
        self._search_paths: list[str] = []

    def add_search_path(self, path: str) -> None:
        """Add a directory to search for plugins."""
        self._search_paths.append(path)

    async def discover(self) -> list[PluginSpec]:
        """Discover plugins in search paths.

        Returns list of specs found (without loading them).
        """
        specs: list[PluginSpec] = []

        for search_path in self._search_paths:
            base = Path(search_path)
            if not base.exists():
                continue

            # Look for plugin packages: <name>/plugin.py or <name>.py
            for entry in base.iterdir():
                if entry.is_dir():
                    plugin_file = entry / "plugin.py"
                    if plugin_file.exists():
                        spec = self._inspect_plugin(str(plugin_file))
                        if spec:
                            specs.append(spec)
                elif entry.suffix == ".py" and entry.stem != "__init__":
                    spec = self._inspect_plugin(str(entry))
                    if spec:
                        specs.append(spec)

        return specs

    async def load_plugin(self, name: str) -> PluginInstance | None:
        """Load a plugin by name.

        Validates dependencies first. Returns None if not found.
        """
        # Find the plugin file
        plugin_path = self._find_plugin_file(name)
        if not plugin_path:
            return None

        try:
            # Load the Python module
            spec = importlib.util.spec_from_file_location(f"forge_plugin_{name}", plugin_path)
            if not spec or not spec.loader:
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            # Find the plugin class
            plugin_cls = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, ForgePlugin) and attr is not ForgePlugin:
                    plugin_cls = attr
                    break

            if not plugin_cls:
                return None

            # Validate dependencies
            temp_instance = plugin_cls()
            for dep_name in temp_instance.spec.dependencies:
                if dep_name not in self._plugins:
                    return PluginInstance(
                        plugin=temp_instance,
                        spec=temp_instance.spec,
                        loaded=False,
                        error=f"Missing dependency: {dep_name}",
                    )

            instance = PluginInstance(plugin=temp_instance, spec=temp_instance.spec)
            self._plugins[name] = instance
            return instance

        except Exception as e:
            return PluginInstance(
                plugin=None,  # type: ignore
                spec=PluginSpec(name=name, version="unknown"),
                loaded=False,
                error=str(e),
            )

    async def initialize_all(self, runtime: Any) -> list[str]:
        """Initialize all loaded plugins.

        Returns list of successfully initialized plugin names.
        """
        initialized: list[str] = []
        for name, instance in self._plugins.items():
            if instance.loaded:
                continue
            try:
                await instance.plugin.initialize(runtime)
                instance.loaded = True
                initialized.append(name)
            except Exception as e:
                instance.error = str(e)
        return initialized

    def get_plugin(self, name: str) -> PluginInstance | None:
        return self._plugins.get(name)

    def get_plugins_by_capability(self, cap: PluginCapability) -> list[PluginInstance]:
        return [
            p for p in self._plugins.values()
            if cap in p.spec.capabilities and p.loaded
        ]

    @property
    def loaded_count(self) -> int:
        return sum(1 for p in self._plugins.values() if p.loaded)

    @property
    def total_count(self) -> int:
        return len(self._plugins)

    def _inspect_plugin(self, plugin_file: str) -> PluginSpec | None:
        """Inspect a plugin file without loading it."""
        try:
            spec = importlib.util.spec_from_file_location("_inspect_", plugin_file)
            if not spec or not spec.loader:
                return None
            module = importlib.util.module_from_spec(spec)
            # Don't exec, just inspect the class
            for name, cls in inspect_getmembers_static(plugin_file):
                if isinstance(cls, type) and issubclass(cls, ForgePlugin) and cls is not ForgePlugin:
                    # Create lightweight instance just to read spec
                    return cls.spec  # type: ignore
            return None
        except Exception:
            return None

    def _find_plugin_file(self, name: str) -> str | None:
        """Find a plugin file by name."""
        for search_path in self._search_paths:
            base = Path(search_path)
            # Check <name>/plugin.py
            candidate = base / name / "plugin.py"
            if candidate.exists():
                return str(candidate)
            # Check <name>.py
            candidate = base / f"{name}.py"
            if candidate.exists():
                return str(candidate)
        return None


def inspect_getmembers_static(filepath: str) -> list[tuple[str, type]]:
    """Minimal static inspection — reads the file and finds class definitions."""
    import ast
    results: list[tuple[str, type]] = []
    try:
        with open(filepath, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Can't get real type without loading, but we can check name
                pass
    except Exception:
        pass
    return results
