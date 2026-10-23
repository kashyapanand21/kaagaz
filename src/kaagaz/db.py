from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id           INTEGER PRIMARY KEY,
    sha256       TEXT NOT NULL UNIQUE,
    path         TEXT NOT NULL,
    size_bytes   INTEGER NOT NULL,
    mtime        REAL NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',   -- pending / indexed / needs_review / failed
    pages        INTEGER,
    doc_type     TEXT,
    confidence   REAL,
    person_name  TEXT,
    issuer       TEXT,
    year         INTEGER,
    issue_date   TEXT,
    valid_until  TEXT,
    id_last4     TEXT,
    language     TEXT,
    summary      TEXT,
    model        TEXT,
    seconds      REAL,
    error        TEXT,
    raw          TEXT,                              -- model output, scrubbed before saving
    thumb        TEXT,
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_type   ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_documents_path   ON documents(path);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT status, COUNT(*) AS n FROM documents GROUP BY status")
    return {r["status"]: r["n"] for r in rows}