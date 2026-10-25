"""New packet: paste portal rules → editable checklist → match files → build & verify."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

import jobs
import store
from uikit import GROUPS, badge, banner, esc, header, hero, kb, nice, open_path, stepper, thumb_html

ALL_TYPES = [t for ts in GROUPS.values() for t in ts]
SPECIMEN = Path("samples/instructions/nsp_specimen.txt")


def _state() -> dict:
    return st.session_state.setdefault("np", {"step": 1, "name": "", "text": "", "items": None,
                                              "choices": {}, "result": None, "parse": None})


def _go(step: int) -> None:
    _state()["step"] = step
    st.rerun()


def render() -> None:
    np = _state()
    header("New packet", "Get every file ready for one form",
           "Paste the portal's upload rules. Kaagaz makes a checklist, picks your files, "
           "converts them to the exact limits and measures every output.")
    stepper(np["step"])
    {1: _paste, 2: _checklist, 3: _match, 4: _result}[np["step"]](np)


# ── Step 1: paste ───────────────────────────────────────────────────────────────
def _paste(np: dict) -> None:
    with st.container(key="card-paste"):
        np["name"] = st.text_input("Packet name", value=np["name"] or "NSP Scholarship 2026",
                                   help="Becomes the folder name, e.g. NSP_Scholarship_2026_20261025-2130")
        if SPECIMEN.exists() and st.button("Use the specimen NSP rules", icon=":material/description:",
                                           key="np_specimen", type="tertiary"):
            st.session_state.np_text = SPECIMEN.read_text(encoding="utf-8")
        text = st.text_area("Paste the “Documents to upload” section from the portal", key="np_text",
                            height=260, placeholder="1. Recent passport size photograph, white background, "
                                                    "3.5 cm x 4.5 cm, JPG, 20 KB to 50 KB …")
        a, b = st.columns([1, 1], vertical_alignment="bottom")
        make = a.button("Make checklist", type="primary", icon=":material/arrow_forward:",
                        disabled=not (text or "").strip(), key="np_make", width="stretch")
        saved = store.saved_checklists()
        with b:
            if saved:
                pick = st.selectbox("Or load a saved checklist", saved, format_func=lambda p: p.stem,
                                    index=None, placeholder="Saved checklists…", key="np_saved")
                if pick and st.button("Use this checklist", key="np_load", width="stretch"):
                    from kaagaz.packets.checklist import load_checklist
                    np.update(items=load_checklist(pick), name=pick.stem.replace("_", " "), parse=None)
                    _go(2)

    if make:
        from kaagaz.ai.client import OllamaUnavailable
        from kaagaz.ai.requirements import parse_requirements
        from kaagaz.engine.naming import clean
        from kaagaz.packets.checklist import save_checklist
        try:
            with st.spinner("Gemma is reading the rules… about 15 seconds"):
                items, info = parse_requirements(text)
        except OllamaUnavailable as e:
            banner(f"The local AI isn't reachable: {esc(e)}", "bad")
            return
        if info.error or not items:
            banner(f"Gemma couldn't turn that into a checklist ({esc(info.error or 'no documents found')}). "
                   "Paste just the documents section and try again.", "bad")
            return
        save_checklist(items, store.checklists_dir() / f"{clean(np['name']) or 'checklist'}.json")
        np.update(items=items, choices={}, parse=(len(items), info.seconds))
        _go(2)


# ── Step 2: editable checklist ──────────────────────────────────────────────────
COLS = ["Required", "Document", "Check", "Types", "Format", "Min KB", "Max KB", "Width cm", "Height cm",
        "Width px", "Height px", "DPI", "Background", "Pages", "File name", "Issued after"]
FIELD = {"Min KB": "min_kb", "Max KB": "max_kb", "Width cm": "width_cm", "Height cm": "height_cm",
         "Width px": "width_px", "Height px": "height_px", "DPI": "dpi", "Background": "background",
         "Pages": "pages", "File name": "name_pattern", "Issued after": "issued_after",
         "Types": "doc_types", "Format": "formats", "Document": "label"}


def _to_df(items) -> pd.DataFrame:
    rows = []
    for it in items:
        rows.append({
            "Required": it.mandatory, "Document": it.label,
            "Types": ", ".join(t.value for t in it.doc_types), "Format": ", ".join(it.formats),
            "Min KB": it.min_kb, "Max KB": it.max_kb, "Width cm": it.width_cm, "Height cm": it.height_cm,
            "Width px": it.width_px, "Height px": it.height_px, "DPI": it.dpi,
            "Background": it.background, "Pages": it.pages, "File name": it.name_pattern or "",
            "Issued after": it.issued_after,
            "Check": ", ".join(k for k, v in FIELD.items() if v in it.uncertain_fields),
        })
    df = pd.DataFrame(rows, columns=COLS)
    for c in ["Min KB", "Max KB", "Width px", "Height px", "DPI", "Width cm", "Height cm"]:
        df[c] = pd.to_numeric(df[c])
    df["Issued after"] = pd.to_datetime(df["Issued after"])
    return df


def _num(v, cast=int):
    return None if v is None or pd.isna(v) else cast(v)


def _from_df(df: pd.DataFrame):
    from kaagaz.schemas import RequirementItem
    items, errors = [], []
    for i, r in df.iterrows():
        try:
            ia = r["Issued after"]
            items.append(RequirementItem(
                label=str(r["Document"]).strip() or f"Document {i + 1}",
                doc_types=[t.strip() for t in str(r["Types"]).split(",") if t.strip()],
                formats=[f.strip().lower().replace("jpeg", "jpg") for f in str(r["Format"]).split(",") if f.strip()],
                min_kb=_num(r["Min KB"]), max_kb=_num(r["Max KB"]),
                width_cm=_num(r["Width cm"], float), height_cm=_num(r["Height cm"], float),
                width_px=_num(r["Width px"]), height_px=_num(r["Height px"]), dpi=_num(r["DPI"]),
                background=r["Background"] or "any", pages=r["Pages"] or "single",
                name_pattern=(str(r["File name"]).strip() or None) if r["File name"] is not None else None,
                issued_after=None if ia is None or pd.isna(ia) else pd.Timestamp(ia).date(),
                mandatory=bool(r["Required"]),
            ))
        except Exception as e:
            msg = str(e).split("\n")
            errors.append(f"Row {i + 1} ({esc(r['Document'])}): {esc(msg[1] if len(msg) > 1 else msg[0])}")
    return items, errors


def _checklist(np: dict) -> None:
    items = np["items"]
    if np.get("parse"):
        n, secs = np["parse"]
        banner(f"Gemma read the rules on this laptop and found <b>{n} documents</b> in {secs:.1f} s.", "ok")
    flagged = [it.label for it in items if it.uncertain_fields]
    if flagged:
        banner(f"⚑ Kaagaz highlighted <b>{len(flagged)}</b> row{'s' if len(flagged) != 1 else ''} to check "
               f"(see the <b>Check</b> column): {esc(', '.join(flagged))}. Every cell is editable.", "warn")
    else:
        banner("Every limit was found in the portal text. Check the rows, edit anything, then find your files.",
               "info")

    with st.container(key="card-checklist"):
        df = st.data_editor(
            _to_df(items), key="np_editor", hide_index=True, num_rows="dynamic", width="stretch",
            column_config={
                "Required": st.column_config.CheckboxColumn(width="small"),
                "Document": st.column_config.TextColumn(width="medium", required=True),
                "Types": st.column_config.TextColumn(help="Accepted types, comma-separated: "
                                                          + ", ".join(ALL_TYPES)),
                "Format": st.column_config.TextColumn(help="pdf, jpg, png", width="small"),
                "Min KB": st.column_config.NumberColumn(min_value=1, step=1, width="small"),
                "Max KB": st.column_config.NumberColumn(min_value=1, step=1, width="small"),
                "Width cm": st.column_config.NumberColumn(min_value=0.1, step=0.1, format="%.1f", width="small"),
                "Height cm": st.column_config.NumberColumn(min_value=0.1, step=0.1, format="%.1f", width="small"),
                "Width px": st.column_config.NumberColumn(min_value=1, step=1, width="small"),
                "Height px": st.column_config.NumberColumn(min_value=1, step=1, width="small"),
                "DPI": st.column_config.NumberColumn(min_value=1, step=1, width="small"),
                "Background": st.column_config.SelectboxColumn(options=["any", "white", "light"], width="small"),
                "Pages": st.column_config.SelectboxColumn(options=["single", "merge_all", "first_only"]),
                "File name": st.column_config.TextColumn(help="Tokens: {roll} {name} {doctype} {date}"),
                "Issued after": st.column_config.DateColumn(format="DD MMM YYYY"),
                "Check": st.column_config.TextColumn("⚑ Check", disabled=True,
                                                     help="Fields Kaagaz couldn't confirm from the text"),
            })

    a, b, c = st.columns([1, 1, 2])
    if a.button("Back", icon=":material/arrow_back:", key="np_back1", width="stretch"):
        _go(1)
    new_items, errors = _from_df(df)
    if b.button("Save checklist", icon=":material/bookmark_add:", key="np_save", width="stretch",
                disabled=bool(errors)):
        from kaagaz.engine.naming import clean
        from kaagaz.packets.checklist import save_checklist
        p = store.checklists_dir() / f"{clean(np['name']) or 'checklist'}.json"
        save_checklist(new_items, p)
        st.toast(f"Saved as “{p.stem}”. Load it next time from step 1.", icon="✅")
    if c.button("Find my files", type="primary", icon=":material/arrow_forward:", key="np_find",
                width="stretch", disabled=bool(errors) or not new_items):
        np.update(items=new_items, choices={})
        _go(3)
    for e in errors:
        banner(e, "bad")


# ── Step 3: match ───────────────────────────────────────────────────────────────
def _spec(it) -> str:
    bits = ["/".join(f.upper() for f in it.formats)]
    if it.min_kb and it.max_kb:
        bits.append(f"{it.min_kb}–{it.max_kb} KB")
    elif it.max_kb:
        bits.append(f"≤ {it.max_kb} KB")
    elif it.min_kb:
        bits.append(f"≥ {it.min_kb} KB")
    if it.width_cm and it.height_cm:
        bits.append(f"{it.width_cm:g} × {it.height_cm:g} cm")
    if it.width_px and it.height_px:
        bits.append(f"{it.width_px} × {it.height_px} px")
    if it.background != "any":
        bits.append(f"{it.background} background")
    if it.pages == "merge_all":
        bits.append("all pages in one file")
    if it.pages == "first_only":
        bits.append("first page only")
    if it.issued_after:
        bits.append(f"issued on/after {it.issued_after:%d %b %Y}")
    if not it.mandatory:
        bits.append("optional")
    return " · ".join(bits)


def _match(np: dict) -> None:
    from kaagaz.packets.matcher import match_items
    s = store.settings()
    with store.db() as conn:
        matches = match_items(conn, np["items"], s.profile.name, date.today())
    pools = []
    for i, m in enumerate(matches):
        pools.append([m.best, *m.alternatives] if m.best else [])   # matcher's own ranking, best first
        jobs.apply_choice(m, np["choices"].get(i, 0), s.profile.name)

    tally = {k: sum(m.status == k for m in matches) for k in ("matched", "check_date", "expired", "missing")}
    parts = [f"<b>{tally['matched']} ready</b>"]
    if tally["check_date"]:
        parts.append(f"{tally['check_date']} to check")
    if tally["expired"]:
        parts.append(f"{tally['expired']} expired")
    if tally["missing"]:
        parts.append(f"{tally['missing']} missing")
    bad = tally["expired"] + tally["missing"]
    banner(" · ".join(parts) + (". Fix these before you start the form." if bad else ". Ready to build."),
           "bad" if bad else "warn" if tally["check_date"] else "ok")

    for i, m in enumerate(matches):
        with st.container(key=f"card-match-{i}"):
            a, b, c = st.columns([5, 4, 4], gap="medium", vertical_alignment="center")
            with a:
                st.markdown(f"{badge(m.status.upper())}<div class='kz-title' style='margin-top:.35rem'>"
                            f"{esc(m.item.label)}</div><div class='kz-small'>{esc(_spec(m.item))}</div>",
                            unsafe_allow_html=True)
            with b:
                if m.best:
                    doc = store.document(m.best.id) or {}
                    st.markdown(
                        f"<div style='display:flex;gap:.7rem;align-items:center'>"
                        f"<div style='width:64px;flex:0 0 64px'>{thumb_html(doc.get('thumb'), height=64)}</div>"
                        f"<div style='min-width:0'><div class='kz-mono' style='overflow:hidden;text-overflow:ellipsis;"
                        f"white-space:nowrap'>{esc(m.best.path.name)}</div>"
                        f"<div class='kz-small'>{esc(nice(m.best.doc_type.value))}"
                        f"{' · ' + esc(m.best.person_name) if m.best.person_name else ''}"
                        f"{' · ' + str(m.best.year) if m.best.year else ''}</div></div></div>",
                        unsafe_allow_html=True)
                else:
                    st.markdown("<div class='kz-banner bad' style='margin:0'>No matching document in your "
                                "library. Add it to a watched folder and scan.</div>", unsafe_allow_html=True)
            with c:
                pool = pools[i]
                if len(pool) > 1:
                    current = np["choices"].get(i, 0)
                    pick = st.selectbox(
                        f"{len(pool) - 1} other file{'s' if len(pool) != 2 else ''} found", range(len(pool)),
                        index=current, key=f"np_alt_{i}",
                        format_func=lambda k, pool=pool: (f"{pool[k].path.name} · "
                                                          f"{pool[k].validity.status.replace('_', ' ')}"
                                                          + (" (Kaagaz's pick)" if k == 0 else "")))
                    if pick != current:
                        np["choices"][i] = pick
                        st.rerun()
                for note in m.notes:
                    st.markdown(f"<div class='kz-small'>• {esc(note)}</div>", unsafe_allow_html=True)

    st.write("")
    a, b = st.columns([1, 3])
    if a.button("Back", icon=":material/arrow_back:", key="np_back2", width="stretch"):
        _go(2)
    if b.button("Build packet", type="primary", icon=":material/construction:", key="np_build", width="stretch",
                disabled=not any(m.best for m in matches)):
        with st.spinner("Converting, compressing and measuring every file…"):
            np["result"] = jobs.build(np["items"], np["name"] or "packet", np["choices"])
        _go(4)


# ── Step 4: results ─────────────────────────────────────────────────────────────
def _result(np: dict) -> None:
    out_dir, rows, secs = np["result"]
    built = [r for r in rows if r.output]
    ready = sum(r.status in ("PASS", "WARN") for r in rows)
    with st.container(key="card-built"):
        hero(f"Built {len(built)} file{'s' if len(built) != 1 else ''} in {secs:.1f} s.",
             "Every file was re-opened and measured against the portal's rules. "
             "<b>Kaagaz never uploads anything.</b> You upload these files yourself.", kind="built", emoji="📦")

    trs = []
    for r in rows:
        why = "<br>".join(esc(x) for x in r.reasons)
        trs.append(
            f"<tr><td><b>{esc(r.label)}</b></td><td class='kz-mono'>{esc(r.source or '–')}</td>"
            f"<td class='kz-mono'>{esc(r.output or '–')}</td>"
            f"<td>{kb(r.size_bytes) if r.size_bytes else '–'}</td><td>{badge(r.status)}"
            f"{'<div class=kz-small style=margin-top:.3rem>' + why + '</div>' if why else ''}</td></tr>")
    st.markdown(
        "<div style='overflow-x:auto'><table style='width:100%;border-collapse:separate;border-spacing:0 6px'>"
        "<thead><tr style='text-align:left' class='kz-eyebrow'><th>Requirement</th><th>Picked file</th>"
        "<th>Output</th><th>Measured</th><th>Check</th></tr></thead><tbody>"
        + "".join(trs) + "</tbody></table></div>"
        "<style>tbody tr{background:#FFFDF8;box-shadow:0 1px 3px rgba(30,42,47,.06)}"
        "tbody td{padding:.65rem .7rem;vertical-align:top;border-top:1px solid #E6DFD0;border-bottom:1px solid #E6DFD0}"
        "tbody td:first-child{border-left:1px solid #E6DFD0;border-radius:12px 0 0 12px}"
        "tbody td:last-child{border-right:1px solid #E6DFD0;border-radius:0 12px 12px 0}"
        "th{padding:.2rem .7rem}</style>", unsafe_allow_html=True)

    todo = len(rows) - ready
    banner(f"<b>{ready} of {len(rows)} ready.</b>" + (f" Fix {todo} before you start the form." if todo else ""),
           "warn" if todo else "ok")

    a, b, c, d = st.columns(4)
    if a.button("Open packet folder", type="primary", icon=":material/folder_open:", key="np_open", width="stretch"):
        open_path(out_dir)
    md = Path(out_dir) / "checklist.md"
    if md.exists():
        b.download_button("Download checklist", md.read_bytes(), file_name="checklist.md", mime="text/markdown",
                          icon=":material/download:", key="np_dl", width="stretch")
    if c.button("Change files", icon=":material/swap_horiz:", key="np_back3", width="stretch"):
        _go(3)
    if d.button("New packet", icon=":material/add:", key="np_new", width="stretch"):
        st.session_state.pop("np", None)
        st.session_state.pop("np_text", None)
        st.rerun()
    st.markdown(f"<p class='kz-small kz-mono' style='margin-top:.6rem;word-break:break-all'>{esc(out_dir)}</p>",
                unsafe_allow_html=True)
