"""Research phase tracking for long-running ML/RL projects."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..memory.sqlite_store import SQLiteStore

DEFAULT_PHASES = [
    "baseline",
    "ablation",
    "unseen_map",
    "sensitivity",
    "camera_ready",
    "revision",
]

PHASE_LABELS = {
    "baseline": "Baseline experiments",
    "ablation": "Ablation studies",
    "unseen_map": "Generalization / unseen maps",
    "sensitivity": "Hyperparameter sensitivity",
    "camera_ready": "Camera-ready polish",
    "revision": "Reviewer revision",
}


def ensure_default_phases(store: SQLiteStore, repo_id: int) -> None:
    for name in DEFAULT_PHASES:
        store.upsert_phase(repo_id, name, status="pending")


def set_active_phase(store: SQLiteStore, repo_id: int, phase_name: str) -> None:
    ensure_default_phases(store, repo_id)
    now = datetime.now(timezone.utc).isoformat()
    store.upsert_phase(repo_id, phase_name, status="active", started_at=now)
    store.set_memory(repo_id, "active_phase", phase_name, confidence=1.0)


def complete_phase_task(
    store: SQLiteStore,
    repo_id: int,
    phase_name: str,
    task: str,
) -> None:
    phase = store.get_phase(repo_id, phase_name)
    if not phase:
        store.upsert_phase(repo_id, phase_name, status="active")
        phase = store.get_phase(repo_id, phase_name)
    tasks = json.loads(phase.get("tasks_json", "[]") or "[]")
    if task not in tasks:
        tasks.append(task)
    store.upsert_phase(repo_id, phase_name, status="active", tasks_json=tasks)


def mark_phase_done(store: SQLiteStore, repo_id: int, phase_name: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    store.upsert_phase(
        repo_id, phase_name, status="done",
        completed_at=now,
    )


def generate_phase_status(
    cfg_context_dir: Path,
    store: SQLiteStore,
    repo_id: int,
    repo_name: str,
) -> str:
    """Write PHASE_STATUS.md for agent handoff."""
    ensure_default_phases(store, repo_id)
    phases = store.get_phases(repo_id)
    active = store.get_memory(repo_id, "active_phase") or "none"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# Phase Status: {repo_name}",
        f"Updated: {now} | **Active phase:** `{active}`",
        "",
        "| Phase | Status | Tasks done |",
        "|---|---|---|",
    ]
    for p in phases:
        tasks = json.loads(p.get("tasks_json", "[]") or "[]")
        label = PHASE_LABELS.get(p["phase_name"], p["phase_name"])
        lines.append(
            f"| {label} (`{p['phase_name']}`) | {p['status']} | {len(tasks)} |"
        )

    lines.extend([
        "",
        "## Rules for agents",
        "- Do NOT start a new phase until active phase is `done`.",
        "- Run `agentmemory phase set <name>` before switching phase.",
        "- Record decisions with `agentmemory note \"...\"`.",
        "- LOCK metrics before citing in paper: `agentmemory lock result <file>`.",
    ])
    content = "\n".join(lines)
    path = cfg_context_dir / "PHASE_STATUS.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)
