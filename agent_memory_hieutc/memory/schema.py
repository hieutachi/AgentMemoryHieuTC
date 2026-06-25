"""SQLite schema definition for AgentMemoryHieuTC."""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS repositories (
    repo_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_name       TEXT NOT NULL,
    repo_path       TEXT NOT NULL UNIQUE,
    git_remote      TEXT DEFAULT '',
    current_branch  TEXT DEFAULT '',
    latest_commit   TEXT DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS files (
    file_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id           INTEGER NOT NULL REFERENCES repositories(repo_id),
    path              TEXT NOT NULL,
    file_type         TEXT DEFAULT 'unknown',
    hash              TEXT DEFAULT '',
    size_bytes        INTEGER DEFAULT 0,
    last_modified     TEXT DEFAULT '',
    importance_score  REAL DEFAULT 1.0,
    summary           TEXT DEFAULT '',
    last_indexed_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(repo_id, path)
);

CREATE TABLE IF NOT EXISTS symbols (
    symbol_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id      INTEGER NOT NULL REFERENCES files(file_id),
    symbol_type  TEXT NOT NULL,
    name         TEXT NOT NULL,
    start_line   INTEGER DEFAULT 0,
    end_line     INTEGER DEFAULT 0,
    signature    TEXT DEFAULT '',
    docstring    TEXT DEFAULT '',
    summary      TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS relations (
    relation_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type   TEXT NOT NULL,
    source_id     INTEGER NOT NULL,
    relation_type TEXT NOT NULL,
    target_type   TEXT NOT NULL,
    target_id     INTEGER NOT NULL,
    confidence    REAL DEFAULT 0.5,
    metadata      TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS experiments (
    experiment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id        INTEGER NOT NULL REFERENCES repositories(repo_id),
    name           TEXT NOT NULL,
    script_path    TEXT DEFAULT '',
    config_path    TEXT DEFAULT '',
    result_path    TEXT DEFAULT '',
    algorithms     TEXT DEFAULT '[]',
    environment    TEXT DEFAULT '',
    seeds          TEXT DEFAULT '[]',
    metrics        TEXT DEFAULT '[]',
    status         TEXT DEFAULT 'unknown',
    summary        TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS paper_sections (
    section_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id        INTEGER NOT NULL REFERENCES repositories(repo_id),
    paper_file     TEXT NOT NULL,
    section_title  TEXT NOT NULL,
    section_type   TEXT DEFAULT '',
    line_number    INTEGER DEFAULT 0,
    summary        TEXT DEFAULT '',
    claims         TEXT DEFAULT '[]',
    related_files  TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS figures (
    figure_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id          INTEGER NOT NULL REFERENCES repositories(repo_id),
    figure_name      TEXT NOT NULL,
    output_path      TEXT DEFAULT '',
    generator_script TEXT DEFAULT '',
    source_data      TEXT DEFAULT '[]',
    paper_reference  TEXT DEFAULT '',
    caption          TEXT DEFAULT '',
    status           TEXT DEFAULT 'unknown'
);

CREATE TABLE IF NOT EXISTS memory_items (
    memory_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id      INTEGER NOT NULL REFERENCES repositories(repo_id),
    scope        TEXT DEFAULT 'global',
    key          TEXT NOT NULL,
    value        TEXT DEFAULT '',
    source_path  TEXT DEFAULT '',
    confidence   REAL DEFAULT 0.5,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_files_repo ON files(repo_id);
CREATE INDEX IF NOT EXISTS idx_files_type ON files(file_type);
CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_relations_type ON relations(relation_type);
CREATE INDEX IF NOT EXISTS idx_experiments_repo ON experiments(repo_id);
CREATE INDEX IF NOT EXISTS idx_paper_sections_repo ON paper_sections(repo_id);
CREATE INDEX IF NOT EXISTS idx_figures_repo ON figures(repo_id);
CREATE INDEX IF NOT EXISTS idx_memory_items_repo ON memory_items(repo_id);
CREATE INDEX IF NOT EXISTS idx_memory_items_key ON memory_items(key);

CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_items_repo_key ON memory_items(repo_id, key);
"""

SCHEMA_V2_SQL = """
CREATE TABLE IF NOT EXISTS locks (
    lock_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id       INTEGER NOT NULL REFERENCES repositories(repo_id),
    lock_type     TEXT NOT NULL,
    target_path   TEXT DEFAULT '',
    label         TEXT NOT NULL,
    file_hash     TEXT DEFAULT '',
    metrics_json  TEXT DEFAULT '{}',
    git_commit    TEXT DEFAULT '',
    locked_at     TEXT DEFAULT (datetime('now')),
    metadata      TEXT DEFAULT '{}',
    UNIQUE(repo_id, label)
);

CREATE TABLE IF NOT EXISTS phases (
    phase_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id       INTEGER NOT NULL REFERENCES repositories(repo_id),
    phase_name    TEXT NOT NULL,
    status        TEXT DEFAULT 'pending',
    tasks_json    TEXT DEFAULT '[]',
    notes         TEXT DEFAULT '',
    started_at    TEXT DEFAULT '',
    completed_at  TEXT DEFAULT '',
    UNIQUE(repo_id, phase_name)
);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id       INTEGER NOT NULL REFERENCES repositories(repo_id),
    phase         TEXT DEFAULT '',
    content       TEXT NOT NULL,
    outcome       TEXT DEFAULT '',
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS run_artifacts (
    artifact_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id       INTEGER NOT NULL REFERENCES repositories(repo_id),
    source        TEXT NOT NULL,
    run_id        TEXT DEFAULT '',
    run_name      TEXT DEFAULT '',
    metrics_json  TEXT DEFAULT '{}',
    config_json   TEXT DEFAULT '{}',
    artifact_path TEXT DEFAULT '',
    synced_at     TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_locks_repo ON locks(repo_id);
CREATE INDEX IF NOT EXISTS idx_phases_repo ON phases(repo_id);
CREATE INDEX IF NOT EXISTS idx_decisions_repo ON decisions(repo_id);
CREATE INDEX IF NOT EXISTS idx_run_artifacts_repo ON run_artifacts(repo_id);
"""
