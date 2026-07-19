"""Dependency Graph — import chains and file-level dependency resolution.

Answers: "What does this file depend on?"
         "What files depend on this file?"

Built from scanning import statements across the codebase.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class DepKind(str, Enum):
    IMPORT = "import"
    FROM_IMPORT = "from_import"
    RELATIVE = "relative"


@dataclass
class Dependency:
    """A single dependency relationship between two files."""

    source: str  # file that has the import
    target: str  # file being imported
    kind: DepKind
    symbol: str = ""  # specific symbol imported (for "from X import Y")
    line: int = 0


class DependencyGraph:
    """File-level dependency graph for a project.

    Tracks both incoming and outgoing dependencies.
    Enables transitive dependency resolution.
    """

    def __init__(self) -> None:
        self._dependencies: list[Dependency] = []
        self._outgoing: dict[str, set[str]] = defaultdict(set)  # file → files it imports
        self._incoming: dict[str, set[str]] = defaultdict(set)  # file → files importing it

    def add_dependency(self, dep: Dependency) -> None:
        """Record a dependency."""
        self._dependencies.append(dep)
        self._outgoing[dep.source].add(dep.target)
        self._incoming[dep.target].add(dep.source)

    def scan_file(self, file_path: str, content: str = "") -> list[Dependency]:
        """Scan a file for import statements and extract dependencies.

        Args:
            file_path: Path of the file (for resolving relative imports)
            content: File contents. If empty, reads from disk.

        Returns:
            List of Dependency objects found
        """
        path = Path(file_path)
        if not content:
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                return []

        import ast
        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError:
            return []

        file_dir = path.parent
        deps: list[Dependency] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = self._resolve_import(alias.name)
                    if target:
                        dep = Dependency(
                            source=str(file_path).replace("\\", "/"),
                            target=target,
                            kind=DepKind.IMPORT,
                            symbol=alias.asname or alias.name,
                            line=node.lineno or 0,
                        )
                        deps.append(dep)
                        self.add_dependency(dep)

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                level = node.level  # 0 = absolute, 1+ = relative

                for alias in node.names:
                    if level > 0:
                        # Relative import
                        relative_to = file_dir
                        for _ in range(level - 1):
                            relative_to = relative_to.parent
                        if module:
                            target_path = relative_to / module.replace(".", "/") / f"{alias.name}.py"
                        else:
                            target_path = relative_to / f"{alias.name}.py"
                        target = str(target_path.resolve()).replace("\\", "/")
                    else:
                        if module:
                            target = self._resolve_import(f"{module}.{alias.name}")
                        else:
                            target = self._resolve_import(alias.name)

                    if target:
                        dep = Dependency(
                            source=str(file_path).replace("\\", "/"),
                            target=target,
                            kind=DepKind.FROM_IMPORT,
                            symbol=alias.name,
                            line=node.lineno or 0,
                        )
                        deps.append(dep)
                        self.add_dependency(dep)

        return deps

    def scan_directory(self, directory: str) -> dict[str, list[Dependency]]:
        """Scan all Python files in a directory for dependencies."""
        root = Path(directory)
        results: dict[str, list[Dependency]] = {}
        for py_file in sorted(root.glob("**/*.py")):
            deps = self.scan_file(str(py_file))
            if deps:
                rel = str(py_file.relative_to(root))
                results[rel] = deps
        return results

    def _resolve_import(self, import_name: str) -> str:
        """Resolve a Python import name to a file path.

        This is a best-effort heuristic. Real resolution needs
        sys.path context which we don't have here.
        """
        # Convert "os.path" to "os/path.py"
        return import_name.replace(".", "/") + ".py"

    def get_outgoing(self, file_path: str) -> list[str]:
        """Get files that file_path imports."""
        normalized = file_path.replace("\\", "/")
        return sorted(self._outgoing.get(normalized, set()))

    def get_incoming(self, file_path: str) -> list[str]:
        """Get files that import file_path."""
        normalized = file_path.replace("\\", "/")
        return sorted(self._incoming.get(normalized, set()))

    def get_transitive_outgoing(self, file_path: str, max_depth: int = 3) -> dict[str, int]:
        """Get transitive dependencies (things this file depends on indirectly).

        Returns dict of file → depth.
        """
        normalized = file_path.replace("\\", "/")
        result: dict[str, int] = {}
        visited: set[str] = set()

        def walk(current: str, depth: int) -> None:
            if depth > max_depth or current in visited:
                return
            visited.add(current)
            for dep in self._outgoing.get(current, set()):
                if dep not in result:
                    result[dep] = depth
                walk(dep, depth + 1)

        walk(normalized, 1)
        return result

    def get_transitive_incoming(self, file_path: str, max_depth: int = 3) -> dict[str, int]:
        """Get transitive dependents (files that depend on this indirectly)."""
        normalized = file_path.replace("\\", "/")
        result: dict[str, int] = {}
        visited: set[str] = set()

        def walk(current: str, depth: int) -> None:
            if depth > max_depth or current in visited:
                return
            visited.add(current)
            for dep in self._incoming.get(current, set()):
                if dep not in result:
                    result[dep] = depth
                walk(dep, depth + 1)

        walk(normalized, 1)
        return result

    @property
    def total_dependencies(self) -> int:
        return len(self._dependencies)

    @property
    def file_count(self) -> int:
        return len(set(d.source for d in self._dependencies) |
                    set(d.target for d in self._dependencies))

    def summary(self) -> dict[str, Any]:
        return {
            "total_dependencies": self.total_dependencies,
            "files_in_graph": self.file_count,
            "avg_outgoing": round(len(self._dependencies) / max(self.file_count, 1), 2),
        }
