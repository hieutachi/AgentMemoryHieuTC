"""Generate context pack files for AI agent handoff."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import MemoryConfig
from ..memory.sqlite_store import SQLiteStore
from ..utils.text import estimate_tokens, truncate

SKIP_FILE_TYPES = frozenset({
    "test_file", "log_file", "checkpoint", "unknown", "documentation",
})


def generate_context_pack(cfg: MemoryConfig, store: SQLiteStore,
                          repo_id: int) -> list[str]:
    """Generate context pack files. Returns list of generated file paths."""
    if cfg.context_mode == "compact":
        return _generate_compact_pack(cfg, store, repo_id)
    return _generate_full_pack(cfg, store, repo_id)


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _write_file(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def _short_summary(text: str, max_len: int) -> str:
    return truncate((text or "").replace("\n", " ").strip(), max_len)


def _filtered_files(files: list[dict], cfg: MemoryConfig) -> list[dict]:
    out = [
        f for f in files
        if f.get("file_type") not in SKIP_FILE_TYPES
        and f.get("importance_score", 0) >= cfg.context_importance_min
    ]
    out.sort(key=lambda f: f.get("importance_score", 0), reverse=True)
    return out[: cfg.context_max_files]


def _parse_json_field(val: Any, default: list | None = None) -> list:
    if default is None:
        default = []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else default
        except (json.JSONDecodeError, TypeError):
            return default
    return default


# ---- Compact mode (default): minimal tokens ----

def _generate_compact_pack(cfg: MemoryConfig, store: SQLiteStore,
                           repo_id: int) -> list[str]:
    generated: list[str] = []
    compact = _build_compact_context(cfg, store, repo_id)
    generated.append(_write_file(cfg.context_dir / "CONTEXT_COMPACT.md", compact))
    generated.append(_write_file(
        cfg.context_dir / "NEXT_AGENT_PROMPT.md",
        _compact_next_prompt(cfg, estimate_tokens(compact)),
    ))
    # Tiny index for humans
    generated.append(_write_file(
        cfg.context_dir / "AGENT_BRIEF.md",
        _minimal_brief(cfg, store, repo_id, estimate_tokens(compact)),
    ))
    return generated


def _build_compact_context(cfg: MemoryConfig, store: SQLiteStore,
                           repo_id: int) -> str:
    files = store.get_all_files(repo_id)
    experiments = store.get_experiments(repo_id)[: cfg.context_max_experiments]
    figures = store.get_figures(repo_id)[: cfg.context_max_figures]
    sections = store.get_paper_sections(repo_id)
    stats = store.get_stats(repo_id)
    top = _filtered_files(files, cfg)
    smax = cfg.context_summary_max_chars

    paper_title = store.get_memory(repo_id, "paper_title") or ""
    lines = [
        f"# {cfg.repo_name}",
        f"scan:{_now_str()} | files:{stats.get('files', 0)} "
        f"sym:{stats.get('symbols', 0)} exp:{stats.get('experiments', 0)}",
    ]
    if paper_title:
        lines.append(f"paper:{paper_title}")

    lines.extend(["", "## Read first"])
    for i, f in enumerate(top, 1):
        summ = _short_summary(f.get("summary", ""), smax)
        tag = f.get("file_type", "?").replace("_", "")
        line = f"{i}. `{f['path']}` [{tag}]"
        if summ:
            line += f" — {summ}"
        lines.append(line)

    if experiments:
        lines.extend(["", "## Experiments"])
        for exp in experiments:
            algos = ",".join(_parse_json_field(exp.get("algorithms"))[:3]) or "-"
            script = exp.get("script_path") or "-"
            env = exp.get("environment") or "-"
            lines.append(f"- {exp['name']}: `{script}` | {algos} | {env}")

    if sections:
        lines.extend(["", "## Paper"])
        for s in sections[:8]:
            lines.append(f"- {s.get('section_type', '?')}: {s['section_title']}")

    if figures:
        lines.extend(["", "## Figures"])
        for fig in figures:
            gen = fig.get("generator_script") or "-"
            lines.append(f"- {fig['figure_name']}: `{gen}`")

    lines.extend([
        "",
        "## Skip",
        ".agent_memory_hieutc/, checkpoints, logs, tests/ (unless task needs them)",
        "",
        "## On demand",
        "`agentmemory ask \"...\"` | `agentmemory diff`",
    ])
    return "\n".join(lines)


def _compact_next_prompt(cfg: MemoryConfig, token_est: int) -> str:
    return f"""Continue **{cfg.repo_name}**. Do NOT reread the whole repo.

Read ONLY: `.agent_memory_hieutc/context/CONTEXT_COMPACT.md` (~{token_est} tokens).

Then open source files relevant to the current task only.
Use `agentmemory ask` / `agentmemory diff` if you need more context.
"""


def _minimal_brief(cfg: MemoryConfig, store: SQLiteStore,
                   repo_id: int, token_est: int) -> str:
    stats = store.get_stats(repo_id)
    return (
        f"# {cfg.repo_name}\n\n"
        f"Primary context: `CONTEXT_COMPACT.md` (~{token_est} tokens)\n"
        f"Indexed: {stats.get('files', 0)} files, "
        f"{stats.get('experiments', 0)} experiments\n"
        f"Mode: compact\n"
    )


# ---- Full mode: detailed markdown set ----

def _generate_full_pack(cfg: MemoryConfig, store: SQLiteStore,
                        repo_id: int) -> list[str]:
    files = [
        _generate_agent_brief(cfg, store, repo_id),
        _generate_project_context(cfg, store, repo_id),
        _generate_paper_mapping(cfg, store, repo_id),
        _generate_experiment_mapping(cfg, store, repo_id),
        _generate_figure_mapping(cfg, store, repo_id),
        _generate_changelog_context(cfg, store, repo_id),
        _generate_next_agent_prompt(cfg),
    ]
    return [f for f in files if f]


def _generate_agent_brief(cfg: MemoryConfig, store: SQLiteStore,
                          repo_id: int) -> str:
    files = store.get_all_files(repo_id)
    experiments = store.get_experiments(repo_id)[: cfg.context_max_experiments]
    figures = store.get_figures(repo_id)[: cfg.context_max_figures]
    top_files = _filtered_files(files, cfg)
    smax = cfg.context_summary_max_chars

    lines = [
        f"# Agent Brief: {cfg.repo_name}",
        f"Generated: {_now_str()}",
        "",
        "## Read first",
    ]
    for i, f in enumerate(top_files, 1):
        summ = _short_summary(f.get("summary", ""), smax)
        lines.append(f"{i}. `{f['path']}`" + (f" — {summ}" if summ else ""))

    if experiments:
        lines.extend(["", "## Experiments"])
        for exp in experiments:
            lines.append(
                f"- {exp['name']}: `{exp.get('script_path', '-')}` "
                f"({exp.get('status', '?')})"
            )

    if figures:
        lines.extend(["", "## Figures"])
        for fig in figures:
            lines.append(f"- {fig['figure_name']}: `{fig.get('generator_script', '-')}`")

    lines.extend([
        "",
        "## Skip",
        "checkpoints, logs, `.agent_memory_hieutc/`, low-importance files",
    ])
    return _write_file(cfg.context_dir / "AGENT_BRIEF.md", "\n".join(lines))


def _generate_project_context(cfg: MemoryConfig, store: SQLiteStore,
                              repo_id: int) -> str:
    files = _filtered_files(store.get_all_files(repo_id), cfg)
    smax = cfg.context_summary_max_chars
    lines = [f"# Project Context: {cfg.repo_name}", f"Generated: {_now_str()}", ""]
    for f in files:
        summ = _short_summary(f.get("summary", ""), smax)
        lines.append(
            f"- `{f['path']}` ({f['importance_score']:.1f}) "
            f"[{f.get('file_type', '?')}]" + (f" — {summ}" if summ else "")
        )
    return _write_file(cfg.context_dir / "PROJECT_CONTEXT.md", "\n".join(lines))


def _generate_paper_mapping(cfg: MemoryConfig, store: SQLiteStore,
                            repo_id: int) -> str:
    sections = store.get_paper_sections(repo_id)
    if not sections:
        return ""
    lines = [f"# Paper Mapping: {cfg.repo_name}", ""]
    for s in sections[:15]:
        lines.append(f"- [{s.get('section_type', '-')}] {s['section_title']}")
    return _write_file(cfg.context_dir / "PAPER_MAPPING.md", "\n".join(lines))


def _generate_experiment_mapping(cfg: MemoryConfig, store: SQLiteStore,
                                 repo_id: int) -> str:
    experiments = store.get_experiments(repo_id)[: cfg.context_max_experiments]
    if not experiments:
        return ""
    lines = [f"# Experiments: {cfg.repo_name}", ""]
    for exp in experiments:
        algos = ",".join(_parse_json_field(exp.get("algorithms"))[:3]) or "-"
        lines.append(
            f"- **{exp['name']}** script:`{exp.get('script_path', '-')}` "
            f"cfg:`{exp.get('config_path', '-')}` algo:{algos}"
        )
    return _write_file(cfg.context_dir / "EXPERIMENT_MAPPING.md", "\n".join(lines))


def _generate_figure_mapping(cfg: MemoryConfig, store: SQLiteStore,
                             repo_id: int) -> str:
    figures = store.get_figures(repo_id)[: cfg.context_max_figures]
    if not figures:
        return ""
    lines = [f"# Figures: {cfg.repo_name}", ""]
    for fig in figures:
        lines.append(
            f"- {fig['figure_name']}: gen `{fig.get('generator_script', '-')}`"
        )
    return _write_file(cfg.context_dir / "FIGURE_MAPPING.md", "\n".join(lines))


def _generate_changelog_context(cfg: MemoryConfig, store: SQLiteStore,
                                repo_id: int) -> str:
    return _write_file(
        cfg.context_dir / "CHANGELOG_CONTEXT.md",
        f"# Changelog\n\nRun `agentmemory diff` for updates.\n",
    )


def _generate_next_agent_prompt(cfg: MemoryConfig) -> str:
    if cfg.context_mode == "compact":
        return _write_file(
            cfg.context_dir / "NEXT_AGENT_PROMPT.md",
            _compact_next_prompt(cfg, 0),
        )
    prompt = f"""Continue **{cfg.repo_name}**. Do NOT reread the entire codebase.

Read in order:
1. `.agent_memory_hieutc/context/AGENT_BRIEF.md`
2. `.agent_memory_hieutc/context/PROJECT_CONTEXT.md`
3. `.agent_memory_hieutc/context/EXPERIMENT_MAPPING.md` (if exists)

Open only task-relevant source files. Use `agentmemory ask` / `agentmemory diff` on demand.
"""
    return _write_file(cfg.context_dir / "NEXT_AGENT_PROMPT.md", prompt)
