"""Decision log: record what was tried and outcomes."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..memory.sqlite_store import SQLiteStore


def add_decision(
    store: SQLiteStore,
    repo_id: int,
    content: str,
    phase: str = "",
    outcome: str = "",
) -> int:
    if not phase:
        phase = store.get_memory(repo_id, "active_phase") or ""
    return store.insert_decision(repo_id, content, phase=phase, outcome=outcome)


def generate_decision_log(
    context_dir: Path,
    store: SQLiteStore,
    repo_id: int,
    repo_name: str,
    max_entries: int = 15,
) -> str:
    decisions = store.get_decisions(repo_id, limit=max_entries)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# Decision Log: {repo_name}", f"Updated: {now}", ""]
    if not decisions:
        lines.append("_No decisions recorded. Use `agentmemory note \"...\"`._")
    else:
        for d in decisions:
            phase = d.get("phase") or "?"
            outcome = d.get("outcome") or ""
            suffix = f" → {outcome}" if outcome else ""
            lines.append(f"- [{phase}] {d['content']}{suffix}")
    content = "\n".join(lines)
    path = context_dir / "DECISION_LOG.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)
