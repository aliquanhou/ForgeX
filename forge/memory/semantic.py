"""Semantic Memory — project knowledge graph.

Extracts and stores entities (files, functions, classes, concepts)
and their relationships from the codebase.

Built incrementally as the agent reads files and makes discoveries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from enum import Enum


class EntityKind(str, Enum):
    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"
    MODULE = "module"
    CONCEPT = "concept"
    CONFIG = "config"
    API = "api"
    TEST = "test"
    UNKNOWN = "unknown"


class RelationKind(str, Enum):
    CONTAINS = "contains"  # file contains class
    IMPORTS = "imports"  # file imports file
    CALLS = "calls"  # function calls function
    EXTENDS = "extends"  # class extends class
    CONFIGURES = "configures"  # config affects module
    DEPENDS_ON = "depends_on"  # module depends on module
    RELATED_TO = "related_to"  # generic relationship


@dataclass
class Entity:
    """A knowledge entity in the project graph."""

    name: str
    kind: EntityKind
    file_path: str = ""
    line: int = 0
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.kind.value}:{self.name}"


@dataclass
class Relation:
    """A relationship between two entities."""

    source: str  # entity key
    target: str  # entity key
    kind: RelationKind
    strength: float = 1.0  # 0.0-1.0


class SemanticMemory:
    """Project knowledge graph built incrementally.

    Stores entities and relationships discovered during code exploration.
    Enables the agent to answer "how does X relate to Y?"
    """

    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}
        self._relations: list[Relation] = []

    def add_entity(self, entity: Entity) -> None:
        """Add or update an entity."""
        self._entities[entity.key] = entity

    def add_relation(self, relation: Relation) -> None:
        """Add a relationship between entities."""
        self._relations.append(relation)

    def get_entity(self, name: str, kind: EntityKind | None = None) -> Entity | None:
        """Get an entity by name."""
        if kind:
            return self._entities.get(f"{kind.value}:{name}")
        # Search by name across all kinds
        for key, entity in self._entities.items():
            if entity.name == name:
                return entity
        return None

    def find(self, query: str, limit: int = 10) -> list[Entity]:
        """Find entities matching a text query."""
        query_lower = query.lower()
        results = []
        for entity in self._entities.values():
            if (query_lower in entity.name.lower() or
                query_lower in entity.description.lower() or
                query_lower in entity.file_path.lower()):
                results.append(entity)
        return results[:limit]

    def get_relations(self, entity_key: str, max_depth: int = 1) -> list[Relation]:
        """Get all relations for an entity, optionally with traversal."""
        direct = [r for r in self._relations if r.source == entity_key or r.target == entity_key]
        if max_depth <= 1:
            return direct

        # Breadth-first traversal
        visited = {entity_key}
        queue = [entity_key]
        all_relations = list(direct)

        while queue:
            current = queue.pop(0)
            for r in self._relations:
                other = r.target if r.source == current else r.source if r.target == current else None
                if other and other not in visited:
                    visited.add(other)
                    all_relations.append(r)
                    queue.append(other)
                    if len(visited) > 20:  # safety cap
                        break

        return all_relations

    def query(self, question: str) -> list[str]:
        """Answer simple knowledge queries."""
        answers = []
        question_lower = question.lower()

        if "what" in question_lower or "find" in question_lower:
            for entity in self._entities.values():
                if (entity.name.lower() in question_lower or
                    any(w in entity.name.lower() for w in question_lower.split())):
                    answers.append(f"{entity.kind.value}: {entity.name} ({entity.file_path})")

        if "relation" in question_lower or "how" in question_lower:
            for r in self._relations:
                src = self._entities.get(r.source)
                tgt = self._entities.get(r.target)
                if src and tgt:
                    answers.append(f"{src.name} {r.kind.value} {tgt.name}")

        return answers[:10]

    def discover_from_content(self, file_path: str, content: str) -> list[Entity]:
        """Extract entities from file content (simple heuristic)."""
        entities = []

        # File entity
        file_entity = Entity(
            name=file_path.split("/")[-1],
            kind=EntityKind.FILE,
            file_path=file_path,
        )
        self.add_entity(file_entity)

        # Extract class definitions
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()

            if stripped.startswith("class "):
                class_name = stripped.split(" ")[1].split("(")[0].split(":")[0]
                entity = Entity(
                    name=class_name,
                    kind=EntityKind.CLASS,
                    file_path=file_path,
                    line=i,
                )
                self.add_entity(entity)
                self.add_relation(Relation(
                    source=file_entity.key,
                    target=entity.key,
                    kind=RelationKind.CONTAINS,
                ))
                entities.append(entity)

            elif stripped.startswith("def ") or stripped.startswith("async def "):
                func_name = stripped.split(" ")[-1].split("(")[0].split(":")[0]
                entity = Entity(
                    name=func_name,
                    kind=EntityKind.FUNCTION,
                    file_path=file_path,
                    line=i,
                    description=stripped,
                )
                self.add_entity(entity)
                self.add_relation(Relation(
                    source=file_entity.key,
                    target=entity.key,
                    kind=RelationKind.CONTAINS,
                ))
                entities.append(entity)

        return entities

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    @property
    def relation_count(self) -> int:
        return len(self._relations)

    def summary(self) -> dict[str, Any]:
        return {
            "entities": self.entity_count,
            "relations": self.relation_count,
            "by_kind": {
                k.value: sum(1 for e in self._entities.values() if e.kind == k)
                for k in EntityKind
            },
        }
