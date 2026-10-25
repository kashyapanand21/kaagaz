"""Kaagaz UI. Run from the repo root:  kaagaz ui   (or: streamlit run ui/app.py)

A thin layer over the tested `kaagaz` package. Every button calls the same code as the CLI.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # so `import uikit` works however it's launched

import streamlit as st

st.set_page_config(page_title="Kaagaz", page_icon="🦥", layout="wide", initial_sidebar_state="auto")

import store  # noqa: E402
import uikit  # noqa: E402
from screens import library, new_packet, packets, review, settings, welcome  # noqa: E402

uikit.inject_css()

# ── First run: no folders yet → welcome screen only ───────────────────────────
if store.needs_onboarding():
    welcome.render()
    st.stop()

# ── Navigation ─────────────────────────────────────────────────────────────────
c = store.counts()
n_review = c.get("needs_review", 0)
review_title = f"Review ({n_review})" if n_review else "Review"

PAGES = {
    "library": st.Page(library.render, title="Library", icon=":material/folder_open:", default=True),
    "review": st.Page(review.render, title=review_title, icon=":material/rate_review:", url_path="review"),
    "new_packet": st.Page(new_packet.render, title="New packet", icon=":material/auto_fix_high:", url_path="new-packet"),
    "packets": st.Page(packets.render, title="Packets", icon=":material/inventory_2:", url_path="packets"),
    "settings": st.Page(settings.render, title="Settings & privacy", icon=":material/shield_lock:", url_path="settings"),
}
st.session_state["pages"] = PAGES
page = st.navigation(list(PAGES.values()), position="sidebar")

# ── Sidebar footer ─────────────────────────────────────────────────────────────
s = store.settings()
logo = uikit.asset("sloth_logo.png") or uikit.asset("sloth.png")
if logo:
    st.logo(str(logo), size="large")
with st.sidebar:
    st.markdown(
        "<div style='margin-top:.6rem'><div style='font-family:Georgia,\"Palatino Linotype\",serif;"
        "font-size:1.5rem;font-weight:600;color:#FFFDF8'>Kaagaz</div><div style='font-size:.78rem;opacity:.8'>Offline document assistant</div></div>",
        unsafe_allow_html=True)
    st.markdown(
        "<div style='margin-top:1rem;display:inline-flex;gap:.45rem;align-items:center;padding:.3rem .75rem;"
        "border-radius:999px;background:rgba(255,255,255,.10);font-size:.78rem'>"
        "<span class='kz-dot' style='background:#7CD3A0'></span>Offline · local only</div>",
        unsafe_allow_html=True)
    if s.profile.name:
        st.markdown(f"<div style='margin-top:.8rem;font-size:.85rem'><b>{uikit.esc(s.profile.name)}</b>"
                    f"<br><span style='opacity:.75'>Roll {uikit.esc(s.profile.roll or '–')}</span></div>",
                    unsafe_allow_html=True)

# ── Top status bar (every page) ────────────────────────────────────────────────
problems = store.model_problems()
labelled = c.get("indexed", 0)
dot = "#2E8B57" if not problems else "#C0392B"
model_txt = f"{s.models.vision} ready on this laptop" if not problems else "local AI not reachable"
chips = [f"<span class='kz-chip'><span class='kz-dot' style='background:{dot}'></span>"
         f"Offline · {uikit.esc(model_txt)}</span>",
         f"<span class='kz-chip'>📚 {uikit.plural(labelled, 'document')} labelled</span>"]
if n_review:
    chips.append(f"<span class='kz-chip' style='border-color:#F3C77D;background:#FFF4E0'>⚑ {n_review} to review</span>")
if c.get("pending"):
    chips.append(f"<span class='kz-chip'>… {c['pending']} not read yet</span>")
st.markdown(f"<div style='display:flex;gap:.5rem;flex-wrap:wrap;justify-content:flex-end;margin-bottom:.6rem'>"
            f"{''.join(chips)}</div>", unsafe_allow_html=True)
if problems:
    uikit.banner("<b>The local AI isn't running.</b> Start the Ollama app, then try again. "
                 "Work pauses; nothing is lost.<br>" + "<br>".join(uikit.esc(p) for p in problems), "bad")

page.run()
