"""SQLite storage backend for AgentMemoryHieuTC."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import SCHEMA_SQL


class SQLiteStore:
    """Manages all persistent indexed data for a repository."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None

    def open(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

    def initialize_schema(self) -> None:
        assert self.conn
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    # ---- Repository ----

    def upsert_repository(self, name: str, path: str, remote: str = "",
                          branch: str = "", commit: str = "") -> int:
        assert self.conn
        cur = self.conn.execute(
            "SELECT repo_id FROM repositories WHERE repo_path = ?", (path,)
        )
        row = cur.fetchone()
        now = datetime.utcnow().isoformat()
        if row:
            self.conn.execute(
                """UPDATE repositories SET repo_name=?, git_remote=?,
                   current_branch=?, latest_commit=?, updated_at=?
                   WHERE repo_id=?""",
                (name, remote, branch, commit, now, row["repo_id"]),
            )
            self.conn.commit()
            return row["repo_id"]
        else:
            cur = self.conn.execute(
                """INSERT INTO repositories (repo_name, repo_path, git_remote,
                   current_branch, latest_commit)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, path, remote, branch, commit),
            )
            self.conn.commit()
            return cur.lastrowid  # type: ignore

    def get_repo_id(self, path: str) -> int | None:
        assert self.conn
        cur = self.conn.execute(
            "SELECT repo_id FROM repositories WHERE repo_path = ?", (path,)
        )
        row = cur.fetchone()
        return row["repo_id"] if row else None

    # ---- Files ----

    def upsert_file(self, repo_id: int, path: str, file_type: str = "unknown",
                    hash_val: str = "", size: int = 0, importance: float = 1.0,
                    summary: str = "") -> int:
        assert self.conn
        cur = self.conn.execute(
            "SELECT file_id FROM files WHERE repo_id=? AND path=?",
            (repo_id, path),
        )
        row = cur.fetchone()
        now = datetime.utcnow().isoformat()
        if row:
            self.conn.execute(
                """UPDATE files SET file_type=?, hash=?, size_bytes=?,
                   importance_score=?, summary=?, last_indexed_at=?
                   WHERE file_id=?""",
                (file_type, hash_val, size, importance, summary, now, row["file_id"]),
            )
            self.conn.commit()
            return row["file_id"]
        else:
            cur = self.conn.execute(
                """INSERT INTO files (repo_id, path, file_type, hash, size_bytes,
                   importance_score, summary, last_indexed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (repo_id, path, file_type, hash_val, size, importance, summary, now),
            )
            self.conn.commit()
            return cur.lastrowid  # type: ignore

    def get_file(self, repo_id: int, path: str) -> dict | None:
        assert self.conn
        cur = self.conn.execute(
            "SELECT * FROM files WHERE repo_id=? AND path=?", (repo_id, path)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def get_all_files(self, repo_id: int) -> list[dict]:
        assert self.conn
        cur = self.conn.execute(
            "SELECT * FROM files WHERE repo_id=? ORDER BY importance_score DESC",
            (repo_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def delete_file(self, repo_id: int, path: str) -> None:
        assert self.conn
        cur = self.conn.execute(
            "SELECT file_id FROM files WHERE repo_id=? AND path=?",
            (repo_id, path),
        )
        row = cur.fetchone()
        if row:
            fid = row["file_id"]
            self.conn.execute("DELETE FROM symbols WHERE file_id=?", (fid,))
            self.conn.execute(
                "DELETE FROM relations WHERE (source_type='file' AND source_id=?) "
                "OR (target_type='file' AND target_id=?)",
                (fid, fid),
            )
            self.conn.execute("DELETE FROM files WHERE file_id=?", (fid,))
            self.conn.commit()

    # ---- Symbols ----

    def insert_symbol(self, file_id: int, symbol_type: str, name: str,
                      start_line: int = 0, end_line: int = 0,
                      signature: str = "", docstring: str = "",
                      summary: str = "") -> int:
        assert self.conn
        cur = self.conn.execute(
            """INSERT INTO symbols (file_id, symbol_type, name, start_line,
               end_line, signature, docstring, summary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (file_id, symbol_type, name, start_line, end_line, signature, docstring, summary),
        )
        self.conn.commit()
        return cur.lastrowid  # type: ignore

    def clear_symbols_for_file(self, file_id: int) -> None:
        assert self.conn
        self.conn.execute("DELETE FROM symbols WHERE file_id=?", (file_id,))
        self.conn.commit()

    def search_symbols(self, keyword: str) -> list[dict]:
        assert self.conn
        pattern = f"%{keyword}%"
        cur = self.conn.execute(
            """SELECT s.*, f.path as file_path FROM symbols s
               JOIN files f ON s.file_id = f.file_id
               WHERE s.name LIKE ? OR s.docstring LIKE ? OR s.summary LIKE ?
               ORDER BY s.name LIMIT 30""",
            (pattern, pattern, pattern),
        )
        return [dict(r) for r in cur.fetchall()]

    # ---- Relations ----

    def insert_relation(self, source_type: str, source_id: int,
                        relation_type: str, target_type: str, target_id: int,
                        confidence: float = 0.5, metadata: dict | None = None) -> int:
        assert self.conn
        cur = self.conn.execute(
            """INSERT INTO relations (source_type, source_id, relation_type,
               target_type, target_id, confidence, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (source_type, source_id, relation_type, target_type, target_id,
             confidence, json.dumps(metadata or {})),
        )
        self.conn.commit()
        return cur.lastrowid  # type: ignore

    def clear_relations_for_file(self, file_id: int) -> None:
        assert self.conn
        self.conn.execute(
            "DELETE FROM relations WHERE (source_type='file' AND source_id=?) "
            "OR (target_type='file' AND target_id=?)",
            (file_id, file_id),
        )
        self.conn.commit()

    def get_relations(self, repo_id: int, relation_type: str | None = None) -> list[dict]:
        assert self.conn
        if relation_type:
            cur = self.conn.execute(
                "SELECT * FROM relations WHERE relation_type=?", (relation_type,)
            )
        else:
            cur = self.conn.execute("SELECT * FROM relations")
        return [dict(r) for r in cur.fetchall()]

    # ---- Experiments ----

    def insert_experiment(self, repo_id: int, name: str, script_path: str = "",
                          config_path: str = "", result_path: str = "",
                          algorithms: list[str] | None = None,
                          environment: str = "", seeds: list | None = None,
                          metrics: list[str] | None = None,
                          status: str = "unknown", summary: str = "") -> int:
        assert self.conn
        cur = self.conn.execute(
            """INSERT INTO experiments (repo_id, name, script_path, config_path,
               result_path, algorithms, environment, seeds, metrics, status, summary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (repo_id, name, script_path, config_path, result_path,
             json.dumps(algorithms or []), environment,
             json.dumps(seeds or []), json.dumps(metrics or []),
             status, summary),
        )
        self.conn.commit()
        return cur.lastrowid  # type: ignore

    def get_experiments(self, repo_id: int) -> list[dict]:
        assert self.conn
        cur = self.conn.execute(
            "SELECT * FROM experiments WHERE repo_id=?", (repo_id,)
        )
        return [dict(r) for r in cur.fetchall()]

    def search_experiments(self, keyword: str) -> list[dict]:
        assert self.conn
        pattern = f"%{keyword}%"
        cur = self.conn.execute(
            """SELECT * FROM experiments
               WHERE name LIKE ? OR script_path LIKE ? OR algorithms LIKE ?
               OR environment LIKE ? OR summary LIKE ?
               LIMIT 20""",
            (pattern, pattern, pattern, pattern, pattern),
        )
        return [dict(r) for r in cur.fetchall()]

    # ---- Paper Sections ----

    def insert_paper_section(self, repo_id: int, paper_file: str,
                             section_title: str, section_type: str = "",
                             line_number: int = 0, summary: str = "",
                             claims: list[str] | None = None,
                             related_files: list[str] | None = None) -> int:
        assert self.conn
        cur = self.conn.execute(
            """INSERT INTO paper_sections (repo_id, paper_file, section_title,
               section_type, line_number, summary, claims, related_files)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (repo_id, paper_file, section_title, section_type, line_number,
             summary, json.dumps(claims or []),
             json.dumps(related_files or [])),
        )
        self.conn.commit()
        return cur.lastrowid  # type: ignore

    def get_paper_sections(self, repo_id: int) -> list[dict]:
        assert self.conn
        cur = self.conn.execute(
            "SELECT * FROM paper_sections WHERE repo_id=?", (repo_id,)
        )
        return [dict(r) for r in cur.fetchall()]

    # ---- Figures ----

    def insert_figure(self, repo_id: int, figure_name: str,
                      output_path: str = "", generator_script: str = "",
                      source_data: list[str] | None = None,
                      paper_reference: str = "", caption: str = "",
                      status: str = "unknown") -> int:
        assert self.conn
        cur = self.conn.execute(
            """INSERT INTO figures (repo_id, figure_name, output_path,
               generator_script, source_data, paper_reference, caption, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (repo_id, figure_name, output_path, generator_script,
             json.dumps(source_data or []), paper_reference, caption, status),
        )
        self.conn.commit()
        return cur.lastrowid  # type: ignore

    def get_figures(self, repo_id: int) -> list[dict]:
        assert self.conn
        cur = self.conn.execute(
            "SELECT * FROM figures WHERE repo_id=?", (repo_id,)
        )
        return [dict(r) for r in cur.fetchall()]

    # ---- Memory Items ----

    def set_memory(self, repo_id: int, key: str, value: str,
                   scope: str = "global", source_path: str = "",
                   confidence: float = 0.5) -> None:
        assert self.conn
        now = datetime.utcnow().isoformat()
        self.conn.execute(
            """INSERT INTO memory_items (repo_id, scope, key, value,
               source_path, confidence, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(repo_id, key) DO UPDATE SET
               value=excluded.value, source_path=excluded.source_path,
               confidence=excluded.confidence, updated_at=excluded.updated_at""",
            (repo_id, scope, key, value, source_path, confidence, now),
        )
        self.conn.commit()

    def get_memory(self, repo_id: int, key: str) -> str | None:
        assert self.conn
        cur = self.conn.execute(
            "SELECT value FROM memory_items WHERE repo_id=? AND key=?",
            (repo_id, key),
        )
        row = cur.fetchone()
        return row["value"] if row else None

    def search_memory(self, keyword: str) -> list[dict]:
        assert self.conn
        pattern = f"%{keyword}%"
        cur = self.conn.execute(
            "SELECT * FROM memory_items WHERE key LIKE ? OR value LIKE ? LIMIT 20",
            (pattern, pattern),
        )
        return [dict(r) for r in cur.fetchall()]

    # ---- File Search ----

    def search_files(self, keyword: str) -> list[dict]:
        assert self.conn
        pattern = f"%{keyword}%"
        cur = self.conn.execute(
            """SELECT * FROM files
               WHERE path LIKE ? OR summary LIKE ? OR file_type LIKE ?
               ORDER BY importance_score DESC LIMIT 20""",
            (pattern, pattern, pattern),
        )
        return [dict(r) for r in cur.fetchall()]

    # ---- Stats ----

    def get_stats(self, repo_id: int) -> dict[str, int]:
        assert self.conn
        stats: dict[str, int] = {}
        for table in ["files", "symbols", "relations", "experiments",
                       "paper_sections", "figures", "memory_items"]:
            cur = self.conn.execute(
                f"SELECT COUNT(*) as cnt FROM {table} WHERE repo_id=?",
                (repo_id,),
            )
            stats[table] = cur.fetchone()["cnt"]
        return stats

    def clear_repo_data(self, repo_id: int) -> None:
        """Clear all indexed data for a repository (used before full rescan)."""
        assert self.conn
        for table in ["memory_items", "figures", "paper_sections",
                       "experiments", "relations", "symbols", "files"]:
            self.conn.execute(
                f"DELETE FROM {table} WHERE repo_id=?", (repo_id,)
            )
        self.conn.commit()
