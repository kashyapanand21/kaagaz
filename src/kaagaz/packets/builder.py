from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from PIL import Image

from kaagaz.config import Settings
from kaagaz.engine.cleanup import background_is_light, whiten_signature
from kaagaz.engine.facecrop import face_crop
from kaagaz.engine.naming import clean, render_name, unique
from kaagaz.engine.transform import (CannotFit, crop_to_aspect, fit_jpeg, fit_pdf, first_page_only,
                                     image_to_pdf, max_bytes_for, min_bytes_for, open_image,
                                     pdf_page_image, target_px)
from kaagaz.engine.validate import validate
from kaagaz.packets.matcher import Match
from kaagaz.schemas import DocType, RequirementItem

INK_TYPES = {DocType.SIGNATURE, DocType.THUMB_IMPRESSION}


@dataclass
class BuiltRow:
    label: str
    status: str                       # PASS / WARN / FAIL / MISSING / EXPIRED
    source: str = ""
    output: str = ""
    size_bytes: int = 0
    reasons: list[str] = field(default_factory=list)


def _make(src: Path, spec: RequirementItem, doc_type: DocType) -> tuple[bytes, str, int | None, list[str]]:
    """Returns (data, extension, raster_dpi, notes). Raises CannotFit."""
    notes: list[str] = []
    is_pdf = src.suffix.lower() == ".pdf"
    max_b = max_bytes_for(spec.max_kb) if spec.max_kb else None
    min_b = min_bytes_for(spec.min_kb) if spec.min_kb else None

    if "pdf" in spec.formats and (is_pdf or "jpg" not in spec.formats):
        if is_pdf:
            data = src.read_bytes()
            if spec.pages == "first_only":
                data = first_page_only(data)
        else:
            data = image_to_pdf(open_image(src))
        data, dpi = fit_pdf(data, max_b)
        return data, "pdf", dpi, notes

    img = pdf_page_image(src.read_bytes(), dpi=200) if is_pdf else open_image(src)
    if doc_type in INK_TYPES:
        img = whiten_signature(img)
    size = target_px(spec)
    if size:
        aspect = size[0] / size[1]
        if doc_type is DocType.PHOTO:
            fc = face_crop(img, aspect)
            img = fc.image
            if fc.warning:
                notes.append(fc.warning)
        else:
            img = crop_to_aspect(img, aspect)
        img = img.resize(size, Image.LANCZOS)
    if doc_type is DocType.PHOTO and spec.background == "white" and not background_is_light(img):
        notes.append("background doesn't look white; retake or edit the photo")
    return fit_jpeg(img, max_b, min_b, fixed_size=bool(size)), "jpg", None, notes

def build_packet(matches: list[Match], s: Settings, name: str) -> tuple[Path, list[BuiltRow]]:
    out_dir = s.packets_dir / f"{clean(name) or 'packet'}_{datetime.now():%Y%m%d-%H%M%S}"
    out_dir.mkdir(parents=True, exist_ok=True)
    taken: set[str] = set()
    rows: list[BuiltRow] = []

    for m in matches:
        spec = m.item
        if m.best is None:
            rows.append(BuiltRow(spec.label, "MISSING", reasons=m.notes))
            continue
        src = m.best.path
        if m.status == "expired":
            rows.append(BuiltRow(spec.label, "EXPIRED", src.name, reasons=m.notes))
            continue
        try:
            data, ext, dpi, notes = _make(src, spec, m.best.doc_type)
        except CannotFit as e:
            rows.append(BuiltRow(spec.label, "FAIL", src.name, reasons=[str(e)]))
            continue
        except Exception as e:                                 # unreadable source, etc.
            rows.append(BuiltRow(spec.label, "FAIL", src.name, reasons=[f"could not process: {e}"]))
            continue

        filename, name_warnings = render_name(spec.name_pattern, ext, doctype=m.best.doc_type,
                                              name=s.profile.name, roll=s.profile.roll)
        filename = unique(filename, taken)
        check = validate(data, spec, raster_dpi=dpi, notes=[*m.notes, *notes, *name_warnings])
        if check.status != "FAIL":                             # never write a file that breaks the rules
            (out_dir / filename).write_bytes(data)
        rows.append(BuiltRow(spec.label, check.status, src.name,
                             filename if check.status != "FAIL" else "", check.size_bytes, check.reasons))

    _write_reports(out_dir, name, rows)
    return out_dir, rows

def _write_reports(out_dir: Path, name: str, rows: list[BuiltRow]) -> None:
    ready = sum(r.status in ("PASS", "WARN") for r in rows)
    now = datetime.now()
    md = [f"# {name}", "",
          f"Built {now:%d %b %Y, %H:%M} by Kaagaz, offline. **{ready} of {len(rows)} ready.**", "",
          "| Requirement | Picked file | Output | Size | Check |",
          "|---|---|---|---|---|"]
    for r in rows:
        size = f"{r.size_bytes / 1000:.1f} KB" if r.size_bytes else ""
        md.append(f"| {r.label} | {r.source or '-'} | {r.output or '-'} | {size} | {r.status} |")
    notes = [(r.label, why) for r in rows for why in r.reasons]
    if notes:
        md += ["", "## Notes", ""] + [f"- **{label}**: {why}" for label, why in notes]
    md += ["", "Kaagaz never uploads anything. Check each file, then upload it to the portal yourself."]
    (out_dir / "checklist.md").write_text("\n".join(md), encoding="utf-8")

    manifest = {"name": name, "built_at": now.isoformat(timespec="seconds"),
                "rows": [asdict(r) for r in rows]}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")