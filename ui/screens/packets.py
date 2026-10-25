"""Packets: every packet built so far, read from each folder's manifest.json."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st

import jobs
import store
from uikit import badge, banner, esc, header, hero, open_path


def render() -> None:
    header("Packets", "Your packets",
           "Each packet is a normal folder on this laptop with the files, a checklist.md and a manifest.json.")
    found = store.packets()
    if not found:
        with st.container(key="card-nopackets"):
            hero("No packets yet.",
                 "Go to <b>New packet</b>, paste a portal's document rules, and Kaagaz prepares every file.",
                 kind="empty", emoji="🗂️")
        if st.button("Create a packet", type="primary", icon=":material/add:", key="pk_new"):
            st.switch_page(st.session_state["pages"]["new_packet"])
        return

    for i, p in enumerate(found):
        rows = p.get("rows", [])
        ready = sum(r["status"] in ("PASS", "WARN") for r in rows)
        try:
            when = datetime.fromisoformat(p.get("built_at", "")).strftime("%d %b %Y, %H:%M")
        except ValueError:
            when = "–"
        with st.container(key=f"card-pk-{i}"):
            a, b = st.columns([3, 2], vertical_alignment="center")
            with a:
                st.markdown(
                    f"<div class='kz-eyebrow'>{esc(when)}</div>"
                    f"<div class='kz-title' style='font-size:1.3rem'>{esc(p.get('name', p['dir'].name))}</div>"
                    f"<div class='kz-small'>{ready} of {len(rows)} ready</div>"
                    f"<div style='margin-top:.5rem;display:flex;gap:.35rem;flex-wrap:wrap'>"
                    + "".join(f"<span title='{esc(r['label'])}'>{badge(r['status'])}</span>" for r in rows)
                    + "</div>", unsafe_allow_html=True)
                with st.expander("Rows"):
                    for r in rows:
                        why = "; ".join(r.get("reasons") or [])
                        st.markdown(f"{badge(r['status'])} <b>{esc(r['label'])}</b> → "
                                    f"<span class='kz-mono'>{esc(r.get('output') or '–')}</span>"
                                    f"{'<div class=kz-small>' + esc(why) + '</div>' if why else ''}",
                                    unsafe_allow_html=True)
            with b:
                c1, c2 = st.columns(2)
                if c1.button("Open folder", icon=":material/folder_open:", key=f"pk_open_{i}", width="stretch"):
                    open_path(p["dir"])
                can_rebuild = (Path(p["dir"]) / "checklist.json").exists()
                if c2.button("Rebuild", type="primary", icon=":material/refresh:", key=f"pk_re_{i}",
                             width="stretch", disabled=not can_rebuild,
                             help="Builds a fresh packet with the same checklist and today's library."
                             if can_rebuild else "Built before rebuild support; make it again from New packet."):
                    from kaagaz.packets.checklist import load_checklist
                    with st.spinner("Rebuilding…"):
                        out_dir, new_rows, secs = jobs.build(load_checklist(Path(p["dir"]) / "checklist.json"),
                                                             p.get("name", "packet"))
                    n = sum(r.status in ("PASS", "WARN") for r in new_rows)
                    banner(f"Rebuilt in {secs:.1f} s: <b>{n} of {len(new_rows)} ready</b>.", "ok")
                    st.button("Refresh list", key=f"pk_refresh_{i}")
