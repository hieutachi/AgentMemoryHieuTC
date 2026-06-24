"""Build codebase and research workflow graphs from indexed data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False


@dataclass
class GraphData:
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    node_ids: set[str] = field(default_factory=set)

    def add_node(self, node_id: str, **attrs: Any) -> None:
        if node_id not in self.node_ids:
            self.node_ids.add(node_id)
            self.nodes.append({"id": node_id, **attrs})

    def add_edge(self, source: str, target: str, relation: str = "", **attrs: Any) -> None:
        if source in self.node_ids and target in self.node_ids:
            self.edges.append({"source": source, "target": target, "relation": relation, **attrs})

    def to_dict(self) -> dict:
        return {"nodes": self.nodes, "edges": self.edges}

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)


def build_codebase_graph(files: list[dict], symbols: list[dict],
                         relations: list[dict],
                         max_nodes: int = 80) -> GraphData:
    """Build a graph of the codebase structure."""
    graph = GraphData()

    # Add file nodes, limited by importance
    sorted_files = sorted(files, key=lambda f: f.get("importance_score", 0), reverse=True)
    for f in sorted_files[:max_nodes]:
        graph.add_node(
            f"file:{f['path']}",
            label=f["path"].split("/")[-1],
            full_path=f["path"],
            node_type="file",
            file_type=f.get("file_type", "unknown"),
            importance=f.get("importance_score", 0),
        )

    # Add edges from relations
    file_id_map = {f["file_id"]: f["path"] for f in files}
    for rel in relations:
        src_path = file_id_map.get(rel["source_id"])
        tgt_path = file_id_map.get(rel["target_id"])
        if src_path and tgt_path:
            src_node = f"file:{src_path}"
            tgt_node = f"file:{tgt_path}"
            graph.add_edge(src_node, tgt_node, relation=rel["relation_type"])

    return graph


def build_research_workflow_graph(
    experiments: list[dict],
    paper_sections: list[dict],
    figures: list[dict],
    files: list[dict],
) -> GraphData:
    """Build a graph of the research workflow."""
    graph = GraphData()

    # Add paper section nodes
    for ps in paper_sections:
        graph.add_node(
            f"section:{ps['section_title']}",
            label=ps["section_title"],
            node_type="section",
            section_type=ps.get("section_type", ""),
        )

    # Add experiment nodes
    for exp in experiments:
        graph.add_node(
            f"experiment:{exp['name']}",
            label=exp["name"],
            node_type="experiment",
            status=exp.get("status", ""),
        )
        # Link to script
        if exp.get("script_path"):
            graph.add_node(
                f"script:{exp['script_path']}",
                label=exp["script_path"].split("/")[-1],
                node_type="script",
            )
            graph.add_edge(
                f"experiment:{exp['name']}", f"script:{exp['script_path']}",
                relation="runs_script",
            )
        # Link to config
        if exp.get("config_path"):
            graph.add_node(
                f"config:{exp['config_path']}",
                label=exp["config_path"].split("/")[-1],
                node_type="config",
            )
            edge_src = f"script:{exp['script_path']}" if exp.get("script_path") else f"experiment:{exp['name']}"
            graph.add_edge(edge_src, f"config:{exp['config_path']}", relation="reads_config")
        # Link to result
        if exp.get("result_path"):
            graph.add_node(
                f"result:{exp['result_path']}",
                label=exp["result_path"].split("/")[-1],
                node_type="result",
            )
            edge_src = f"script:{exp['script_path']}" if exp.get("script_path") else f"experiment:{exp['name']}"
            graph.add_edge(edge_src, f"result:{exp['result_path']}", relation="writes_result")

    # Add figure nodes
    for fig in figures:
        fig_id = f"figure:{fig['figure_name']}"
        graph.add_node(
            fig_id,
            label=fig["figure_name"],
            node_type="figure",
            status=fig.get("status", ""),
        )
        if fig.get("generator_script"):
            gen_id = f"script:{fig['generator_script']}"
            graph.add_node(gen_id, label=fig["generator_script"].split("/")[-1], node_type="script")
            graph.add_edge(gen_id, fig_id, relation="generates_figure")
        if fig.get("source_data"):
            for sd in fig["source_data"]:
                data_id = f"result:{sd}"
                graph.add_node(data_id, label=sd.split("/")[-1], node_type="result")
                graph.add_edge(data_id, fig_id, relation="provides_data")

    # Link sections to figures (by name pattern matching)
    for ps in paper_sections:
        for fig in figures:
            if fig["figure_name"].lower() in ps.get("summary", "").lower():
                graph.add_edge(
                    f"section:{ps['section_title']}",
                    f"figure:{fig['figure_name']}",
                    relation="references_figure",
                )

    return graph


def compute_graph_metrics(graph: GraphData) -> dict[str, Any]:
    """Compute basic graph metrics."""
    metrics: dict[str, Any] = {
        "nodes": graph.node_count,
        "edges": graph.edge_count,
        "density": 0.0,
        "connected_components": 0,
    }

    if not HAS_NETWORKX or graph.node_count == 0:
        return metrics

    G = nx.DiGraph()
    for node in graph.nodes:
        G.add_node(node["id"], **{k: v for k, v in node.items() if k != "id"})
    for edge in graph.edges:
        G.add_edge(edge["source"], edge["target"], relation=edge.get("relation", ""))

    metrics["density"] = round(nx.density(G), 4)

    undirected = G.to_undirected()
    metrics["connected_components"] = nx.number_connected_components(undirected)

    # Degree stats
    degrees = [d for _, d in G.degree()]
    if degrees:
        metrics["max_degree"] = max(degrees)
        metrics["avg_degree"] = round(sum(degrees) / len(degrees), 2)

    return metrics
