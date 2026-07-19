"""Execute Tools — run shell commands in sandboxed environments.

This is the most security-sensitive module.
All commands are validated before execution.
"""

from __future__ import annotations

import asyncio
import subprocess
import shlex
from pathlib import Path
from typing import Any

from .registry import registry, ToolSpec, ToolKind, ToolResult, ToolStatus


# Commands that are always blocked
BLOCKED_COMMANDS = {
    "rm -rf /", "rm -rf /*", "sudo", "su ",
    "shutdown", "reboot", "init 0", "init 6",
    "dd if=", "mkfs.", "fdisk", "format",
    "> /dev/", "> /dev/sda", ":(){ :|:& };:",  # fork bomb
    "chmod 777 /", "chown -R",
}

# Command prefixes that are always allowed
ALLOWED_PREFIXES = {
    "python", "python3", "node", "npm", "npx",
    "pip", "pip3", "cargo", "go", "rustc",
    "tsc", "eslint", "prettier", "black", "ruff",
    "pytest", "mypy", "git",
    "ls", "cat", "head", "tail", "wc", "echo",
    "mkdir", "cp", "mv",
    "which", "file", "stat", "du", "df",
    "grep", "rg", "find",
    "curl", "wget",
    "docker", "docker-compose",
    "make", "cmake",
    "env", "printenv", "pwd", "date",
    "cd", "pwd",
}


def _validate_command(command: str) -> str | None:
    """Validate a command. Returns error message or None if valid."""
    if not command or not command.strip():
        return "Empty command"

    trimmed = command.strip().lower()

    # Check blocked patterns
    for blocked in BLOCKED_COMMANDS:
        if blocked in trimmed:
            return f"Command blocked for security: contains '{blocked}'"

    # Check first token is allowed
    first_token = shlex.split(command)[0].lower()
    allowed = False
    for prefix in ALLOWED_PREFIXES:
        if first_token == prefix or first_token.startswith(prefix + "/") or first_token.startswith("./"):
            allowed = True
            break
    if not allowed:
        return f"Command not in allowed list: {first_token}"

    return None


class ExecuteTools:
    """Tools for executing shell commands."""

    DEFAULT_TIMEOUT: float = 30.0
    MAX_OUTPUT: int = 10_000_000  # 10MB

    @staticmethod
    async def execute(
        command: str,
        cwd: str = "",
        timeout: float = 0,
        env: dict[str, str] | None = None,
    ) -> ToolResult:
        """Execute a shell command in a subprocess.

        Args:
            command: Shell command to run
            cwd: Working directory (default: current)
            timeout: Timeout in seconds (default: 30)
            env: Additional environment variables

        Returns:
            ToolResult with stdout, stderr, exit code
        """
        # Validate
        error = _validate_command(command)
        if error:
            return ToolResult(ToolStatus.REJECTED, error=error)

        timeout = timeout or ExecuteTools.DEFAULT_TIMEOUT
        work_dir = Path(cwd).resolve() if cwd else Path.cwd()

        exec_env = os.environ.copy()
        if env:
            exec_env.update(env)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(work_dir),
                env=exec_env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ToolResult(
                    ToolStatus.ERROR,
                    error=f"Command timed out after {timeout}s: {command[:100]}",
                )

            stdout_str = stdout.decode("utf-8", errors="replace")[:ExecuteTools.MAX_OUTPUT]
            stderr_str = stderr.decode("utf-8", errors="replace")[:ExecuteTools.MAX_OUTPUT]

            return ToolResult(
                ToolStatus.SUCCESS if proc.returncode == 0 else ToolStatus.FAILED,
                data={
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "exit_code": proc.returncode or 0,
                    "command": command,
                    "cwd": str(work_dir),
                },
            )
        except FileNotFoundError:
            return ToolResult(ToolStatus.ERROR, error=f"Command not found: {command}")
        except Exception as e:
            return ToolResult(ToolStatus.ERROR, error=str(e))

    @staticmethod
    async def execute_python(code: str, cwd: str = "") -> ToolResult:
        """Execute a Python snippet.

        Args:
            code: Python code to run
            cwd: Working directory

        Returns:
            ToolResult with output
        """
        return await ExecuteTools.execute(f'python3 -c "{code.replace(chr(34), chr(39))}"', cwd)


# Register execute tools
async def _register() -> None:
    exec_spec = ToolSpec(
        name="execute",
        description="Run a shell command with validation",
        kind=ToolKind.EXECUTE,
        requires_approval=True,
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to run"},
                "cwd": {"type": "string", "description": "Working directory"},
                "timeout": {"type": "number", "description": "Timeout in seconds"},
            },
            "required": ["command"],
        },
        handler=ExecuteTools.execute,
    )
    registry.register(exec_spec)
