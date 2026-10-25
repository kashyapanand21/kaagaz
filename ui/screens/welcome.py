"""First run: check the local AI, choose folders + profile, start reading."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

import jobs
import store
from uikit import banner, esc, hero, pick_folder


def render() -> None:
    s = store.settings()
    st.session_state.setdefault("wel_folders", [str(f) for f in s.folders])

    st.markdown("<div class='kz-eyebrow'>First-time setup · takes 2 minutes</div>", unsafe_allow_html=True)
    hero("Welcome to Kaagaz.",
         "Your documents, ready for any form. Offline. Kaagaz reads the folders you choose, learns which "
         "file is your marksheet, certificate or signature, and prepares upload-ready files to each "
         "portal's exact rules. Nothing leaves this laptop.", kind="hero")
    st.write("")

    c1, c2, c3 = st.columns(3, gap="medium")

    # ── 1. Local AI ───────────────────────────────────────────────────────────
    with c1, st.container(key="card-w1"):
        st.markdown("<div class='kz-eyebrow'>Step 1</div><h3>Local AI</h3>", unsafe_allow_html=True)
        problems = store.model_problems()
        if not problems:
            banner(f"✓ <b>Gemma 4 is ready</b><br><span class='kz-mono'>{esc(s.models.vision)}</span> "
                   "via Ollama on this laptop.", "ok")
        else:
            banner("✕ <b>Not ready yet.</b><br>" + "<br>".join(esc(p) for p in problems), "bad")
            st.code(f"ollama pull {s.models.vision}", language=None)
        st.markdown("<p class='kz-small'>The only network connection Kaagaz makes is to "
                    f"<span class='kz-mono'>{esc(s.models.host)}</span>, the model on your own machine.</p>",
                    unsafe_allow_html=True)
        if st.button("Check again", icon=":material/refresh:", key="w_recheck"):
            store.model_problems.clear()
            st.rerun()

    # ── 2. Folders + profile ──────────────────────────────────────────────────
    with c2, st.container(key="card-w2"):
        st.markdown("<div class='kz-eyebrow'>Step 2</div><h3>Your folders</h3>", unsafe_allow_html=True)
        st.markdown("<p class='kz-small'>Kaagaz only reads these folders. It never changes, moves or "
                    "deletes your files.</p>", unsafe_allow_html=True)
        for i, f in enumerate(list(st.session_state.wel_folders)):
            a, b = st.columns([6, 1], vertical_alignment="center")
            ok = Path(f).is_dir()
            a.markdown(f"<span class='kz-mono'>{'📁' if ok else '⚠️'} {esc(f)}</span>", unsafe_allow_html=True)
            if b.button("✕", key=f"w_rm{i}", help="Remove"):
                st.session_state.wel_folders.pop(i)
                st.rerun()
        new = st.text_input("Folder path", placeholder=r"e.g. C:\Users\you\Downloads", key="w_new",
                            label_visibility="collapsed")
        a, b = st.columns(2)
        if a.button("Add folder", icon=":material/create_new_folder:", key="w_add", width="stretch"):
            _add(new)
        if b.button("Browse…", icon=":material/folder_open:", key="w_browse", width="stretch"):
            chosen = pick_folder()
            if chosen:
                _add(chosen)
            else:
                st.toast("Paste the folder path instead (the folder picker isn't available here).")
        st.markdown("<h4 style='margin-top:.6rem'>About you</h4>", unsafe_allow_html=True)
        st.text_input("Your name, as printed on documents", value=s.profile.name, key="w_name",
                      help="Used to pick your documents when family documents are mixed in.")
        st.text_input("Roll / registration number", value=s.profile.roll, key="w_roll",
                      help="Used in file names, e.g. 12345_Photograph.jpg")

    # ── 3. Start ──────────────────────────────────────────────────────────────
    with c3, st.container(key="card-w3"):
        st.markdown("<div class='kz-eyebrow'>Step 3</div><h3>Start reading</h3>", unsafe_allow_html=True)
        st.markdown("<p>The sloth reads each document slowly and privately: about <b>2 seconds per "
                    "document</b> on a 6 GB GPU. You can close the laptop; it resumes next time.</p>",
                    unsafe_allow_html=True)
        n = len(st.session_state.wel_folders)
        st.markdown(f"<p class='kz-small'>{n} folder{'s' if n != 1 else ''} chosen.</p>", unsafe_allow_html=True)
        start = st.button("Start", type="primary", icon=":material/arrow_forward:", key="w_start",
                          width="stretch", disabled=not n)
        later = st.button("Save and read later", key="w_later", width="stretch", disabled=not n)

    if start or later:
        folders = [f for f in st.session_state.wel_folders if Path(f).is_dir()]
        if not folders:
            banner("None of those folders exist. Check the paths.", "bad")
            return
        store.save_settings(folders, st.session_state.w_name, st.session_state.w_roll)
        st.cache_data.clear()
        jobs.run_scan()
        if start and not store.model_problems():
            jobs.run_label()
        st.session_state.pop("wel_folders", None)
        st.button("Open my library", type="primary", icon=":material/arrow_forward:", key="w_go")


def _add(path: str) -> None:
    path = (path or "").strip().strip('"')
    if not path:
        return
    if not Path(path).is_dir():
        st.toast(f"Folder not found: {path}")
        return
    if path not in st.session_state.wel_folders:
        st.session_state.wel_folders.append(path)
    st.rerun()
