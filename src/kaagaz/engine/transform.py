from __future__ import annotations

import io
from pathlib import Path
import pymupdf
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

from kaagaz.schemas import RequirementItem

register_heif_opener()  # lets Image.open read iPhone .heic files

DEFAULT_DPI = 300
MIN_Q, MAX_Q = 20, 95


class CannotFit(Exception):
    """The output can't meet the limit without ignoring the portal's rules."""


def max_bytes_for(kb: int) -> int:
    return kb * 1000   # strict reading of "max N KB"


def min_bytes_for(kb: int) -> int:
    return kb * 1024   # strict reading of "min N KB"


def cm_to_px(cm: float, dpi: int = DEFAULT_DPI) -> int:
    return round(cm / 2.54 * dpi)


def target_px(spec: RequirementItem) -> tuple[int, int] | None:
    """Exact output size the portal wants, from px or cm@DPI. None = no size rule."""
    if spec.width_px and spec.height_px:
        return spec.width_px, spec.height_px
    if spec.width_cm and spec.height_cm:
        dpi = spec.dpi or DEFAULT_DPI
        return cm_to_px(spec.width_cm, dpi), cm_to_px(spec.height_cm, dpi)
    return None

def to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, "white")
        bg.paste(rgba, mask=rgba.getchannel("A"))
        return bg
    return img.convert("RGB")


def open_image(path: Path) -> Image.Image:
    with Image.open(path) as img:
        return to_rgb(ImageOps.exif_transpose(img))

def crop_to_aspect(img: Image.Image, aspect: float, center: tuple[float, float] | None = None) -> Image.Image:
    """Largest crop with width/height == aspect, centred on `center` (default: image centre)."""
    w, h = img.size
    if w / h > aspect:
        cw, ch = round(h * aspect), h
    else:
        cw, ch = w, round(w / aspect)
    cx, cy = center or (w / 2, h / 2)
    left = round(min(max(cx - cw / 2, 0), w - cw))
    top = round(min(max(cy - ch / 2, 0), h - ch))
    return img.crop((left, top, left + cw, top + ch))

def encode_jpeg(img: Image.Image, quality: int, subsampling: int = 2) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, optimize=True, subsampling=subsampling)
    return buf.getvalue()


def _best_under(img: Image.Image, max_bytes: int) -> bytes | None:
    best, lo, hi = None, MIN_Q, MAX_Q
    while lo <= hi:
        q = (lo + hi) // 2
        data = encode_jpeg(img, q)
        if len(data) <= max_bytes:
            best, lo = data, q + 1
        else:
            hi = q - 1
    return best


def fit_jpeg(img: Image.Image, max_bytes: int | None = None, min_bytes: int | None = None,
             fixed_size: bool = False, rounds: int = 6) -> bytes:
    if max_bytes is None:
        data = encode_jpeg(img, 90)
    else:
        for _ in range(rounds):
            data = _best_under(img, max_bytes)
            if data:
                break
            if fixed_size:
                raise CannotFit(f"{img.width}x{img.height} px can't get under "
                                f"{max_bytes // 1000} KB even at quality {MIN_Q}")
            img = img.resize((round(img.width * 0.85), round(img.height * 0.85)), Image.LANCZOS)
        else:
            raise CannotFit(f"too detailed to fit {max_bytes // 1000} KB after {rounds} downscales")

    if min_bytes and len(data) < min_bytes:
        bigger = encode_jpeg(img, MAX_Q, subsampling=0)   # 4:4:4 adds real detail, not padding
        if max_bytes is None or len(bigger) <= max_bytes:
            data = bigger
    return data

A4 = pymupdf.paper_rect("a4")
MARGIN_PT = 24
PDF_DPI_LADDER = (200, 150, 120, 100, 85, 72)


def image_to_pdf(img: Image.Image) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=A4.width, height=A4.height)
    box = A4 + (MARGIN_PT, MARGIN_PT, -MARGIN_PT, -MARGIN_PT)
    page.insert_image(box, stream=encode_jpeg(img, 90), keep_proportion=True)
    return doc.tobytes(garbage=4, deflate=True)


def merge_pdfs(parts: list[bytes]) -> bytes:
    out = pymupdf.open()
    for part in parts:
        with pymupdf.open(stream=part, filetype="pdf") as src:
            out.insert_pdf(src)
    return out.tobytes(garbage=4, deflate=True)


def first_page_only(pdf: bytes) -> bytes:
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        doc.select([0])
        return doc.tobytes(garbage=4, deflate=True)


def pdf_page_image(pdf: bytes, dpi: int = 150, page_no: int = 0) -> Image.Image:
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        pix = doc[page_no].get_pixmap(dpi=dpi, alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

def _rasterise(doc: pymupdf.Document, dpi: int, page_budget: int) -> bytes | None:
    out = pymupdf.open()
    for page in doc:
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        jpg = _best_under(img, page_budget)
        if jpg is None:
            return None
        new = out.new_page(width=page.rect.width, height=page.rect.height)
        new.insert_image(new.rect, stream=jpg)
    return out.tobytes(garbage=4, deflate=True)


def fit_pdf(pdf: bytes, max_bytes: int | None) -> tuple[bytes, int | None]:
    """Returns (pdf_bytes, raster_dpi). raster_dpi is None if the lossless pass was enough."""
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        lossless = doc.tobytes(garbage=4, deflate=True, clean=True)
        if max_bytes is None or len(lossless) <= max_bytes:
            return lossless, None

        budget = int(max_bytes * 0.97) // doc.page_count
        for dpi in PDF_DPI_LADDER:
            data = _rasterise(doc, dpi, budget)
            if data and len(data) <= max_bytes:
                return data, dpi

        raise CannotFit(f"{doc.page_count}-page PDF can't reach {max_bytes // 1000} KB "
                        f"even at {PDF_DPI_LADDER[-1]} DPI; needs fewer pages or a higher limit")

