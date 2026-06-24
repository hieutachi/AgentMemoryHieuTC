"""Tests for the graph builder module."""

from agent_memory_hieutc.graph.graph_builder import GraphData, build_codebase_graph
from agent_memory_hieutc.graph.mermaid_exporter import export_mermaid


def test_graph_data_add_node():
    g = GraphData()
    g.add_node("a", label="Node A", node_type="file")
    assert g.node_count == 1
    # Duplicate
    g.add_node("a", label="Node A", node_type="file")
    assert g.node_count == 1


def test_graph_data_add_edge():
    g = GraphData()
    g.add_node("a", label="A")
    g.add_node("b", label="B")
    g.add_edge("a", "b", relation="imports")
    assert g.edge_count == 1


def test_graph_data_edge_no_missing_nodes():
    g = GraphData()
    g.add_node("a", label="A")
    g.add_edge("a", "nonexistent")
    assert g.edge_count == 0


def test_build_codebase_graph():
    files = [
        {"file_id": 1, "path": "train.py", "file_type": "training_script",
         "importance_score": 9.0, "summary": "Main training script"},
        {"file_id": 2, "path": "model.py", "file_type": "source_code",
         "importance_score": 6.0, "summary": "Model definition"},
    ]
    relations = [
        {"source_id": 1, "target_id": 2, "relation_type": "imports"},
    ]
    graph = build_codebase_graph(files, [], relations)
    assert graph.node_count == 2
    assert graph.edge_count == 1


def test_mermaid_export():
    g = GraphData()
    g.add_node("f:train.py", label="train.py", node_type="script")
    g.add_node("f:model.py", label="model.py", node_type="file")
    g.add_edge("f:train.py", "f:model.py", relation="imports")
    mermaid = export_mermaid(g, title="Test")
    assert "flowchart" in mermaid
    assert "imports" in mermaid
