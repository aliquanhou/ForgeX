"""Code Graph — AST-based code structure extraction.

Extracts classes, functions, imports, and module structure
from Python source files using the built-in ast module.

This is the foundation layer of the World Model.
Without understanding what exists in the code, you can't
analyze impact, dependencies, or architecture.

Supports Python only in v0.4. Tree-sitter extension planned.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class CodeNodeKind(str, Enum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    IMPORT = "import"
    CONSTANT = "constant"


@dataclass
class CodeNode:
    """A single node in the code graph."""

    name: str
    kind: CodeNodeKind
    file_path: str
    line: int
    end_line: int = 0
    parent: str = ""  # parent node name (e.g., class name for methods)
    docstring: str = ""
    signature: str = ""  # e.g., "def foo(x: int) -> str"
    decorators: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # names of things this node references

    @property
    def qualified_name(self) -> str:
        if self.parent:
            return f"{self.parent}.{self.name}"
        return self.name


class CodeGraph:
    """AST-based code graph for a project.

    Walks Python files and extracts:
    - Classes with methods and decorators
    - Functions with signatures
    - Module-level variables and constants
    - Import relationships
    """

    SUPPORTED_EXTENSIONS = {".py"}

    def __init__(self) -> None:
        self._nodes: dict[str, list[CodeNode]] = {}  # file_path → nodes
        self._module_docstrings: dict[str, str] = {}

    def scan_file(self, file_path: str) -> list[CodeNode]:
        """Scan a single Python file and extract code nodes.

        Args:
            file_path: Path to the .py file

        Returns:
            List of extracted CodeNodes
        """
        path = Path(file_path)
        if path.suffix not in self.SUPPORTED_EXTENSIONS:
            return []

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content, filename=file_path)

            nodes = self._extract_nodes(tree, file_path, content)
            self._nodes[file_path] = nodes

            # Extract module docstring
            mod = ast.get_docstring(tree)
            if mod:
                self._module_docstrings[file_path] = mod

            return nodes

        except SyntaxError as e:
            return []  # Can't parse, skip
        except Exception:
            return []

    def scan_directory(self, directory: str, recursive: bool = True) -> dict[str, list[CodeNode]]:
        """Scan all Python files in a directory.

        Args:
            directory: Root directory to scan
            recursive: Whether to recurse into subdirectories

        Returns:
            Dict of file_path → list of CodeNodes
        """
        root = Path(directory)

        pattern = "**/*.py" if recursive else "*.py"
        results: dict[str, list[CodeNode]] = {}

        for py_file in sorted(root.glob(pattern)):
            rel_path = str(py_file.relative_to(root) if py_file.is_relative_to(root) else py_file)
            nodes = self.scan_file(str(py_file))
            if nodes:
                results[rel_path] = nodes

        self._nodes.update(results)
        return results

    def _extract_nodes(self, tree: ast.Module, file_path: str, content: str) -> list[CodeNode]:
        """Extract CodeNodes from an AST."""
        nodes: list[CodeNode] = []
        lines = content.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                cn = CodeNode(
                    name=node.name,
                    kind=CodeNodeKind.CLASS,
                    file_path=file_path,
                    line=node.lineno or 0,
                    end_line=node.end_lineno or 0,
                    docstring=ast.get_docstring(node) or "",
                    decorators=[self._decorator_name(d) for d in node.decorator_list],
                    signature=f"class {node.name}",
                )
                nodes.append(cn)

                # Extract methods
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                        method = CodeNode(
                            name=item.name,
                            kind=CodeNodeKind.METHOD,
                            file_path=file_path,
                            line=item.lineno or 0,
                            end_line=item.end_lineno or 0,
                            parent=node.name,
                            docstring=ast.get_docstring(item) or "",
                            decorators=[self._decorator_name(d) for d in item.decorator_list],
                            signature=self._function_signature(item),
                        )
                        nodes.append(method)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Module-level function (not inside a class)
                if not self._is_method(node, tree):
                    fn = CodeNode(
                        name=node.name,
                        kind=CodeNodeKind.FUNCTION,
                        file_path=file_path,
                        line=node.lineno or 0,
                        end_line=node.end_lineno or 0,
                        docstring=ast.get_docstring(node) or "",
                        decorators=[self._decorator_name(d) for d in node.decorator_list],
                        signature=self._function_signature(node),
                    )
                    nodes.append(fn)

            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    imp = CodeNode(
                        name=alias.name if isinstance(node, ast.Import) else
                             f"{node.module}.{alias.name}" if node.module else alias.name,
                        kind=CodeNodeKind.IMPORT,
                        file_path=file_path,
                        line=node.lineno or 0,
                    )
                    nodes.append(imp)

        return nodes

    def _function_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Build a simple signature string."""
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                try:
                    ann = ast.dump(arg.annotation)
                    arg_str += f": {ann}"
                except Exception:
                    pass
            args.append(arg_str)
        returns = ""
        if node.returns:
            try:
                returns = f" -> {ast.dump(node.returns)}"
            except Exception:
                pass
        prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
        return f"{prefix}{node.name}({', '.join(args)}){returns}"

    def _decorator_name(self, node: ast.expr) -> str:
        """Extract decorator name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node, ast.Attribute):
            return f"{self._decorator_name(node.value)}.{node.attr}"
        return ast.dump(node)

    def _is_method(self, node: ast.FunctionDef, tree: ast.Module) -> bool:
        """Check if a function is inside a class."""
        for parent in ast.walk(tree):
            if isinstance(parent, ast.ClassDef):
                for child in parent.body:
                    if child is node:
                        return True
        return False

    def get_nodes(self, file_path: str | None = None) -> list[CodeNode]:
        """Get all nodes, optionally filtered by file."""
        if file_path:
            return self._nodes.get(file_path, [])
        all_nodes = []
        for nodes in self._nodes.values():
            all_nodes.extend(nodes)
        return all_nodes

    def find(self, name: str, kind: CodeNodeKind | None = None) -> list[CodeNode]:
        """Find nodes by name."""
        results = []
        for nodes in self._nodes.values():
            for node in nodes:
                if node.name == name or node.qualified_name == name:
                    if kind is None or node.kind == kind:
                        results.append(node)
        return results

    @property
    def file_count(self) -> int:
        return len(self._nodes)

    @property
    def node_count(self) -> int:
        return sum(len(nodes) for nodes in self._nodes.values())

    def summary(self) -> dict[str, Any]:
        from collections import Counter
        kind_counts = Counter()
        for nodes in self._nodes.values():
            for node in nodes:
                kind_counts[node.kind.value] += 1
        return {
            "files": self.file_count,
            "total_nodes": self.node_count,
            "by_kind": dict(kind_counts.most_common()),
        }
