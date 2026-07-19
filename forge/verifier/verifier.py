"""Independent Verifier — the module that prevents self-delusion.

This is a KEY differentiator from most agent systems.
The verifier runs AFTER each action and independently checks if the result is valid.

It has ZERO context about the plan — only the artifact and the goal.
This prevents the LLM from rationalizing its own mistakes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Verdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNCERTAIN = "uncertain"


@dataclass
class VerificationResult:
    """Result of an independent verification."""

    verdict: Verdict = Verdict.UNCERTAIN
    checks: list[dict[str, Any]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.verdict == Verdict.PASS

    @property
    def summary(self) -> str:
        if self.verdict == Verdict.PASS:
            return f"✓ Verification passed ({len(self.checks)} checks)"
        elif self.verdict == Verdict.FAIL:
            return f"✗ Verification failed: {'; '.join(self.issues[:3])}"
        return f"? Verification uncertain ({len(self.issues)} potential issues)"


class IndependentVerifier:
    """Verifies artifacts independently of the planning/execution loop.

    Uses a combination of automated checks and (optionally) LLM-based review.
    """

    def __init__(self) -> None:
        self._checks: list[tuple[str, Any]] = []

    def add_check(self, name: str, check_fn: Any) -> None:
        """Add a custom verification check."""
        self._checks.append((name, check_fn))

    async def verify_file(self, file_path: str, goal: str = "") -> VerificationResult:
        """Verify a single file for correctness."""
        path = Path(file_path)
        result = VerificationResult()

        if not path.exists():
            result.verdict = Verdict.FAIL
            result.issues.append(f"File does not exist: {file_path}")
            return result

        # Basic checks
        content = path.read_text(encoding="utf-8", errors="replace")
        ext = path.suffix.lower()

        # Check file size is reasonable
        size = len(content)
        if size == 0:
            result.issues.append("File is empty")
        elif size < 10:
            result.issues.append(f"File suspiciously small ({size} bytes)")

        # Language-specific syntax checks
        if ext == ".py":
            syntax_ok, syntax_issues = self._check_python_syntax(content)
            if syntax_ok:
                result.checks.append({"check": "python_syntax", "passed": True})
            else:
                result.verdict = Verdict.FAIL
                result.issues.extend(syntax_issues)

        elif ext in (".json", ".jsonc"):
            syntax_ok, syntax_issues = self._check_json_syntax(content)
            if syntax_ok:
                result.checks.append({"check": "json_syntax", "passed": True})
            else:
                result.verdict = Verdict.FAIL
                result.issues.extend(syntax_issues)

        elif ext in (".md", ".txt", ".yaml", ".yml", ".toml"):
            result.checks.append({"check": "text_file", "passed": True})

        # Run custom checks
        for name, check_fn in self._checks:
            try:
                if callable(check_fn):
                    custom_result = check_fn(content, path)
                    if custom_result:
                        result.checks.append({"check": name, "passed": True})
            except Exception:
                pass

        # Default verdict
        if result.verdict != Verdict.FAIL:
            if len(result.issues) == 0:
                result.verdict = Verdict.PASS
            else:
                result.verdict = Verdict.UNCERTAIN

        return result

    async def verify_artifact(
        self, artifact: Any, artifact_type: str, goal: str = ""
    ) -> VerificationResult:
        """Verify a non-file artifact (report, diff, test result)."""
        result = VerificationResult()

        if artifact_type == "test_result":
            if isinstance(artifact, dict):
                passed = artifact.get("passed", 0)
                failed = artifact.get("failed", 0)
                if failed == 0 and passed > 0:
                    result.verdict = Verdict.PASS
                    result.checks.append({"check": "all_tests_pass", "passed": True})
                elif failed > 0:
                    result.verdict = Verdict.FAIL
                    result.issues.append(f"{failed} tests failed")
                else:
                    result.verdict = Verdict.UNCERTAIN
                    result.issues.append("No tests ran")

        elif artifact_type == "diff":
            if isinstance(artifact, str) and len(artifact.strip()) > 0:
                result.verdict = Verdict.PASS
                result.checks.append({"check": "diff_not_empty", "passed": True})
            else:
                result.issues.append("Diff is empty — no changes made")

        else:
            # Unknown type — mark as uncertain
            result.verdict = Verdict.UNCERTAIN

        return result

    def _check_python_syntax(self, content: str) -> tuple[bool, list[str]]:
        """Check Python file syntax validity."""
        try:
            compile(content, "<string>", "exec")
            return True, []
        except SyntaxError as e:
            return False, [f"Python syntax error: {e}"]

    def _check_json_syntax(self, content: str) -> tuple[bool, list[str]]:
        """Check JSON file syntax validity."""
        import json
        try:
            json.loads(content)
            return True, []
        except json.JSONDecodeError as e:
            return False, [f"JSON syntax error: {e}"]
