"""Generate SPECIMEN documents for the Kaagaz demo.

Invented person and institutions only, watermarked on every page. Not real documents.
Usage:  python samples\\make_specimens.py  [output folder]   (default: D:\\kaagaz-private\\demo)
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"D:\kaagaz-private\demo")
FONTS = Path(r"C:\Windows\Fonts")
W, H = 1240, 1754                      # A4 at 150 DPI
INK, RED, PAPER = (25, 35, 60), (150, 30, 30), (252, 250, 243)
NAME, NAME_HI, FATHER, ROLL = "RIYA SHARMA", "रिया शर्मा", "RAKESH SHARMA", "12345"
random.seed(7)


def font(names: tuple[str, ...], size: int) -> ImageFont.FreeTypeFont:
    for n in names:
        try:
            return ImageFont.truetype(str(FONTS / n), size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def serif(s): return font(("georgiab.ttf", "timesbd.ttf"), s)
def sans(s): return font(("arial.ttf", "segoeui.ttf"), s)
def bold(s): return font(("arialbd.ttf", "segoeuib.ttf"), s)
def hindi(s): return font(("Nirmala.ttf", "Nirmala.ttc", "NirmalaB.ttf", "mangal.ttf"), s)
def script(s): return font(("segoesc.ttf", "segoescb.ttf", "LHANDW.TTF"), s)


def centred(d: ImageDraw.ImageDraw, y: int, text: str, f, fill=INK) -> int:
    w = d.textlength(text, font=f)
    d.text(((W - w) / 2, y), text, font=f, fill=fill)
    return y + int(f.size * 1.45)


def watermark(img: Image.Image) -> Image.Image:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = bold(110)
    for y in range(150, H, 520):
        d.text((90, y), "SPECIMEN", font=f, fill=(190, 40, 40, 38))
    layer = layer.rotate(28, center=(W / 2, H / 2))
    out = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    ImageDraw.Draw(out).text((40, H - 50), "SPECIMEN - not a real document. Made for the Kaagaz demo.",
                             font=sans(20), fill=(150, 40, 40))
    return out


def page(org: str, org_hi: str | None, title: str, rows: list[tuple[str, str]],
         table: list[tuple[str, str]] | None = None, issued: str = "", place: str = "") -> Image.Image:
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    d.rectangle([30, 30, W - 30, H - 80], outline=INK, width=4)
    d.rectangle([44, 44, W - 44, H - 94], outline=INK, width=1)
    d.ellipse([W / 2 - 55, 80, W / 2 + 55, 190], outline=RED, width=5)      # invented seal, no real emblem
    centred(d, 115, "SPEC", bold(30), RED)
    y = 215
    if org_hi:
        y = centred(d, y, org_hi, hindi(38))
    y = centred(d, y, org, serif(40))
    y = centred(d, y + 10, title, bold(36), RED) + 30
    for k, v in rows:
        d.text((110, y), f"{k}", font=sans(30), fill=(70, 80, 90))
        d.text((480, y), f": {v}", font=bold(30), fill=INK)
        y += 56
    if table:
        y += 20
        d.rectangle([110, y, W - 110, y + 54], fill=(232, 228, 214), outline=INK)
        d.text((130, y + 10), "Subject", font=bold(28), fill=INK)
        d.text((W - 330, y + 10), "Marks (100)", font=bold(28), fill=INK)
        y += 54
        for subj, marks in table:
            d.rectangle([110, y, W - 110, y + 50], outline=(150, 150, 150))
            d.text((130, y + 9), subj, font=sans(28), fill=INK)
            d.text((W - 300, y + 9), marks, font=sans(28), fill=INK)
            y += 50
    bottom = H - 330
    if issued:
        d.text((110, bottom), f"Date of issue: {issued}", font=bold(30), fill=INK)
    if place:
        d.text((110, bottom + 50), f"Place: {place}", font=sans(28), fill=INK)
    d.text((W - 420, bottom + 40), "Issuing Officer", font=sans(28), fill=INK)
    d.text((W - 430, bottom - 30), "S. K. Verma", font=script(44), fill=(30, 40, 120))
    return watermark(img)


def phone_photo(img: Image.Image) -> Image.Image:
    """Tilted page on a table, uneven light, slight blur: like a WhatsApp forward."""
    bg = Image.new("RGB", (W + 220, H + 260), (96, 80, 64))
    tilted = img.rotate(random.uniform(-3.5, 3.5), expand=True, fillcolor=(96, 80, 64), resample=Image.BICUBIC)
    bg.paste(tilted, ((bg.width - tilted.width) // 2, (bg.height - tilted.height) // 2))
    light = Image.linear_gradient("L").transpose(Image.Transpose.ROTATE_90).resize(bg.size)
    light = light.point(lambda v: 255 - v * 45 // 255)                      # brighter on one side, no hard edges
    out = ImageChops.multiply(bg, Image.merge("RGB", [light] * 3))
    return out.filter(ImageFilter.GaussianBlur(0.7))


def signature() -> Image.Image:
    img = Image.new("RGB", (1100, 420), (236, 232, 220))           # off-white paper, like a phone photo
    d = ImageDraw.Draw(img)
    d.text((90, 90), "Riya Sharma", font=script(150), fill=(20, 30, 95))
    d.line([(100, 330), (640, 315), (900, 335)], fill=(20, 30, 95), width=5)
    return img.rotate(-2, expand=True, fillcolor=(236, 232, 220)).filter(ImageFilter.GaussianBlur(0.5))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    common = [("Name of candidate", NAME), ("Father's name", FATHER), ("Roll number", ROLL)]

    m10 = page("Specimen Board of Secondary Education", "स्पेसिमेन माध्यमिक शिक्षा परिषद",
               "SECONDARY SCHOOL EXAMINATION (CLASS X) 2022", common + [("School", "Specimen Public School")],
               [("Hindi", "88"), ("English", "91"), ("Mathematics", "95"), ("Science", "90"), ("Social Science", "87")],
               issued="14/06/2022", place="Lucknow")
    phone_photo(m10).save(OUT / "IMG-20240612-WA0007.jpg", quality=88)

    m12 = page("Specimen Board of Secondary Education", "स्पेसिमेन माध्यमिक शिक्षा परिषद",
               "SENIOR SECONDARY EXAMINATION (CLASS XII) 2024", common + [("School", "Specimen Public School")],
               [("English", "90"), ("Physics", "93"), ("Chemistry", "89"), ("Mathematics", "96"), ("Computer Science", "98")],
               issued="20/05/2024", place="Lucknow")
    m12.save(OUT / "class12_marksheet_scan.pdf", resolution=150)

    income = page("Office of the Tehsildar, Specimen Tehsil", "कार्यालय तहसीलदार, स्पेसिमेन तहसील",
                  "INCOME CERTIFICATE / आय प्रमाण पत्र",
                  [("Name", NAME), ("Father's name", FATHER), ("Annual family income", "Rs. 2,40,000"),
                   ("Certificate no.", "SPEC/INC/2026/0417")],
                  issued="12/03/2026", place="Specimen Tehsil")
    phone_photo(income).save(OUT / "IMG-20260315-WA0011.jpg", quality=88)       # issued before 01 Apr 2026 → EXPIRED

    caste = page("Office of the Sub-Divisional Magistrate, Specimen District", "कार्यालय उप-जिलाधिकारी",
                 "CASTE CERTIFICATE / जाति प्रमाण पत्र",
                 [("Name", NAME), ("Father's name", FATHER), ("Category", "OBC (specimen)"),
                  ("Certificate no.", "SPEC/CST/2025/1182")],
                 issued="02/07/2025", place="Specimen District")
    caste.save(OUT / "caste_certificate.pdf", resolution=150)

    dom = page("Office of the Tehsildar, Specimen Tehsil", "कार्यालय तहसीलदार, स्पेसिमेन तहसील",
               "निवास प्रमाण पत्र (DOMICILE CERTIFICATE)",
               [("नाम / Name", f"{NAME_HI} / Riya Sharma"), ("पिता का नाम", "राकेश शर्मा"),
                ("निवास", "स्पेसिमेन नगर, लखनऊ")],
               issued="05/08/2026", place="Specimen Tehsil")
    phone_photo(dom).save(OUT / "IMG-20261019-WA0003.jpg", quality=88)

    signature().save(OUT / "signature_riya.jpg", quality=92)

    print(f"Wrote 6 specimen documents to {OUT}")
    print("Now add a real photo of yourself (plain wall behind you) as passport_photo.jpg in that folder.")
    print("No bank passbook on purpose: the demo shows it as MISSING.")


if __name__ == "__main__":
    main()