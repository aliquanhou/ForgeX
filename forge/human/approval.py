"""Approval Manager — diff-level approval with selective apply.

Enables the human to:
- See exactly what the agent wants to change
- Approve or reject individual changes
- Request modifications before approval
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ApprovalDecision(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


@dataclass
class ChangeItem:
    """A single atomic change that needs approval."""

    id: str
    action: str  # "edit", "create", "delete", "execute"
    path: str  # file path or command description
    diff: str = ""  # unified diff if applicable
    reason: str = ""  # why this change is needed
    risk: str = "low"  # "low", "medium", "high"
    category: str = "code"  # "code", "config", "test", "infra"
    decision: ApprovalDecision = ApprovalDecision.PENDING
    feedback: str = ""

    @property
    def needs_review(self) -> bool:
        return self.risk in ("medium", "high") or self.action == "delete"


@dataclass
class ApprovalRequest:
    """A request for human approval containing multiple changes."""

    id: str
    task_id: str
    goal: str
    items: list[ChangeItem] = field(default_factory=list)
    created_at: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    @property
    def summary(self) -> str:
        total = len(self.items)
        approved = sum(1 for i in self.items if i.decision == ApprovalDecision.APPROVED)
        rejected = sum(1 for i in self.items if i.decision == ApprovalDecision.REJECTED)
        pending = total - approved - rejected
        return f"Goal: {self.goal[:80]} | {total} changes | {approved} approved, {rejected} rejected, {pending} pending"

    @property
    def all_decided(self) -> bool:
        return all(i.decision != ApprovalDecision.PENDING for i in self.items)

    @property
    def approved_items(self) -> list[ChangeItem]:
        return [i for i in self.items if i.decision == ApprovalDecision.APPROVED]

    @property
    def rejected_items(self) -> list[ChangeItem]:
        return [i for i in self.items if i.decision == ApprovalDecision.REJECTED]


class ApprovalManager:
    """Manages the approval workflow for changes.

    Routes high-risk changes to human review.
    Low-risk changes can be auto-approved based on policy.
    """

    def __init__(self, auto_approve_low_risk: bool = True) -> None:
        self.auto_approve_low_risk = auto_approve_low_risk
        self._requests: dict[str, ApprovalRequest] = {}

    def create_request(self, task_id: str, goal: str, changes: list[dict[str, Any]]) -> ApprovalRequest:
        """Create an approval request from a list of changes.

        Args:
            task_id: The task that produced these changes
            goal: What the task is trying to achieve
            changes: List of change dicts with keys: action, path, diff, reason, risk, category

        Returns:
            ApprovalRequest with items
        """
        import uuid

        items = []
        for c in changes:
            item = ChangeItem(
                id=uuid.uuid4().hex[:8],
                action=c.get("action", "edit"),
                path=c.get("path", ""),
                diff=c.get("diff", ""),
                reason=c.get("reason", ""),
                risk=c.get("risk", "low"),
                category=c.get("category", "code"),
            )

            # Auto-approve low risk if configured
            if self.auto_approve_low_risk and not item.needs_review:
                item.decision = ApprovalDecision.APPROVED

            items.append(item)

        request = ApprovalRequest(
            id=uuid.uuid4().hex[:12],
            task_id=task_id,
            goal=goal,
            items=items,
        )
        self._requests[request.id] = request
        return request

    def get_request(self, request_id: str) -> ApprovalRequest | None:
        return self._requests.get(request_id)

    def approve(self, request_id: str, item_ids: list[str] | None = None) -> ApprovalRequest | None:
        """Approve all or specific items in a request.

        Args:
            request_id: The approval request
            item_ids: If provided, only approve these items. None = approve all.

        Returns:
            Updated request, or None if not found
        """
        request = self._requests.get(request_id)
        if request is None:
            return None

        for item in request.items:
            if item_ids is None or item.id in item_ids:
                if item.decision == ApprovalDecision.PENDING:
                    item.decision = ApprovalDecision.APPROVED

        return request

    def reject(self, request_id: str, item_ids: list[str] | None = None, feedback: str = "") -> ApprovalRequest | None:
        """Reject all or specific items."""
        request = self._requests.get(request_id)
        if request is None:
            return None

        for item in request.items:
            if item_ids is None or item.id in item_ids:
                if item.decision == ApprovalDecision.PENDING:
                    item.decision = ApprovalDecision.REJECTED
                    if feedback:
                        item.feedback = feedback

        return request

    def get_pending(self, task_id: str = "") -> list[ApprovalRequest]:
        """Get all requests with pending items."""
        results = []
        for req in self._requests.values():
            if task_id and req.task_id != task_id:
                continue
            if not req.all_decided:
                results.append(req)
        return results

    def summary(self) -> dict[str, Any]:
        total = len(self._requests)
        all_items = [i for req in self._requests.values() for i in req.items]
        return {
            "total_requests": total,
            "total_changes": len(all_items),
            "approved": sum(1 for i in all_items if i.decision == ApprovalDecision.APPROVED),
            "rejected": sum(1 for i in all_items if i.decision == ApprovalDecision.REJECTED),
            "pending": sum(1 for i in all_items if i.decision == ApprovalDecision.PENDING),
        }
