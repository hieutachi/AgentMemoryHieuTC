"""Discover MLflow runs from local mlruns/ directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..memory.sqlite_store import SQLiteStore


def discover_mlflow_runs(
    store: SQLiteStore,
    repo_id: int,
    repo_root: Path,
    max_runs: int = 20,
) -> list[dict[str, Any]]:
    """Scan mlruns/ for experiment run metadata."""
    found: list[dict[str, Any]] = []
    mlruns = repo_root / "mlruns"
    if not mlruns.is_dir():
        return found

    count = 0
    for meta_path in mlruns.rglob("meta.yaml"):
        if count >= max_runs:
            break
        run_dir = meta_path.parent
        run_id = run_dir.name
        run_name = run_id
        metrics: dict[str, Any] = {}
        try:
            text = meta_path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                if line.startswith("run_name:"):
                    run_name = line.split(":", 1)[1].strip().strip('"')
        except OSError:
            continue
        metrics_dir = run_dir / "metrics"
        if metrics_dir.is_dir():
            for mf in metrics_dir.iterdir():
                if mf.is_file():
                    metrics[mf.name] = mf.name
        rel = str(run_dir.relative_to(repo_root)).replace("\\", "/")
        store.insert_run_artifact(
            repo_id=repo_id,
            source="mlflow",
            run_id=run_id,
            run_name=run_name,
            metrics_json=metrics,
            artifact_path=rel,
        )
        found.append({"run_id": run_id, "name": run_name})
        count += 1
    return found
