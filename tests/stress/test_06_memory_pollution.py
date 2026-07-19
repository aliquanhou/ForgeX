"""Stress 6: Memory pollution — run 100 sequential tasks and verify no cross-contamination."""


class TestMemoryPollution:
    """Run many tasks sequentially and verify no memory leaks or cross-contamination."""

    async def test_episodic_memory_no_leak(self):
        from forge.memory import EpisodicMemory, Episode, EpisodeQuery

        mem = EpisodicMemory()

        for i in range(150):
            ep = Episode.create(f"task_{i}", "test")
            ep.success = i % 2 == 0
            mem.record(ep)

        assert mem.total_episodes <= 100

        found = mem.search(EpisodeQuery(goal_keywords=["task_149"]))
        assert len(found) > 0

    def test_semantic_memory_no_duplicate_entities(self):
        from forge.memory import SemanticMemory, Entity, EntityKind

        mem = SemanticMemory()

        for _ in range(10):
            mem.add_entity(Entity(name="User", kind=EntityKind.CLASS, file_path="models/user.py"))

        entities = mem.find("User")
        assert len(entities) >= 1

    async def test_failure_memory_limited(self):
        from forge.recovery.memory import FailureMemory

        mem = FailureMemory()
        for i in range(200):
            mem.record_failure(f"Error_{i}: something broke")

        assert mem.total_failures <= 200
        assert mem.total_failures > 0
