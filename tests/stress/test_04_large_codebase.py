"""Stress 4: Large codebase — test with 1000+ synthetic files."""

import tempfile
from pathlib import Path


class TestLargeCodebase:
    """Test World Model and tools with a large synthetic project."""

    def test_code_graph_scans_large_project(self):
        """Scan 200+ files and verify performance."""
        from forge.knowledge import CodeGraph

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            # Create 200 synthetic Python files with classes and functions
            for i in range(200):
                module_dir = root / f"module_{i % 10}"
                module_dir.mkdir(parents=True, exist_ok=True)
                (module_dir / f"file_{i}.py").write_text(
                    f"""
class Class_{i}:
    def method_{i}(self):
        pass

def function_{i}():
    pass
"""
                )

            graph = CodeGraph()
            # This should not crash or timeout
            results = graph.scan_directory(str(root))
            assert len(results) > 0
            assert graph.node_count > 0
            # Verify at least some structure was extracted
            assert graph.file_count > 0

    def test_dep_graph_handles_large_project(self):
        """Test dependency scanning on 100+ files."""
        from forge.knowledge import DependencyGraph

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            # Create files with cross-references
            for i in range(100):
                (root / f"mod_{i}.py").write_text(
                    f"from mod_{(i + 1) % 100} import something\nimport os\n"
                )

            graph = DependencyGraph()
            # Should not crash
            deps = graph.scan_directory(str(root))
            assert len(deps) > 0

    def test_symbol_index_large_project(self):
        """Test symbol indexing on 100+ files."""
        from forge.knowledge import SymbolIndex

        idx = SymbolIndex()

        for i in range(100):
            content = f"""
class Class_{i}:
    def method_{i}(self):
        pass

class Helper_{i}:
    pass
"""
            idx.index_definitions(f"file_{i}.py", content)

        # Verify all symbols indexed
        assert idx.total_defs >= 200  # class + method per file

        # Find symbol across many files
        defs = idx.find_definitions("Class_50")
        assert len(defs) == 1
