"""Export graphs to JSON format."""

from __future__ import annotations

import json
from pathlib import Path

from .graph_builder import GraphData


def export_graph_json(graph: GraphData, output_path: Path) -> None:
    """Export a GraphData to a JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = graph.to_dict()
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def load_graph_json(path: Path) -> dict:
    """Load a graph from a JSON file."""
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"nodes": [], "edges": []}
