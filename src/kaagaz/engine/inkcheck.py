from __future__ import annotations

import numpy as np
from PIL import Image

from kaagaz.engine.facecrop import detect_faces


def looks_like_signature(img: Image.Image) -> bool:
    """Mostly one plain background tone, a little dark ink, no face."""
    small = img.convert("L")
    small.thumbnail((512, 512))
    a = np.asarray(small, dtype=np.int16)
    bg = int(np.median(a))                         # paper tone: white, grey or yellowish
    background = (np.abs(a - bg) < 30).mean()
    ink = (a < bg - 60).mean()
    return background > 0.80 and 0.002 < ink < 0.12 and not detect_faces(img)