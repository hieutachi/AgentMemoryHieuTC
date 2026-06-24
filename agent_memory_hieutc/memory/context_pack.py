"""Generate context pack files for AI agent handoff."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import MemoryConfig
from ..memory.sqlite_store import SQLiteStore


def generate_context_pack(cfg: MemoryConfig, store: SQLiteStore,
                          repo_id: int) -> list[str]:
    """Generate all context pack files. Returns list of generated file paths."""
    generated: list[str] = []

    files = [
        _generate_agent_brief(cfg, store, repo_id),
        _generate_project_context(cfg, store, repo_id),
        _generate_paper_mapping(cfg, store, repo_id),
        _generate_experiment_mapping(cfg, store, repo_id),
        _generate_figure_mapping(cfg, store, repo_id),
        _generate_changelog_context(cfg, store, repo_id),
        _generate_next_agent_prompt(cfg),
    ]

    for filepath in files:
        if filepath:
            generated.append(filepath)

    return generated


def _write_file(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def _generate_agent_brief(cfg: MemoryConfig, store: SQLiteStore,
                          repo_id: int) -> str:
    """Generate AGENT_BRIEF.md — the main entry point for any AI agent."""
    files = store.get_all_files(repo_id)
    experiments = store.get_experiments(repo_id)
    figures = store.get_figures(repo_id)
    stats = store.get_stats(repo_id)

    # Top files by importance
    top_files = sorted(files, key=lambda f: f.get("importance_score", 0), reverse=True)[:15]

    # Key scripts
    training_scripts = [f for f in files if f["file_type"] == "training_script"]
    experiment_scripts = [f for f in files if f["file_type"] == "experiment_script"]
    eval_scripts = [f for f in files if f["file_type"] == "evaluation_script"]
    figure_scripts = [f for f in files if f["file_type"] == "figure_generation_script"]
    configs = [f for f in files if f["file_type"] == "config_file"]
    results = [f for f in files if f["file_type"] == "result_file"]
    paper_files = [f for f in files if f["file_type"] in ("paper_latex", "paper_markdown", "paper_draft")]

    paper_title = store.get_memory(repo_id, "paper_title") or "Not detected"
    target_venue = store.get_memory(repo_id, "target_venue") or "Not detected"

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# Agent Brief: {cfg.repo_name}",
        f"",
        f"**Generated:** {now}",
        f"**Purpose:** This file is the primary context document for any AI agent working on this repository.",
        f"",
        f"---",
        f"",
        f"## 1. Project Identity",
        f"",
        f"- **Repository:** {cfg.repo_name}",
        f"- **Path:** {cfg.repo_root}",
        f"- **Paper Title:** {paper_title}",
        f"- **Target Venue:** {target_venue}",
        f"",
        f"## 2. Repository Statistics",
        f"",
        f"- **Indexed Files:** {stats.get('files', 0)}",
        f"- **Symbols:** {stats.get('symbols', 0)}",
        f"- **Relations:** {stats.get('relations', 0)}",
        f"- **Experiments:** {stats.get('experiments', 0)}",
        f"- **Paper Sections:** {stats.get('paper_sections', 0)}",
        f"- **Figures:** {stats.get('figures', 0)}",
        f"",
        f"## 3. Key Scripts (Read First)",
        f"",
    ]

    if training_scripts:
        lines.append("### Training Scripts")
        for f in training_scripts[:5]:
            lines.append(f"- `{f['path']}` — Importance: {f['importance_score']:.1f}")
        lines.append("")

    if experiment_scripts:
        lines.append("### Experiment Scripts")
        for f in experiment_scripts[:5]:
            lines.append(f"- `{f['path']}` — Importance: {f['importance_score']:.1f}")
        lines.append("")

    if eval_scripts:
        lines.append("### Evaluation Scripts")
        for f in eval_scripts[:5]:
            lines.append(f"- `{f['path']}` — Importance: {f['importance_score']:.1f}")
        lines.append("")

    if figure_scripts:
        lines.append("### Figure Generation Scripts")
        for f in figure_scripts[:5]:
            lines.append(f"- `{f['path']}` — Importance: {f['importance_score']:.1f}")
        lines.append("")

    lines.extend([
        "## 4. Key Folders",
        "",
    ])

    # Detect key folders
    folders: dict[str, int] = {}
    for f in files:
        parts = f["path"].split("/")
        if len(parts) > 1:
            folder = parts[0]
            folders[folder] = folders.get(folder, 0) + 1
    for folder, count in sorted(folders.items(), key=lambda x: x[1], reverse=True)[:10]:
        lines.append(f"- `{folder}/` ({count} files)")

    lines.extend([
        "",
        "## 5. Experiments",
        "",
    ])
    if experiments:
        lines.append("| Experiment | Script | Status |")
        lines.append("|---|---|---|")
        for exp in experiments[:15]:
            lines.append(f"| {exp['name']} | `{exp.get('script_path', 'N/A')}` | {exp.get('status', 'unknown')} |")
    else:
        lines.append("No experiments indexed.")

    lines.extend([
        "",
        "## 6. Figures",
        "",
    ])
    if figures:
        lines.append("| Figure | Generator | Status |")
        lines.append("|---|---|---|")
        for fig in figures[:15]:
            lines.append(f"| {fig['figure_name']} | `{fig.get('generator_script', 'N/A')}` | {fig.get('status', 'unknown')} |")
    else:
        lines.append("No figures indexed.")

    lines.extend([
        "",
        "## 7. What to Read First",
        "",
        "An AI agent should read these files first, in order:",
        "",
    ])
    for i, f in enumerate(top_files[:10], 1):
        summary = f.get("summary", "")
        summary_str = f" — {summary}" if summary else ""
        lines.append(f"{i}. `{f['path']}`{summary_str}")

    lines.extend([
        "",
        "## 8. What to Skip",
        "",
        "- Checkpoint files (`.pt`, `.pth`, `.ckpt`)",
        "- Log files and wandb runs",
        "- Virtual environments",
        "- Large result files (read summaries instead)",
        "- Cache and build directories",
        "",
        "## 9. How to Resume Work",
        "",
        "1. Read this file and the files listed in Section 7.",
        "2. Check `EXPERIMENT_MAPPING.md` for current experiment status.",
        "3. Check `PAPER_MAPPING.md` for paper section coverage.",
        "4. Check `FIGURE_MAPPING.md` for figure status.",
        "5. Run `agentmemory diff` to see recent changes.",
        "",
    ])

    return _write_file(cfg.context_dir / "AGENT_BRIEF.md", "\n".join(lines))


def _generate_project_context(cfg: MemoryConfig, store: SQLiteStore,
                              repo_id: int) -> str:
    """Generate PROJECT_CONTEXT.md with detailed file inventory."""
    files = store.get_all_files(repo_id)

    # Group by type
    by_type: dict[str, list[dict]] = {}
    for f in files:
        by_type.setdefault(f["file_type"], []).append(f)

    lines = [
        f"# Project Context: {cfg.repo_name}",
        "",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    type_labels = {
        "training_script": "Training Scripts",
        "experiment_script": "Experiment Scripts",
        "evaluation_script": "Evaluation Scripts",
        "figure_generation_script": "Figure Generation Scripts",
        "config_file": "Configuration Files",
        "source_code": "Source Code",
        "result_file": "Result Files",
        "paper_latex": "LaTeX Files",
        "paper_markdown": "Markdown Paper Files",
        "paper_draft": "Paper Draft / Revision Files",
        "notebook": "Notebooks",
        "documentation": "Documentation",
        "dataset_metadata": "Dataset Metadata",
    }

    priority_types = [
        "training_script", "experiment_script", "evaluation_script",
        "figure_generation_script", "config_file", "result_file",
        "source_code", "paper_latex", "paper_markdown", "paper_draft",
    ]

    for ftype in priority_types:
        if ftype in by_type:
            label = type_labels.get(ftype, ftype)
            lines.append(f"## {label}")
            lines.append("")
            lines.append(f"| File | Importance | Summary |")
            lines.append(f"|---|---|---|")
            for f in sorted(by_type[ftype], key=lambda x: x["importance_score"], reverse=True):
                summary = (f.get("summary", "") or "")[:80]
                lines.append(f"| `{f['path']}` | {f['importance_score']:.1f} | {summary} |")
            lines.append("")

    return _write_file(cfg.context_dir / "PROJECT_CONTEXT.md", "\n".join(lines))


def _generate_paper_mapping(cfg: MemoryConfig, store: SQLiteStore,
                            repo_id: int) -> str:
    sections = store.get_paper_sections(repo_id)
    figures = store.get_figures(repo_id)
    experiments = store.get_experiments(repo_id)

    lines = [
        f"# Paper Mapping: {cfg.repo_name}",
        "",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Paper Section Mapping",
        "",
        "| Paper Section | Type | Claims | Related Files | Status |",
        "|---|---|---|---|---|",
    ]

    for s in sections:
        claims_str = s.get("claims", "[]")
        if isinstance(claims_str, str):
            try:
                claims = json.loads(claims_str)
            except (json.JSONDecodeError, TypeError):
                claims = []
        else:
            claims = claims_str
        claims_display = "; ".join(claims[:3]) if claims else "-"
        related_str = s.get("related_files", "[]")
        if isinstance(related_str, str):
            try:
                related = json.loads(related_str)
            except (json.JSONDecodeError, TypeError):
                related = []
        else:
            related = related_str
        related_display = ", ".join(f"`{r}`" for r in related[:3]) if related else "-"
        lines.append(
            f"| {s['section_title']} | {s.get('section_type', '-')} | "
            f"{claims_display} | {related_display} | - |"
        )

    lines.extend([
        "",
        "## Result-to-Paper Cross-Reference",
        "",
        "| Result File | Experiment | Paper Section | Figure |",
        "|---|---|---|---|",
    ])

    for exp in experiments:
        result = exp.get("result_path", "-") or "-"
        lines.append(f"| `{result}` | {exp['name']} | - | - |")

    return _write_file(cfg.context_dir / "PAPER_MAPPING.md", "\n".join(lines))


def _generate_experiment_mapping(cfg: MemoryConfig, store: SQLiteStore,
                                 repo_id: int) -> str:
    experiments = store.get_experiments(repo_id)

    lines = [
        f"# Experiment Mapping: {cfg.repo_name}",
        "",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "| Experiment | Script | Config | Algorithms | Environment | Seeds | Status |",
        "|---|---|---|---|---|---|---|",
    ]

    for exp in experiments:
        algos = exp.get("algorithms", "[]")
        if isinstance(algos, str):
            try:
                algos = json.loads(algos)
            except (json.JSONDecodeError, TypeError):
                algos = []
        algos_str = ", ".join(algos[:3]) if algos else "-"

        seeds = exp.get("seeds", "[]")
        if isinstance(seeds, str):
            try:
                seeds = json.loads(seeds)
            except (json.JSONDecodeError, TypeError):
                seeds = []
        seeds_str = str(len(seeds)) + " seeds" if seeds else "-"

        lines.append(
            f"| {exp['name']} | `{exp.get('script_path', '-') or '-'}` | "
            f"`{exp.get('config_path', '-') or '-'}` | "
            f"{algos_str} | {exp.get('environment', '-') or '-'} | "
            f"{seeds_str} | {exp.get('status', 'unknown')} |"
        )

    return _write_file(cfg.context_dir / "EXPERIMENT_MAPPING.md", "\n".join(lines))


def _generate_figure_mapping(cfg: MemoryConfig, store: SQLiteStore,
                             repo_id: int) -> str:
    figures = store.get_figures(repo_id)

    lines = [
        f"# Figure Mapping: {cfg.repo_name}",
        "",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "| Figure | Generator | Source Data | Paper Ref | Status |",
        "|---|---|---|---|---|",
    ]

    for fig in figures:
        src_data = fig.get("source_data", "[]")
        if isinstance(src_data, str):
            try:
                src_data = json.loads(src_data)
            except (json.JSONDecodeError, TypeError):
                src_data = []
        src_str = ", ".join(f"`{s}`" for s in src_data[:3]) if src_data else "-"

        lines.append(
            f"| {fig['figure_name']} | `{fig.get('generator_script', '-') or '-'}` | "
            f"{src_str} | {fig.get('paper_reference', '-') or '-'} | "
            f"{fig.get('status', 'unknown')} |"
        )

    return _write_file(cfg.context_dir / "FIGURE_MAPPING.md", "\n".join(lines))


def _generate_changelog_context(cfg: MemoryConfig, store: SQLiteStore,
                                repo_id: int) -> str:
    lines = [
        f"# Changelog Context: {cfg.repo_name}",
        "",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "This file tracks significant changes between scans.",
        "",
        "_Run `agentmemory diff` to see the latest changes._",
        "",
    ]
    return _write_file(cfg.context_dir / "CHANGELOG_CONTEXT.md", "\n".join(lines))


def _generate_next_agent_prompt(cfg: MemoryConfig) -> str:
    """Generate the ready-to-copy prompt for the next AI agent session."""
    prompt = f"""You are continuing work on the repository **{cfg.repo_name}**.

Do NOT reread the entire codebase first. The previous agent already indexed the project.

Start by reading these context files in order:

1. `.agent_memory_hieutc/context/AGENT_BRIEF.md` — Project overview, key scripts, and structure.
2. `.agent_memory_hieutc/context/PROJECT_CONTEXT.md` — Detailed file inventory with importance scores.
3. `.agent_memory_hieutc/context/EXPERIMENT_MAPPING.md` — Experiment-to-script-to-config mapping.
4. `.agent_memory_hieutc/context/PAPER_MAPPING.md` — Paper section, claim, and result mapping.
5. `.agent_memory_hieutc/context/FIGURE_MAPPING.md` — Figure generators, sources, and status.

Then ONLY inspect source files that are directly relevant to the current task.

If you need to see recent changes, ask the user to run:
```bash
agentmemory diff
```

If you need to search for a specific concept, ask the user to run:
```bash
agentmemory ask "your question here"
```
"""
    return _write_file(cfg.context_dir / "NEXT_AGENT_PROMPT.md", prompt)
