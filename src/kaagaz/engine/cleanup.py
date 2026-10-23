from __future__ import annotations

import numpy as np
from PIL import Image


def whiten_signature(img: Image.Image) -> Image.Image:
    """Paper → pure white, ink kept, cropped to the ink with a margin."""
    a = np.asarray(img.convert("L"), dtype=np.uint8)
    bg = int(np.median(a))
    ink = a < bg - 50
    if not ink.any():
        return img.convert("RGB")                       # nothing that looks like ink; leave it alone
    out = np.where(ink, a, 255).astype(np.uint8)
    ys, xs = np.nonzero(ink)
    pad = max(10, int(0.05 * max(a.shape)))
    box = (max(int(xs.min()) - pad, 0), max(int(ys.min()) - pad, 0),
           min(int(xs.max()) + pad, a.shape[1]), min(int(ys.max()) + pad, a.shape[0]))
    return Image.fromarray(out).crop(box).convert("RGB")


def background_is_light(img: Image.Image) -> bool:
    """Is the background around the head light and even?

    Checks the top strip and the upper halves of the side strips, never the bottom:
    shoulders and clothes always reach the bottom edge of a passport photo."""
    g = np.asarray(img.convert("L"), dtype=np.float32)
    h, w = g.shape
    k = max(2, int(min(h, w) * 0.05))
    upper = h // 2
    border = np.concatenate([g[:k].ravel(), g[:upper, :k].ravel(), g[:upper, -k:].ravel()])
    return border.mean() > 200 and border.std() < 30