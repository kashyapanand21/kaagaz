from PIL import Image, ImageDraw

from kaagaz.engine.cleanup import background_is_light, whiten_signature


def signature_photo() -> Image.Image:
    img = Image.new("RGB", (1200, 500), (230, 228, 215))           # yellowish paper
    ImageDraw.Draw(img).line([(100, 300), (400, 120), (700, 350), (1000, 150)], fill=(20, 20, 60), width=8)
    return img


def test_whiten_makes_paper_pure_white_and_crops_to_ink():
    out = whiten_signature(signature_photo())
    assert out.getpixel((0, 0)) == (255, 255, 255) and out.width < 1200


def test_background_check():
    assert background_is_light(Image.new("RGB", (300, 400), "white"))
    assert not background_is_light(Image.new("RGB", (300, 400), (40, 80, 160)))