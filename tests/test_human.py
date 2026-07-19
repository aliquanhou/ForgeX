"""Tests for Human Collaboration Layer."""

import tempfile
from pathlib import Path


class TestApprovalManager:
    """Diff-level approval workflow."""

    def test_create_request(self):
        from forge.human import ApprovalManager, ApprovalDecision

        mgr = ApprovalManager(auto_approve_low_risk=False)
        req = mgr.create_request("task_1", "fix login bug", [
            {"action": "edit", "path": "auth.py", "reason": "fix jwt validation", "risk": "low"},
            {"action": "edit", "path": "config.py", "reason": "update secret key", "risk": "high"},
        ])
        assert req.goal == "fix login bug"
        assert len(req.items) == 2
        # All pending since auto_approve is False
        assert all(i.decision == ApprovalDecision.PENDING for i in req.items)

    def test_auto_approve_low_risk(self):
        from forge.human import ApprovalManager, ApprovalDecision

        mgr = ApprovalManager(auto_approve_low_risk=True)
        req = mgr.create_request("t1", "update config", [
            {"action": "edit", "path": "settings.py", "reason": "minor", "risk": "low"},
            {"action": "edit", "path": "core.py", "reason": "dangerous", "risk": "high"},
        ])
        low_item = next(i for i in req.items if i.risk == "low")
        high_item = next(i for i in req.items if i.risk == "high")
        assert low_item.decision == ApprovalDecision.APPROVED
        assert high_item.decision == ApprovalDecision.PENDING  # still needs review

    def test_approve_all(self):
        from forge.human import ApprovalManager, ApprovalDecision

        mgr = ApprovalManager(auto_approve_low_risk=False)
        req = mgr.create_request("t1", "test", [
            {"action": "edit", "path": "a.py", "risk": "low"},
            {"action": "edit", "path": "b.py", "risk": "low"},
        ])
        mgr.approve(req.id)
        assert all(i.decision == ApprovalDecision.APPROVED for i in req.items)

    def test_approve_selected(self):
        from forge.human import ApprovalManager, ApprovalDecision

        mgr = ApprovalManager(auto_approve_low_risk=False)
        req = mgr.create_request("t1", "test", [
            {"action": "edit", "path": "a.py", "risk": "low"},
            {"action": "edit", "path": "b.py", "risk": "low"},
        ])
        item_id = req.items[0].id
        mgr.approve(req.id, item_ids=[item_id])
        assert req.items[0].decision == ApprovalDecision.APPROVED
        assert req.items[1].decision == ApprovalDecision.PENDING

    def test_reject_with_feedback(self):
        from forge.human import ApprovalManager, ApprovalDecision

        mgr = ApprovalManager(auto_approve_low_risk=False)
        req = mgr.create_request("t1", "test", [
            {"action": "edit", "path": "a.py", "risk": "low"},
        ])
        mgr.reject(req.id, feedback="not the right approach")
        assert req.items[0].decision == ApprovalDecision.REJECTED
        assert req.items[0].feedback == "not the right approach"

    def test_summary(self):
        from forge.human import ApprovalManager

        mgr = ApprovalManager(auto_approve_low_risk=False)
        mgr.create_request("t1", "test", [{"action": "edit", "path": "a.py", "risk": "low"}])
        s = mgr.summary()
        assert s["total_requests"] == 1

    def test_needs_review_property(self):
        from forge.human import ChangeItem

        low = ChangeItem(id="1", action="edit", path="a.py", risk="low")
        high = ChangeItem(id="2", action="edit", path="b.py", risk="high")
        delete = ChangeItem(id="3", action="delete", path="c.py", risk="low")
        assert not low.needs_review
        assert high.needs_review
        assert delete.needs_review


class TestExplainer:
    """Change explanation generation."""

    def test_explain_edit(self):
        from forge.human import Explainer

        exp = Explainer()
        expl = exp.explain_edit("auth.py", "old_code", "new_code", "Fix JWT validation")
        assert "auth.py" in expl.what
        assert "Fix JWT validation" in expl.why
        assert expl.to_text()
        assert expl.to_markdown()

    def test_explain_create(self):
        from forge.human import Explainer

        exp = Explainer()
        expl = exp.explain_create("new_file.py", "# new file", "Need utility functions")
        assert "new_file.py" in expl.what
        assert expl.evidence


class TestImpactReport:
    """Human-readable impact report generation."""

    def test_from_dict(self):
        from forge.human import ReportGenerator

        gen = ReportGenerator()
        report = gen.from_dict({
            "affected_files": ["a.py", "b.py"],
            "affected_tests": ["test_a.py"],
            "risk": "medium",
            "target": "core.py",
        }, goal="Refactor core module")
        assert "core.py" in report.goal or "Refactor" in report.goal
        assert len(report.affected_modules) == 2
        assert report.to_markdown()

    def test_markdown_output(self):
        from forge.human import ReportGenerator

        gen = ReportGenerator()
        report = gen.from_dict({"affected_files": [], "risk": "none"}, goal="test")
        md = report.to_markdown()
        assert "#" in md
        assert "Risk Assessment" in md


class TestPartialMerge:
    """Selective change application."""

    def test_chunk_diff(self):
        from forge.human import PartialMerge

        merger = PartialMerge()
        diff = """@@ -1,3 +1,4 @@
 old line
+new line
 another line
"""
        chunks = merger.chunk_diff(diff, "test.py")
        # At least one chunk should be found
        assert len(chunks) >= 1

    def test_extract_new_content(self):
        from forge.human import PartialMerge

        merger = PartialMerge()
        hunk = """@@ -1,3 +1,4 @@
 old_line
+added_line
 context_line
-removed_line
"""
        lines = merger._extract_new_content(hunk)
        assert lines is not None
        assert "added_line" in "".join(lines)
        assert "removed_line" not in "".join(lines)
