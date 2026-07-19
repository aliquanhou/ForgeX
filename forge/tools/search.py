"""Search Tools — ripgrep-based content search and symbol lookup.

Provides fast, regex-powered search across the codebase.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any

from .registry import registry, ToolSpec, ToolKind, ToolResult, ToolStatus


class SearchTools:
    """Tools for searching code and files."""

    @staticmethod
    async def grep(
        pattern: str,
        path: str = ".",
        glob: str = "",
        context: int = 0,
        max_results: int = 50,
    ) -> ToolResult:
        """Search files using ripgrep (rg).

        Args:
            pattern: Regex pattern to search for
            path: Directory or file to search
            glob: File pattern filter (e.g. "*.py")
            context: Lines of context before/after match
            max_results: Maximum matches to return

        Returns:
            ToolResult with list of matches
        """
        cmd = ["rg", "-n", pattern, str(path)]
        if glob:
            cmd.extend(["-g", glob])
        if context > 0:
            cmd.extend(["-C", str(context)])
        if max_results > 0:
            cmd.extend(["--max-count", str(max_results)])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                lines = stdout.decode("utf-8").splitlines()
                return ToolResult(
                    ToolStatus.SUCCESS,
                    data={"matches": lines, "count": len(lines)},
                    metadata={"pattern": pattern, "path": str(path)},
                )
            elif proc.returncode == 1:
                # rg returns 1 when no matches found
                return ToolResult(
                    ToolStatus.SUCCESS,
                    data={"matches": [], "count": 0},
                )
            else:
                return ToolResult(
                    ToolStatus.ERROR,
                    error=stderr.decode("utf-8", errors="replace")[:2000],
                )
        except FileNotFoundError:
            return ToolResult(
                ToolStatus.ERROR,
                error="ripgrep (rg) not found. Install with: winget install BurntSushi.ripgrep",
            )

    @staticmethod
    async def glob_files(pattern: str, path: str = ".") -> ToolResult:
        """Find files matching a glob pattern.

        Args:
            pattern: Glob pattern (e.g. "**/*.py")
            path: Base directory

        Returns:
            ToolResult with list of file paths
        """
        from pathlib import Path as P

        base = P(path).resolve()
        matches = list(base.rglob(pattern))
        return ToolResult(
            ToolStatus.SUCCESS,
            data={
                "files": [str(m.relative_to(base)) for m in matches],
                "count": len(matches),
            },
        )

    @staticmethod
    async def find_symbol(name: str, path: str = ".") -> ToolResult:
        """Find a symbol (function, class, variable) across codebase.

        Uses a combination of rg patterns for common symbol definitions.
        Only works for Python currently.

        Args:
            name: Symbol name to find
            path: Directory to search

        Returns:
            ToolResult with symbol locations
        """
        patterns = [
            rf"class\s+{name}\b",
            rf"def\s+{name}\b",
            rf"async\s+def\s+{name}\b",
            rf"{name}\s*=\s*(?:lambda|class|def)",
        ]
        all_matches: list[dict] = []
        for p in patterns:
            result = await SearchTools.grep(p, path)
            if result.ok and result.data.get("matches"):
                for m in result.data["matches"]:
                    all_matches.append({"type": "definition", "line": m})

        return ToolResult(
            ToolStatus.SUCCESS,
            data={"symbol": name, "definitions": all_matches, "count": len(all_matches)},
        )


# Register all search tools
async def _register() -> None:
    rg_spec = ToolSpec(
        name="grep",
        description="Search files using ripgrep regex pattern",
        kind=ToolKind.SEARCH,
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern"},
                "path": {"type": "string", "description": "Directory or file"},
                "glob": {"type": "string", "description": "File pattern filter"},
                "context": {"type": "integer", "description": "Context lines"},
            },
            "required": ["pattern"],
        },
        handler=SearchTools.grep,
    )
    registry.register(rg_spec)

    glob_spec = ToolSpec(
        name="glob",
        description="Find files matching a glob pattern",
        kind=ToolKind.SEARCH,
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern"},
                "path": {"type": "string", "description": "Base directory"},
            },
            "required": ["pattern"],
        },
        handler=SearchTools.glob_files,
    )
    registry.register(glob_spec)

    sym_spec = ToolSpec(
        name="find_symbol",
        description="Find symbol definitions (functions, classes) across codebase",
        kind=ToolKind.ANALYSIS,
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Symbol name"},
                "path": {"type": "string", "description": "Directory"},
            },
            "required": ["name"],
        },
        handler=SearchTools.find_symbol,
    )
    registry.register(sym_spec)
