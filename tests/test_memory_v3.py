"""Tests for Memory Architecture v0.3 — 4-layer memory."""


class TestContextWindow:
    """Multi-turn context window."""

    def test_add_and_snapshot(self):
        from forge.memory import ContextWindow, CompressedState, ContextPriority

        cw = ContextWindow(max_entries=5)
        cs = CompressedState(goal="test", phase="exploration", round=1)
        cw.add(cs, ContextPriority.HIGH)
        assert cw.entry_count == 1

        snapshot = cw.get_snapshot()
        assert "test" in snapshot

    def test_eviction(self):
        from forge.memory import ContextWindow, CompressedState, ContextPriority

        cw = ContextWindow(max_entries=3)
        for i in range(5):
            cs = CompressedState(goal=f"goal_{i}", phase="impl", round=i)
            cw.add(cs, ContextPriority.LOW)
        assert cw.entry_count <= 3

    def test_priority_retention(self):
        from forge.memory import ContextWindow, CompressedState, ContextPriority

        cw = ContextWindow(max_entries=2)
        cw.add(CompressedState(goal="critical_goal", phase="impl", round=1), ContextPriority.CRITICAL)
        cw.add(CompressedState(goal="low_goal", phase="impl", round=2), ContextPriority.LOW)
        cw.add(CompressedState(goal="new_goal", phase="impl", round=3), ContextPriority.NORMAL)
        # Critical should survive eviction
        snapshot = cw.get_snapshot()
        assert "critical_goal" in snapshot


class TestEpisodicMemory:
    """Cross-session task experience."""

    def test_record_and_search(self):
        from forge.memory import EpisodicMemory, Episode, EpisodeQuery

        mem = EpisodicMemory()
        ep = Episode.create("fix auth bug", "debug")
        ep.success = True
        mem.record(ep)
        assert mem.total_episodes == 1

        results = mem.search(EpisodeQuery(goal_keywords=["auth"]))
        assert len(results) == 1

    def test_find_by_error(self):
        from forge.memory import EpisodicMemory, Episode

        mem = EpisodicMemory()
        ep = Episode.create("debug task", "debug")
        ep.errors = ["ModuleNotFoundError: No module named 'flask'"]
        mem.record(ep)
        results = mem.find_by_error("ModuleNotFoundError")
        assert len(results) == 1

    def test_success_rate(self):
        from forge.memory import EpisodicMemory, Episode

        mem = EpisodicMemory()
        for i in range(4):
            ep = Episode.create(f"task_{i}")
            ep.success = i < 3
            mem.record(ep)
        assert mem.success_rate == 0.75


class TestSemanticMemory:
    """Project knowledge graph."""

    def test_add_and_find_entity(self):
        from forge.memory import SemanticMemory, Entity, EntityKind

        mem = SemanticMemory()
        entity = Entity(name="UserModel", kind=EntityKind.CLASS, file_path="models/user.py")
        mem.add_entity(entity)
        assert mem.entity_count == 1

        found = mem.find("UserModel")
        assert len(found) == 1
        assert found[0].name == "UserModel"

    def test_relations(self):
        from forge.memory import SemanticMemory, Entity, EntityKind, Relation, RelationKind

        mem = SemanticMemory()
        f1 = Entity(name="user.py", kind=EntityKind.FILE)
        f2 = Entity(name="UserModel", kind=EntityKind.CLASS)
        mem.add_entity(f1)
        mem.add_entity(f2)
        mem.add_relation(Relation(source=f1.key, target=f2.key, kind=RelationKind.CONTAINS))

        rels = mem.get_relations(f1.key)
        assert len(rels) == 1
        assert rels[0].kind == RelationKind.CONTAINS

    def test_discover_from_content(self):
        from forge.memory import SemanticMemory, EntityKind

        mem = SemanticMemory()
        content = """
        class UserModel:
            pass

        def get_user():
            pass

        async def create_user():
            pass
        """
        entities = mem.discover_from_content("models/user.py", content)
        # Should find class + 2 functions
        assert len(entities) == 3
        assert any(e.kind == EntityKind.CLASS for e in entities)
        assert any(e.kind == EntityKind.FUNCTION for e in entities)

    def test_query(self):
        from forge.memory import SemanticMemory, Entity, EntityKind

        mem = SemanticMemory()
        mem.add_entity(Entity(name="AuthRouter", kind=EntityKind.CLASS, file_path="routes/auth.py"))
        answers = mem.query("what is AuthRouter?")
        assert len(answers) > 0


class TestProceduralMemory:
    """Success patterns and fix templates."""

    def test_add_and_find_procedure(self):
        from forge.memory import ProceduralMemory, Procedure

        mem = ProceduralMemory()
        proc = Procedure(
            id="p1", name="Fix import error",
            description="When import fails, check requirements.txt",
            trigger_pattern="import error",
            steps=[],
            tags=["import", "python"],
        )
        mem.add_procedure(proc)
        assert mem.procedure_count == 1

        found = mem.find_procedure("fix import error")
        assert found is not None

    def test_find_pattern(self):
        from forge.memory import ProceduralMemory, ProcedurePattern

        mem = ProceduralMemory()
        mem.add_pattern(ProcedurePattern(
            error_pattern="ModuleNotFoundError",
            fix_action="pip install",
            fix_target="requirements.txt",
            success_rate=0.8,
            times_used=5,
        ))
        result = mem.find_pattern("ModuleNotFoundError: No module named 'flask'")
        assert result is not None
        assert result.fix_action == "pip install"
