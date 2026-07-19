"""Impact Analysis — what breaks if I change X?

Uses the CodeGraph, DependencyGraph, and SymbolIndex to compute
the blast radius of a proposed change.

This is the key module that turns Forge from "AI programmer"
into "AI architect". Before writing any code, it can tell you
what the consequences will be.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class RiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class ImpactResult:
    """Result of an impact analysis."""

    target: str  # what was analyzed (file path or symbol name)
    risk: RiskLevel

    # Direct impacts
    affected_files: list[str] = field(default_factory=list)
    affected_symbols: list[str] = field(default_factory=list)
    affected_apis: list[str] = field(default_factory=list)
    affected_tests: list[str] = field(default_factory=list)

    # Metrics
    total_files_affected: int = 0
    total_tests_affected: int = 0
    transitive_file_count: int = 0

    # Recommendations
    suggestions: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        lines = [f"Impact analysis for: {self.target}"]
        lines.append(f"Risk: {self.risk.value}")
        if self.affected_files:
            lines.append(f"Files affected: {len(self.affected_files)}")
        if self.affected_tests:
            lines.append(f"Tests affected: {len(self.affected_tests)}")
        if self.affected_apis:
            lines.append(f"APIs affected: {len(self.affected_apis)}")
        if self.suggestions:
            lines.append("Suggestions:")
            for s in self.suggestions[:3]:
                lines.append(f"  • {s}")
        return "\n".join(lines)


class ImpactAnalysis:
    """Impact analysis engine.

    Usage:
        analysis = ImpactAnalysis(code_graph, dep_graph, symbol_index)
        result = analysis.analyze_file("models/user.py")
        print(result.summary)
    """

    # Common test file markers
    TEST_MARKERS = {"test_", "_test", "tests/", "test/"}

    # Common API file markers
    API_MARKERS = {"routes", "api", "endpoint", "view", "controller", "handler"}

    def __init__(self) -> None:
        self._code_graph = None
        self._dep_graph = None
        self._symbol_index = None
        self._project_root: str = ""

    def setup(self, code_graph, dep_graph, symbol_index, project_root: str = "") -> None:
        """Connect to the knowledge graph subsystems."""
        self._code_graph = code_graph
        self._dep_graph = dep_graph
        self._symbol_index = symbol_index
        self._project_root = project_root

    def analyze_file(self, file_path: str) -> ImpactResult:
        """Analyze impact of modifying a file."""
        normalized = file_path.replace("\\", "/")

        # 1. Direct dependents
        direct_dependents = []
        transitive_dependents = {}
        if self._dep_graph:
            direct_dependents = self._dep_graph.get_incoming(normalized)
            transitive_dependents = self._dep_graph.get_transitive_incoming(normalized, max_depth=2)

        # 2. Symbols defined in this file
        symbols = []
        if self._symbol_index:
            symbols = self._symbol_index.get_file_symbols(normalized)

        # 3. Find references to those symbols
        referenced_in = set()
        for sym in symbols:
            _, refs = self._symbol_index.find_all_usages(sym.name) if self._symbol_index else ([])
            for ref in refs:
                if ref.file_path != normalized:
                    referenced_in.add(ref.file_path)

        # 4. Classify affected files
        all_affected = list(set(direct_dependents) | referenced_in)
        tests_affected = [f for f in all_affected if self._is_test_file(f)]
        apis_affected = [f for f in all_affected if self._is_api_file(f)]
        source_affected = [f for f in all_affected if not self._is_test_file(f) and not self._is_api_file(f)]

        # 5. Compute risk
        risk = self._compute_risk(len(all_affected), len(tests_affected), len(apis_affected),
                                   len(transitive_dependents))

        # 6. Suggestions
        suggestions = []
        if tests_affected:
            suggestions.append(f"Run tests for {len(tests_affected)} affected test files")
        if apis_affected:
            suggestions.append(f"Verify {len(apis_affected)} API endpoints still work")
        if len(all_affected) > 5:
            suggestions.append(f"Consider incremental deployment — {len(all_affected)} files affected")

        affected_symbols = [s.qualified_name for s in symbols]

        return ImpactResult(
            target=normalized,
            risk=risk,
            affected_files=sorted(all_affected),
            affected_symbols=affected_symbols,
            affected_apis=sorted(apis_affected),
            affected_tests=sorted(tests_affected),
            total_files_affected=len(all_affected),
            total_tests_affected=len(tests_affected),
            transitive_file_count=len(transitive_dependents),
            suggestions=suggestions,
        )

    def analyze_symbol(self, symbol_name: str) -> ImpactResult:
        """Analyze impact of modifying a symbol."""
        if not self._symbol_index:
            return ImpactResult(target=symbol_name, risk=RiskLevel.UNKNOWN,
                                suggestions=["Symbol index not available"])

        defs, refs = self._symbol_index.find_all_usages(symbol_name)

        if not defs:
            return ImpactResult(target=symbol_name, risk=RiskLevel.NONE,
                                suggestions=["Symbol not found in index"])

        # Files containing definitions
        def_files = set(d.file_path for d in defs)

        # Files containing references
        ref_files = set(r.file_path for r in refs)

        all_files = def_files | ref_files
        tests = [f for f in all_files if self._is_test_file(f)]
        apis = [f for f in all_files if self._is_api_file(f)]

        risk = self._compute_risk(len(all_files), len(tests), len(apis), len(ref_files))

        return ImpactResult(
            target=symbol_name,
            risk=risk,
            affected_files=sorted(all_files),
            affected_symbols=[symbol_name],
            affected_apis=sorted(apis),
            affected_tests=sorted(tests),
            total_files_affected=len(all_files),
            total_tests_affected=len(tests),
            suggestions=[
                f"Symbol defined in {len(def_files)} file(s)",
                f"Referenced in {len(ref_files)} file(s)",
            ],
        )

    def _compute_risk(
        self,
        files_affected: int,
        tests_affected: int,
        apis_affected: int,
        transitive_count: int,
    ) -> RiskLevel:
        """Compute risk level from impact metrics."""
        score = 0

        if files_affected == 0:
            return RiskLevel.NONE
        elif files_affected <= 2:
            score += 1
        elif files_affected <= 5:
            score += 2
        elif files_affected <= 10:
            score += 3
        else:
            score += 4

        if tests_affected > 0:
            score += 1
        if apis_affected > 0:
            score += 2
        if transitive_count > 5:
            score += 1

        if score >= 5:
            return RiskLevel.CRITICAL
        elif score >= 4:
            return RiskLevel.HIGH
        elif score >= 3:
            return RiskLevel.MEDIUM
        elif score >= 1:
            return RiskLevel.LOW
        return RiskLevel.NONE

    def _is_test_file(self, file_path: str) -> bool:
        """Check if a file is a test file."""
        return any(marker in file_path for marker in self.TEST_MARKERS)

    def _is_api_file(self, file_path: str) -> bool:
        """Check if a file is an API/endpoint file."""
        return any(marker in file_path.lower() for marker in self.API_MARKERS)
