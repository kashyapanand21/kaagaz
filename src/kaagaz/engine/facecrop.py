from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image

from kaagaz.engine.transform import crop_to_aspect

FACE_SHARE = 0.5     # face box height as a share of crop height
DETECT_SIDE = 800    # detect on a copy no larger than this
CASCADES = (         # (file, minNeighbors): strict first, then a second model, slightly looser
    ("haarcascade_frontalface_default.xml", 5),
    ("haarcascade_frontalface_alt2.xml", 3),
)


@dataclass
class FaceCrop:
    image: Image.Image
    faces: int
    warning: str | None = None


@lru_cache(maxsize=4)
def _cascade(name: str) -> cv2.CascadeClassifier:
    c = cv2.CascadeClassifier(cv2.data.haarcascades + name)
    if c.empty():
        raise RuntimeError(f"Haar cascade {name} failed to load (check the OpenCV install path)")
    return c


def detect_faces(img: Image.Image) -> list[tuple[int, int, int, int]]:
    scale = min(1.0, DETECT_SIDE / max(img.size))
    small = img.convert("L").resize((round(img.width * scale), round(img.height * scale)))
    gray = cv2.equalizeHist(np.asarray(small))
    side = max(20, round(min(small.size) * 0.08))
    for name, neighbours in CASCADES:
        found = _cascade(name).detectMultiScale(gray, scaleFactor=1.1, minNeighbors=neighbours,
                                                minSize=(side, side))
        if len(found):
            return [tuple(round(v / scale) for v in f) for f in found]
    return []


def face_crop(img: Image.Image, aspect: float) -> FaceCrop:
    faces = detect_faces(img)
    if not faces:
        return FaceCrop(crop_to_aspect(img, aspect), 0,
                        "No face found; used a centre crop. Check the photo.")

    x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
    w, h = img.size
    ch = min(fh / FACE_SHARE, h)
    cw = ch * aspect
    if cw > w:
        cw, ch = w, w / aspect

    cx = x + fw / 2
    cy = y + fh / 2 + 0.05 * ch          # face sits a bit above centre → room for shoulders
    left = min(max(cx - cw / 2, 0), w - cw)
    top = min(max(cy - ch / 2, 0), h - ch)
    box = (round(left), round(top), round(left + cw), round(top + ch))

    warning = f"{len(faces)} faces found; used the largest." if len(faces) > 1 else None
    return FaceCrop(img.crop(box), len(faces), warning)