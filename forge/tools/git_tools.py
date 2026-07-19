"""Git Tools — version control operations for checkpointing work.

Every significant change should create a checkpoint.
The snapshot system uses these under the hood.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any

from .registry import registry, ToolSpec, ToolKind, ToolResult, ToolStatus


class GitTools:
    """Tools for git operations."""

    @staticmethod
    async def _run_git(args: list[str], cwd: str = ".") -> tuple[str, str, int]:
        """Run a git command and return (stdout, stderr, returncode)."""
        cmd = ["git"] + args
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await proc.communicate()
        return (
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
            proc.returncode or 0,
        )

    @staticmethod
    async def status(cwd: str = ".") -> ToolResult:
        """Show working tree status."""
        stdout, stderr, rc = await GitTools._run_git(["status", "--short"], cwd)
        if rc != 0:
            return ToolResult(ToolStatus.ERROR, error=stderr[:2000])
        lines = [l for l in stdout.splitlines() if l.strip()]
        return ToolResult(
            ToolStatus.SUCCESS,
            data={
                "changed_files": lines,
                "count": len(lines),
                "is_clean": len(lines) == 0,
            },
        )

    @staticmethod
    async def diff(cwd: str = "") -> ToolResult:
        """Show unstaged diff."""
        stdout, stderr, rc = await GitTools._run_git(["diff"], cwd)
        if rc != 0:
            return ToolResult(ToolStatus.ERROR, error=stderr[:2000])
        cached_stdout, _, _ = await GitTools._run_git(["diff", "--cached"], cwd)
        return ToolResult(
            ToolStatus.SUCCESS,
            data={
                "unstaged": stdout,
                "staged": cached_stdout,
            },
        )

    @staticmethod
    async def commit(message: str, cwd: str = "") -> ToolResult:
        """Stage all changes and commit.

        Args:
            message: Commit message
            cwd: Working directory
        """
        # Stage all
        _, stderr, rc = await GitTools._run_git(["add", "-A"], cwd)
        if rc != 0:
            return ToolResult(ToolStatus.ERROR, error=stderr[:2000])

        # Commit
        stdout, stderr, rc = await GitTools._run_git(["commit", "-m", message], cwd)
        if rc != 0:
            return ToolResult(
                ToolStatus.FAILED if "nothing to commit" not in stderr else ToolStatus.SUCCESS,
                data={"message": stdout or stderr},
            )
        # Get commit hash
        hash_out, _, _ = await GitTools._run_git(["rev-parse", "--short", "HEAD"], cwd)
        return ToolResult(
            ToolStatus.SUCCESS,
            data={
                "hash": hash_out.strip(),
                "message": message,
                "output": stdout,
            },
        )

    @staticmethod
    async def log(count: int = 10, cwd: str = "") -> ToolResult:
        """Show recent commit log."""
        stdout, stderr, rc = await GitTools._run_git(
            ["log", f"--max-count={count}", "--oneline", "--graph", "--decorate"], cwd
        )
        if rc != 0:
            return ToolResult(ToolStatus.ERROR, error=stderr[:2000])
        return ToolResult(
            ToolStatus.SUCCESS,
            data={"log": stdout, "count": len([l for l in stdout.splitlines() if l.strip()])},
        )

    @staticmethod
    async def reset_hard(commit: str = "HEAD", cwd: str = "") -> ToolResult:
        """Hard reset to a specific commit. DANGEROUS."""
        stdout, stderr, rc = await GitTools._run_git(["reset", "--hard", commit], cwd)
        if rc != 0:
            return ToolResult(ToolStatus.ERROR, error=stderr[:2000])
        return ToolResult(
            ToolStatus.SUCCESS,
            data={"reset_to": commit, "output": stdout},
        )

    @staticmethod
    async def stash(cwd: str = "") -> ToolResult:
        """Stash current changes."""
        stdout, stderr, rc = await GitTools._run_git(["stash"], cwd)
        if rc != 0:
            return ToolResult(ToolStatus.ERROR, error=stderr[:2000])
        return ToolResult(
            ToolStatus.SUCCESS,
            data={"output": stdout},
        )

    @staticmethod
    async def stash_pop(cwd: str = "") -> ToolResult:
        """Pop most recent stash."""
        stdout, stderr, rc = await GitTools._run_git(["stash", "pop"], cwd)
        if rc != 0:
            return ToolResult(ToolStatus.ERROR, error=stderr[:2000])
        return ToolResult(
            ToolStatus.SUCCESS,
            data={"output": stdout},
        )


# Register git tools
async def _register() -> None:
    git_specs = [
        ToolSpec(
            name="git_status",
            description="Show working tree status (changed files)",
            kind=ToolKind.GIT,
            parameters={"type": "object", "properties": {"cwd": {"type": "string"}}},
            handler=GitTools.status,
        ),
        ToolSpec(
            name="git_diff",
            description="Show unstaged and staged diffs",
            kind=ToolKind.GIT,
            parameters={"type": "object", "properties": {"cwd": {"type": "string"}}},
            handler=GitTools.diff,
        ),
        ToolSpec(
            name="git_commit",
            description="Stage all and commit changes",
            kind=ToolKind.GIT,
            requires_approval=True,
            parameters={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit message"},
                    "cwd": {"type": "string"},
                },
                "required": ["message"],
            },
            handler=GitTools.commit,
        ),
        ToolSpec(
            name="git_log",
            description="Show recent commit history",
            kind=ToolKind.GIT,
            parameters={
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "Number of commits"},
                    "cwd": {"type": "string"},
                },
            },
            handler=GitTools.log,
        ),
        ToolSpec(
            name="git_reset",
            description="Hard reset to a specific commit (DANGEROUS)",
            kind=ToolKind.GIT,
            requires_approval=True,
            parameters={
                "type": "object",
                "properties": {
                    "commit": {"type": "string", "description": "Commit hash"},
                    "cwd": {"type": "string"},
                },
                "required": ["commit"],
            },
            handler=GitTools.reset_hard,
        ),
    ]
    for spec in git_specs:
        registry.register(spec)
