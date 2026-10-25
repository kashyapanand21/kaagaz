"""Long-running actions with live progress: scan folders, label with Gemma, build a packet."""
from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import streamlit as st

import store
from uikit import banner, esc, nice, plural

def run_scan(show: bool = True):
    from kaagaz.scan import scan
    with store.db() as conn:
        rep = scan(conn, store.settings())
    if show:
        msg = (f"Found {rep.seen} files: <b>{rep.new} new</b>, {rep.unchanged} unchanged, "
               f"{rep.moved} moved, {rep.duplicate} duplicate copies.")
        if rep.cloud_only:
            msg += (f"<br>Skipped {rep.cloud_only} OneDrive online-only files "
                    "(right-click → <i>Always keep on this device</i> to include them).")
        banner(msg, "ok" if rep.seen else "warn")
        for f in rep.missing_folders:
            banner(f"Folder not found: <span class='kz-mono'>{esc(f)}</span>", "warn")
        for e in rep.errors[:5]:
            banner(esc(e), "warn")
    return rep


def run_label(limit: int | None = None) -> dict:
    """Label pending documents one by one with a live progress bar. Safe to interrupt."""
    from kaagaz.ai.classify import classify_pending
    from kaagaz.ai.client import OllamaUnavailable
    from kaagaz.db import counts

    s = store.settings()
    result = {"done": 0, "indexed": 0, "review": 0, "failed": 0, "times": [], "paused": None}
    with store.db() as conn:
        total = counts(conn).get("pending", 0)
        if limit:
            total = min(total, limit)
        if not total:
            banner("Nothing new to read. Every document is already labelled.", "ok")
            return result
        bar = st.progress(0.0, text=f"The sloth is reading 0 of {total} · about 2 s each · "
                                    "you can stop anytime, it resumes")
        line = st.empty()
        try:
            for i, (row, out) in enumerate(classify_pending(conn, s, limit), 1):
                result["done"] = i
                if out.seconds:
                    result["times"].append(out.seconds)
                result[{"indexed": "indexed", "needs_review": "review"}.get(out.status, "failed")] += 1
                bar.progress(i / total, text=f"The sloth is reading {i} of {total} · about 2 s each")
                line.markdown(f"<span class='kz-small'>{esc(Path(row['path']).name)} → "
                              f"<b>{esc(nice(out.doc_type))}</b> · {out.seconds:.1f} s</span>",
                              unsafe_allow_html=True)
        except OllamaUnavailable as e:
            result["paused"] = str(e)
            result["detail"] = getattr(e, "detail", "")
    st.cache_data.clear()
    if result["paused"]:
        banner(f"<b>Paused.</b> {esc(result['paused'])} Nothing is lost; the rest stays queued.", "bad")
        if result.get("detail"):
            with st.expander("Technical details"):
                st.code(result["detail"], language=None)
    else:
        t = sorted(result["times"])
        p50 = f" · median {t[len(t) // 2]:.1f} s per document" if t else ""
        banner(f"Read {plural(result['done'], 'document')}: <b>{result['indexed']} labelled</b>, "
               f"{result['review']} sent to review, {result['failed']} unreadable{p50}.", "ok")
    return result

_ROW = {"ok": "matched", "check_date": "check_date", "expired": "expired"}


def apply_choice(match, choice: int, profile_name: str):
    """Use the alternative the person picked instead of Kaagaz's first choice."""
    from kaagaz.packets.matcher import name_score
    if not match.best or choice <= 0 or choice > len(match.alternatives):
        return match
    pool = [match.best, *match.alternatives]
    best = pool.pop(choice)
    match.best, match.alternatives = best, pool
    match.status = _ROW[best.validity.status]
    notes = []
    if best.validity.status != "ok" or best.validity.estimated:
        notes.append(best.validity.reason)
    if not best.confirmed:
        notes.append("label not confirmed yet (it's in the review queue)")
    if name_score(best.person_name, profile_name) < 0:
        notes.append("name on the document differs from your profile name")
    match.notes = notes
    return match


def build(items, name: str, choices: dict[int, int] | None = None):
    """Match → (apply the person's picks) → build → save the checklist next to the packet."""
    from kaagaz.packets.builder import build_packet
    from kaagaz.packets.checklist import save_checklist
    from kaagaz.packets.matcher import match_items

    s = store.settings()
    t0 = time.perf_counter()
    with store.db() as conn:
        matches = match_items(conn, items, s.profile.name, date.today())
    for i, m in enumerate(matches):
        apply_choice(m, (choices or {}).get(i, 0), s.profile.name)
    out_dir, rows = build_packet(matches, s, name)
    save_checklist(items, out_dir / "checklist.json")   # lets the Packets page rebuild it later
    return out_dir, rows, time.perf_counter() - t0
