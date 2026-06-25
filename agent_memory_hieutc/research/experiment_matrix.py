"""Experiment matrix: algo × environment × seeds."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..memory.sqlite_store import SQLiteStore


def build_experiment_matrix(store: SQLiteStore, repo_id: int) -> list[dict[str, Any]]:
    """Build rows for experiment matrix from indexed experiments + locks."""
    experiments = store.get_experiments(repo_id)
    rows: list[dict[str, Any]] = []

    for exp in experiments:
        algos = _parse_list(exp.get("algorithms"))
        seeds = _parse_list(exp.get("seeds"))
        rows.append({
            "name": exp["name"],
            "script": exp.get("script_path", ""),
            "config": exp.get("config_path", ""),
            "algorithm": algos[0] if algos else "-",
            "environment": exp.get("environment") or "-",
            "seeds": len(seeds) if seeds else "-",
            "status": exp.get("status", "?"),
        })

    # Add locked results as matrix rows
    for lock in store.get_locks(repo_id):
        if lock["lock_type"] != "result":
            continue
        metrics = _parse_dict(lock.get("metrics_json"))
        rows.append({
            "name": f"LOCK:{lock['label']}",
            "script": "-",
            "config": "-",
            "algorithm": ",".join(metrics.get("algorithms", [])[:1]) if metrics.get("algorithms") else "-",
            "environment": ",".join(metrics.get("environments", [])[:1]) if metrics.get("environments") else "-",
            "seeds": len(metrics.get("seeds", [])) or "-",
            "status": "locked",
        })
    return rows


def export_matrix_markdown(
    context_dir: Path,
    store: SQLiteStore,
    repo_id: int,
    repo_name: str,
) -> str:
    rows = build_experiment_matrix(store, repo_id)
    lines = [
        f"# Experiment Matrix: {repo_name}",
        "",
        "| Name | Script | Config | Algo | Env | Seeds | Status |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows[:30]:
        lines.append(
            f"| {r['name']} | `{r['script']}` | `{r['config']}` | "
            f"{r['algorithm']} | {r['environment']} | {r['seeds']} | {r['status']} |"
        )
    if not rows:
        lines.append("| _none_ | - | - | - | - | - | - |")
    content = "\n".join(lines)
    path = context_dir / "EXPERIMENT_MATRIX.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def _parse_list(val: Any) -> list:
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            p = json.loads(val)
            return p if isinstance(p, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _parse_dict(val: Any) -> dict:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            p = json.loads(val)
            return p if isinstance(p, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}
