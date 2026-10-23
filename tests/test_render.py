import io

import pymupdf
import pytest
from PIL import Image

from kaagaz.engine.render import RenderError, render


def test_phone_photo_is_downscaled_with_thumb(tmp_path):
    p = tmp_path / "IMG-20240612-WA0007.jpg"
    Image.new("RGB", (3000, 2000), "white").save(p)
    r = render(p, long_side=1024)
    assert r.pages == 1 and len(r.images) == 1 and r.text == ""
    with Image.open(io.BytesIO(r.images[0])) as im:
        assert max(im.size) == 1024
    with Image.open(io.BytesIO(r.thumb)) as im:
        assert max(im.size) <= 256


def test_pdf_text_layer_is_extracted(tmp_path):
    p = tmp_path / "cert.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Income Certificate - Specimen Tehsil Office")
    doc.save(p)
    doc.close()
    r = render(p)
    assert "Income Certificate" in r.text and r.pages == 1


def test_locked_pdf_has_a_clear_reason(tmp_path):
    p = tmp_path / "locked.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(p, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="o", user_pw="u")
    doc.close()
    with pytest.raises(RenderError, match="locked"):
        render(p)


def test_corrupt_file_raises_render_error(tmp_path):
    p = tmp_path / "bad.jpg"
    p.write_bytes(b"not an image" * 100)
    with pytest.raises(RenderError):
        render(p)