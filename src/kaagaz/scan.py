from __future__ import annotations

import hashlib
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from kaagaz.config import Settings

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "$recycle.bin", "appdata"}
CLOUD_ONLY = 0x00400000 | 0x00040000   # Windows: RECALL_ON_DATA_ACCESS | RECALL_ON_OPEN


@dataclass
class ScanReport:
    seen: int = 0
    new: int = 0
    unchanged: int = 0
    moved: int = 0
    duplicate: int = 0
    cloud_only: int = 0
    missing_folders: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def discover(s: Settings, rep: ScanReport) -> Iterator[tuple[Path, os.stat_result]]:
    own = [s.data_dir, s.packets_dir]
    lo, hi = s.thresholds.min_file_kb * 1024, s.thresholds.max_file_mb * 1024 * 1024
    for root in s.folders:
        if not root.is_dir():
            rep.missing_folders.append(str(root))
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            here = Path(dirpath)
            dirnames[:] = [n for n in dirnames
                           if n.lower() not in SKIP_DIRS and not n.startswith(".")
                           and not any(_inside(here / n, o) for o in own)]
            for name in filenames:
                p = here / name
                if p.suffix.lower() not in s.extensions:
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                if getattr(st, "st_file_attributes", 0) & CLOUD_ONLY:
                    rep.cloud_only += 1
                    continue
                if lo <= st.st_size <= hi:
                    yield p, st

def register(conn: sqlite3.Connection, path: Path, st: os.stat_result) -> str:
    p = str(path)
    if conn.execute("SELECT 1 FROM documents WHERE path=? AND size_bytes=? AND mtime=?",
                    (p, st.st_size, st.st_mtime)).fetchone():
        return "unchanged"                                   # no hashing needed

    digest = sha256_file(path)
    row = conn.execute("SELECT id, path FROM documents WHERE sha256=?", (digest,)).fetchone()
    if row:
        if row["path"] == p:
            conn.execute("UPDATE documents SET size_bytes=?, mtime=? WHERE id=?",
                         (st.st_size, st.st_mtime, row["id"]))
            return "unchanged"
        if Path(row["path"]).exists():
            return "duplicate"                               # another copy; keep one document
        conn.execute("UPDATE documents SET path=?, size_bytes=?, mtime=?, "
                     "updated_at=datetime('now') WHERE id=?",
                     (p, st.st_size, st.st_mtime, row["id"]))
        return "moved"                                       # renamed or moved; keeps its label

    conn.execute("DELETE FROM documents WHERE path=?", (p,))   # same path, edited content
    conn.execute("INSERT INTO documents (sha256, path, size_bytes, mtime) VALUES (?, ?, ?, ?)",
                 (digest, p, st.st_size, st.st_mtime))
    return "new"


def scan(conn: sqlite3.Connection, s: Settings) -> ScanReport:
    rep = ScanReport()
    for path, st in discover(s, rep):
        rep.seen += 1
        try:
            outcome = register(conn, path, st)
        except OSError as e:
            rep.errors.append(f"{path.name}: {e.strerror or e}")
            continue
        setattr(rep, outcome, getattr(rep, outcome) + 1)
        if rep.seen % 50 == 0:
            conn.commit()
    conn.commit()
    return rep