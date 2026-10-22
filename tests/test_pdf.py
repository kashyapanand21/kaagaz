import numpy as np
import pymupdf
import pytest
from PIL import Image

from kaagaz.engine.transform import (CannotFit, first_page_only, fit_pdf,
                                     image_to_pdf, merge_pdfs)


def noisy(w: int, h: int) -> Image.Image:
    rng = np.random.default_rng(0)
    return Image.fromarray(rng.integers(0, 256, (h, w, 3), dtype=np.uint8))


def pages(pdf: bytes) -> int:
    with pymupdf.open(stream=pdf, filetype="pdf") as d:
        return d.page_count


def test_image_to_pdf_is_one_a4_page():
    with pymupdf.open(stream=image_to_pdf(noisy(400, 300)), filetype="pdf") as d:
        assert d.page_count == 1 and round(d[0].rect.width) == 595


def test_merge_and_first_page():
    a = image_to_pdf(noisy(200, 200))
    merged = merge_pdfs([a, a, a])
    assert pages(merged) == 3
    assert pages(first_page_only(merged)) == 1


def test_fit_pdf_rasterises_to_limit():
    data, dpi = fit_pdf(image_to_pdf(noisy(1600, 1200)), max_bytes=100_000)
    assert len(data) <= 100_000 and dpi is not None


def test_impossible_pdf_reports():
    six = merge_pdfs([image_to_pdf(noisy(1600, 1200))] * 6)
    with pytest.raises(CannotFit):
        fit_pdf(six, max_bytes=5_000)