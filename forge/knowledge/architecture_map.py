"""Architecture Map — high-level understanding of project structure.

Answers: "What layers does this project have?"
         "Which module does this file belong to?"
         "What's the boundary between components?"

Built from directory structure, naming conventions, and import patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class LayerKind(str, Enum):
    PRESENTATION = "presentation"  # UI, views, templates
    API = "api"  # REST, GraphQL, RPC endpoints
    APPLICATION = "application"  # use cases, services, business logic
    DOMAIN = "domain"  # core domain models and logic
    INFRASTRUCTURE = "infrastructure"  # DB, cache, external services
    CONFIG = "config"  # configuration, settings
    TEST = "test"  # tests
    UNKNOWN = "unknown"


@dataclass
class Layer:
    """A logical layer in the architecture."""

    name: str
    kind: LayerKind
    path: str  # directory path
    files: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)  # layer names this depends on
    is_boundary: bool = False  # is this an external boundary?


# Heuristics for identifying layer types from directory names
_DIR_LAYER_MAP: list[tuple[list[str], LayerKind]] = [
    (["view", "template", "ui", "component", "page", "frontend", "static"], LayerKind.PRESENTATION),
    (["api", "route", "endpoint", "controller", "handler", "resource"], LayerKind.API),
    (["service", "use_case", "interactor", "orchestrator", "application"], LayerKind.APPLICATION),
    (["domain", "entity", "model", "core", "exception", "value_object"], LayerKind.DOMAIN),
    (["repo", "repository", "db", "database", "cache", "queue", "storage", "adapter",
      "gateway", "external", "infra", "infrastructure"], LayerKind.INFRASTRUCTURE),
    (["config", "settings", "env", "constants"], LayerKind.CONFIG),
    (["test", "spec", "tests", "__tests__"], LayerKind.TEST),
]


class ArchitectureMap:
    """High-level architecture map of a project.

    Built by scanning directory structure and applying naming heuristics.
    """

    def __init__(self) -> None:
        self._layers: dict[str, Layer] = {}
        self._file_to_layer: dict[str, str] = {}  # file → layer name

    def scan_project(self, project_root: str) -> list[Layer]:
        """Scan a project directory and build architecture map.

        Args:
            project_root: Root directory of the project

        Returns:
            List of discovered layers
        """
        root = Path(project_root)
        if not root.exists():
            return []

        layers: dict[str, Layer] = {}

        # Walk top-level directories
        for entry in sorted(root.iterdir()):
            if not entry.is_dir() or entry.name.startswith((".", "_", "__")):
                continue

            # Classify this directory as a layer
            layer = self._classify_directory(entry)
            if layer and layer.files:
                layers[layer.name] = layer

                # Map files to layer
                for f in layer.files:
                    self._file_to_layer[f] = layer.name

        self._layers = layers

        # Infer layer dependencies from file imports
        self._infer_dependencies(project_root)

        return list(layers.values())

    def _classify_directory(self, directory: Path) -> Layer | None:
        """Classify a directory as an architecture layer.

        Scans one level deep for Python files.
        """
        py_files = list(directory.rglob("*.py"))
        if not py_files:
            return None

        rel_files = []
        for f in py_files:
            try:
                rel = str(f.relative_to(directory.parent))
                rel_files.append(rel.replace("\\", "/"))
            except ValueError:
                rel_files.append(str(f).replace("\\", "/"))

        # Classify by directory name
        dir_name = directory.name.lower()
        kind = LayerKind.UNKNOWN
        for keywords, layer_kind in _DIR_LAYER_MAP:
            if any(kw in dir_name for kw in keywords):
                kind = layer_kind
                break

        return Layer(
            name=directory.name,
            kind=kind,
            path=str(directory).replace("\\", "/"),
            files=rel_files,
        )

    def _infer_dependencies(self, project_root: str) -> None:
        """Infer layer dependencies from import patterns.

        If a file in layer A imports something from layer B,
        then layer A depends on layer B.
        """
        import ast

        for layer_name, layer in self._layers.items():
            for file_path in layer.files:
                full_path = Path(project_root) / file_path
                if not full_path.exists():
                    continue
                try:
                    content = full_path.read_text(encoding="utf-8", errors="replace")
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                self._check_import_target(layer, alias.name)
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                self._check_import_target(layer, node.module)
                except (SyntaxError, Exception):
                    pass

    def _check_import_target(self, source_layer: Layer, import_name: str) -> None:
        """If an import targets another known layer, record the dependency."""
        for target_name, target_layer in self._layers.items():
            if target_name == source_layer.name:
                continue
            # Check if import path matches target layer directory
            if target_name in import_name.split("."):
                if target_name not in source_layer.depends_on:
                    source_layer.depends_on.append(target_name)

    def get_layer(self, file_path: str) -> Layer | None:
        """Get the layer a file belongs to."""
        normalized = file_path.replace("\\", "/")
        layer_name = self._file_to_layer.get(normalized)
        if layer_name:
            return self._layers.get(layer_name)
        return None

    def get_boundary_files(self) -> list[str]:
        """Get files at layer boundaries (where layers depend on each other)."""
        boundary_files = []
        for layer_name, layer in self._layers.items():
            if layer.depends_on:
                boundary_files.extend(layer.files)
        return boundary_files

    @property
    def layer_count(self) -> int:
        return len(self._layers)

    def summary(self) -> dict[str, Any]:
        return {
            "layers": {
                name: {
                    "kind": layer.kind.value,
                    "files": len(layer.files),
                    "depends_on": layer.depends_on,
                }
                for name, layer in self._layers.items()
            },
            "layer_count": self.layer_count,
        }
