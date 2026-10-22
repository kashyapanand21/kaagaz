import io

import numpy as np
from PIL import Image

from kaagaz.engine.transform import encode_jpeg
from kaagaz.engine.validate import validate
from kaagaz.schemas import RequirementItem

PHOTO = RequirementItem(label="Photo", doc_types=["photo"], formats=["jpg"],
                        width_cm=3.5, height_cm=4.5)


def jpg(w: int, h: int) -> bytes:
    return encode_jpeg(Image.new("RGB", (w, h), "white"), 90)


def test_exact_photo_passes():
    assert validate(jpg(413, 531), PHOTO).status == "PASS"


def test_wrong_size_fails_with_numbers():
    c = validate(jpg(400, 500), PHOTO)
    assert c.status == "FAIL" and "expected 413x531" in c.summary


def test_png_named_jpg_is_caught():
    buf = io.BytesIO()
    Image.new("RGB", (413, 531)).save(buf, "PNG")
    assert validate(buf.getvalue(), PHOTO).status == "FAIL"


def test_over_max_kb_fails():
    noise = np.random.default_rng(0).integers(0, 256, (600, 800, 3), dtype=np.uint8)
    spec = RequirementItem(label="Doc", doc_types=["other"], formats=["jpg"], max_kb=10)
    assert validate(encode_jpeg(Image.fromarray(noise), 95), spec).status == "FAIL"


def test_low_dpi_and_notes_warn():
    c = validate(jpg(413, 531), PHOTO, raster_dpi=72, notes=["No face found"])
    assert c.status == "WARN" and len(c.reasons) == 2


def test_corrupt_output_fails_not_crashes():
    assert validate(b"\xff\xd8\xff" + b"junk" * 10, PHOTO).status == "FAIL"