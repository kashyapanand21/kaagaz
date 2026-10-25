"""Data access for the UI. Thin wrappers over the tested kaagaz package; no business logic here."""
from __future__ import annotations

import json
import os
import re
import shutil
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Iterator

import streamlit as st

from kaagaz.config import get_settings, load_settings
from kaagaz.db import connect
from kaagaz.db import counts as _counts


def settings():
    return get_settings()


def config_path() -> Path:
    return Path(os.environ.get("KAAGAZ_CONFIG", "config.toml"))


@contextmanager
def db() -> Iterator:
    conn = connect(settings().db_path)
    try:
        yield conn
    finally:
        conn.close()


def counts() -> dict[str, int]:
    with db() as conn:
        return _counts(conn)


# ── Library ───────────────────────────────────────────────────────────────────
_SYNONYMS = {"xii": "12", "x": "10", "sign": "signature", "pic": "photo", "photograph": "photo",
             "marks": "marksheet", "mark": "marksheet", "cert": "certificate", "passbook": "passbook"}


def _words(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[\wऀ-ॿ]+", text.lower()):
        w = re.sub(r"^(\d+)(st|nd|rd|th)$", r"\1", w)        # 12th -> 12
        out.append(_SYNONYMS.get(w, w))
    return out


def documents(query: str = "", types: list[str] | None = None, status: str | None = None) -> list[dict]:
    """Filter in SQL, then plain-word search in Python ('12th marksheet', 'my signature', 'income 2026')."""
    from uikit import nice
    sql = "SELECT * FROM documents WHERE 1=1"
    args: list = []
    if status:
        sql += " AND status = ?"
        args.append(status)
    if types:
        sql += f" AND doc_type IN ({','.join('?' * len(types))})"
        args += types
    sql += " ORDER BY CASE status WHEN 'needs_review' THEN 0 WHEN 'indexed' THEN 1 ELSE 2 END, updated_at DESC"
    with db() as conn:
        rows = [dict(r) for r in conn.execute(sql, args)]
    wanted = [w for w in _words(query) if w not in {"my", "the", "a", "of", "latest", "find", "where", "is"}]
    if not wanted:
        return rows
    hits = []
    for r in rows:
        hay = " ".join(_words(" ".join(str(r.get(k) or "") for k in
                                       ("doc_type", "person_name", "issuer", "summary", "year", "path"))
                              + " " + nice(r.get("doc_type"))))
        if all(w in hay for w in wanted):
            hits.append(r)
    return hits


def document(doc_id: int) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None


CONFIRMED = "confirmed by you"


def confirm_label(doc_id: int, doc_type: str, person_name: str | None = None) -> None:
    """A human confirmed (or corrected) the type. The label is now trusted."""
    with db() as conn:
        conn.execute(
            "UPDATE documents SET status='indexed', doc_type=?, person_name=coalesce(?, person_name), "
            "model=?, error=NULL, raw=NULL, updated_at=datetime('now') WHERE id=?",
            (doc_type, person_name or None, CONFIRMED, doc_id))
        conn.commit()


def review_queue() -> list[dict]:
    return documents(status="needs_review")


def validity_of(doc: dict, today: date | None = None):
    """Validity for a library card (no portal rule). None if the type is unknown."""
    from kaagaz.packets.validity import check_validity
    from kaagaz.schemas import DocType
    try:
        return check_validity(
            DocType(doc["doc_type"]),
            issue_date=date.fromisoformat(doc["issue_date"]) if doc.get("issue_date") else None,
            valid_until=date.fromisoformat(doc["valid_until"]) if doc.get("valid_until") else None,
            year=doc.get("year"), today=today)
    except Exception:
        return None


# ── Model health (cached briefly so every rerun doesn't ping Ollama) ──────────
@st.cache_data(ttl=20, show_spinner=False)
def model_problems() -> list[str]:
    try:
        from kaagaz.ai.client import health
        return health()
    except Exception as e:  # never let the header crash the app
        return [f"Couldn't check the local AI: {e}"]


# ── Settings (written back to config.toml) ────────────────────────────────────
def _q(value: object) -> str:
    return json.dumps(str(value))  # JSON strings are valid TOML basic strings (handles \ in Windows paths)


def save_settings(folders: list[str], name: str, roll: str) -> Path:
    s = settings()
    m, t = s.models, s.thresholds
    lines = ["# Written by the Kaagaz app. Safe to edit by hand.",
             "folders = [" + ", ".join(_q(f) for f in folders) + "]", "",
             "[models]", f"vision = {_q(m.vision)}"]
    if m.escalation:
        lines.append(f"escalation = {_q(m.escalation)}")
    if m.embed:
        lines.append(f"embed = {_q(m.embed)}")
    lines += [f"host = {_q(m.host)}", f"keep_alive = {_q(m.keep_alive)}", f"num_ctx = {int(m.num_ctx)}", "",
              "[thresholds]",
              f"escalate_below = {t.escalate_below}", f"review_below = {t.review_below}",
              f"image_long_side = {t.image_long_side}", f"min_file_kb = {t.min_file_kb}",
              f"max_file_mb = {t.max_file_mb}", "",
              "[profile]", f"name = {_q(name.strip())}", f"roll = {_q(roll.strip())}", ""]
    path = config_path()
    text = "\n".join(lines)
    tmp = path.with_suffix(".toml.tmp")
    tmp.write_text(text, encoding="utf-8")
    load_settings(tmp)          # validate before replacing (e.g. the localhost-only host rule)
    tmp.replace(path)
    get_settings.cache_clear()
    return path


def needs_onboarding() -> bool:
    return not settings().folders


# ── Saved checklists ──────────────────────────────────────────────────────────
def checklists_dir() -> Path:
    d = settings().data_dir / "checklists"
    d.mkdir(parents=True, exist_ok=True)
    return d


def saved_checklists() -> list[Path]:
    return sorted(checklists_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


# ── Packets on disk ───────────────────────────────────────────────────────────
def packets() -> list[dict]:
    root = settings().packets_dir
    if not root.exists():
        return []
    found = []
    for d in root.iterdir():
        mf = d / "manifest.json"
        if d.is_dir() and mf.exists():
            try:
                data = json.loads(mf.read_text(encoding="utf-8"))
            except Exception:
                continue
            data["dir"] = d
            found.append(data)
    return sorted(found, key=lambda p: p.get("built_at", ""), reverse=True)


# ── Delete everything Kaagaz made (never the originals) ───────────────────────
def delete_all_data() -> list[str]:
    s = settings()
    removed = []
    for p in [s.db_path, Path(str(s.db_path) + "-wal"), Path(str(s.db_path) + "-shm")]:
        if p.exists():
            p.unlink()
            removed.append(p.name)
    for d in [s.thumbs_dir, s.data_dir / "checklists"]:
        if d.exists():
            shutil.rmtree(d)
            removed.append(d.name + "/")
    st.cache_data.clear()
    return removed
