"""Symbol Index — cross-file symbol definitions, references, and locations.

Answers: "Where is this symbol defined?"
         "Where is this symbol used?"

Built on top of CodeGraph for definitions and text search for references.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SymbolDef:
    """A symbol definition — where something is declared."""

    name: str
    kind: str  # "class", "function", "method", "variable"
    file_path: str
    line: int
    qualified_name: str = ""

    def __post_init__(self) -> None:
        if not self.qualified_name:
            self.qualified_name = self.name


@dataclass
class SymbolRef:
    """A symbol reference — where something is used."""

    name: str
    file_path: str
    line: int
    context: str = ""  # the line of code


class SymbolIndex:
    """Cross-file symbol index.

    Tracks every definition and reference for important symbols.
    Enables "find all usages" and "go to definition" style queries.
    """

    # Regex patterns for finding references
    REF_PATTERNS = {
        "class": re.compile(r'\bclass\s+(\w+)'),
        "function": re.compile(r'\bdef\s+(\w+)'),
        "call": re.compile(r'(\w+)\s*\('),
        "import": re.compile(r'(?:import|from)\s+([\w.]+)'),
        "decorator": re.compile(r'@(\w+)'),
    }

    def __init__(self) -> None:
        self._defs: dict[str, list[SymbolDef]] = {}  # name → definitions
        self._refs: dict[str, list[SymbolRef]] = {}  # name → references
        self._def_index: dict[str, list[SymbolDef]] = {}  # file → definitions

    def index_definitions(self, file_path: str, content: str) -> list[SymbolDef]:
        """Extract symbol definitions from file content.

        Args:
            file_path: Source file path
            content: File contents

        Returns:
            List of discovered definitions
        """
        defs: list[SymbolDef] = []
        for line_no, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()

            # Class definitions
            m = re.match(r'class\s+(\w+)', stripped)
            if m:
                sd = SymbolDef(name=m.group(1), kind="class", file_path=file_path, line=line_no)
                defs.append(sd)
                self._defs.setdefault(m.group(1), []).append(sd)
                continue

            # Function definitions
            m = re.match(r'(?:async\s+)?def\s+(\w+)', stripped)
            if m:
                sd = SymbolDef(name=m.group(1), kind="function", file_path=file_path, line=line_no)
                defs.append(sd)
                self._defs.setdefault(m.group(1), []).append(sd)
                continue

            # Module-level variable assignments
            m = re.match(r'(\w+)\s*=\s*(?:class|def|lambda|\(|\{)', stripped)
            if m:
                sd = SymbolDef(name=m.group(1), kind="variable", file_path=file_path, line=line_no)
                defs.append(sd)
                self._defs.setdefault(m.group(1), []).append(sd)

        self._def_index[file_path] = defs
        return defs

    def index_references(self, file_path: str, content: str,
                         symbols_of_interest: set[str] | None = None) -> list[SymbolRef]:
        """Find references to known symbols in file content.

        Args:
            file_path: Source file path
            content: File contents
            symbols_of_interest: If provided, only look for these symbols.
                                 If None, looks for all known definitions.

        Returns:
            List of references found
        """
        candidates = symbols_of_interest or set(self._defs.keys())
        if not candidates:
            return []

        refs: list[SymbolRef] = []
        # Word boundary regex per candidate
        for line_no, line in enumerate(content.splitlines(), 1):
            for sym in candidates:
                # Match as word (not part of longer identifier)
                if re.search(rf'\b{re.escape(sym)}\b', line):
                    # Skip if it's a definition line
                    if re.match(rf'\s*(?:class|def|async\s+def)\s+{re.escape(sym)}\b', line):
                        continue
                    refs.append(SymbolRef(name=sym, file_path=file_path, line=line_no, context=line.strip()))
                    break  # one reference per line max

        self._refs.setdefault(file_path, []).extend(refs)
        return refs

    def find_definitions(self, name: str) -> list[SymbolDef]:
        """Find all definitions of a symbol across the codebase."""
        return self._defs.get(name, [])

    def find_references(self, name: str) -> list[SymbolRef]:
        """Find all references to a symbol across the codebase."""
        refs = []
        for file_refs in self._refs.values():
            for r in file_refs:
                if r.name == name:
                    refs.append(r)
        return refs

    def find_all_usages(self, name: str) -> tuple[list[SymbolDef], list[SymbolRef]]:
        """Get definitions and references for a symbol."""
        return self.find_definitions(name), self.find_references(name)

    def get_file_symbols(self, file_path: str) -> list[SymbolDef]:
        """Get all symbols defined in a file."""
        return self._def_index.get(file_path, [])

    @property
    def total_defs(self) -> int:
        return sum(len(defs) for defs in self._defs.values())

    @property
    def total_refs(self) -> int:
        return sum(len(refs) for refs in self._refs.values())

    def summary(self) -> dict[str, Any]:
        return {
            "total_symbols": len(self._defs),
            "total_definitions": self.total_defs,
            "total_references": self.total_refs,
            "symbols_with_references": sum(1 for refs in self._refs.values() if refs),
        }
