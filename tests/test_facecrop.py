from PIL import Image

from kaagaz.engine.facecrop import face_crop

ASPECT = 413 / 531


def test_no_face_falls_back_to_centre_with_warning():
    r = face_crop(Image.new("RGB", (1200, 900), "white"), ASPECT)
    assert r.faces == 0 and r.warning
    assert abs(r.image.width / r.image.height - ASPECT) < 0.01