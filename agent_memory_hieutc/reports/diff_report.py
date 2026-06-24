"""Generate diff report showing changes since last scan."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..config import MemoryConfig
from ..git_utils import get_changed_files
from ..memory.sqlite_store import SQLiteStore


def generate_diff_report(cfg: MemoryConfig, store: SQLiteStore,
                         repo_id: int) -> str:
    """Generate a diff report comparing current state to last scan."""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"diff_report_{timestamp}.md"
    filepath = cfg.reports_dir / filename

    last_commit = cfg.data.get("last_scan_commit", "")
    changed_files = get_changed_files(cfg.repo_root, last_commit if last_commit else None)
    indexed_files = store.get_all_files(repo_id)
    indexed_paths = {f["path"] for f in indexed_files}

    # Categorize changes
    added = [f for f in changed_files if f not in indexed_paths]
    modified = [f for f in changed_files if f in indexed_paths]
    deleted = [f for f in indexed_paths if f not in {cf for cf in changed_files} and not (cfg.repo_root / f).exists()]

    lines = [
        f"# Diff Report",
        "",
        f"**Time:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Since:** {last_commit[:8] if last_commit else 'initial scan'}",
        "",
        "## Summary",
        "",
        f"- **Added:** {len(added)} files",
        f"- **Modified:** {len(modified)} files",
        f"- **Deleted:** {len(deleted)} files",
        "",
    ]

    if added:
        lines.extend(["### Added Files", ""])
        for f in sorted(added)[:30]:
            lines.append(f"- `{f}`")
        if len(added) > 30:
            lines.append(f"- ... and {len(added) - 30} more")
        lines.append("")

    if modified:
        lines.extend(["### Modified Files", ""])
        for f in sorted(modified)[:30]:
            lines.append(f"- `{f}`")
        if len(modified) > 30:
            lines.append(f"- ... and {len(modified) - 30} more")
        lines.append("")

    if deleted:
        lines.extend(["### Deleted Files", ""])
        for f in sorted(deleted)[:30]:
            lines.append(f"- `{f}`")
        lines.append("")

    content = "\n".join(lines)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    return str(filepath)
