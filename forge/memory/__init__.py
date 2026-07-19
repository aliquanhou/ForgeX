"""Memory Architecture — the cognitive layer of Forge.

Four memory tiers:
1. Short-term: current task context (compressed state, sliding window)
2. Episodic: cross-session task experiences
3. Semantic: project knowledge graph (entities + relationships)
4. Procedural: success patterns and reusable templates
"""

from .compressor import StateCompressor, CompressedState
from .context import ContextWindow, ContextEntry, ContextPriority
from .episodic import EpisodicMemory, Episode, EpisodeQuery
from .semantic import SemanticMemory, Entity, Relation, EntityKind, RelationKind
from .procedural import ProceduralMemory, Procedure, ProcedurePattern

__all__ = [
    "StateCompressor", "CompressedState",
    "ContextWindow", "ContextEntry", "ContextPriority",
    "EpisodicMemory", "Episode", "EpisodeQuery",
    "SemanticMemory", "Entity", "Relation",
    "ProceduralMemory", "Procedure", "ProcedurePattern",
]
