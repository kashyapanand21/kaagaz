from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Literal

import pymupdf
from PIL import Image

from kaagaz.engine.transform import max_bytes_for, min_bytes_for, target_px
from kaagaz.schemas import RequirementItem

Status = Literal["PASS", "WARN", "FAIL"]
READABLE_DPI = 100


def kb(n: int) -> str:
    return f"{n / 1000:.1f} KB"


def sniff(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:5] == b"%PDF-":
        return "pdf"
    return None


def measure(data: bytes) -> tuple[str | None, int | None, int | None, int | None]:
    """(format, width, height, pages). Raises if the file can't be re-opened."""
    fmt = sniff(data)
    if fmt in ("jpg", "png"):
        with Image.open(io.BytesIO(data)) as im:
            w, h = im.size
            im.verify()
        return fmt, w, h, 1
    if fmt == "pdf":
        with pymupdf.open(stream=data, filetype="pdf") as d:
            return fmt, None, None, d.page_count
    return fmt, None, None, None

@dataclass
class Check:
    status: Status
    size_bytes: int
    fmt: str | None
    width: int | None = None
    height: int | None = None
    pages: int | None = None
    reasons: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        tail = f" · {'; '.join(self.reasons)}" if self.reasons else ""
        return f"{self.status} · {kb(self.size_bytes)}{tail}"


def validate(data: bytes, spec: RequirementItem,
             raster_dpi: int | None = None, notes: list[str] | None = None) -> Check:
    n = len(data)
    try:
        fmt, w, h, pages = measure(data)
    except Exception as e:
        return Check("FAIL", n, None, reasons=[f"output can't be re-opened: {e}"])

    fails: list[str] = []
    warns: list[str] = list(notes or [])

    if fmt not in spec.formats:
        fails.append(f"format {fmt or 'unknown'}, expected {'/'.join(spec.formats)}")
    if spec.max_kb and n > max_bytes_for(spec.max_kb):
        fails.append(f"{kb(n)} > {spec.max_kb} KB")
    if spec.min_kb and n < min_bytes_for(spec.min_kb):
        fails.append(f"{kb(n)} < {spec.min_kb} KB")
    want = target_px(spec)
    if want and fmt in ("jpg", "png") and (w, h) != want:
        fails.append(f"{w}x{h} px, expected {want[0]}x{want[1]}")
    if spec.pages == "first_only" and pages != 1:
        fails.append(f"{pages} pages, expected 1")
    if raster_dpi and raster_dpi < READABLE_DPI:
        warns.append(f"rasterised at {raster_dpi} DPI; check readability")

    status: Status = "FAIL" if fails else "WARN" if warns else "PASS"
    return Check(status, n, fmt, w, h, pages, fails + warns)