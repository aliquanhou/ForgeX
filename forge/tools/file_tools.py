"""File Tools — read, write, edit, and diff files.

These are the most important tools — they directly manipulate user code.
"""

from __future__ import annotations

import difflib
import os
from pathlib import Path
from typing import Any

from .registry import registry, ToolSpec, ToolKind, ToolResult, ToolStatus


class FileTools:
    """Tools for file operations."""

    MAX_READ_SIZE: int = 1_000_000  # 1MB

    @staticmethod
    async def read_file(path: str, offset: int = 0, limit: int = 0) -> ToolResult:
        """Read a file with optional offset and limit.

        Args:
            path: Absolute or relative path to the file
            offset: Line number to start from (0 = beginning)
            limit: Max lines to read (0 = all)

        Returns:
            ToolResult with file content and metadata
        """
        try:
            filepath = Path(path).resolve()
            if not filepath.exists():
                return ToolResult(ToolStatus.ERROR, error=f"File not found: {path}")
            if not filepath.is_file():
                return ToolResult(ToolStatus.ERROR, error=f"Not a file: {path}")

            size = filepath.stat().st_size
            if size > FileTools.MAX_READ_SIZE:
                return ToolResult(
                    ToolStatus.ERROR,
                    error=f"File too large: {size} bytes (max {FileTools.MAX_READ_SIZE})",
                )

            content = filepath.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines(keepends=True)
            total_lines = len(lines)

            if offset > 0:
                lines = lines[offset:]
            if limit > 0:
                lines = lines[:limit]

            return ToolResult(
                ToolStatus.SUCCESS,
                data={
                    "path": str(filepath),
                    "content": "".join(lines),
                    "total_lines": total_lines,
                    "offset": offset,
                    "lines_returned": len(lines),
                    "size": size,
                },
            )
        except PermissionError:
            return ToolResult(ToolStatus.ERROR, error=f"Permission denied: {path}")
        except Exception as e:
            return ToolResult(ToolStatus.ERROR, error=str(e))

    @staticmethod
    async def write_file(path: str, content: str) -> ToolResult:
        """Write content to a file (creates parent directories if needed).

        Args:
            path: Absolute or relative path
            content: File content to write

        Returns:
            ToolResult confirming write
        """
        try:
            filepath = Path(path).resolve()
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content, encoding="utf-8")
            return ToolResult(
                ToolStatus.SUCCESS,
                data={"path": str(filepath), "bytes": len(content.encode("utf-8"))},
            )
        except Exception as e:
            return ToolResult(ToolStatus.ERROR, error=str(e))

    @staticmethod
    async def edit_file(path: str, search: str, replace: str) -> ToolResult:
        """Search and replace in a file (exact string match).

        Args:
            path: File path
            search: Exact string to search for
            replace: Replacement string

        Returns:
            ToolResult confirming edit with diff
        """
        try:
            filepath = Path(path).resolve()
            content = filepath.read_text(encoding="utf-8")

            if search not in content:
                return ToolResult(
                    ToolStatus.ERROR,
                    error=f"Search string not found in {path}. "
                          f"The exact text must match. "
                          f"Search was {len(search)} chars.",
                )

            new_content = content.replace(search, replace, 1)

            # Generate diff
            diff = list(difflib.unified_diff(
                content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=str(filepath),
                tofile=str(filepath),
            ))

            filepath.write_text(new_content, encoding="utf-8")

            return ToolResult(
                ToolStatus.SUCCESS,
                data={
                    "path": str(filepath),
                    "diff": "".join(diff),
                    "modified": content != new_content,
                },
            )
        except Exception as e:
            return ToolResult(ToolStatus.ERROR, error=str(e))

    @staticmethod
    async def list_dir(path: str = ".") -> ToolResult:
        """List directory contents.

        Args:
            path: Directory path

        Returns:
            ToolResult with directory listing
        """
        try:
            dirpath = Path(path).resolve()
            if not dirpath.exists():
                return ToolResult(ToolStatus.ERROR, error=f"Directory not found: {path}")
            if not dirpath.is_dir():
                return ToolResult(ToolStatus.ERROR, error=f"Not a directory: {path}")

            entries = []
            for entry in sorted(dirpath.iterdir()):
                info = entry.stat()
                entries.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size": info.st_size if entry.is_file() else 0,
                    "modified": info.st_mtime,
                })

            return ToolResult(
                ToolStatus.SUCCESS,
                data={"path": str(dirpath), "entries": entries, "count": len(entries)},
            )
        except PermissionError:
            return ToolResult(ToolStatus.ERROR, error=f"Permission denied: {path}")
        except Exception as e:
            return ToolResult(ToolStatus.ERROR, error=str(e))

    @staticmethod
    async def create_file(path: str, content: str = "") -> ToolResult:
        """Create a new empty or pre-filled file.

        Fails if the file already exists.
        """
        filepath = Path(path).resolve()
        if filepath.exists():
            return ToolResult(ToolStatus.ERROR, error=f"File already exists: {path}")
        return await FileTools.write_file(path, content)


# Register file tools
async def _register() -> None:
    for spec in [
        ToolSpec(
            name="read_file",
            description="Read a file's contents",
            kind=ToolKind.READ,
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to file"},
                    "offset": {"type": "integer", "description": "Line offset"},
                    "limit": {"type": "integer", "description": "Max lines"},
                },
                "required": ["path"],
            },
            handler=FileTools.read_file,
        ),
        ToolSpec(
            name="write_file",
            description="Write content to a file (creates directories)",
            kind=ToolKind.WRITE,
            requires_approval=True,
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to write"},
                    "content": {"type": "string", "description": "File content"},
                },
                "required": ["path", "content"],
            },
            handler=FileTools.write_file,
        ),
        ToolSpec(
            name="edit_file",
            description="Search and replace text in a file",
            kind=ToolKind.WRITE,
            requires_approval=True,
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "search": {"type": "string", "description": "Text to find"},
                    "replace": {"type": "string", "description": "Replacement"},
                },
                "required": ["path", "search", "replace"],
            },
            handler=FileTools.edit_file,
        ),
        ToolSpec(
            name="list_dir",
            description="List directory contents",
            kind=ToolKind.READ,
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"},
                },
                "required": [],
            },
            handler=FileTools.list_dir,
        ),
        ToolSpec(
            name="create_file",
            description="Create a new file (fails if exists)",
            kind=ToolKind.WRITE,
            requires_approval=True,
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "content": {"type": "string", "description": "Initial content"},
                },
                "required": ["path"],
            },
            handler=FileTools.create_file,
        ),
    ]:
        registry.register(spec)
