"""Tests for phase tracker."""

import tempfile
from pathlib import Path

from agent_memory_hieutc.config import MemoryConfig, ensure_memory_dirs
from agent_memory_hieutc.memory.sqlite_store import SQLiteStore
from agent_memory_hieutc.research.phase_tracker import (
    ensure_default_phases,
    generate_phase_status,
    set_active_phase,
)


def test_phase_tracking():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        cfg = MemoryConfig.resolve(repo_root)
        cfg.data["repo_name"] = "test_project"
        ensure_memory_dirs(cfg)

        store = SQLiteStore(cfg.db_path)
        store.open()
        store.initialize_schema()
        repo_id = store.upsert_repository("test_project", str(repo_root))

        ensure_default_phases(store, repo_id)
        set_active_phase(store, repo_id, "baseline")
        assert store.get_memory(repo_id, "active_phase") == "baseline"

        path = generate_phase_status(cfg.context_dir, store, repo_id, "test_project")
        store.close()

        content = Path(path).read_text(encoding="utf-8")
        assert "baseline" in content
        assert "Active phase" in content
