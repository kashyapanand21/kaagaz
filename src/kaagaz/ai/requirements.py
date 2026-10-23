from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from kaagaz.ai.client import CallInfo, chat_json
from kaagaz.schemas import DocType, Format, RequirementItem

MAX_CHARS = 12_000
NUMERIC = ("min_kb", "max_kb", "width_px", "height_px", "width_cm", "height_cm", "dpi")


class ParsedItem(BaseModel):
    # Every key is REQUIRED in the schema sent to Ollama (null still allowed), so the model must
    # consider each field instead of skipping it. Python defaults stay, for tests.
    model_config = ConfigDict(json_schema_extra=lambda s, _: s.update(required=list(s["properties"])))
    label: str = Field(description="Short name of the document, e.g. 'Class 12 Marksheet'")
    source: str = Field(description="The exact sentence(s) from the instructions this item comes from, copied word for word")
    doc_types: list[DocType] = Field(description="Every document type that would satisfy this item")
    formats: list[Format]
    min_kb: int | None = Field(None, description="Minimum size in KB, only if stated (1 MB = 1000 KB)")
    max_kb: int | None = Field(None, description="Maximum size in KB, only if stated (1 MB = 1000 KB)")
    width_px: int | None = None
    height_px: int | None = None
    width_cm: float | None = Field(None, description="Width in cm if given in cm or mm (mm / 10)")
    height_cm: float | None = Field(None, description="Height in cm if given in cm or mm (mm / 10)")
    dpi: int | None = None
    background: Literal["white", "light", "any"] = "any"
    pages: Literal["single", "merge_all", "first_only"] = "single"
    name_pattern: str | None = Field(None, description="File name rule using {roll} {name} {doctype} {date}, only if stated")
    issued_after: date | None = Field(None, description="Only if the document must be issued on or after a stated date")
    mandatory: bool = True
    unsure: list[str] = Field(default_factory=list, description="Names of fields you had to guess")


class Checklist(BaseModel):
    items: list[ParsedItem]


SYSTEM = """You turn the document-upload section of an Indian online form into a checklist.
Rules:
- One item per document the applicant must UPLOAD. Ignore details that are typed into the form.
- Copy limits exactly as written. Never invent a limit; if it is not stated, use null.
- Sizes go in KB (1 MB = 1000 KB). Pixel sizes go in width_px/height_px. Sizes in cm go in
  width_cm/height_cm; sizes in mm are divided by 10 into cm.
- formats: only pdf, jpg, png. JPEG means jpg.
- doc_types: every allowed type that satisfies the item. Use "other" only if nothing fits.
- pages: "merge_all" if front and back or all pages must be in one file, "first_only" if only the
  first page, otherwise "single".
- background: "white" if a white background is required, "light" if a light one, else "any".
- name_pattern: if a file name rule is given anywhere, apply it to EVERY item, written with
  {roll}, {name}, {doctype}, {date}. Example: "RollNo_DocumentName" -> "{roll}_{doctype}".
- Fill every stated limit: both min_kb and max_kb for a range, width and height, background.
- issued_after: only if the document must be issued on or after a stated date (YYYY-MM-DD).
- mandatory: false only if the text says optional or "if applicable".
- source: copy the instruction sentence(s) for this item word for word.
- unsure: list any field you had to guess."""

def _numbers(text: str) -> set[float]:
    return {float(x) for x in re.findall(r"\d+(?:\.\d+)?", text)}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _grounded(field: str, value: float, nums: set[float]) -> bool:
    if field.endswith("_kb"):
        candidates = (value, value / 1000, value / 1024)   # 200 KB ↔ 0.2 MB
    elif field.endswith("_cm"):
        candidates = (value, value * 10)                    # 3.5 cm ↔ 35 mm
    else:
        candidates = (value,)
    return any(abs(c - n) < 0.011 for c in candidates for n in nums)

_UNIT = r"(kb|mb|cm|mm|px|pixels?|dpi)\b"
_STATED = re.compile(rf"(\d+(?:\.\d+)?)\s*{_UNIT}", re.I)
_RANGE = re.compile(rf"(\d+(?:\.\d+)?)\s*(?:-|–|to|and|x|×)\s*(\d+(?:\.\d+)?)\s*{_UNIT}", re.I)
UNIT_FIELDS = {"kb": ("min_kb", "max_kb"), "mb": ("min_kb", "max_kb"),
               "cm": ("width_cm", "height_cm"), "mm": ("width_cm", "height_cm"),
               "px": ("width_px", "height_px"), "dpi": ("dpi",)}


def _stated(source: str) -> list[tuple[float, str]]:
    """Numbers with units in the source: '20 KB to 50 KB', '3.5 x 4.5 cm', '0.3 MB'."""
    found = [(float(v), u) for v, u in _STATED.findall(source)]
    for a, b, u in _RANGE.findall(source):
        found += [(float(a), u), (float(b), u)]
    return [(v, "px" if u.lower().startswith("pixel") else u.lower()) for v, u in found]


def _missed(source: str, data: dict) -> set[str]:
    """Fields for stated numbers that no returned value accounts for."""
    missed: set[str] = set()
    for value, unit in _stated(source):
        fields = UNIT_FIELDS[unit]
        if not any(data[f] is not None and _grounded(f, data[f], {value}) for f in fields):
            missed |= {f for f in fields if data[f] is None} or set(fields)
    return missed


def to_requirement(p: ParsedItem, text: str) -> RequirementItem:
    unsure = set(p.unsure)
    data = p.model_dump(exclude={"source", "unsure"})

    nums = _numbers(p.source)
    quoted = bool(p.source) and _norm(p.source) in _norm(text)
    if not quoted:
        unsure.add("label")               # not a real quote; check against the whole text
        nums |= _numbers(text)

    for f in NUMERIC:
        v = data[f]
        if v is None:
            continue
        if v <= 0:
            data[f] = None
            unsure.add(f)
        elif not _grounded(f, v, nums):
            unsure.add(f)                 # number not found in the instructions

    if data["min_kb"] and data["max_kb"] and data["min_kb"] > data["max_kb"]:
        data["min_kb"], data["max_kb"] = data["max_kb"], data["min_kb"]
        unsure |= {"min_kb", "max_kb"}
    for a, b in (("width_px", "height_px"), ("width_cm", "height_cm")):
        if (data[a] is None) != (data[b] is None):
            data[a] = data[b] = None
            unsure |= {a, b}
    if not data["doc_types"]:
        data["doc_types"] = [DocType.OTHER]
        unsure.add("doc_types")
    if not data["formats"]:
        data["formats"] = ["pdf", "jpg"]
        unsure.add("formats")

    if quoted:                            # coverage is only trustworthy against a real quote
        unsure |= _missed(p.source, data)
    return RequirementItem(**data, uncertain_fields=sorted(unsure))

def parse_requirements(text: str) -> tuple[list[RequirementItem], CallInfo]:
    text = text.strip()[:MAX_CHARS]
    result, info = chat_json(Checklist, SYSTEM, f'Instructions:\n"""\n{text}\n"""')
    if result is None:
        return [], info
    return [to_requirement(p, text) for p in result.items], info