"""Look and feel: theme CSS, badges, cards, previews, small OS helpers.

Everything here is offline: no web fonts, no CDN, no remote images.
Fonts are system fonts (Georgia for headings, Segoe UI + Nirmala UI for body and Hindi).
"""
from __future__ import annotations

import base64
import html
import io
import os
import subprocess
import sys
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).parent / "assets"

# ── Palette: ink teal + marigold saffron + paper cream ────────────────────────
INK, INK_DARK, INK_TINT = "#0F4C5C", "#0A3642", "#E3EFF1"
SAFFRON, SAFFRON_DARK = "#F2A541", "#D98A1F"
PAPER, CARD, LINE = "#FBF6EC", "#FFFDF8", "#E6DFD0"
TEXT, MUTED = "#1E2A2F", "#5B6B70"
OK, WARN, BAD = "#2E8B57", "#B7791F", "#C0392B"

CSS = f"""
:root {{
  --ink:{INK}; --ink-d:{INK_DARK}; --ink-t:{INK_TINT};
  --saf:{SAFFRON}; --saf-d:{SAFFRON_DARK};
  --paper:{PAPER}; --card:{CARD}; --line:{LINE};
  --text:{TEXT}; --muted:{MUTED}; --ok:{OK}; --warn:{WARN}; --bad:{BAD};
  --sh: 0 1px 2px rgba(15,76,92,.05), 0 4px 10px rgba(30,42,47,.06), 0 16px 28px -14px rgba(30,42,47,.16);
  --sh-hi: 0 2px 4px rgba(15,76,92,.07), 0 10px 22px rgba(30,42,47,.10), 0 26px 40px -16px rgba(30,42,47,.22);
  --serif: Georgia, "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
  --sans: "Segoe UI", "Nirmala UI", system-ui, -apple-system, Roboto, "Noto Sans", "Noto Sans Devanagari", sans-serif;
}}
html, body, .stApp, .stMarkdown, button, input, textarea, select {{ font-family: var(--sans); }}
.stApp {{
  background:
    radial-gradient(1200px 500px at 85% -10%, rgba(242,165,65,.10), transparent 60%),
    radial-gradient(900px 500px at -10% 110%, rgba(15,76,92,.07), transparent 60%),
    var(--paper);
  color: var(--text);
}}
.block-container {{ max-width: 1240px; padding-top: 1.2rem; padding-bottom: 4rem; }}
h1, h2, h3, .kz-serif {{ font-family: var(--serif) !important; color: var(--ink) !important; letter-spacing: -.01em; }}
h1 {{ font-weight: 600 !important; }}

/* ── Sidebar ───────────────────────────────────────── */
section[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, {INK} 0%, {INK_DARK} 100%);
  box-shadow: 4px 0 18px rgba(10,54,66,.18);
}}
section[data-testid="stSidebar"] * {{ color: #EAF2F2; }}
section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"] {{ border-radius: 10px; margin: 2px 0; }}
section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"][aria-current="page"],
section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"]:hover {{
  background: rgba(255,255,255,.10); box-shadow: inset 0 1px 0 rgba(255,255,255,.12);
}}

/* ── Raised paper cards: any container whose key starts with "card" ───── */
div[class*="st-key-card"] {{
  background: var(--card); border: 1px solid var(--line); border-radius: 16px;
  box-shadow: var(--sh), inset 0 1px 0 rgba(255,255,255,.9);
  padding: 16px 18px; transition: transform .18s ease, box-shadow .18s ease;
}}
div[class*="st-key-card"]:hover {{ transform: translateY(-3px); box-shadow: var(--sh-hi), inset 0 1px 0 rgba(255,255,255,.9); }}
div[class*="st-key-cardteal"] {{ background: linear-gradient(160deg, {INK} 0%, {INK_DARK} 100%); border-color: {INK_DARK}; }}
div[class*="st-key-cardteal"] * {{ color: #F4EFE4 !important; }}
div[class*="st-key-cardteal"] code {{ background: rgba(255,255,255,.14) !important; color: #FFE3B0 !important; }}

/* ── Buttons: raised, pressable ─────────────────────── */
.stButton > button, .stDownloadButton > button, div[data-testid="stFormSubmitButton"] > button {{
  border-radius: 11px; border: 1px solid var(--line); background: var(--card); color: var(--ink);
  box-shadow: 0 2px 0 rgba(10,54,66,.12), 0 4px 10px rgba(30,42,47,.06), inset 0 1px 0 #fff;
  transition: transform .08s ease, box-shadow .08s ease; font-weight: 600;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{ border-color: var(--ink); color: var(--ink); }}
.stButton > button:active, .stDownloadButton > button:active {{
  transform: translateY(2px); box-shadow: 0 0 0 rgba(0,0,0,0), inset 0 2px 4px rgba(10,54,66,.15);
}}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"],
div[data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"] {{
  background: linear-gradient(180deg, #156177 0%, {INK} 100%); color: #fff; border-color: {INK_DARK};
  box-shadow: 0 3px 0 {INK_DARK}, 0 8px 16px rgba(15,76,92,.25), inset 0 1px 0 rgba(255,255,255,.22);
}}
.stButton > button[kind="primary"]:hover {{ color: #fff; filter: brightness(1.06); }}
button:focus-visible, input:focus-visible, textarea:focus-visible {{ outline: 3px solid var(--saf) !important; outline-offset: 2px; }}
div[data-testid="stProgress"] div[role="progressbar"] > div > div {{ background: linear-gradient(90deg, {SAFFRON}, {SAFFRON_DARK}); }}

/* ── Inputs ─────────────────────────────────────────── */
div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] > div {{
  background: #FFFEFA; border-radius: 10px; box-shadow: inset 0 1px 3px rgba(30,42,47,.06);
}}

/* ── Small components ───────────────────────────────── */
.kz-eyebrow {{ font-size: .72rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }}
.kz-sub {{ color: var(--muted); margin-top: -.4rem; }}
.kz-chip {{ display:inline-flex; align-items:center; gap:.45rem; padding:.3rem .8rem; border-radius:999px;
  background: var(--card); border:1px solid var(--line); font-size:.82rem; color: var(--text);
  box-shadow: 0 1px 2px rgba(15,76,92,.06); }}
.kz-dot {{ width:.55rem; height:.55rem; border-radius:50%; display:inline-block; }}
.kz-badge {{ display:inline-flex; align-items:center; gap:.3rem; padding:.16rem .6rem; border-radius:999px;
  font-size:.72rem; font-weight:700; letter-spacing:.04em; white-space:nowrap; }}
.kz-muted {{ color: var(--muted); font-size: .86rem; }}
.kz-small {{ font-size: .8rem; color: var(--muted); }}
.kz-title {{ font-family: var(--serif); color: var(--ink); font-size: 1.05rem; font-weight: 600; line-height: 1.25; }}
.kz-thumb {{ width:100%; height:150px; object-fit:cover; border-radius:10px; background:#EFE8DA;
  box-shadow: inset 0 1px 3px rgba(0,0,0,.06); display:block; }}
.kz-thumb.empty {{ display:flex; align-items:center; justify-content:center; font-size:2.2rem; }}
.kz-preview {{ width:100%; max-height:560px; object-fit:contain; border-radius:12px; background:#F3EDE0;
  box-shadow: 0 6px 18px rgba(30,42,47,.10); }}
.kz-hero {{ display:flex; gap:1.2rem; align-items:center; }}
.kz-mascot {{ width:84px; height:84px; flex:0 0 84px; border-radius:20px; display:flex; align-items:center;
  justify-content:center; font-size:2.6rem; background: linear-gradient(160deg, #FFF7E6, #F6E5C4);
  box-shadow: 0 3px 0 rgba(217,138,31,.35), 0 10px 20px rgba(30,42,47,.10), inset 0 1px 0 #fff; }}
.kz-mascot img {{ width:84px; height:84px; object-fit:contain; }}
.kz-banner {{ border-radius:14px; padding:.85rem 1.1rem; margin:.4rem 0 1rem; border:1px solid; }}
.kz-banner.warn {{ background:#FDF3E1; border-color:#F0D29A; color:#6B4710; }}
.kz-banner.bad {{ background:#FBE7E3; border-color:#EFB9AF; color:#7A2418; }}
.kz-banner.ok {{ background:#E6F2EA; border-color:#B8DAC5; color:#1D5A39; }}
.kz-banner.info {{ background:var(--ink-t); border-color:#BFD8DD; color:var(--ink-d); }}
.kz-steps {{ display:flex; gap:.5rem; flex-wrap:wrap; margin:.2rem 0 1.2rem; }}
.kz-step {{ flex:1 1 140px; display:flex; align-items:center; gap:.6rem; padding:.55rem .8rem; border-radius:12px;
  background: var(--card); border:1px solid var(--line); color: var(--muted); font-weight:600; font-size:.9rem; }}
.kz-step .n {{ width:1.7rem; height:1.7rem; border-radius:50%; display:flex; align-items:center; justify-content:center;
  background:#EFE8DA; color:var(--muted); font-size:.85rem; flex:0 0 auto; }}
.kz-step.done {{ color: var(--ink); }}
.kz-step.done .n {{ background: var(--ink); color:#fff; }}
.kz-step.active {{ background: #FFF1D9; border-color: #F3C77D; color: #6B4710;
  box-shadow: 0 3px 0 rgba(217,138,31,.35), 0 8px 18px rgba(242,165,65,.25); }}
.kz-step.active .n {{ background: var(--saf); color: #3A2600; }}
.kz-kv {{ display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:.55rem 1rem; }}
.kz-kv div span {{ display:block; font-size:.72rem; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; }}
.kz-kv div b {{ font-weight:600; color:var(--text); }}
.kz-mono {{ font-family: Consolas, "Cascadia Mono", ui-monospace, monospace; font-size:.85rem; }}
@media (max-width: 640px) {{
  .block-container {{ padding: .8rem .8rem 3rem; }}
  h1 {{ font-size: 1.6rem !important; }}
  .kz-hero {{ flex-direction: column; align-items: flex-start; }}
  .kz-kv {{ grid-template-columns: 1fr; }}
  .kz-thumb {{ height: 190px; }}
}}
"""


def inject_css() -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value))


# ── Status badges: always text + symbol + colour, never colour alone ─────────
_BADGES = {
    "PASS": ("✓ PASS", OK, "#E3F1E8"),
    "OK": ("✓ OK", OK, "#E3F1E8"),
    "MATCHED": ("✓ MATCHED", OK, "#E3F1E8"),
    "INDEXED": ("✓ LABELLED", OK, "#E3F1E8"),
    "WARN": ("! WARN", WARN, "#FBEFD9"),
    "CHECK_DATE": ("? CHECK DATE", WARN, "#FBEFD9"),
    "REVIEW": ("⚑ NEEDS REVIEW", "#8A5A12", "#FFE9C2"),
    "PENDING": ("… NOT READ YET", MUTED, "#EFE8DA"),
    "FAIL": ("✕ FAIL", BAD, "#F8E1DD"),
    "EXPIRED": ("✕ EXPIRED", BAD, "#F8E1DD"),
    "MISSING": ("✕ MISSING", BAD, "#F8E1DD"),
    "FAILED": ("✕ UNREADABLE", BAD, "#F8E1DD"),
}


def badge(key: str) -> str:
    text, fg, bg = _BADGES.get(key.upper(), (key.upper(), MUTED, "#EFE8DA"))
    return f'<span class="kz-badge" style="color:{fg};background:{bg};border:1px solid {fg}33">{esc(text)}</span>'


def banner(text: str, kind: str = "info") -> None:
    st.markdown(f'<div class="kz-banner {kind}">{text}</div>', unsafe_allow_html=True)


def header(eyebrow: str, title: str, subtitle: str | None = None) -> None:
    st.markdown(f'<div class="kz-eyebrow">{esc(eyebrow)}</div>', unsafe_allow_html=True)
    st.markdown(f"# {title}")
    if subtitle:
        st.markdown(f'<p class="kz-sub">{subtitle}</p>', unsafe_allow_html=True)


def stepper(active: int) -> None:
    names = ["Paste rules", "Checklist", "Match files", "Build & verify"]
    parts = []
    for i, name in enumerate(names, 1):
        cls = "done" if i < active else "active" if i == active else ""
        mark = "✓" if i < active else str(i)
        parts.append(f'<div class="kz-step {cls}"><span class="n">{mark}</span>{name}</div>')
    st.markdown(f'<div class="kz-steps">{"".join(parts)}</div>', unsafe_allow_html=True)


# ── Mascot: your 3D sloth PNGs if present in ui/assets, else a clay-style emoji tile ──
def asset(name: str) -> Path | None:
    p = ASSETS / name
    return p if p.exists() else None


def mascot_html(kind: str = "hero", emoji: str = "🦥") -> str:
    p = asset(f"sloth_{kind}.png") or asset("sloth.png")
    if p:
        b64 = base64.b64encode(p.read_bytes()).decode()
        return f'<div class="kz-mascot"><img alt="Kaagaz sloth" src="data:image/png;base64,{b64}"/></div>'
    return f'<div class="kz-mascot" aria-hidden="true">{emoji}</div>'


def hero(title: str, body: str, kind: str = "hero", emoji: str = "🦥") -> None:
    st.markdown(
        f'<div class="kz-hero">{mascot_html(kind, emoji)}<div>'
        f'<div class="kz-serif" style="font-size:1.45rem;font-weight:600;line-height:1.25">{title}</div>'
        f'<div class="kz-muted" style="margin-top:.25rem">{body}</div></div></div>',
        unsafe_allow_html=True,
    )


# ── Image previews (all local; resized before embedding) ───────────────────────
@st.cache_data(show_spinner=False, max_entries=512)
def _b64_file(path: str, mtime: float) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode()


@st.cache_data(show_spinner=False, max_entries=64)
def _b64_preview(path: str, mtime: float, long_side: int) -> str | None:
    """Page 1 of any supported file (PDF, JPG, PNG, HEIC, WEBP), rendered locally."""
    try:
        from kaagaz.engine.render import render
        data = render(Path(path), long_side).images[0]
    except Exception:
        try:
            from PIL import Image, ImageOps
            with Image.open(path) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((long_side, long_side))
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=85)
                data = buf.getvalue()
        except Exception:
            return None
    return base64.b64encode(data).decode()


def thumb_html(thumb: str | None, emoji: str = "📄", height: int | None = None) -> str:
    style = f' style="height:{height}px;font-size:{max(16, height // 3)}px"' if height else ""
    if thumb and Path(thumb).exists():
        b64 = _b64_file(thumb, Path(thumb).stat().st_mtime)
        return f'<img class="kz-thumb" alt=""{style} src="data:image/jpeg;base64,{b64}"/>'
    return f'<div class="kz-thumb empty" aria-hidden="true"{style}>{emoji}</div>'


def preview_html(path: str, long_side: int = 1000) -> str:
    p = Path(path)
    if not p.exists():
        return '<div class="kz-banner bad">This file is no longer in that folder. Scan again.</div>'
    b64 = _b64_preview(str(p), p.stat().st_mtime, long_side)
    if not b64:
        return '<div class="kz-banner warn">Preview not available for this file.</div>'
    return f'<img class="kz-preview" alt="Document preview" src="data:image/jpeg;base64,{b64}"/>'


# ── Labels and formatting ──────────────────────────────────────────────────────
_NICE = {
    "marksheet_10": "Class 10 marksheet", "marksheet_12": "Class 12 marksheet",
    "pan": "PAN card", "aadhaar": "Aadhaar", "voter_id": "Voter ID", "ews_certificate": "EWS certificate",
    "photo": "Passport photo", "id_last4": "ID",
}
EMOJI = {
    "Education": "🎓", "Certificates": "📜", "Identity": "🪪", "Finance": "🏦",
    "Photo & signature": "🖋️", "Other": "📄",
}
GROUPS = {
    "Education": ["marksheet_10", "marksheet_12", "semester_marksheet", "degree_certificate",
                  "provisional_certificate", "migration_certificate", "transfer_certificate", "admit_card"],
    "Certificates": ["caste_certificate", "income_certificate", "domicile_certificate", "ews_certificate",
                     "disability_certificate", "character_certificate"],
    "Identity": ["aadhaar", "pan", "voter_id", "passport", "driving_licence"],
    "Finance": ["bank_passbook", "cancelled_cheque", "fee_receipt"],
    "Photo & signature": ["photo", "signature", "thumb_impression"],
    "Other": ["resume", "offer_letter", "other"],
}


def nice(doc_type: str | None) -> str:
    if not doc_type:
        return "Not read yet"
    return _NICE.get(doc_type, doc_type.replace("_", " ").capitalize())


def group_of(doc_type: str | None) -> str:
    for g, types in GROUPS.items():
        if doc_type in types:
            return g
    return "Other"


def kb(n: int | float | None) -> str:
    return f"{(n or 0) / 1000:.1f} KB"


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


# ── OS helpers (Windows first, with fallbacks) ─────────────────────────────────
def open_path(path: str | Path) -> None:
    path = str(path)
    if sys.platform.startswith("win"):
        os.startfile(path)  # noqa: S606 - local file the user owns
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def reveal(path: str | Path) -> None:
    """Open the folder with the file selected (Explorer on Windows)."""
    p = Path(path)
    if sys.platform.startswith("win"):
        subprocess.Popen(["explorer", "/select,", str(p)])
    else:
        open_path(p.parent)


def pick_folder() -> str | None:
    """Native folder dialog via tkinter. Returns None if unavailable or cancelled."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)
        chosen = filedialog.askdirectory(master=root, title="Choose a folder for Kaagaz to read")
        root.destroy()
        return chosen or None
    except Exception:
        return None
