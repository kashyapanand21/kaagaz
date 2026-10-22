from __future__ import annotations

import re
import unicodedata
from datetime import date
from string import Formatter

from kaagaz.schemas import DocType

DEFAULT_PATTERN = "{roll}_{doctype}"
RESERVED = {"CON", "PRN", "AUX", "NUL",
            *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def doctype_label(t: DocType) -> str:
    return "".join(part.capitalize() for part in t.value.split("_"))


def clean(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    text = re.sub(r"_{2,}", "_", text)
    return text.strip("._- ")

def _tokens(pattern: str) -> list[tuple[str, str | None]]:
    return [(literal, field) for literal, field, _, _ in Formatter().parse(pattern)]


def render_name(pattern: str | None, ext: str, *, doctype: DocType, name: str = "",
                roll: str = "", today: date | None = None,
                max_len: int | None = None) -> tuple[str, list[str]]:
    """Returns (filename, warnings)."""
    values = {"name": name, "roll": roll, "doctype": doctype_label(doctype),
              "date": (today or date.today()).strftime("%d%m%Y")}
    warnings: list[str] = []

    try:
        tokens = _tokens(pattern or DEFAULT_PATTERN)
    except ValueError:
        warnings.append(f"name pattern {pattern!r} is malformed; used {DEFAULT_PATTERN}")
        tokens = _tokens(DEFAULT_PATTERN)

    parts: list[str] = []
    for literal, field in tokens:
        parts.append(literal)
        if field is None:
            continue
        value = values.get(field.lower())
        if value is None:
            warnings.append(f"unknown token {{{field}}} in name pattern; left out")
        elif not value:
            warnings.append(f"no value for {{{field}}}; left out (set it in your profile)")
        else:
            parts.append(value)

    stem = clean("".join(parts)) or values["doctype"]
    if stem.upper() in RESERVED:
        stem += "_file"
    ext = "." + ext.lower().lstrip(".")
    if max_len and len(stem) + len(ext) > max_len:
        stem = stem[: max(1, max_len - len(ext))].rstrip("._-")
        warnings.append(f"name shortened to {max_len} characters")
    return stem + ext, warnings

def unique(filename: str, taken: set[str]) -> str:
    """Make `filename` unique within `taken` (case-insensitive, like Windows), and record it."""
    stem, _, ext = filename.rpartition(".")
    candidate, n = filename, 2
    while candidate.lower() in taken:
        candidate = f"{stem}_{n}.{ext}"
        n += 1
    taken.add(candidate.lower())
    return candidate