"""Tests for experiment matrix."""

import tempfile
from pathlib import Path

from agent_memory_hieutc.config import MemoryConfig, ensure_memory_dirs
from agent_memory_hieutc.memory.sqlite_store import SQLiteStore
from agent_memory_hieutc.research.experiment_matrix import build_experiment_matrix


def test_experiment_matrix():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        cfg = MemoryConfig.resolve(repo_root)
        ensure_memory_dirs(cfg)
        store = SQLiteStore(cfg.db_path)
        store.open()
        store.initialize_schema()
        repo_id = store.upsert_repository("test", str(repo_root))

        store.insert_experiment(
            repo_id, "exp1", script_path="train.py",
            algorithms=["MAPPO"], environment="env1", seeds=[1, 2],
        )
        rows = build_experiment_matrix(store, repo_id)
        store.close()
        assert len(rows) == 1
        assert rows[0]["algorithm"] == "MAPPO"
