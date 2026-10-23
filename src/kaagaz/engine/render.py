from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from PIL import Image

from kaagaz.engine.transform import encode_jpeg, open_image

PDF_DPI = 150
MODEL_PAGES = 1          # page 1 identifies the document; text layer covers the rest
TEXT_PAGES = 2
TEXT_CHARS = 1500
THUMB_PX = 256


class RenderError(Exception):
    """A file Kaagaz can't read. The message is shown in the library."""


@dataclass
class Rendered:
    images: list[bytes]      # JPEGs for the model
    text: str                # PDF text layer, trimmed ("" for images)
    pages: int
    thumb: bytes


def _shrink(img: Image.Image, long_side: int) -> Image.Image:
    img = img.copy()
    img.thumbnail((long_side, long_side), Image.LANCZOS)   # keeps aspect, only ever shrinks
    return img


def _pdf(path: Path) -> tuple[list[Image.Image], str, int]:
    try:
        doc = pymupdf.open(path)
    except Exception as e:
        raise RenderError(f"unreadable PDF: {e}") from e
    with doc:
        if doc.needs_pass:
            raise RenderError("locked: password-protected PDF")
        if doc.page_count == 0:
            raise RenderError("empty PDF")
        images = []
        for i in range(min(MODEL_PAGES, doc.page_count)):
            pix = doc[i].get_pixmap(dpi=PDF_DPI, alpha=False)
            images.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
        text = " ".join(doc[i].get_text() for i in range(min(TEXT_PAGES, doc.page_count)))
        return images, re.sub(r"\s+", " ", text).strip()[:TEXT_CHARS], doc.page_count


def render(path: Path, long_side: int = 1024) -> Rendered:
    if path.suffix.lower() == ".pdf":
        pages, text, n = _pdf(path)
    else:
        try:
            pages, text, n = [open_image(path)], "", 1
        except Exception as e:
            raise RenderError(f"unreadable image: {e}") from e
    return Rendered(
        images=[encode_jpeg(_shrink(p, long_side), 85) for p in pages],
        text=text,
        pages=n,
        thumb=encode_jpeg(_shrink(pages[0], THUMB_PX), 80),
    )