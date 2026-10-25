"""Settings & privacy: folders, profile, model status, privacy facts, delete-all."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

import store
from uikit import banner, esc, header, pick_folder


def render() -> None:
    s = store.settings()
    header("Your setup", "Settings & privacy",
           f"Saved to <span class='kz-mono'>{esc(store.config_path().resolve())}</span>")
    st.session_state.setdefault("st_folders", [str(f) for f in s.folders])

    left, right = st.columns([7, 5], gap="large")

    with left:
        # ── Folders ───────────────────────────────────────────────────────────
        with st.container(key="card-folders"):
            st.markdown("### Folders Kaagaz reads")
            st.markdown("<p class='kz-small'>Read-only. Kaagaz never changes, moves or deletes your files. "
                        "Its own Packets folder is always skipped.</p>", unsafe_allow_html=True)
            folders = st.session_state.st_folders
            for i, f in enumerate(list(folders)):
                a, b = st.columns([8, 1], vertical_alignment="center")
                ok = Path(f).is_dir()
                a.markdown(f"<span class='kz-mono'>{'📁' if ok else '⚠️ not found:'} {esc(f)}</span>",
                           unsafe_allow_html=True)
                if b.button("✕", key=f"st_rm{i}", help="Stop reading this folder"):
                    folders.pop(i)
                    st.rerun()
            new = st.text_input("Add a folder", placeholder=r"C:\Users\you\Documents", key="st_new",
                                label_visibility="collapsed")
            a, b = st.columns(2)
            if a.button("Add folder", icon=":material/create_new_folder:", key="st_add", width="stretch"):
                _add(new)
            if b.button("Browse…", icon=":material/folder_open:", key="st_browse", width="stretch"):
                chosen = pick_folder()
                _add(chosen) if chosen else st.toast("Paste the folder path instead.")

        # ── Profile ───────────────────────────────────────────────────────────
        with st.container(key="card-profile"):
            st.markdown("### Profile")
            name = st.text_input("Name, as printed on your documents", value=s.profile.name, key="st_name",
                                 help="Used to prefer your documents over family members'.")
            roll = st.text_input("Roll / registration number", value=s.profile.roll, key="st_roll",
                                 help="Used in output file names, e.g. 12345_Photograph.jpg")
            if st.button("Save settings", type="primary", icon=":material/save:", key="st_save"):
                valid = [f for f in st.session_state.st_folders if Path(f).is_dir()]
                try:
                    store.save_settings(valid, name, roll)
                    st.cache_data.clear()
                    st.toast("Saved. Press Scan folders in the Library to pick up new folders.", icon="✅")
                except Exception as e:
                    banner(f"Couldn't save: {esc(e)}", "bad")

        # ── Danger zone ───────────────────────────────────────────────────────
        with st.container(key="card-danger"):
            st.markdown("### Delete all Kaagaz data")
            st.markdown("<p class='kz-small'>Removes Kaagaz's database, thumbnails and saved checklists from "
                        f"<span class='kz-mono'>{esc(s.data_dir)}</span>. <b>Your original documents and built "
                        "packets are not touched.</b></p>", unsafe_allow_html=True)
            sure = st.checkbox("I understand Kaagaz will need to read my folders again.", key="st_sure")
            if st.button("Delete all Kaagaz data", key="st_delete", disabled=not sure, icon=":material/delete:"):
                removed = store.delete_all_data()
                banner("Deleted: " + esc(", ".join(removed) or "nothing to delete") + ".", "ok")

    with right:
        # ── Model ─────────────────────────────────────────────────────────────
        with st.container(key="card-model"):
            st.markdown("### Local AI")
            problems = store.model_problems()
            if problems:
                banner("✕ <b>Not reachable.</b><br>" + "<br>".join(esc(p) for p in problems), "bad")
            else:
                banner(f"✓ <b>{esc(s.models.vision)}</b> is pulled and ready.", "ok")
            st.markdown(
                "<div class='kz-kv'>"
                f"<div><span>Model</span><b class='kz-mono'>{esc(s.models.vision)}</b></div>"
                f"<div><span>Runs at</span><b class='kz-mono'>{esc(s.models.host)}</b></div>"
                f"<div><span>Context</span><b>{s.models.num_ctx:,} tokens</b></div>"
                f"<div><span>Kept loaded</span><b>{esc(s.models.keep_alive)}</b></div>"
                f"<div><span>Image size sent</span><b>{s.thresholds.image_long_side} px</b></div>"
                f"<div><span>Review below</span><b>{round(s.thresholds.escalate_below * 100)}% confidence</b></div>"
                "</div>", unsafe_allow_html=True)
            if st.button("Check again", icon=":material/refresh:", key="st_recheck"):
                store.model_problems.clear()
                st.rerun()

        # ── Privacy ───────────────────────────────────────────────────────────
        with st.container(key="cardteal-privacy"):
            st.markdown("### 🔒 Privacy, in plain words")
            st.markdown(
                f"- **Only network connection:** `{esc(s.models.host)}`, the model on this laptop. "
                "Kaagaz refuses to start if it's pointed anywhere else.\n"
                "- **Usage statistics:** off. This app only listens on `127.0.0.1`.\n"
                "- **ID numbers:** stored as the last 4 digits only, enforced in code.\n"
                "- **Your files:** never changed, moved or deleted. Outputs go to a separate Packets folder.\n"
                "- **Uploads:** none. You upload the files to the portal yourself.")


def _add(path: str | None) -> None:
    path = (path or "").strip().strip('"')
    if not path:
        return
    if not Path(path).is_dir():
        st.toast(f"Folder not found: {path}")
        return
    if path not in st.session_state.st_folders:
        st.session_state.st_folders.append(path)
    st.rerun()
