"""Tests for Forge tool modules."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
async def register_tools():
    """Ensure tools are registered before each test."""
    from forge.tools import search
    from forge.tools import file_tools
    from forge.tools import execute
    from forge.tools import git_tools

    # Call registration functions synchronously
    for mod in [search, file_tools, execute, git_tools]:
        for name in dir(mod):
            if name == '_register':
                fn = getattr(mod, name)
                # _register is async, but we can just call the registry directly
                import inspect
                if inspect.iscoroutinefunction(fn):
                    await fn()
                else:
                    fn()


class TestFileTools:
    """File reading/writing tools."""

    async def test_read_file_not_found(self):
        from forge.tools.file_tools import FileTools
        from forge.tools.registry import ToolStatus

        result = await FileTools.read_file("/nonexistent/path/file.txt")
        assert result.status == ToolStatus.ERROR
        assert "not found" in result.error

    async def test_write_and_read_file(self):
        from forge.tools.file_tools import FileTools
        from forge.tools.registry import ToolStatus

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            name = f.name

        try:
            content = "hello forge"
            result = await FileTools.write_file(name, content)
            assert result.status == ToolStatus.SUCCESS
            assert result.data["bytes"] == len(content)

            result = await FileTools.read_file(name)
            assert result.status == ToolStatus.SUCCESS
            assert "hello forge" in result.data["content"]
        finally:
            Path(name).unlink(missing_ok=True)

    async def test_list_dir(self):
        from forge.tools.file_tools import FileTools
        from forge.tools.registry import ToolStatus

        result = await FileTools.list_dir(".")
        assert result.status == ToolStatus.SUCCESS
        assert result.data["count"] > 0

    async def test_edit_file(self):
        from forge.tools.file_tools import FileTools
        from forge.tools.registry import ToolStatus

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("old_text")
            name = f.name

        try:
            result = await FileTools.edit_file(name, "old_text", "new_text")
            assert result.status == ToolStatus.SUCCESS
            assert result.data["modified"]

            content = Path(name).read_text()
            assert content == "new_text"
        finally:
            Path(name).unlink(missing_ok=True)


class TestSearchTools:
    """Code search tools."""

    async def test_glob_files(self):
        from forge.tools.search import SearchTools
        from forge.tools.registry import ToolStatus

        result = await SearchTools.glob_files("*.py", ".")
        assert result.status == ToolStatus.SUCCESS
        assert isinstance(result.data["files"], list)


class TestToolRegistry:
    """Tool registration and execution."""

    def test_register_and_list(self):
        from forge.tools.registry import registry, ToolSpec, ToolKind

        spec = ToolSpec(
            name="test_tool",
            description="test",
            kind=ToolKind.SYSTEM,
            parameters={},
        )
        registry.register(spec)
        all_tools = registry.list_all()
        names = [t.name for t in all_tools]
        assert "test_tool" in names

    def test_get_by_name(self):
        from forge.tools.registry import registry

        # First, directly register a known tool
        from forge.tools.registry import ToolSpec, ToolKind
        spec = ToolSpec(
            name="read_file",
            description="Read a file's contents",
            kind=ToolKind.READ,
            parameters={},
        )
        registry.register(spec)

        spec = registry.get("read_file")
        assert spec is not None
        assert spec.kind.value == "read"
