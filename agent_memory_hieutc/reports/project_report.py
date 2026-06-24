"""Generate scan report after indexing."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def generate_scan_report(
    output_dir: Path,
    repo_name: str,
    stats: dict,
    context_files: list[str],
) -> str:
    """Generate a Markdown scan report."""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"scan_report_{timestamp}.md"
    filepath = output_dir / filename

    lines = [
        f"# Scan Report: {repo_name}",
        "",
        f"**Time:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Statistics",
        "",
        f"- **Total files found:** {stats.get('total', 0)}",
        f"- **Files parsed:** {stats.get('parsed', 0)}",
        f"- **Files skipped:** {stats.get('skipped', 0)}",
        f"- **Scan duration:** {stats.get('elapsed_seconds', 0):.1f}s",
        "",
        "### Files by Type",
        "",
        "| Type | Count |",
        "|---|---|",
    ]

    for ftype, count in sorted(stats.get("by_type", {}).items(), key=lambda x: x[1], reverse=True):
        lines.append(f"| {ftype} | {count} |")

    lines.extend([
        "",
        "## Generated Context Files",
        "",
    ])
    for cf in context_files:
        lines.append(f"- `{cf}`")

    lines.append("")
    content = "\n".join(lines)

    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    return str(filepath)
