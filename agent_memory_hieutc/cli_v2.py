"""v2.0 CLI commands: lock, phase, note, verify, matrix, hooks, embed."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import MemoryConfig
from .embeddings.semantic_search import index_repository, semantic_search
from .hooks.installer import install_hooks, uninstall_hooks
from .integrations.mlflow_mapper import discover_mlflow_runs
from .integrations.wandb_mapper import discover_wandb_runs
from .memory.context_pack import generate_context_pack
from .memory.lock_registry import lock_file, lock_metric, parse_metric_kv, verify_locks
from .memory.sqlite_store import SQLiteStore
from .research.claim_verifier import generate_verify_report, verify_claims
from .research.decision_log import add_decision, generate_decision_log
from .research.experiment_matrix import export_matrix_markdown
from .research.phase_tracker import (
    complete_phase_task,
    generate_phase_status,
    mark_phase_done,
    set_active_phase,
)

console = Console()

lock_app = typer.Typer(help="Lock results, configs, and metrics.")
phase_app = typer.Typer(help="Research phase tracking.")
hooks_app = typer.Typer(help="Git hooks for auto-update.")
embed_app = typer.Typer(help="Semantic search (optional embeddings).")


def _repo_store(path: str) -> tuple[MemoryConfig, SQLiteStore, int]:
    cfg = MemoryConfig.resolve(Path(path))
    if not cfg.memory_dir.exists():
        console.print("[red]Not initialized. Run `agentmemory init` first.[/red]")
        raise typer.Exit(1)
    store = SQLiteStore(cfg.db_path)
    store.open()
    store.initialize_schema()
    repo_id = store.get_repo_id(str(cfg.repo_root))
    if repo_id is None:
        store.close()
        console.print("[red]Repository not indexed. Run `agentmemory scan` first.[/red]")
        raise typer.Exit(1)
    return cfg, store, repo_id


@lock_app.command("result")
def lock_result(
    target: str = typer.Argument(..., help="Result file path."),
    label: str = typer.Option("", "--label", "-l", help="Lock label."),
    path: str = typer.Option(".", help="Repository root."),
):
    """Lock a result file (hash + metrics snapshot)."""
    cfg, store, repo_id = _repo_store(path)
    try:
        info = lock_file(store, repo_id, cfg.repo_root, "result", target, label)
        generate_context_pack(cfg, store, repo_id)
        console.print(f"[green]LOCKED result:[/green] {info['label']} ({info['hash']}...)")
    finally:
        store.close()


@lock_app.command("config")
def lock_config(
    target: str = typer.Argument(..., help="Config file path."),
    label: str = typer.Option("", "--label", "-l"),
    path: str = typer.Option(".", help="Repository root."),
):
    """Lock a config file."""
    cfg, store, repo_id = _repo_store(path)
    try:
        info = lock_file(store, repo_id, cfg.repo_root, "config", target, label)
        generate_context_pack(cfg, store, repo_id)
        console.print(f"[green]LOCKED config:[/green] {info['label']}")
    finally:
        store.close()


@lock_app.command("metric")
def lock_metric_cmd(
    label: str = typer.Argument(..., help="Metric label e.g. table2_mean_reward."),
    values: str = typer.Argument(..., help="key=val pairs: reward=0.84,seed=3"),
    path: str = typer.Option(".", help="Repository root."),
):
    """Lock explicit metric values for paper tables."""
    cfg, store, repo_id = _repo_store(path)
    try:
        metrics = parse_metric_kv(values)
        info = lock_metric(store, repo_id, cfg.repo_root, label, metrics)
        generate_context_pack(cfg, store, repo_id)
        console.print(f"[green]LOCKED metric:[/green] {info['label']} {metrics}")
    finally:
        store.close()


@lock_app.command("list")
def lock_list(path: str = typer.Option(".", help="Repository root.")):
    """List all locks."""
    cfg, store, repo_id = _repo_store(path)
    try:
        locks = store.get_locks(repo_id)
        if not locks:
            console.print("No locks.")
            return
        t = Table(title="Locks")
        t.add_column("Label")
        t.add_column("Type")
        t.add_column("Path")
        t.add_column("Commit")
        for lk in locks:
            t.add_row(
                lk["label"], lk["lock_type"],
                lk.get("target_path", ""), (lk.get("git_commit") or "")[:8],
            )
        console.print(t)
    finally:
        store.close()


@lock_app.command("verify")
def lock_verify(path: str = typer.Option(".", help="Repository root.")):
    """Verify locked files unchanged."""
    cfg, store, repo_id = _repo_store(path)
    try:
        report = verify_locks(store, repo_id, cfg.repo_root)
        ok = all(r["status"] == "ok" for r in report)
        for r in report:
            color = "green" if r["status"] == "ok" else "red"
            console.print(f"[{color}]{r['label']}[/{color}] ({r['type']}) — {r['status']}")
            for issue in r.get("issues", []):
                console.print(f"  ! {issue}")
        if not ok:
            raise typer.Exit(1)
    finally:
        store.close()


@lock_app.command("unlock")
def lock_unlock(
    label: str = typer.Argument(..., help="Lock label to remove."),
    path: str = typer.Option(".", help="Repository root."),
):
    """Remove a lock."""
    cfg, store, repo_id = _repo_store(path)
    try:
        if store.delete_lock(repo_id, label):
            generate_context_pack(cfg, store, repo_id)
            console.print(f"[yellow]Unlocked:[/yellow] {label}")
        else:
            console.print(f"[red]Lock not found:[/red] {label}")
            raise typer.Exit(1)
    finally:
        store.close()


@phase_app.command("set")
def phase_set(
    name: str = typer.Argument(..., help="Phase: baseline, ablation, revision, ..."),
    path: str = typer.Option(".", help="Repository root."),
):
    """Set active research phase."""
    cfg, store, repo_id = _repo_store(path)
    try:
        set_active_phase(store, repo_id, name)
        generate_phase_status(cfg.context_dir, store, repo_id, cfg.repo_name)
        generate_context_pack(cfg, store, repo_id)
        console.print(f"[green]Active phase:[/green] {name}")
    finally:
        store.close()


@phase_app.command("done")
def phase_done(
    name: str = typer.Argument(..., help="Phase name to mark complete."),
    path: str = typer.Option(".", help="Repository root."),
):
    """Mark a phase as done."""
    cfg, store, repo_id = _repo_store(path)
    try:
        mark_phase_done(store, repo_id, name)
        generate_phase_status(cfg.context_dir, store, repo_id, cfg.repo_name)
        generate_context_pack(cfg, store, repo_id)
        console.print(f"[green]Phase done:[/green] {name}")
    finally:
        store.close()


@phase_app.command("task")
def phase_task(
    task: str = typer.Argument(..., help="Completed task description."),
    phase: str = typer.Option("", "--phase", "-p", help="Phase name (default: active)."),
    path: str = typer.Option(".", help="Repository root."),
):
    """Record a completed task in a phase."""
    cfg, store, repo_id = _repo_store(path)
    try:
        pname = phase or store.get_memory(repo_id, "active_phase") or "baseline"
        complete_phase_task(store, repo_id, pname, task)
        generate_phase_status(cfg.context_dir, store, repo_id, cfg.repo_name)
        console.print(f"[green]Task recorded[/green] in `{pname}`: {task}")
    finally:
        store.close()


@phase_app.command("status")
def phase_status(path: str = typer.Option(".", help="Repository root.")):
    """Show phase status."""
    cfg, store, repo_id = _repo_store(path)
    try:
        p = generate_phase_status(cfg.context_dir, store, repo_id, cfg.repo_name)
        console.print(f"[green]Phase status:[/green] {p}")
    finally:
        store.close()


def register_note_command(app: typer.Typer) -> None:
    @app.command("note")
    def note_cmd(
        message: str = typer.Argument(..., help="Decision or observation to remember."),
        outcome: str = typer.Option("", "--outcome", "-o", help="Result: success/fail/pending."),
        phase: str = typer.Option("", "--phase", "-p"),
        path: str = typer.Option(".", help="Repository root."),
    ):
        """Log a research decision for future agents."""
        cfg, store, repo_id = _repo_store(path)
        try:
            add_decision(store, repo_id, message, phase=phase, outcome=outcome)
            generate_decision_log(cfg.context_dir, store, repo_id, cfg.repo_name)
            generate_context_pack(cfg, store, repo_id)
            console.print("[green]Decision logged.[/green]")
        finally:
            store.close()


def register_verify_command(app: typer.Typer) -> None:
    @app.command("verify")
    def verify_cmd(path: str = typer.Option(".", help="Repository root.")):
        """Verify locks and paper claims."""
        cfg, store, repo_id = _repo_store(path)
        try:
            result = verify_claims(store, repo_id, cfg.repo_root)
            report = generate_verify_report(cfg.reports_dir, result, cfg.repo_name)
            console.print(Panel(
                f"Status: {result['status']}\n"
                f"Locks: {result['locks_checked']} | Violations: {result['lock_violations']}",
                title="Verify",
            ))
            console.print(f"Report: {report}")
            if result["status"] != "ok":
                raise typer.Exit(1)
        finally:
            store.close()


def register_matrix_command(app: typer.Typer) -> None:
    @app.command("matrix")
    def matrix_cmd(path: str = typer.Option(".", help="Repository root.")):
        """Export experiment matrix."""
        cfg, store, repo_id = _repo_store(path)
        try:
            p = export_matrix_markdown(cfg.context_dir, store, repo_id, cfg.repo_name)
            console.print(f"[green]Matrix:[/green] {p}")
        finally:
            store.close()


@hooks_app.command("install")
def hooks_install(path: str = typer.Option(".", help="Repository root.")):
    """Install git post-commit and pre-commit hooks."""
    repo_root = Path(path).resolve()
    try:
        installed = install_hooks(repo_root)
        for p in installed:
            console.print(f"[green]Installed:[/green] {p}")
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@hooks_app.command("uninstall")
def hooks_uninstall(path: str = typer.Option(".", help="Repository root.")):
    """Remove AgentMemory git hooks."""
    removed = uninstall_hooks(Path(path).resolve())
    for p in removed:
        console.print(f"[yellow]Removed:[/yellow] {p}")


@embed_app.command("index")
def embed_index(path: str = typer.Option(".", help="Repository root.")):
    """Build semantic embedding index (requires [embeddings] extra)."""
    cfg, store, repo_id = _repo_store(path)
    try:
        n = index_repository(store, repo_id, cfg.memory_dir)
        cfg.data["embeddings_enabled"] = True
        cfg.save()
        console.print(f"[green]Indexed {n} files for semantic search.[/green]")
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    finally:
        store.close()


@embed_app.command("search")
def embed_search(
    query: str = typer.Argument(..., help="Semantic search query."),
    path: str = typer.Option(".", help="Repository root."),
):
    """Semantic search over indexed files."""
    cfg = MemoryConfig.resolve(Path(path))
    try:
        results = semantic_search(cfg.memory_dir, query)
        if not results:
            console.print("No results. Run `agentmemory embed index` first.")
            return
        for r in results:
            console.print(f"- `{r.get('path')}` (importance {r.get('importance')})")
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


def sync_external_runs(cfg: MemoryConfig, store: SQLiteStore, repo_id: int) -> dict[str, int]:
    """Sync WandB/MLflow if enabled."""
    counts = {"wandb": 0, "mlflow": 0}
    store.clear_run_artifacts(repo_id)
    if cfg.wandb_sync_enabled:
        counts["wandb"] = len(discover_wandb_runs(store, repo_id, cfg.repo_root))
    if cfg.mlflow_sync_enabled:
        counts["mlflow"] = len(discover_mlflow_runs(store, repo_id, cfg.repo_root))
    return counts


def register_v2_commands(app: typer.Typer) -> None:
    """Attach v2 subcommands to main app."""
    app.add_typer(lock_app, name="lock")
    app.add_typer(phase_app, name="phase")
    app.add_typer(hooks_app, name="hooks")
    app.add_typer(embed_app, name="embed")
    register_note_command(app)
    register_verify_command(app)
    register_matrix_command(app)
