"""Generate health report checking repository quality."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..config import MemoryConfig
from ..memory.sqlite_store import SQLiteStore


def generate_health_report(cfg: MemoryConfig, store: SQLiteStore,
                           repo_id: int) -> str:
    """Generate a health report identifying issues and missing items."""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"health_report_{timestamp}.md"
    filepath = cfg.reports_dir / filename

    files = store.get_all_files(repo_id)
    experiments = store.get_experiments(repo_id)
    figures = store.get_figures(repo_id)
    sections = store.get_paper_sections(repo_id)

    issues: list[tuple[str, str, str]] = []  # (severity, category, description)

    # Check for README
    has_readme = any(f["path"].lower().startswith("readme") for f in files)
    if not has_readme:
        issues.append(("warning", "documentation", "No README file found."))

    # Check for requirements
    has_reqs = any(f["path"].lower() in ("requirements.txt", "pyproject.toml", "setup.py", "setup.cfg", "environment.yml")
                   for f in files)
    if not has_reqs:
        issues.append(("warning", "packaging", "No requirements.txt or pyproject.toml found."))

    # Check experiments for missing configs
    for exp in experiments:
        if not exp.get("config_path") and exp.get("status") != "config_only":
            issues.append(("info", "experiment", f"Experiment `{exp['name']}` has no associated config file."))

    # Check experiments for missing results
    for exp in experiments:
        if not exp.get("result_path") and exp.get("status") == "detected":
            issues.append(("info", "experiment", f"Experiment `{exp['name']}` has no associated result file."))

    # Check figures for missing generators
    for fig in figures:
        if not fig.get("generator_script"):
            issues.append(("info", "figure", f"Figure `{fig['figure_name']}` has no detected generator script."))

    # Check for source code without docstrings/symbols
    source_files = [f for f in files if f["file_type"] == "source_code"]
    for f in source_files[:10]:
        if not f.get("summary"):
            issues.append(("info", "code_quality", f"File `{f['path']}` has no summary (may lack docstrings)."))

    # Check for too many files (graph density warning)
    stats = store.get_stats(repo_id)
    if stats.get("relations", 0) > 500:
        issues.append(("info", "graph", "Very dense codebase graph. Consider increasing importance_threshold."))

    # Generate report
    lines = [
        f"# Health Report: {cfg.repo_name}",
        "",
        f"**Time:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Summary",
        "",
        f"- **Issues found:** {len(issues)}",
        f"- **Warnings:** {sum(1 for s, _, _ in issues if s == 'warning')}",
        f"- **Info:** {sum(1 for s, _, _ in issues if s == 'info')}",
        "",
    ]

    if issues:
        lines.extend([
            "## Issues",
            "",
            "| Severity | Category | Description |",
            "|---|---|---|",
        ])
        for severity, category, desc in issues:
            lines.append(f"| {severity} | {category} | {desc} |")
    else:
        lines.append("No issues found. The repository is well-indexed.")

    lines.extend([
        "",
        "## Recommendations",
        "",
    ])

    if not has_readme:
        lines.append("- Add a README.md with project description, setup instructions, and experiment usage.")
    if not has_reqs:
        lines.append("- Add a requirements.txt or pyproject.toml for reproducibility.")
    if not sections:
        lines.append("- No paper sections detected. Add paper files (.tex, .md) for better paper mapping.")
    if not experiments:
        lines.append("- No experiments detected. Ensure experiment scripts use recognizable patterns.")

    content = "\n".join(lines)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    return str(filepath)
