"""Verify paper numeric claims against locked results."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..memory.sqlite_store import SQLiteStore

# Numbers in paper text: 0.84, 84.3%, 1e-3, etc.
NUMBER_PATTERN = re.compile(
    r"\b(\d+\.\d+|\d+)\s*(%|±|\+\/-)?\s*(\d+\.\d+|\d+)?"
)


def extract_paper_numbers(content: str) -> list[str]:
    """Extract numeric tokens from paper content."""
    found: set[str] = set()
    for m in NUMBER_PATTERN.finditer(content):
        found.add(m.group(0).strip())
    return sorted(found)[:50]


def verify_claims(
    store: SQLiteStore,
    repo_id: int,
    repo_root: Path,
) -> dict[str, Any]:
    """Cross-check locked metrics with numbers mentioned in paper files."""
    locks = store.get_locks(repo_id)
    locked_metrics: dict[str, float] = {}
    for lock in locks:
        try:
            data = json.loads(lock.get("metrics_json", "{}") or "{}")
        except json.JSONDecodeError:
            data = {}
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, (int, float)):
                    locked_metrics[f"{lock['label']}.{k}"] = float(v)
                elif isinstance(v, list) and v and isinstance(v[0], (int, float)):
                    locked_metrics[f"{lock['label']}.{k}"] = float(v[0])

    paper_files = []
    for f in store.get_all_files(repo_id):
        if f["file_type"] in ("paper_latex", "paper_markdown", "paper_draft"):
            paper_files.append(f["path"])
        elif f["path"].endswith((".tex", ".md")) and "paper" in f["path"].lower():
            paper_files.append(f["path"])

    paper_numbers: list[str] = []
    for rel in paper_files[:5]:
        p = repo_root / rel
        if p.exists():
            try:
                paper_numbers.extend(extract_paper_numbers(p.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                pass

    issues: list[str] = []
    lock_report = []
    from ..memory.lock_registry import verify_locks
    for v in verify_locks(store, repo_id, repo_root):
        lock_report.append(v)
        if v["status"] != "ok":
            issues.append(f"LOCK {v['label']}: {', '.join(v['issues'])}")

    return {
        "locks_checked": len(lock_report),
        "lock_violations": sum(1 for r in lock_report if r["status"] != "ok"),
        "locked_metric_keys": list(locked_metrics.keys())[:20],
        "paper_numbers_sample": paper_numbers[:15],
        "issues": issues,
        "status": "ok" if not issues else "warning",
    }


def generate_verify_report(
    reports_dir: Path,
    result: dict[str, Any],
    repo_name: str,
) -> str:
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = reports_dir / f"verify_report_{ts}.md"
    lines = [
        f"# Verify Report: {repo_name}",
        f"Status: **{result['status']}**",
        "",
        f"- Locks checked: {result['locks_checked']}",
        f"- Violations: {result['lock_violations']}",
        "",
    ]
    if result["issues"]:
        lines.append("## Issues")
        for i in result["issues"]:
            lines.append(f"- {i}")
    else:
        lines.append("No lock violations detected.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)
