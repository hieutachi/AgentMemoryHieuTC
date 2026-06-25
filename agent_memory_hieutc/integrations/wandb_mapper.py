"""Discover Weights & Biases runs from local wandb/ directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..memory.sqlite_store import SQLiteStore

WANDB_DIRS = ("wandb", "wandb/latest-run")


def discover_wandb_runs(
    store: SQLiteStore,
    repo_id: int,
    repo_root: Path,
    max_runs: int = 20,
) -> list[dict[str, Any]]:
    """Scan local wandb folders for run metadata."""
    found: list[dict[str, Any]] = []
    wandb_root = repo_root / "wandb"
    if not wandb_root.is_dir():
        return found

    for run_dir in sorted(wandb_root.glob("run-*"), reverse=True)[:max_runs]:
        meta_file = None
        for candidate in (run_dir / "files" / "wandb-metadata.json", run_dir / "wandb-metadata.json"):
            if candidate.exists():
                meta_file = candidate
                break
        summary_file = run_dir / "files" / "wandb-summary.json"
        metrics: dict[str, Any] = {}
        run_id = run_dir.name
        run_name = run_dir.name
        if meta_file:
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                run_id = meta.get("run_id", run_id)
                run_name = meta.get("displayName") or meta.get("name") or run_name
            except (OSError, json.JSONDecodeError):
                pass
        if summary_file.exists():
            try:
                metrics = json.loads(summary_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        store.insert_run_artifact(
            repo_id=repo_id,
            source="wandb",
            run_id=run_id,
            run_name=run_name,
            metrics_json=metrics,
            artifact_path=str(run_dir.relative_to(repo_root)).replace("\\", "/"),
        )
        found.append({"run_id": run_id, "name": run_name, "metrics": list(metrics.keys())[:10]})
    return found
