"""Stress 8: Human approval — test partial merge and selective approval."""

import tempfile
from pathlib import Path


class TestHumanApproval:
    """Test the human-in-the-loop approval workflow end-to-end."""

    def test_partial_merge(self):
        from forge.human import PartialMerge

        merger = PartialMerge()
        diff = """@@ -1,3 +1,4 @@
 line1
+added_line
 line2
@@ -10,5 +10,6 @@
 old_code
+new_feature
 more_code
"""

        chunks = merger.chunk_diff(diff, "test.py")
        assert len(chunks) >= 2

        # Exclude the first chunk
        chunks[0].decision = "exclude"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("line1\nline2\nline3\n")
            name = f.name

        try:
            result = merger.apply_chunks(name, chunks)
            assert result.included_chunks >= 1
            assert result.excluded_chunks >= 1
        finally:
            Path(name).unlink(missing_ok=True)

    def test_selective_approval(self):
        from forge.human import ApprovalManager, ApprovalDecision

        mgr = ApprovalManager(auto_approve_low_risk=False)
        req = mgr.create_request("task_1", "update auth", [
            {"action": "edit", "path": "security.py", "risk": "high", "reason": "fix jwt"},
            {"action": "edit", "path": "docs.py", "risk": "low", "reason": "update docs"},
        ])

        # Approve only docs change
        docs_item = next(i for i in req.items if "docs" in i.path)
        mgr.approve(req.id, item_ids=[docs_item.id])

        assert docs_item.decision == ApprovalDecision.APPROVED
        security_item = next(i for i in req.items if "security" in i.path)
        assert security_item.decision == ApprovalDecision.PENDING

    def test_approval_summary_tracks_all(self):
        from forge.human import ApprovalManager

        mgr = ApprovalManager(auto_approve_low_risk=False)
        mgr.create_request("t1", "task1", [
            {"action": "edit", "path": "a.py", "risk": "low"},
            {"action": "edit", "path": "b.py", "risk": "medium"},
        ])
        s = mgr.summary()
        assert s["total_requests"] == 1
        assert s["total_changes"] == 2
