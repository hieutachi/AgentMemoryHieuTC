"""Tests for lock registry."""

import json
import tempfile
from pathlib import Path

from agent_memory_hieutc.config import MemoryConfig, ensure_memory_dirs
from agent_memory_hieutc.memory.lock_registry import lock_file, verify_locks
from agent_memory_hieutc.memory.sqlite_store import SQLiteStore


def test_lock_and_verify_result():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        result_file = repo_root / "results.json"
        result_file.write_text('{"reward": 0.95, "seed": 1}', encoding="utf-8")

        cfg = MemoryConfig.resolve(repo_root)
        ensure_memory_dirs(cfg)
        store = SQLiteStore(cfg.db_path)
        store.open()
        store.initialize_schema()
        repo_id = store.upsert_repository("test", str(repo_root))

        info = lock_file(store, repo_id, repo_root, "result", "results.json", "table1")
        assert info["label"] == "table1"

        report = verify_locks(store, repo_id, repo_root)
        assert report[0]["status"] == "ok"

        result_file.write_text('{"reward": 0.50}', encoding="utf-8")
        report2 = verify_locks(store, repo_id, repo_root)
        assert report2[0]["status"] == "changed"
        store.close()


def test_lock_metric():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        cfg = MemoryConfig.resolve(repo_root)
        ensure_memory_dirs(cfg)
        store = SQLiteStore(cfg.db_path)
        store.open()
        store.initialize_schema()
        repo_id = store.upsert_repository("test", str(repo_root))

        from agent_memory_hieutc.memory.lock_registry import lock_metric
        lock_metric(store, repo_id, repo_root, "main_reward", {"reward": 0.84})
        locks = store.get_locks(repo_id)
        assert len(locks) == 1
        assert locks[0]["lock_type"] == "metric"
        store.close()
