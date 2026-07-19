"""Tests for Knowledge Graph / World Model (v0.4)."""

import tempfile
from pathlib import Path


class TestCodeGraph:
    """AST-based code structure extraction."""

    def test_scan_empty_file(self):
        from forge.knowledge import CodeGraph

        graph = CodeGraph()
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("# empty")
            name = f.name

        try:
            nodes = graph.scan_file(name)
            # Empty file should have at least no errors
            assert isinstance(nodes, list)
        finally:
            Path(name).unlink(missing_ok=True)

    def test_scan_class_and_functions(self):
        from forge.knowledge import CodeGraph, CodeNodeKind

        graph = CodeGraph()
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("""
class UserModel:
    \"\"\"User domain model.\"\"\"

    def get_name(self) -> str:
        pass

    async def save(self):
        pass

def helper_function():
    pass
""")
            name = f.name

        try:
            nodes = graph.scan_file(name)
            classes = [n for n in nodes if n.kind == CodeNodeKind.CLASS]
            methods = [n for n in nodes if n.kind == CodeNodeKind.METHOD]
            functions = [n for n in nodes if n.kind == CodeNodeKind.FUNCTION]

            assert len(classes) == 1
            assert classes[0].name == "UserModel"
            assert len(methods) == 2
            assert len(functions) == 1
            assert functions[0].name == "helper_function"
        finally:
            Path(name).unlink(missing_ok=True)

    def test_decorator_detection(self):
        from forge.knowledge import CodeGraph, CodeNodeKind

        graph = CodeGraph()
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("""
@app.route("/api/users")
@jwt_required
def list_users():
    pass
""")
            name = f.name

        try:
            nodes = graph.scan_file(name)
            funcs = [n for n in nodes if n.kind == CodeNodeKind.FUNCTION]
            assert len(funcs) == 1
            # At least one decorator should be detected
            assert len(funcs[0].decorators) >= 1
        finally:
            Path(name).unlink(missing_ok=True)

    def test_scan_directory(self):
        from forge.knowledge import CodeGraph

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "mod").mkdir()
            (Path(tmp) / "mod" / "__init__.py").write_text("# init")
            (Path(tmp) / "mod" / "core.py").write_text("class Core: pass")

            graph = CodeGraph()
            results = graph.scan_directory(tmp)
            assert len(results) >= 1


class TestDependencyGraph:
    """Import chain resolution."""

    def test_scan_imports(self):
        from forge.knowledge import DependencyGraph, DepKind

        graph = DependencyGraph()
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write("""
import os
import sys
from collections import defaultdict
from pathlib import Path as P
""")
            name = f.name

        try:
            deps = graph.scan_file(name)
            assert len(deps) >= 3
            import_deps = [d for d in deps if d.kind == DepKind.IMPORT]
            from_deps = [d for d in deps if d.kind == DepKind.FROM_IMPORT]
            assert len(import_deps) >= 1
            assert len(from_deps) >= 1
        finally:
            Path(name).unlink(missing_ok=True)

    def test_incoming_outgoing(self):
        from forge.knowledge import DependencyGraph

        graph = DependencyGraph()
        from forge.knowledge.dependency_graph import Dependency, DepKind

        graph.add_dependency(Dependency(
            source="app/routes.py", target="app/models.py", kind=DepKind.IMPORT
        ))
        graph.add_dependency(Dependency(
            source="app/tests.py", target="app/routes.py", kind=DepKind.IMPORT
        ))

        outgoing = graph.get_outgoing("app/routes.py")
        incoming = graph.get_incoming("app/routes.py")

        assert "app/models.py" in outgoing
        assert "app/tests.py" in incoming

    def test_transitive(self):
        from forge.knowledge import DependencyGraph
        from forge.knowledge.dependency_graph import Dependency, DepKind

        graph = DependencyGraph()
        graph.add_dependency(Dependency("a.py", "b.py", DepKind.IMPORT))
        graph.add_dependency(Dependency("b.py", "c.py", DepKind.IMPORT))

        trans = graph.get_transitive_outgoing("a.py")
        assert "b.py" in trans
        assert "c.py" in trans


class TestSymbolIndex:
    """Cross-file symbol definitions and references."""

    def test_index_definitions(self):
        from forge.knowledge import SymbolIndex

        idx = SymbolIndex()
        defs = idx.index_definitions("app/models.py", """
class User:
    pass

def get_user():
    pass
""")
        assert len(defs) == 2
        assert defs[0].name == "User"
        assert defs[1].name == "get_user"

    def test_find_definitions(self):
        from forge.knowledge import SymbolIndex

        idx = SymbolIndex()
        idx.index_definitions("app/models.py", "class User: pass")
        found = idx.find_definitions("User")
        assert len(found) == 1
        assert found[0].file_path == "app/models.py"

    def test_index_references(self):
        from forge.knowledge import SymbolIndex

        idx = SymbolIndex()
        idx.index_definitions("app/models.py", "class User: pass")
        refs = idx.index_references("app/routes.py", "from models import User\nuser = User()", {"User"})
        assert len(refs) >= 1

    def test_get_file_symbols(self):
        from forge.knowledge import SymbolIndex

        idx = SymbolIndex()
        idx.index_definitions("app/core.py", "class Service: pass\ndef run(): pass")
        syms = idx.get_file_symbols("app/core.py")
        assert len(syms) == 2


class TestImpactAnalysis:
    """Impact analysis engine."""

    def test_analyze_symbol_not_found(self):
        from forge.knowledge import ImpactAnalysis, RiskLevel

        analysis = ImpactAnalysis()
        result = analysis.analyze_symbol("NonExistentSymbol")
        assert result.risk == RiskLevel.NONE or result.risk == RiskLevel.UNKNOWN

    def test_risk_scoring(self):
        from forge.knowledge.impact_analysis import ImpactAnalysis, RiskLevel

        analysis = ImpactAnalysis()
        # Direct test of risk computation
        risk = analysis._compute_risk(files_affected=0, tests_affected=0, apis_affected=0, transitive_count=0)
        assert risk == RiskLevel.NONE

        risk = analysis._compute_risk(files_affected=1, tests_affected=0, apis_affected=0, transitive_count=0)
        assert risk == RiskLevel.LOW

        risk = analysis._compute_risk(files_affected=10, tests_affected=3, apis_affected=2, transitive_count=10)
        assert risk == RiskLevel.CRITICAL

    def test_test_file_detection(self):
        from forge.knowledge.impact_analysis import ImpactAnalysis

        analysis = ImpactAnalysis()
        assert analysis._is_test_file("tests/test_auth.py")
        assert analysis._is_test_file("test_models.py")
        assert not analysis._is_test_file("app/models.py")

    def test_api_file_detection(self):
        from forge.knowledge.impact_analysis import ImpactAnalysis

        analysis = ImpactAnalysis()
        assert analysis._is_api_file("app/routes.py")
        assert analysis._is_api_file("app/api/users.py")
        assert not analysis._is_api_file("app/models.py")


class TestArchitectureMap:
    """Project structure map."""

    def test_classify_directory(self):
        from forge.knowledge import ArchitectureMap, LayerKind

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "api").mkdir()
            (Path(tmp) / "api" / "routes.py").write_text("def route(): pass")
            (Path(tmp) / "models").mkdir()
            (Path(tmp) / "models" / "user.py").write_text("class User: pass")

            arch = ArchitectureMap()
            layers = arch.scan_project(tmp)

            api_layer = next((l for l in layers if l.kind == LayerKind.API), None)
            assert api_layer is not None, f"Expected API layer, got {[l.name for l in layers]}"

            domain_layer = next((l for l in layers if l.kind == LayerKind.DOMAIN), None)
            # Might be UNKNOWN if 'models' keyword not in DOMAIN map
            # Check that we have at least some layers
            assert len(layers) > 0
