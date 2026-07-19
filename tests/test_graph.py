"""Tests for Tool Graph DAG."""


class TestToolGraph:
    """DAG-based tool orchestration."""

    def test_add_node(self):
        from forge.graph import ToolGraph, ToolNode

        graph = ToolGraph()
        node = ToolNode(name="read_file", description="Read a file")
        graph.add_node(node)
        assert graph.node_count == 1
        assert graph.get_node("read_file") is node

    def test_resolve_order_no_deps(self):
        from forge.graph import ToolGraph, ToolNode

        graph = ToolGraph()
        graph.add_node(ToolNode(name="a"))
        graph.add_node(ToolNode(name="b"))
        graph.add_node(ToolNode(name="c"))

        order = graph.resolve_order()
        assert len(order) == 3
        assert set(order) == {"a", "b", "c"}

    def test_resolve_order_with_deps(self):
        from forge.graph import ToolGraph, ToolNode

        graph = ToolGraph()
        graph.add_node(ToolNode(name="read_file"))
        graph.add_node(ToolNode(name="edit_file", depends_on=["read_file"]))
        graph.add_node(ToolNode(name="verify", depends_on=["edit_file"]))

        order = graph.resolve_order()
        assert order.index("read_file") < order.index("edit_file") < order.index("verify")

    def test_check_preconditions_passes(self):
        from forge.graph import ToolGraph, ToolNode

        graph = ToolGraph()
        graph.add_node(ToolNode(name="read_file"))
        graph.add_node(ToolNode(name="write_file", depends_on=["read_file"], preconditions=[
            lambda s: s.get("snapshot_taken", False),
        ]))

        # Precondition fails because snapshot not taken
        failures = graph.check_preconditions("write_file")
        assert len(failures) > 0
        assert any("Precondition" in f for f in failures)

        # Set state, still fails because dependency not succeeded
        graph.update_state("snapshot_taken", True)
        failures = graph.check_preconditions("write_file")
        assert any("dependency" in f.lower() for f in failures)

    def test_update_state(self):
        from forge.graph import ToolGraph

        graph = ToolGraph()
        graph.update_state("tested", True)
        assert graph.get_state("tested") is True
        assert graph.get_state("nonexistent", "default") == "default"

    def test_cycle_detection(self):
        from forge.graph import ToolGraph, ToolNode

        graph = ToolGraph()
        graph.add_node(ToolNode(name="a", depends_on=["b"]))
        graph.add_node(ToolNode(name="b", depends_on=["a"]))

        import pytest
        with pytest.raises(ValueError, match="Cycle"):
            graph.resolve_order()

    def test_to_dot(self):
        from forge.graph import ToolGraph, ToolNode

        graph = ToolGraph()
        graph.add_node(ToolNode(name="read", depends_on=[]))
        graph.add_node(ToolNode(name="write", depends_on=["read"]))
        dot = graph.to_dot()
        assert 'digraph' in dot
        assert '"read" -> "write"' in dot

    def test_node_status_transition(self):
        from forge.graph import ToolNode, NodeStatus

        node = ToolNode(name="test_node")
        assert node.status == NodeStatus.PENDING
        assert not node.is_ready
        assert not node.is_done

        node.status = NodeStatus.READY
        assert node.is_ready

        node.status = NodeStatus.SUCCEEDED
        assert node.is_done
