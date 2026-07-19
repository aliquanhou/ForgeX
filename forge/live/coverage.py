"""Execution Coverage — tracks what code paths were executed.

Enables the agent to answer:
- "Did my change actually get exercised by the tests?"
- "Which paths are never tested?"
- "What's the code coverage of my change?"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CoverageLine:
    """A single line's coverage status."""

    line: int
    content: str
    executed: bool
    hit_count: int = 0


@dataclass
class CoverageResult:
    """Coverage for a single file."""

    file_path: str
    lines: list[CoverageLine] = field(default_factory=list)
    total_lines: int = 0
    executed_lines: int = 0

    @property
    def coverage_pct(self) -> float:
        if self.total_lines == 0:
            return 0.0
        return round(self.executed_lines / self.total_lines * 100, 1)

    @property
    def summary(self) -> str:
        return f"{self.file_path}: {self.coverage_pct}% ({self.executed_lines}/{self.total_lines})"


class ExecutionCoverage:
    """Tracks what code gets executed.

    Uses Python's sys.settrace or coverage.py if available.
    Falls back to heuristic coverage from tracebacks and log output.
    """

    def __init__(self) -> None:
        self._results: dict[str, CoverageResult] = {}

    def parse_coverage_report(self, report_path: str) -> dict[str, CoverageResult]:
        """Parse a coverage.py XML or text report.

        Args:
            report_path: Path to coverage report file

        Returns:
            Dict of file_path → CoverageResult
        """
        path = Path(report_path)
        if not path.exists():
            return {}

        content = path.read_text(encoding="utf-8", errors="replace")

        # Try parsing as coverage.py text report
        return self._parse_text_report(content) or self._parse_xml_report(content) or {}

    def _parse_text_report(self, content: str) -> dict[str, CoverageResult] | None:
        """Parse coverage.py text format: 'filename  stmts  miss  cover'"""
        results: dict[str, CoverageResult] = {}
        for line in content.splitlines():
            # Match: "path/to/file.py      10     2    80%"
            m = re.match(r'^(\S+\.py)\s+(\d+)\s+(\d+)\s+(\d+)%', line)
            if m:
                file_path = m.group(1)
                total = int(m.group(2))
                missed = int(m.group(3))
                executed = total - missed
                results[file_path] = CoverageResult(
                    file_path=file_path,
                    total_lines=total,
                    executed_lines=executed,
                )
        return results if results else None

    def _parse_xml_report(self, content: str) -> dict[str, CoverageResult] | None:
        """Parse coverage.py XML format (cobertura)."""
        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            return None

        results: dict[str, CoverageResult] = {}
        ns = "{http://cobertura.sourceforge.net}" if "cobertura" in content else ""

        for pkg in root.iter(f"{ns}package"):
            for cls in pkg.iter(f"{ns}class"):
                file_path = cls.get("filename", "")
                lines_budget = cls.find(f"{ns}lines")
                if lines_budget is None:
                    continue

                total = 0
                executed = 0
                cov_lines = []
                for line_elem in lines_budget.iter(f"{ns}line"):
                    line_num = int(line_elem.get("number", 0))
                    hits = int(line_elem.get("hits", 0))
                    total += 1
                    if hits > 0:
                        executed += 1
                    cov_lines.append(CoverageLine(
                        line=line_num,
                        content="",
                        executed=hits > 0,
                        hit_count=hits,
                    ))

                results[file_path] = CoverageResult(
                    file_path=file_path,
                    lines=cov_lines,
                    total_lines=total,
                    executed_lines=executed,
                )

        return results if results else {}

    def estimate_from_traceback(self, traceback_text: str, project_root: str = "") -> dict[str, set[int]]:
        """Estimate coverage from traceback lines.

        Every line mentioned in a traceback was definitely executed.
        This is pessimistic (misses non-failing paths) but guaranteed accurate
        for the paths that did run.
        """
        root = Path(project_root) if project_root else Path.cwd()
        executed: dict[str, set[int]] = {}

        # Match: 'File "path/to/file.py", line 42, in func'
        for m in re.finditer(r'File "([^"]+)", line (\d+)', traceback_text):
            file_path = m.group(1)
            line_num = int(m.group(2))

            try:
                # Try to make relative to project root
                fp = Path(file_path)
                if root in fp.parents:
                    file_path = str(fp.relative_to(root))
            except (ValueError, Exception):
                pass

            if file_path not in executed:
                executed[file_path] = set()
            executed[file_path].add(line_num)

        return executed

    def summary(self) -> dict[str, Any]:
        if not self._results:
            return {"status": "no coverage data"}
        files = len(self._results)
        total_lines = sum(r.total_lines for r in self._results.values())
        total_executed = sum(r.executed_lines for r in self._results.values())
        overall = round(total_executed / total_lines * 100, 1) if total_lines > 0 else 0
        return {
            "files": files,
            "total_lines": total_lines,
            "executed_lines": total_executed,
            "overall_coverage": overall,
        }
