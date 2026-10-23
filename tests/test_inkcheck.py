import numpy as np
from PIL import Image, ImageDraw

from kaagaz.engine.inkcheck import looks_like_signature


def test_ink_strokes_on_paper_look_like_a_signature():
    img = Image.new("RGB", (900, 300), (235, 232, 220))           # off-white, like a phone photo
    ImageDraw.Draw(img).line([(100, 200), (250, 80), (400, 220), (600, 90), (800, 180)],
                             fill=(20, 20, 60), width=6)
    assert looks_like_signature(img)


def test_blank_page_and_busy_photo_do_not():
    assert not looks_like_signature(Image.new("RGB", (900, 300), "white"))
    noise = np.random.default_rng(0).integers(0, 256, (300, 900, 3), dtype=np.uint8)
    assert not looks_like_signature(Image.fromarray(noise))