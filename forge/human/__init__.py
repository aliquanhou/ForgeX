"""Human Collaboration Layer — makes Forge explainable, reviewable, and safely controllable by humans.

Modules:
- approval: Diff-level approval with selective apply
- explanation: Structured explanation of why changes are needed
- impact_report: Human-readable impact report generation
- partial_merge: Apply only approved parts of a change set
"""

from .approval import ApprovalRequest, ApprovalDecision, ApprovalManager, ChangeItem
from .explanation import ChangeExplanation, Explainer
from .impact_report import ImpactReport, ReportGenerator
from .partial_merge import PartialMerge, MergeChunk, MergeDecision

__all__ = [
    "ApprovalRequest", "ApprovalDecision", "ApprovalManager", "ChangeItem",
    "ChangeExplanation", "Explainer",
    "ImpactReport", "ReportGenerator",
    "PartialMerge", "MergeChunk", "MergeDecision",
]
