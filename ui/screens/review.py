"""Review queue: confirm or fix the labels Gemma (or the code checks) weren't sure about."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

import store
from uikit import GROUPS, banner, esc, header, hero, nice, preview_html

ALL_TYPES = [t for ts in GROUPS.values() for t in ts]


def render() -> None:
    queue = store.review_queue()
    if not queue:
        header("Review", "All clear.")
        with st.container(key="card-done"):
            hero("Every document is labelled.",
                 "When Gemma is unsure about a file, it waits here for a quick look from you.",
                 kind="done", emoji="😌")
        return

    skipped: set[int] = st.session_state.setdefault("rv_skipped", set())
    remaining = [d for d in queue if d["id"] not in skipped]
    if not remaining:          # skipped everything: start the round again
        skipped.clear()
        remaining = queue
    d = remaining[0]
    pos = queue.index(d) + 1

    header("Review", f"{len(queue)} document{'s' if len(queue) != 1 else ''} need a quick look",
           f"Reviewing {pos} of {len(queue)} · your answer updates the library immediately, on this laptop.")

    with st.container(key=f"card-review-{d['id']}"):
        left, right = st.columns([3, 2], gap="large")
        with left:
            st.markdown(f"<div class='kz-small kz-mono' style='margin-bottom:.4rem'>📷 "
                        f"{esc(Path(d['path']).name)}</div>", unsafe_allow_html=True)
            st.markdown(preview_html(d["path"], 1100), unsafe_allow_html=True)
        with right:
            guess = d["doc_type"]
            conf = d.get("confidence")
            st.markdown("<div class='kz-eyebrow'>Gemma's guess</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='kz-title' style='font-size:1.6rem'>{esc(nice(guess))}</div>"
                        f"<div class='kz-small'>confidence {round((conf or 0) * 100)}%</div>",
                        unsafe_allow_html=True)
            reason = d.get("error") or "Gemma wasn't sure about this one."
            banner(f"⚑ <b>Why it's here:</b> {esc(_explain(reason))}", "warn")

            current = guess if guess in ALL_TYPES else "other"
            new_type = st.selectbox("Document type", ALL_TYPES, index=ALL_TYPES.index(current),
                                    format_func=nice, key=f"rv_type_{d['id']}")
            new_name = st.text_input("Name on the document (optional)", value=d.get("person_name") or "",
                                     key=f"rv_name_{d['id']}")
            a, b = st.columns([3, 2])
            if a.button("Confirm", type="primary", icon=":material/check_circle:", width="stretch",
                        key=f"rv_ok_{d['id']}", shortcut="Ctrl+Enter"):
                store.confirm_label(d["id"], new_type, new_name)
                st.cache_data.clear()
                st.toast(f"Saved: {nice(new_type)}", icon="✅")
                st.rerun()
            if b.button("Skip", width="stretch", key=f"rv_skip_{d['id']}", shortcut="Ctrl+Right"):
                skipped.add(d["id"])
                st.rerun()
            st.markdown("<p class='kz-small'>Shortcuts: <b>Ctrl+Enter</b> confirm · <b>Ctrl+→</b> skip</p>",
                        unsafe_allow_html=True)

    others = [x for x in queue if x["id"] != d["id"]]
    if others:
        st.markdown("<div class='kz-eyebrow' style='margin-top:1.2rem'>Up next</div>", unsafe_allow_html=True)
        for x in others[:5]:
            st.markdown(f"<span class='kz-chip'>⚑ {esc(nice(x['doc_type']))} · "
                        f"<span class='kz-mono'>{esc(Path(x['path']).name)}</span></span>", unsafe_allow_html=True)


def _explain(reason: str) -> str:
    if reason.startswith("type: other"):
        return "it doesn't look like any document type Kaagaz knows. Pick one, or keep 'Other'."
    if reason.startswith("low confidence"):
        return f"Gemma was unsure ({reason})."
    if reason.startswith("PDF text suggests"):
        return f"the label and the PDF's own text disagree ({reason})."
    if reason.startswith("invalid JSON") or reason.startswith("ollama error"):
        return "Gemma's answer couldn't be read. Please label it yourself."
    return reason
