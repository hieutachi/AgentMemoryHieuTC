"""Export graphs to Mermaid diagram format."""

from __future__ import annotations

from ..utils.paths import sanitize_mermaid_id
from .graph_builder import GraphData


def export_mermaid(graph: GraphData, title: str = "Codebase Graph",
                   direction: str = "TD", max_edges: int = 150) -> str:
    """Export a GraphData to Mermaid flowchart format."""
    lines: list[str] = [f"flowchart {direction}"]

    if title:
        lines.append(f"    %% {title}")

    # Group nodes by type for subgraphs
    node_groups: dict[str, list[dict]] = {}
    for node in graph.nodes:
        group = node.get("node_type", "other")
        node_groups.setdefault(group, []).append(node)

    # Emit subgraphs
    node_id_map: dict[str, str] = {}  # original_id -> mermaid_id
    emitted_ids: set[str] = set()

    group_labels = {
        "file": "Source Files",
        "script": "Scripts",
        "config": "Configs",
        "experiment": "Experiments",
        "result": "Results",
        "figure": "Figures",
        "section": "Paper Sections",
        "other": "Other",
    }

    for group_name, nodes in node_groups.items():
        label = group_labels.get(group_name, group_name.title())
        safe_group = sanitize_mermaid_id(group_name)
        lines.append(f"    subgraph {safe_group}[\"{label}\"]")

        for node in nodes:
            orig_id = node["id"]
            mermaid_id = sanitize_mermaid_id(orig_id)
            display = node.get("label", orig_id.split(":")[-1])
            # Truncate long labels
            if len(display) > 30:
                display = display[:27] + "..."
            lines.append(f"        {mermaid_id}[\"{display}\"]")
            node_id_map[orig_id] = mermaid_id
            emitted_ids.add(mermaid_id)

        lines.append("    end")

    # Emit edges
    edge_count = 0
    for edge in graph.edges[:max_edges]:
        src = node_id_map.get(edge["source"])
        tgt = node_id_map.get(edge["target"])
        if src and tgt and src in emitted_ids and tgt in emitted_ids:
            rel = edge.get("relation", "")
            if rel:
                lines.append(f"    {src} -->|\"{rel}\"| {tgt}")
            else:
                lines.append(f"    {src} --> {tgt}")
            edge_count += 1

    # Style classes
    lines.append("")
    lines.append("    classDef script fill:#2563eb,color:#fff,stroke:none")
    lines.append("    classDef config fill:#059669,color:#fff,stroke:none")
    lines.append("    classDef result fill:#d97706,color:#fff,stroke:none")
    lines.append("    classDef figure fill:#7c3aed,color:#fff,stroke:none")
    lines.append("    classDef section fill:#dc2626,color:#fff,stroke:none")

    return "\n".join(lines)


def export_research_workflow_mermaid(graph: GraphData) -> str:
    """Export the research workflow graph as a left-to-right Mermaid diagram."""
    return export_mermaid(graph, title="Research Workflow", direction="LR", max_edges=100)
