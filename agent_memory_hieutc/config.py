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
    "*.pt", "*.pth", "*.ckpt", "*.onnx", "*.pkl", "*.pickle",
    "*.zip", "*.tar", "*.tar.gz", "*.rar", "*.7z",
    "*.mp4", "*.avi", "*.mov", "*.wav", "*.mp3",
    "*.o", "*.so", "*.dylib", "*.dll",
    "*.pyc", "*.pyo",
]

DEFAULT_CONFIG: dict[str, Any] = {
    "version": "1.0.0",
    "repo_name": "",
    "scan_paths": ["."],
    "ignore_patterns": DEFAULT_IGNORE_PATTERNS,
    "max_file_size_mb": 10,
    "importance_threshold": 3,
    "graph_max_nodes": 80,
    "graph_max_edges": 200,
    "last_scan_commit": None,
    "last_scan_time": None,
    "embeddings_enabled": False,
    "embeddings_backend": "sentence-transformers",
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


def ensure_memory_dirs(cfg: MemoryConfig) -> None:
    for d in [cfg.memory_dir, cfg.graph_dir, cfg.context_dir, cfg.reports_dir]:
        d.mkdir(parents=True, exist_ok=True)
