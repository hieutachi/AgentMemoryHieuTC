"""Configuration management for AgentMemoryHieuTC."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

MEMORY_DIR_NAME = ".agent_memory_hieutc"
CONFIG_FILE = "config.yaml"
DB_FILE = "repo_index.sqlite"

DEFAULT_IGNORE_PATTERNS: list[str] = [
    ".git/", "__pycache__/", ".venv/", "venv/", "env/",
    "node_modules/", "wandb/", "runs/", ".cache/", "dist/", "build/",
    ".eggs/", "*.egg-info/", ".mypy_cache/", ".pytest_cache/",
    ".ruff_cache/", ".tox/", ".nox/",
    f"{MEMORY_DIR_NAME}/",
    "*.sqlite-shm", "*.sqlite-wal",
    "*.pt", "*.pth", "*.ckpt", "*.onnx", "*.pkl", "*.pickle",
    "*.zip", "*.tar", "*.tar.gz", "*.rar", "*.7z",
    "*.mp4", "*.avi", "*.mov", "*.wav", "*.mp3",
    "*.o", "*.so", "*.dylib", "*.dll",
    "*.pyc", "*.pyo",
]

DEFAULT_CONFIG: dict[str, Any] = {
    "version": "1.1.0",
    "repo_name": "",
    "scan_paths": ["."],
    "ignore_patterns": DEFAULT_IGNORE_PATTERNS,
    "max_file_size_mb": 10,
    "importance_threshold": 3,
    "graph_max_nodes": 50,
    "graph_max_edges": 120,
    "last_scan_commit": None,
    "last_scan_time": None,
    "embeddings_enabled": False,
    "embeddings_backend": "sentence-transformers",
    # Context / token budget (compact = default)
    "context_mode": "compact",
    "context_max_files": 12,
    "context_max_experiments": 8,
    "context_max_figures": 6,
    "context_summary_max_chars": 48,
    "context_importance_min": 5.0,
}


@dataclass
class MemoryConfig:
    """Resolved configuration for a repository memory instance."""

    repo_root: Path
    memory_dir: Path
    config_path: Path
    db_path: Path
    graph_dir: Path
    context_dir: Path
    reports_dir: Path
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def resolve(cls, repo_root: Path | None = None) -> MemoryConfig:
        if repo_root is None:
            repo_root = Path.cwd()
        repo_root = repo_root.resolve()
        memory_dir = repo_root / MEMORY_DIR_NAME
        config_path = memory_dir / CONFIG_FILE
        db_path = memory_dir / DB_FILE

        data = dict(DEFAULT_CONFIG)
        if config_path.exists():
            try:
                with open(config_path) as f:
                    loaded = yaml.safe_load(f) or {}
                data.update(loaded)
            except Exception:
                pass

        return cls(
            repo_root=repo_root,
            memory_dir=memory_dir,
            config_path=config_path,
            db_path=db_path,
            graph_dir=memory_dir / "graph",
            context_dir=memory_dir / "context",
            reports_dir=memory_dir / "reports",
            data=data,
        )

    def save(self) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            yaml.dump(self.data, f, default_flow_style=False, sort_keys=False)

    @property
    def repo_name(self) -> str:
        return self.data.get("repo_name") or self.repo_root.name

    @property
    def max_file_size_bytes(self) -> int:
        return self.data.get("max_file_size_mb", 10) * 1024 * 1024

    @property
    def ignore_patterns(self) -> list[str]:
        return self.data.get("ignore_patterns", DEFAULT_IGNORE_PATTERNS)

    @property
    def graph_max_nodes(self) -> int:
        return self.data.get("graph_max_nodes", 80)

    @property
    def importance_threshold(self) -> int:
        return self.data.get("importance_threshold", 3)

    @property
    def context_mode(self) -> str:
        return self.data.get("context_mode", "compact")

    @property
    def context_max_files(self) -> int:
        return int(self.data.get("context_max_files", 12))

    @property
    def context_max_experiments(self) -> int:
        return int(self.data.get("context_max_experiments", 8))

    @property
    def context_max_figures(self) -> int:
        return int(self.data.get("context_max_figures", 6))

    @property
    def context_summary_max_chars(self) -> int:
        return int(self.data.get("context_summary_max_chars", 48))

    @property
    def context_importance_min(self) -> float:
        return float(self.data.get("context_importance_min", 5.0))

    def effective_ignore_patterns(self) -> list[str]:
        patterns = list(self.ignore_patterns)
        memory_glob = f"{MEMORY_DIR_NAME}/"
        if memory_glob not in patterns:
            patterns.append(memory_glob)
        return patterns


def ensure_memory_dirs(cfg: MemoryConfig) -> None:
    for d in [cfg.memory_dir, cfg.graph_dir, cfg.context_dir, cfg.reports_dir]:
        d.mkdir(parents=True, exist_ok=True)
