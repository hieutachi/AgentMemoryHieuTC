"""CLI interface for AgentMemoryHieuTC."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from .config import MemoryConfig, ensure_memory_dirs
from .git_utils import get_repo_info, get_changed_files, is_git_repo
from .graph.graph_builder import (
    build_codebase_graph,
    build_research_workflow_graph,
    compute_graph_metrics,
)
from .graph.json_exporter import export_graph_json
from .graph.mermaid_exporter import export_mermaid, export_research_workflow_mermaid
from .memory.context_pack import generate_context_pack
from .memory.sqlite_store import SQLiteStore
from .research.experiment_mapper import discover_experiments
from .research.figure_mapper import discover_figures
from .research.paper_mapper import discover_paper_files
from .reports.diff_report import generate_diff_report
from .reports.health_report import generate_health_report
from .reports.project_report import generate_scan_report
from .scanner import scan_repository
from .utils.text import extract_keywords

app = typer.Typer(
    name="agentmemory",
    help="Local research memory agent for AI/ML/RL/MARL codebases.",
    add_completion=False,
)
console = Console()


@app.command()
def init(
    path: str = typer.Argument(".", help="Repository root path."),
    name: str = typer.Option("", "--name", "-n", help="Project name override."),
):
    """Initialize AgentMemoryHieuTC in a Git repository."""
    repo_root = Path(path).resolve()
    if not repo_root.is_dir():
        console.print(f"[red]Error:[/red] {repo_root} is not a directory.")
        raise typer.Exit(1)

    cfg = MemoryConfig.resolve(repo_root)
    if name:
        cfg.data["repo_name"] = name
    else:
        cfg.data["repo_name"] = repo_root.name

    ensure_memory_dirs(cfg)
    cfg.save()

    # Initialize SQLite database
    store = SQLiteStore(cfg.db_path)
    store.open()
    store.initialize_schema()
    store.close()

    console.print(Panel(
        f"[green]Initialized AgentMemoryHieuTC[/green]\n\n"
        f"  Repository: {cfg.repo_name}\n"
        f"  Memory dir: {cfg.memory_dir}\n"
        f"  Database:   {cfg.db_path}\n\n"
        f"  Next step: [bold]agentmemory scan[/bold]",
        title="agentmemory init",
    ))


@app.command()
def scan(
    path: str = typer.Argument(".", help="Repository root path."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show progress."),
):
    """Perform a full static scan of the repository."""
    cfg = MemoryConfig.resolve(Path(path))
    if not cfg.memory_dir.exists():
        console.print("[red]Error:[/red] Not initialized. Run `agentmemory init` first.")
        raise typer.Exit(1)

    def progress(msg: str):
        if verbose:
            console.print(f"  {msg}")

    with SQLiteStore(cfg.db_path) as store:
        store.initialize_schema()

        # Upsert repository
        git = get_repo_info(cfg.repo_root) if is_git_repo(cfg.repo_root) else None
        repo_id = store.upsert_repository(
            name=cfg.repo_name,
            path=str(cfg.repo_root),
            remote=git.remote if git else "",
            branch=git.branch if git else "",
            commit=git.latest_commit if git else "",
        )

        # Run scanner
        console.print("[bold]Scanning repository...[/bold]")
        stats = scan_repository(cfg, store, progress_callback=progress)

        # Run research mappers
        console.print("[bold]Discovering experiments...[/bold]")
        experiments = discover_experiments(store, repo_id, cfg.repo_root)
        console.print(f"  Found {len(experiments)} experiments.")

        console.print("[bold]Discovering paper files...[/bold]")
        papers = discover_paper_files(store, repo_id, cfg.repo_root)
        console.print(f"  Found {len(papers)} paper files.")

        console.print("[bold]Discovering figures...[/bold]")
        figures = discover_figures(store, repo_id, cfg.repo_root)
        console.print(f"  Found {len(figures)} figures.")

        # Generate graphs
        console.print("[bold]Building graphs...[/bold]")
        _generate_graphs(cfg, store, repo_id)

        # Generate context pack
        console.print("[bold]Generating context pack...[/bold]")
        context_files = generate_context_pack(cfg, store, repo_id)

        # Generate scan report
        report_path = generate_scan_report(cfg.reports_dir, cfg.repo_name, stats, context_files)

        # Update config with scan metadata
        if git:
            cfg.data["last_scan_commit"] = git.latest_commit
        cfg.data["last_scan_time"] = datetime.utcnow().isoformat()
        cfg.save()

    console.print(Panel(
        f"[green]Scan complete![/green]\n\n"
        f"  Files indexed: {stats['total']}\n"
        f"  Files parsed:  {stats['parsed']}\n"
        f"  Experiments:   {len(experiments)}\n"
        f"  Paper files:   {len(papers)}\n"
        f"  Figures:       {len(figures)}\n"
        f"  Scan report:   {report_path}\n\n"
        f"  Next steps:\n"
        f"    [bold]agentmemory context[/bold]  — Export context files\n"
        f"    [bold]agentmemory graph[/bold]    — View codebase graph\n"
        f"    [bold]agentmemory health[/bold]   — Check repository health",
        title="agentmemory scan",
    ))


@app.command()
def update(
    path: str = typer.Argument(".", help="Repository root path."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show progress."),
):
    """Update index incrementally using Git diff."""
    cfg = MemoryConfig.resolve(Path(path))
    if not cfg.memory_dir.exists():
        console.print("[red]Error:[/red] Not initialized. Run `agentmemory init` first.")
        raise typer.Exit(1)

    last_commit = cfg.data.get("last_scan_commit", "")
    changed = get_changed_files(cfg.repo_root, last_commit if last_commit else None)

    if not changed:
        console.print("[yellow]No changes detected since last scan.[/yellow]")
        return

    console.print(f"[bold]Updating {len(changed)} changed files...[/bold]")

    with SQLiteStore(cfg.db_path) as store:
        store.initialize_schema()
        repo_id = store.get_repo_id(str(cfg.repo_root))
        if repo_id is None:
            console.print("[red]Repository not indexed. Run `agentmemory scan` first.")
            raise typer.Exit(1)

        # Re-scan only changed files
        from .scanner import classify_file, compute_importance
        from .utils.hashing import file_hash
        from .utils.paths import safe_relative

        for rel_path in changed:
            abs_path = cfg.repo_root / rel_path
            if not abs_path.exists():
                store.delete_file(repo_id, rel_path)
                if verbose:
                    console.print(f"  [red]Deleted:[/red] {rel_path}")
                continue

            ftype = classify_file(rel_path)
            try:
                size = abs_path.stat().st_size
            except OSError:
                continue
            h = file_hash(abs_path)
            importance = compute_importance(ftype, rel_path)
            store.upsert_file(
                repo_id=repo_id, path=rel_path, file_type=ftype,
                hash_val=h, size=size, importance=importance,
            )
            if verbose:
                console.print(f"  [green]Updated:[/green] {rel_path}")

        # Regenerate context
        generate_context_pack(cfg, store, repo_id)
        _generate_graphs(cfg, store, repo_id)

        # Generate diff report
        diff_path = generate_diff_report(cfg, store, repo_id)

        # Update config
        git = get_repo_info(cfg.repo_root) if is_git_repo(cfg.repo_root) else None
        if git:
            cfg.data["last_scan_commit"] = git.latest_commit
        cfg.data["last_scan_time"] = datetime.utcnow().isoformat()
        cfg.save()

    console.print(f"[green]Update complete![/green] {len(changed)} files processed.")
    console.print(f"  Diff report: {diff_path}")


@app.command()
def graph(
    path: str = typer.Argument(".", help="Repository root path."),
):
    """Generate or regenerate codebase and research workflow graphs."""
    cfg = MemoryConfig.resolve(Path(path))
    if not cfg.memory_dir.exists():
        console.print("[red]Error:[/red] Not initialized.")
        raise typer.Exit(1)

    with SQLiteStore(cfg.db_path) as store:
        store.initialize_schema()
        repo_id = store.get_repo_id(str(cfg.repo_root))
        if repo_id is None:
            console.print("[red]Repository not indexed.")
            raise typer.Exit(1)

        _generate_graphs(cfg, store, repo_id)

    console.print("[green]Graphs generated![/green]")
    console.print(f"  Codebase graph:        {cfg.graph_dir / 'codebase_graph.mmd'}")
    console.print(f"  Research workflow:     {cfg.graph_dir / 'research_workflow_graph.mmd'}")


@app.command("context")
def context_cmd(
    path: str = typer.Argument(".", help="Repository root path."),
):
    """Export compact context files for AI agent handoff."""
    cfg = MemoryConfig.resolve(Path(path))
    if not cfg.memory_dir.exists():
        console.print("[red]Error:[/red] Not initialized.")
        raise typer.Exit(1)

    with SQLiteStore(cfg.db_path) as store:
        store.initialize_schema()
        repo_id = store.get_repo_id(str(cfg.repo_root))
        if repo_id is None:
            console.print("[red]Repository not indexed.")
            raise typer.Exit(1)

        context_files = generate_context_pack(cfg, store, repo_id)

    console.print("[green]Context files generated:[/green]")
    for cf in context_files:
        console.print(f"  {cf}")


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question about the repository."),
    path: str = typer.Argument(".", help="Repository root path."),
):
    """Answer questions using indexed metadata (no cloud LLM needed)."""
    cfg = MemoryConfig.resolve(Path(path))
    if not cfg.memory_dir.exists():
        console.print("[red]Error:[/red] Not initialized.")
        raise typer.Exit(1)

    with SQLiteStore(cfg.db_path) as store:
        store.initialize_schema()
        repo_id = store.get_repo_id(str(cfg.repo_root))
        if repo_id is None:
            console.print("[red]Repository not indexed.")
            raise typer.Exit(1)

        answer = _answer_question(question, store, repo_id, cfg)

    console.print(Panel(answer, title="Answer"))


@app.command("paper-map")
def paper_map(
    path: str = typer.Argument(".", help="Repository root path."),
):
    """Generate paper-to-code mapping."""
    cfg = MemoryConfig.resolve(Path(path))
    if not cfg.memory_dir.exists():
        console.print("[red]Error:[/red] Not initialized.")
        raise typer.Exit(1)

    with SQLiteStore(cfg.db_path) as store:
        store.initialize_schema()
        repo_id = store.get_repo_id(str(cfg.repo_root))
        if repo_id is None:
            console.print("[red]Repository not indexed.")
            raise typer.Exit(1)

        papers = discover_paper_files(store, repo_id, cfg.repo_root)
        from .memory.context_pack import _generate_paper_mapping
        filepath = _generate_paper_mapping(cfg, store, repo_id)

    console.print(f"[green]Paper mapping generated:[/green] {filepath}")
    for p in papers:
        console.print(f"  Found: {p.get('path', '?')} — {len(p.get('sections', []))} sections")


@app.command()
def health(
    path: str = typer.Argument(".", help="Repository root path."),
):
    """Check repository health and generate report."""
    cfg = MemoryConfig.resolve(Path(path))
    if not cfg.memory_dir.exists():
        console.print("[red]Error:[/red] Not initialized.")
        raise typer.Exit(1)

    with SQLiteStore(cfg.db_path) as store:
        store.initialize_schema()
        repo_id = store.get_repo_id(str(cfg.repo_root))
        if repo_id is None:
            console.print("[red]Repository not indexed.")
            raise typer.Exit(1)

        report_path = generate_health_report(cfg, store, repo_id)

    console.print(f"[green]Health report generated:[/green] {report_path}")


@app.command()
def diff(
    path: str = typer.Argument(".", help="Repository root path."),
):
    """Show what changed since the previous scan."""
    cfg = MemoryConfig.resolve(Path(path))
    if not cfg.memory_dir.exists():
        console.print("[red]Error:[/red] Not initialized.")
        raise typer.Exit(1)

    with SQLiteStore(cfg.db_path) as store:
        store.initialize_schema()
        repo_id = store.get_repo_id(str(cfg.repo_root))
        if repo_id is None:
            console.print("[red]Repository not indexed.")
            raise typer.Exit(1)

        report_path = generate_diff_report(cfg, store, repo_id)

    console.print(f"[green]Diff report generated:[/green] {report_path}")


# ---- Internal helpers ----

def _generate_graphs(cfg: MemoryConfig, store: SQLiteStore, repo_id: int) -> None:
    """Generate and export all graphs."""
    files = store.get_all_files(repo_id)
    experiments = store.get_experiments(repo_id)
    paper_sections = store.get_paper_sections(repo_id)
    figures = store.get_figures(repo_id)
    relations = store.get_relations(repo_id)

    # Build codebase graph
    code_graph = build_codebase_graph(
        files=files,
        symbols=[],
        relations=relations,
        max_nodes=cfg.graph_max_nodes,
    )

    # Export codebase graph
    export_graph_json(code_graph, cfg.graph_dir / "codebase_graph.json")
    mermaid_code = export_mermaid(code_graph, title="Codebase Graph")
    (cfg.graph_dir / "codebase_graph.mmd").write_text(mermaid_code, encoding="utf-8")

    # Snapshot with timestamp
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    export_graph_json(code_graph, cfg.graph_dir / f"graph_snapshot_{ts}.json")
    (cfg.graph_dir / f"graph_snapshot_{ts}.mmd").write_text(mermaid_code, encoding="utf-8")

    # Build research workflow graph
    research_graph = build_research_workflow_graph(
        experiments=experiments,
        paper_sections=paper_sections,
        figures=figures,
        files=files,
    )
    mermaid_research = export_research_workflow_mermaid(research_graph)
    (cfg.graph_dir / "research_workflow_graph.mmd").write_text(mermaid_research, encoding="utf-8")


def _answer_question(question: str, store: SQLiteStore,
                     repo_id: int, cfg: MemoryConfig) -> str:
    """Answer a question using local indexed data."""
    keywords = extract_keywords(question)
    if not keywords:
        return "Could not extract keywords from your question. Try rephrasing."

    question_lower = question.lower()
    results: list[str] = []

    # Detect question type
    is_where = any(w in question_lower for w in ["where", "which file", "location"])
    is_what = any(w in question_lower for w in ["what", "list", "show"])
    is_how = any(w in question_lower for w in ["how", "should"])
    is_first = "first" in question_lower or "read first" in question_lower

    # "What should I read first?" → return agent brief recommendation
    if is_first:
        top_files = store.get_all_files(repo_id)
        top_files.sort(key=lambda f: f.get("importance_score", 0), reverse=True)
        results.append("**Start by reading these files (in order):**\n")
        for i, f in enumerate(top_files[:10], 1):
            summary = f.get("summary", "")
            summary_str = f" — {summary}" if summary else ""
            results.append(f"{i}. `{f['path']}` (importance: {f['importance_score']:.1f}){summary_str}")
        return "\n".join(results)

    # Search symbols
    symbol_results = []
    for kw in keywords:
        symbol_results.extend(store.search_symbols(kw))
    seen_symbols = set()
    for s in symbol_results:
        key = (s["name"], s.get("file_path", ""))
        if key not in seen_symbols:
            seen_symbols.add(key)
            sym_type = s.get("symbol_type", "symbol")
            doc = s.get("docstring", "")[:100]
            doc_str = f" — {doc}" if doc else ""
            results.append(f"**{sym_type}:** `{s['name']}` in `{s.get('file_path', '?')}` (line {s.get('start_line', '?')}){doc_str}")

    # Search files
    file_results = []
    for kw in keywords:
        file_results.extend(store.search_files(kw))
    seen_files = set()
    for f in file_results:
        if f["path"] not in seen_files:
            seen_files.add(f["path"])
            summary = (f.get("summary", "") or "")[:100]
            results.append(f"**File:** `{f['path']}` ({f.get('file_type', '?')}, importance: {f.get('importance_score', 0):.1f}) — {summary}")

    # Search experiments
    exp_results = []
    for kw in keywords:
        exp_results.extend(store.search_experiments(kw))
    seen_exps = set()
    for e in exp_results:
        if e["name"] not in seen_exps:
            seen_exps.add(e["name"])
            algos = e.get("algorithms", "[]")
            if isinstance(algos, str):
                try:
                    algos = json.loads(algos)
                except Exception:
                    algos = []
            algo_str = ", ".join(algos[:3]) if algos else ""
            results.append(f"**Experiment:** {e['name']} — Script: `{e.get('script_path', '?')}` — {algo_str}")

    # Search memory items
    mem_results = []
    for kw in keywords:
        mem_results.extend(store.search_memory(kw))
    for m in mem_results:
        results.append(f"**Memory:** {m['key']} = {m['value']} (source: {m.get('source_path', '?')})")

    if not results:
        files = store.get_all_files(repo_id)
        suggestions = [f["path"] for f in sorted(files, key=lambda f: f["importance_score"], reverse=True)[:5]]
        suggestion_str = "\n".join(f"  - `{s}`" for s in suggestions)
        return (
            f"Not enough indexed information to answer confidently.\n\n"
            f"Suggested files to inspect:\n{suggestion_str}"
        )

    # Deduplicate and limit
    unique_results = list(dict.fromkeys(results))[:20]
    return "\n\n".join(unique_results)


def main():
    app()
