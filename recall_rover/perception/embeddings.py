"""Cheap appearance signatures for entity association.

An HSV colour histogram of the detection crop. It is not a learned embedding, but it is
deterministic, runs in well under a millisecond on CPU, and lets memory ask
"does this backpack look like the backpack I remember?" across zones and revisits.
A CLIP/SigLIP embedding can replace it later behind the same two functions.
"""

import math

H_BINS = 16
S_BINS = 8


def appearance_signature(frame, bbox):
    """Return a normalised 128-float HSV histogram of the bbox crop, or None."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    if frame is None or not hasattr(frame, "shape") or frame.ndim != 3 or not bbox:
        return None
    h, w = frame.shape[:2]
    x0, y0, x1, y1 = (int(round(v)) for v in bbox)
    x0, x1 = max(0, min(w, x0)), max(0, min(w, x1))
    y0, y1 = max(0, min(h, y0)), max(0, min(h, y1))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    crop = frame[y0:y1, x0:x1]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [H_BINS, S_BINS], [0, 180, 0, 256])
    total = float(hist.sum()) or 1.0
    return [round(float(v) / total, 5) for v in np.asarray(hist).flatten()]


def similarity(a, b):
    """Cosine similarity in [0, 1] for non-negative histograms; 0 when unavailable."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))
