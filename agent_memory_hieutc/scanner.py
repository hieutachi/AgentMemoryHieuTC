"""Repository scanner: walk files, classify, parse, and index."""

from __future__ import annotations

import fnmatch
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from .config import MemoryConfig
from .git_utils import get_repo_info, is_git_repo
from .memory.sqlite_store import SQLiteStore
from .parsers.config_parser import parse_config_file
from .parsers.markdown_parser import parse_markdown
from .parsers.python_parser import PyFileInfo, parse_python_file
from .parsers.result_parser import parse_result_file
from .research.ml_taxonomy import classify_file_content, detect_research_domain
from .utils.hashing import file_hash
from .utils.paths import safe_relative, should_ignore


# File classification patterns
CLASSIFICATION_RULES: list[tuple[str, list[str]]] = [
    ("training_script", ["train*.py", "*training*.py", "*_train.py"]),
    ("evaluation_script", ["eval*.py", "evaluate*.py", "*_eval.py"]),
    ("test_file", ["test_*.py", "tests/**/*.py", "*_test.py"]),
    ("experiment_script", ["run*.py", "experiment*.py", "run_*.py", "sweep*.py", "launch*.py"]),
    ("figure_generation_script", [
        "plot*.py", "figure*.py", "generate*figure*.py", "make*figure*.py",
        "viz*.py", "visualize*.py", "draw*.py",
    ]),
    ("config_file", [
        "config*.yaml", "config*.yml", "config*.json",
        "*.cfg", "hydra*.yaml", "settings*.yaml",
        "train*.yaml", "train*.yml",
    ]),
    ("paper_latex", ["*.tex", "*.bib", "*.bst", "*.cls"]),
    ("paper_markdown", ["paper*.md", "manuscript*.md", "draft*.md", "main.md"]),
    ("paper_draft", [
        "response_to_reviewers*.md", "revision*.md", "remaining_issues*.md",
        "reviewer*.md", "changelog*.md", "camera_ready*.md",
    ]),
    ("notebook", ["*.ipynb"]),
    ("documentation", ["README*", "CONTRIBUTING*", "LICENSE*", "CHANGELOG*", "docs/*.md"]),
    ("result_file", [
        "results*.json", "results*.csv", "metrics*.json", "metrics*.csv",
        "outputs/**/*.json", "outputs/**/*.csv",
        "results/**/*.json", "results/**/*.csv",
    ]),
    ("dataset_metadata", [
        "data*.yaml", "data*.json", "dataset*.yaml", "dataset*.json",
        "datasets/*.yaml", "datasets/*.json",
    ]),
    ("log_file", ["*.log", "logs/**"]),
]

LARGE_FILE_EXTENSIONS = {
    ".pt", ".pth", ".ckpt", ".onnx", ".pkl", ".pickle",
    ".zip", ".tar", ".tar.gz", ".rar", ".7z",
    ".mp4", ".avi", ".mov", ".wav", ".mp3",
    ".npy", ".npz", ".h5", ".hdf5",
}


def classify_file(rel_path: str) -> str:
    """Classify a file into a research-relevant category."""
    filename = os.path.basename(rel_path)

    for category, patterns in CLASSIFICATION_RULES:
        for pattern in patterns:
            if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(rel_path, pattern):
                return category

    # Fallback: classify by extension
    ext = Path(rel_path).suffix.lower()
    if ext == ".py":
        return "source_code"
    if ext in (".yaml", ".yml", ".json", ".toml", ".ini"):
        return "config_file"
    if ext in (".md", ".rst", ".txt"):
        return "documentation"
    if ext in (".csv", ".tsv"):
        return "result_file"
    if ext in LARGE_FILE_EXTENSIONS:
        return "checkpoint"

    return "unknown"


def compute_importance(file_type: str, rel_path: str, summary: str = "") -> float:
    """Compute importance score (1-10) for a file."""
    scores: dict[str, float] = {
        "training_script": 9.0,
        "experiment_script": 8.5,
        "evaluation_script": 8.0,
        "figure_generation_script": 7.5,
        "config_file": 7.0,
        "paper_latex": 8.0,
        "paper_markdown": 8.0,
        "paper_draft": 7.5,
        "result_file": 7.0,
        "dataset_metadata": 6.0,
        "source_code": 5.0,
        "notebook": 4.0,
        "documentation": 3.0,
        "test_file": 2.5,
        "log_file": 2.0,
        "checkpoint": 1.5,
        "unknown": 1.0,
    }
    base = scores.get(file_type, 1.0)

    # Boost for key files
    filename = os.path.basename(rel_path).lower()
    if filename in ("__init__.py",):
        return max(base - 2, 1.0)
    if filename in ("setup.py", "pyproject.toml", "requirements.txt"):
        return max(base - 1, 1.0)

    return base


def scan_repository(cfg: MemoryConfig, store: SQLiteStore,
                    progress_callback: Callable[[str], None] | None = None) -> dict:
    """Perform a full scan of the repository."""
    start_time = time.time()
    repo_root = cfg.repo_root
    ignore_patterns = cfg.effective_ignore_patterns()
    max_size = cfg.max_file_size_bytes

    def log(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)

    # Get git info
    git = get_repo_info(repo_root) if is_git_repo(repo_root) else None

    # Upsert repository record
    repo_id = store.upsert_repository(
        name=cfg.repo_name,
        path=str(repo_root),
        remote=git.remote if git else "",
        branch=git.branch if git else "",
        commit=git.latest_commit if git else "",
    )

    # Clear existing data for fresh scan
    store.clear_repo_data(repo_id)

    log("Scanning files...")

    # Walk directory
    all_files: list[tuple[Path, str]] = []  # (absolute_path, relative_path)
    for root, dirs, files in os.walk(repo_root):
        # Skip ignored directories
        dirs[:] = [d for d in dirs if not should_ignore(d + "/", ignore_patterns)]
        root_path = Path(root)
        for fname in files:
            fpath = root_path / fname
            rel = safe_relative(fpath, repo_root)
            if should_ignore(rel, ignore_patterns):
                continue
            all_files.append((fpath, rel))

    log(f"Found {len(all_files)} files. Classifying and parsing...")

    known_paths: set[str] = {rel for _, rel in all_files}

    # Process each file
    stats = {"total": len(all_files), "by_type": {}, "parsed": 0, "skipped": 0}

    for fpath, rel_path in all_files:
        # Check file size
        try:
            size = fpath.stat().st_size
        except OSError:
            stats["skipped"] += 1
            continue

        if size > max_size:
            # Record metadata only
            ftype = classify_file(rel_path)
            importance = compute_importance(ftype, rel_path)
            store.upsert_file(
                repo_id=repo_id, path=rel_path, file_type=ftype,
                hash_val="", size=size, importance=importance,
                summary="Large file, metadata only",
            )
            stats["skipped"] += 1
            continue

        if size == 0:
            continue

        # Classify
        ftype = classify_file(rel_path)
        hash_val = file_hash(fpath)
        importance = compute_importance(ftype, rel_path)
        summary = ""

        # Parse based on type
        if rel_path.endswith(".py"):
            try:
                py_info = parse_python_file(fpath)
                summary = py_info.summary
                importance = compute_importance(ftype, rel_path, summary)

                # Boost importance for RL/MARL files
                if py_info.research_keywords:
                    kw_count = len(py_info.research_keywords)
                    importance = min(importance + kw_count * 0.3, 10.0)

                # Store file
                file_id = store.upsert_file(
                    repo_id=repo_id, path=rel_path, file_type=ftype,
                    hash_val=hash_val, size=size, importance=importance,
                    summary=summary,
                )

                # Store symbols
                store.clear_symbols_for_file(file_id)
                for sym in py_info.symbols:
                    store.insert_symbol(
                        file_id=file_id,
                        symbol_type=sym.symbol_type,
                        name=sym.name,
                        start_line=sym.start_line,
                        end_line=sym.end_line,
                        signature=sym.signature,
                        docstring=sym.docstring[:500],
                        summary="",
                    )

                # Build relations from imports
                for imp in py_info.imports:
                    imp_path = _resolve_import_to_path(imp, rel_path, known_paths)
                    if imp_path:
                        target_file = store.get_file(repo_id, imp_path)
                        if target_file:
                            store.insert_relation(
                                source_type="file", source_id=file_id,
                                relation_type="imports",
                                target_type="file", target_id=target_file["file_id"],
                            )

                # Relations from config/result/figure file references
                for cfg_ref in py_info.config_files_loaded:
                    cfg_file = store.get_file(repo_id, cfg_ref)
                    if cfg_file:
                        store.insert_relation(
                            source_type="file", source_id=file_id,
                            relation_type="reads_config",
                            target_type="file", target_id=cfg_file["file_id"],
                        )

                stats["parsed"] += 1

            except Exception:
                # Fallback: store without detailed parsing
                store.upsert_file(
                    repo_id=repo_id, path=rel_path, file_type=ftype,
                    hash_val=hash_val, size=size, importance=importance,
                    summary="Parse error",
                )
                stats["parsed"] += 1

        elif rel_path.endswith((".md", ".tex", ".bib")):
            try:
                if rel_path.endswith(".tex"):
                    summary = f"LaTeX file ({ftype})"
                else:
                    md_info = parse_markdown(fpath)
                    section_titles = [s.title for s in md_info.sections[:5]]
                    summary = f"Sections: {', '.join(section_titles)}" if section_titles else "Markdown file"

                store.upsert_file(
                    repo_id=repo_id, path=rel_path, file_type=ftype,
                    hash_val=hash_val, size=size, importance=importance,
                    summary=summary,
                )
                stats["parsed"] += 1
            except Exception:
                store.upsert_file(
                    repo_id=repo_id, path=rel_path, file_type=ftype,
                    hash_val=hash_val, size=size, importance=importance,
                    summary="",
                )

        elif rel_path.endswith((".yaml", ".yml", ".json", ".toml")):
            try:
                config_data = parse_config_file(fpath)
                key_count = len(config_data)
                summary = f"Config with {key_count} keys" if key_count else "Config file"
                store.upsert_file(
                    repo_id=repo_id, path=rel_path, file_type=ftype,
                    hash_val=hash_val, size=size, importance=importance,
                    summary=summary,
                )
                stats["parsed"] += 1
            except Exception:
                store.upsert_file(
                    repo_id=repo_id, path=rel_path, file_type=ftype,
                    hash_val=hash_val, size=size, importance=importance,
                    summary="",
                )

        elif rel_path.endswith((".json", ".csv")) and ftype == "result_file":
            try:
                result_data = parse_result_file(fpath)
                summary_parts = []
                if result_data.get("metrics"):
                    summary_parts.append(f"Metrics: {', '.join(result_data['metrics'][:5])}")
                if result_data.get("algorithms"):
                    summary_parts.append(f"Algos: {', '.join(result_data['algorithms'][:3])}")
                summary = "; ".join(summary_parts) or "Result file"
                store.upsert_file(
                    repo_id=repo_id, path=rel_path, file_type=ftype,
                    hash_val=hash_val, size=size, importance=importance,
                    summary=summary,
                )
                stats["parsed"] += 1
            except Exception:
                store.upsert_file(
                    repo_id=repo_id, path=rel_path, file_type=ftype,
                    hash_val=hash_val, size=size, importance=importance,
                    summary="",
                )
        else:
            store.upsert_file(
                repo_id=repo_id, path=rel_path, file_type=ftype,
                hash_val=hash_val, size=size, importance=importance,
                summary="",
            )

        stats["by_type"][ftype] = stats["by_type"].get(ftype, 0) + 1

    elapsed = time.time() - start_time
    stats["elapsed_seconds"] = round(elapsed, 2)

    log(f"Scan complete: {stats['parsed']} files parsed in {elapsed:.1f}s")

    return stats


def _resolve_import_to_path(
    import_name: str,
    from_path: str,
    known_paths: set[str] | None = None,
) -> str | None:
    """Try to resolve a Python import to a file path in the repo."""
    if not import_name or import_name.startswith("typing"):
        return None

    candidates: list[str] = []
    parts = [p for p in import_name.split(".") if p and p != ""]

    if parts:
        candidates.append("/".join(parts) + ".py")
        candidates.append("/".join(parts) + "/__init__.py")

    # Relative import from same package directory
    if from_path.endswith(".py") and parts:
        base_parts = from_path.split("/")[:-1]
        tail = parts[-1] + ".py"
        if base_parts:
            candidates.append("/".join(base_parts + [tail]))
        candidates.append(tail)

    if known_paths:
        for c in candidates:
            if c in known_paths:
                return c
        if parts:
            tail = parts[-1] + ".py"
            matches = [p for p in known_paths if p.endswith("/" + tail) or p == tail]
            if len(matches) == 1:
                return matches[0]
            pkg_tail = "/".join(parts) + ".py"
            pkg_matches = [p for p in known_paths if p.endswith(pkg_tail)]
            if len(pkg_matches) == 1:
                return pkg_matches[0]

    return candidates[0] if candidates else None
