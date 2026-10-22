import numpy as np
import pytest
from PIL import Image

from kaagaz.engine.transform import (CannotFit, cm_to_px, crop_to_aspect,
                                     fit_jpeg, max_bytes_for, to_rgb)


def noisy(w: int, h: int) -> Image.Image:
    rng = np.random.default_rng(0)
    return Image.fromarray(rng.integers(0, 256, (h, w, 3), dtype=np.uint8))


def test_cm_to_px_matches_design_doc():
    assert (cm_to_px(3.5), cm_to_px(4.5)) == (413, 531)


def test_crop_to_aspect():
    out = crop_to_aspect(Image.new("RGB", (1000, 1000)), 413 / 531)
    assert out.height == 1000
    assert abs(out.width / out.height - 413 / 531) < 0.01


def test_transparent_png_becomes_white_not_black():
    assert to_rgb(Image.new("RGBA", (10, 10), (0, 0, 0, 0))).getpixel((5, 5)) == (255, 255, 255)


def test_fits_under_limit():
    assert len(fit_jpeg(noisy(800, 600), max_bytes=max_bytes_for(50))) <= 50_000


def test_fixed_size_reports_instead_of_cheating():
    with pytest.raises(CannotFit):
        fit_jpeg(noisy(2000, 2000), max_bytes=5_000, fixed_size=True)