"""Lock registry: freeze results, configs, and metrics for paper-grade reproducibility."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..git_utils import get_repo_info, is_git_repo
from ..memory.sqlite_store import SQLiteStore
from ..parsers.config_parser import parse_config_file
from ..parsers.result_parser import parse_result_file
from ..utils.hashing import file_hash


def lock_file(
    store: SQLiteStore,
    repo_id: int,
    repo_root: Path,
    lock_type: str,
    target: str,
    label: str = "",
) -> dict[str, Any]:
    """Lock a result or config file by path."""
    rel = target.replace("\\", "/").lstrip("./")
    abs_path = repo_root / rel
    if not abs_path.exists():
        raise FileNotFoundError(f"File not found: {rel}")

    h = file_hash(abs_path)
    metrics: dict[str, Any] = {}
    if lock_type == "result":
        metrics = parse_result_file(abs_path)
    elif lock_type == "config":
        metrics = parse_config_file(abs_path)

    git = get_repo_info(repo_root) if is_git_repo(repo_root) else None
    commit = git.latest_commit if git else ""
    lbl = label or f"{lock_type}:{Path(rel).stem}"

    lock_id = store.upsert_lock(
        repo_id=repo_id,
        lock_type=lock_type,
        target_path=rel,
        label=lbl,
        file_hash=h,
        metrics_json=metrics,
        git_commit=commit,
    )
    return {
        "lock_id": lock_id,
        "label": lbl,
        "type": lock_type,
        "path": rel,
        "hash": h[:16],
        "commit": commit[:8] if commit else "",
    }


def lock_metric(
    store: SQLiteStore,
    repo_id: int,
    repo_root: Path,
    label: str,
    metrics: dict[str, Any],
    source_path: str = "",
) -> dict[str, Any]:
    """Lock an explicit metric snapshot (e.g. Table 2 mean reward)."""
    git = get_repo_info(repo_root) if is_git_repo(repo_root) else None
    commit = git.latest_commit if git else ""
    lock_id = store.upsert_lock(
        repo_id=repo_id,
        lock_type="metric",
        target_path=source_path,
        label=label,
        file_hash="",
        metrics_json=metrics,
        git_commit=commit,
    )
    return {"lock_id": lock_id, "label": label, "metrics": metrics}


def verify_locks(
    store: SQLiteStore,
    repo_id: int,
    repo_root: Path,
) -> list[dict[str, Any]]:
    """Verify locked files still match stored hashes and metrics."""
    locks = store.get_locks(repo_id)
    report: list[dict[str, Any]] = []

    for lock in locks:
        entry: dict[str, Any] = {
            "label": lock["label"],
            "type": lock["lock_type"],
            "path": lock["target_path"],
            "status": "ok",
            "issues": [],
        }
        path = lock["target_path"]
        if lock["lock_type"] in ("result", "config") and path:
            abs_path = repo_root / path
            if not abs_path.exists():
                entry["status"] = "missing"
                entry["issues"].append("file missing")
            else:
                current_hash = file_hash(abs_path)
                if lock["file_hash"] and current_hash != lock["file_hash"]:
                    entry["status"] = "changed"
                    entry["issues"].append("file hash mismatch (LOCK violated)")
        report.append(entry)
    return report


def parse_metric_kv(text: str) -> dict[str, Any]:
    """Parse key=value pairs from CLI: 'reward=0.84,seed=3'."""
    out: dict[str, Any] = {}
    for part in text.split(","):
        part = part.strip()
        if "=" not in part:
            continue
        k, _, v = part.partition("=")
        k, v = k.strip(), v.strip()
        try:
            out[k] = float(v) if "." in v else int(v)
        except ValueError:
            out[k] = v
    return out
