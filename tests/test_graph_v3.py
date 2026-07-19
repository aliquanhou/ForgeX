"""Tests for Adaptive Tool Graph v0.3."""


class TestAdaptiveToolGraph:
    """Dynamic node insertion on failure."""

    def test_add_node_and_resolve(self):
        from forge.graph import ToolGraph, ToolNode

        graph = ToolGraph()
        graph.add_node(ToolNode(name="read"))
        graph.add_node(ToolNode(name="write", depends_on=["read"]))
        order = graph.resolve_order()
        assert order.index("read") < order.index("write")

    def test_failure_triggers_adaptive_hooks(self):
        from forge.graph import ToolGraph, ToolNode, NodeStatus

        graph = ToolGraph()
        graph.add_node(ToolNode(name="test"))

        called = []

        def on_fail(node_name, state):
            called.append(node_name)
            return [ToolNode(name="debug_node", depends_on=[node_name])]

        graph.on_failure(on_fail)
        new_nodes = graph.record_failure("test", "tests failed")
        assert len(new_nodes) == 1
        assert new_nodes[0].name == "debug_node"
        assert "test" in called

    def test_record_success_updates_state(self):
        from forge.graph import ToolGraph, ToolNode, NodeStatus

        graph = ToolGraph()
        node = ToolNode(name="write", postconditions=[("changes_verified", True)])
        graph.add_node(node)
        graph.record_success("write")
        assert node.status == NodeStatus.SUCCEEDED
        assert graph.get_state("changes_verified") is True

    def test_history_tracking(self):
        from forge.graph import ToolGraph, ToolNode

        graph = ToolGraph()
        graph.add_node(ToolNode(name="a"))
        graph.record_success("a")
        graph.record_failure("b", "error")
        hist = graph.history
        assert len(hist) == 2
        assert hist[0]["status"] == "succeeded"
        assert hist[1]["status"] == "failed"

    def test_to_dot(self):
        from forge.graph import ToolGraph, ToolNode

        graph = ToolGraph()
        graph.add_node(ToolNode(name="read"))
        graph.add_node(ToolNode(name="write", depends_on=["read"]))
        dot = graph.to_dot()
        assert "digraph" in dot
