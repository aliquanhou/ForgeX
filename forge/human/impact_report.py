"""Impact Report — human-readable, structured report of what a proposed change will affect.

Integrates with the World Model (ImpactAnalysis) to produce
reports that non-technical stakeholders can understand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ReportLevel(str, Enum):
    EXECUTIVE = "executive"  # One-liner summary
    BRIEF = "brief"  # Key findings only
    DETAILED = "detailed"  # Full analysis


@dataclass
class ReportSection:
    """A section within the impact report."""

    title: str
    content: str
    level: ReportLevel = ReportLevel.DETAILED
    items: list[str] = field(default_factory=list)


@dataclass
class ImpactReport:
    """A complete impact report for human reading."""

    title: str
    goal: str
    timestamp: str = ""

    # Sections
    executive_summary: str = ""
    risk_assessment: str = ""
    affected_modules: list[str] = field(default_factory=list)
    affected_tests: list[str] = field(default_factory=list)
    affected_apis: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    detailed_sections: list[ReportSection] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_markdown(self) -> str:
        """Render as a formatted markdown report."""
        lines = [
            f"# {self.title}",
            f"\n**Goal:** {self.goal}",
            f"**Generated:** {self.timestamp}",
        ]

        if self.executive_summary:
            lines.extend(["\n## Executive Summary", self.executive_summary])

        if self.risk_assessment:
            lines.extend(["\n## Risk Assessment", self.risk_assessment])

        if self.affected_modules:
            lines.extend(["\n## Affected Modules"] + [f"- {m}" for m in self.affected_modules])

        if self.affected_apis:
            lines.extend(["\n## Affected APIs"] + [f"- {a}" for a in self.affected_apis])

        if self.affected_tests:
            lines.extend(["\n## Affected Tests"] + [f"- {t}" for t in self.affected_tests])

        for section in self.detailed_sections:
            lines.extend([f"\n### {section.title}", section.content])
            if section.items:
                lines.extend([f"- {item}" for item in section.items])

        if self.recommendations:
            lines.extend(["\n## Recommendations"] + [f"- {r}" for r in self.recommendations])

        return "\n".join(lines)


class ReportGenerator:
    """Generates human-readable impact reports from analysis data.

    Usage:
        gen = ReportGenerator()
        report = gen.from_impact_result(result, goal="Add field to User model")
        markdown = report.to_markdown()
    """

    def from_impact_result(
        self,
        impact_result: Any,
        goal: str = "",
        project_name: str = "Project",
    ) -> ImpactReport:
        """Generate a report from an ImpactAnalysis result.

        Args:
            impact_result: Result from forge.knowledge.impact_analysis.ImpactAnalysis
            goal: The change goal
            project_name: Name of the project

        Returns:
            Formatted ImpactReport
        """
        risk = impact_result.risk.value if hasattr(impact_result.risk, 'value') else str(impact_result.risk)

        # Executive summary
        exec_summary = (
            f"Modifying **{impact_result.target}** affects "
            f"**{impact_result.total_files_affected} files** "
            f"({impact_result.total_tests_affected} tests, "
            f"{len(impact_result.affected_apis)} APIs). "
            f"Risk level: **{risk.upper()}**."
        )

        # Risk assessment
        risk_lines = {
            "none": "No measurable impact detected.",
            "low": "Isolated change with minimal blast radius. Standard review recommended.",
            "medium": "Change affects multiple modules. Testing recommended before deployment.",
            "high": "Significant blast radius. Requires thorough testing and stakeholder awareness.",
            "critical": "Core system change. Requires full regression suite and architectural review.",
            "unknown": "Could not fully assess impact. Manual review required.",
        }
        risk_assessment = risk_lines.get(risk, "Impact requires manual assessment.")

        # Recommendations
        recommendations = list(impact_result.suggestions) if hasattr(impact_result, 'suggestions') else []
        if impact_result.total_tests_affected > 0:
            recommendations.insert(0, f"Run {impact_result.total_tests_affected} affected test suites")
        if impact_result.total_files_affected > 5:
            recommendations.append("Consider incremental deployment to reduce risk")

        return ImpactReport(
            title=f"Change Impact Report: {project_name}",
            goal=goal or impact_result.target,
            executive_summary=exec_summary,
            risk_assessment=risk_assessment,
            affected_modules=impact_result.affected_files[:20],
            affected_tests=impact_result.affected_tests,
            affected_apis=impact_result.affected_apis,
            recommendations=recommendations,
            metadata={
                "target": impact_result.target,
                "risk": risk,
                "total_files": impact_result.total_files_affected,
                "transitive_files": impact_result.transitive_file_count,
            },
        )

    def from_dict(self, data: dict[str, Any], goal: str = "") -> ImpactReport:
        """Generate a report from a dict (for custom data)."""
        affected = data.get("affected_files", [])
        tests = data.get("affected_tests", [])
        apis = data.get("affected_apis", [])
        risk = data.get("risk", "unknown")

        return ImpactReport(
            title="Change Impact Report",
            goal=goal or data.get("target", "Unknown"),
            executive_summary=(
                f"Change affects **{len(affected)} files** "
                f"({len(tests)} tests, {len(apis)} APIs). "
                f"Risk: **{risk.upper()}**."
            ),
            risk_assessment=f"Risk level: {risk}",
            affected_modules=affected[:20],
            affected_tests=tests,
            affected_apis=apis,
            recommendations=data.get("recommendations", []),
        )
