"""Tests for context pack generation."""

import tempfile
from pathlib import Path

from agent_memory_hieutc.config import MemoryConfig, ensure_memory_dirs
from agent_memory_hieutc.memory.sqlite_store import SQLiteStore
from agent_memory_hieutc.memory.context_pack import generate_context_pack


def test_generate_context_pack():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        cfg = MemoryConfig.resolve(repo_root)
        cfg.data["repo_name"] = "test_project"
        ensure_memory_dirs(cfg)

        store = SQLiteStore(cfg.db_path)
        store.open()
        store.initialize_schema()
        repo_id = store.upsert_repository("test_project", str(repo_root))

        # Add a sample file
        store.upsert_file(repo_id, "train.py", "training_script", "abc123", 1000, 9.0, "Main training script")
        store.insert_experiment(
            repo_id, "main_exp", script_path="train.py",
            algorithms=["MAPPO"], environment="coverage_v1",
            seeds=[1, 2, 3], status="detected",
        )

        files = generate_context_pack(cfg, store, repo_id)
        store.close()

        assert len(files) > 0
        compact = cfg.context_dir / "CONTEXT_COMPACT.md"
        assert compact.exists()
        content = compact.read_text()
        assert "test_project" in content
        assert "train.py" in content

        next_prompt = cfg.context_dir / "NEXT_AGENT_PROMPT.md"
        assert next_prompt.exists()
        prompt_content = next_prompt.read_text()
        assert "Do NOT reread" in prompt_content
