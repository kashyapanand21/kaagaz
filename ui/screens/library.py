"""Library (home): scan, label, search and browse documents."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import streamlit as st

import jobs
import store
from uikit import (EMOJI, GROUPS, badge, banner, esc, group_of, hero, kb, nice, open_path,
                   preview_html, reveal, thumb_html)

PAGE = 24
ALL_TYPES = [t for ts in GROUPS.values() for t in ts]


def render() -> None:
    c = store.counts()
    pending = c.get("pending", 0)

    # ── Action card ───────────────────────────────────────────────────────────
    with st.container(key="card-hero"):
        left, right = st.columns([3, 2], vertical_alignment="center")
        with left:
            hero("The sloth reads your folders, slowly and privately.",
                 "Gemma 4 runs on this laptop. Works with Wi-Fi off. "
                 f"{'<b>' + str(pending) + ' new files</b> waiting to be read.' if pending else 'Everything found so far is read.'}")
        with right:
            a, b = st.columns(2)
            scan = a.button("Scan folders", icon=":material/search:", width="stretch", key="lib_scan",
                            help="Find new or changed files (fast; no AI).")
            label = b.button(f"Read {pending} new" if pending else "Read new files", type="primary",
                             icon=":material/document_scanner:", width="stretch", key="lib_label",
                             disabled=not pending)
        if scan:
            jobs.run_scan()
        if label:
            jobs.run_label()
            st.button("Refresh library", icon=":material/refresh:", key="lib_refresh")

    # ── Search + filters ──────────────────────────────────────────────────────
    st.write("")
    query = st.text_input("Search", placeholder="Search: 12th marksheet, income certificate, my signature, 2026…",
                          key="lib_q", label_visibility="collapsed", icon=":material/search:")
    all_docs = store.documents()
    by_group: dict[str, int] = {}
    for d in all_docs:
        if d["status"] in ("indexed", "needs_review"):
            by_group[group_of(d["doc_type"])] = by_group.get(group_of(d["doc_type"]), 0) + 1
    n_review = sum(d["status"] == "needs_review" for d in all_docs)
    options = ["All", *[g for g in GROUPS if by_group.get(g)], *(["Needs review"] if n_review else [])]
    chosen = st.pills("Filter", options, default="All", key="lib_filter", label_visibility="collapsed",
                      format_func=lambda o: f"⚑ Needs review · {n_review}" if o == "Needs review"
                      else f"All · {len(all_docs)}" if o == "All" else f"{EMOJI[o]} {o} · {by_group[o]}")

    types = GROUPS.get(chosen) if chosen in GROUPS else None
    status = "needs_review" if chosen == "Needs review" else None
    docs = store.documents(query, types, status)

    if not all_docs:
        _empty()
        return
    if not docs:
        banner("No document matches that search. Try fewer words, e.g. <b>marksheet</b> or <b>2026</b>.", "info")
        return

    # ── Grid ──────────────────────────────────────────────────────────────────
    limit = st.session_state.get("lib_limit", PAGE)
    today = date.today()
    cols_per_row = 4
    shown = docs[:limit]
    for start in range(0, len(shown), cols_per_row):
        cols = st.columns(cols_per_row, gap="medium")
        for col, d in zip(cols, shown[start:start + cols_per_row]):
            with col:
                _card(d, today)
    if len(docs) > limit:
        if st.button(f"Show more ({len(docs) - limit} left)", key="lib_more"):
            st.session_state.lib_limit = limit + PAGE
            st.rerun()


def _card(d: dict, today: date) -> None:
    with st.container(key=f"card-doc-{d['id']}"):
        st.markdown(thumb_html(d.get("thumb"), EMOJI.get(group_of(d["doc_type"]), "📄")), unsafe_allow_html=True)
        badges = []
        if d["status"] == "needs_review":
            badges.append(badge("REVIEW"))
        elif d["status"] == "pending":
            badges.append(badge("PENDING"))
        elif d["status"] == "failed":
            badges.append(badge("FAILED"))
        else:
            v = store.validity_of(d, today)
            if v:
                badges.append(badge({"ok": "OK", "check_date": "CHECK_DATE", "expired": "EXPIRED"}[v.status]))
        who = " · ".join(str(x) for x in [d.get("person_name"), d.get("year")] if x)
        if d.get("model") == store.CONFIRMED:
            conf = "✓ Confirmed by you"
        elif d.get("confidence") is not None:
            conf = f"Gemma · {round((d['confidence'] or 0) * 100)}%"
        else:
            conf = ""
        st.markdown(
            f"<div style='margin-top:.6rem'>{' '.join(badges)}</div>"
            f"<div class='kz-title' style='margin-top:.35rem'>{esc(nice(d['doc_type']))}</div>"
            f"<div class='kz-small'>{esc(who) or '&nbsp;'}</div>"
            f"<div class='kz-small' style='margin-top:.2rem;overflow:hidden;text-overflow:ellipsis;"
            f"white-space:nowrap' title='{esc(Path(d['path']).name)}'>{esc(Path(d['path']).name)}</div>"
            f"<div class='kz-small' style='color:#0F4C5C'>{conf}</div>",
            unsafe_allow_html=True)
        if st.button("Details", key=f"lib_open_{d['id']}", width="stretch", icon=":material/visibility:"):
            details(d["id"])


@st.dialog("Document", width="large")
def details(doc_id: int) -> None:
    d = store.document(doc_id)
    if not d:
        st.write("This document was removed.")
        return
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown(preview_html(d["path"]), unsafe_allow_html=True)
    with right:
        st.markdown(f"<div class='kz-title' style='font-size:1.35rem'>{esc(nice(d['doc_type']))}</div>",
                    unsafe_allow_html=True)
        v = store.validity_of(d)
        if d["status"] == "needs_review":
            banner(f"⚑ Waiting for your check: {esc(d.get('error') or 'Gemma was unsure')}.", "warn")
        elif v and v.status != "ok":
            banner(esc(v.reason), "warn" if v.status == "check_date" else "bad")
        elif v and v.estimated:
            banner(esc(v.reason), "info")
        fields = [("Name", d.get("person_name")), ("Issuer", d.get("issuer")), ("Year", d.get("year")),
                  ("Issued", d.get("issue_date")), ("Valid until", d.get("valid_until")),
                  ("ID", f"XXXX {d['id_last4']}" if d.get("id_last4") else None),
                  ("Language", d.get("language")), ("Pages", d.get("pages")),
                  ("File size", kb(d.get("size_bytes")))]
        st.markdown("<div class='kz-kv'>" + "".join(
            f"<div><span>{k}</span><b>{esc(val) if val not in (None, '') else '–'}</b></div>" for k, val in fields)
            + "</div>", unsafe_allow_html=True)
        if d.get("summary"):
            st.markdown(f"<p class='kz-small' style='margin-top:.8rem'>{esc(d['summary'])}</p>", unsafe_allow_html=True)
        if d.get("model") == store.CONFIRMED:
            st.markdown("<p class='kz-small'>✓ Label confirmed by you.</p>", unsafe_allow_html=True)
        elif d.get("confidence") is not None:
            st.markdown(f"<p class='kz-small'>Labelled by <b>{esc(d.get('model') or 'Gemma')}</b> · confidence "
                        f"{round(d['confidence'] * 100)}% · {d.get('seconds') or 0:.1f} s · on this laptop</p>",
                        unsafe_allow_html=True)
        st.markdown(f"<p class='kz-small kz-mono' style='word-break:break-all'>{esc(d['path'])}</p>",
                    unsafe_allow_html=True)
        a, b = st.columns(2)
        if a.button("Open file", icon=":material/open_in_new:", width="stretch", key="d_open"):
            open_path(d["path"])
        if b.button("Show in folder", icon=":material/folder:", width="stretch", key="d_reveal"):
            reveal(d["path"])
        with st.expander("Fix the label"):
            current = d["doc_type"] if d["doc_type"] in ALL_TYPES else "other"
            new_type = st.selectbox("Document type", ALL_TYPES, index=ALL_TYPES.index(current), format_func=nice)
            new_name = st.text_input("Name on the document", value=d.get("person_name") or "")
            if st.button("Save label", type="primary", key="d_save"):
                store.confirm_label(doc_id, new_type, new_name)
                st.cache_data.clear()
                st.rerun()


def _empty() -> None:
    with st.container(key="card-empty"):
        hero("No documents yet.",
             "Press <b>Scan folders</b>, then <b>Read new files</b>. Add folders in "
             "<i>Settings &amp; privacy</i>.", kind="empty", emoji="🗂️")
