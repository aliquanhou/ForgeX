"""Knowledge Graph — World Model for Forge.

Provides structural understanding of the codebase:
- Code graph: AST-based structure extraction
- Dependency graph: import chains and file relationships
- Symbol index: cross-file definitions and references
- Impact analysis: what breaks if I change X?
- Architecture map: high-level system structure
"""

from .code_graph import CodeGraph, CodeNode, CodeNodeKind
from .dependency_graph import DependencyGraph, Dependency, DepKind
from .symbol_index import SymbolIndex, SymbolDef, SymbolRef
from .impact_analysis import ImpactAnalysis, ImpactResult, RiskLevel
from .architecture_map import ArchitectureMap, Layer, LayerKind

__all__ = [
    "CodeGraph", "CodeNode", "CodeNodeKind",
    "DependencyGraph", "Dependency", "DepKind",
    "SymbolIndex", "SymbolDef", "SymbolRef",
    "ImpactAnalysis", "ImpactResult", "RiskLevel",
    "ArchitectureMap", "Layer", "LayerKind",
]
