"""Trajectory + RSSI history. Used for the dashboard, the experiment log, and (stretch) gradient fits."""

import json
import time
from dataclasses import asdict, dataclass


@dataclass
class SamplePoint:
    timestamp: float
    x: float | None
    y: float | None
    yaw: float | None
    rssi: float | None
    state: str = ""
    note: str = ""


class History:
    def __init__(self, path=None):
        self.points = []
        self.path = path
        self._fh = open(path, "a") if path else None

    def add(self, x, y, yaw, rssi, state="", note=""):
        p = SamplePoint(time.time(), x, y, yaw, rssi, state, note)
        self.points.append(p)
        if self._fh:
            self._fh.write(json.dumps(asdict(p)) + "\n")
            self._fh.flush()
        return p

    def gradient(self, k=12, min_span=0.8, min_points=5):
        """Least-squares plane RSSI ≈ a·x + b·y + c over the last k located points.
        Returns (a, b, r2) in dB/m or None when the points don't span enough area (collinear = unconditioned).
        Spatial averaging over ~2 m is what defeats multipath ripple that time-averaging cannot."""
        pts = [p for p in self.points[-k:] if p.rssi is not None and p.x is not None and p.y is not None]
        if len(pts) < min_points:
            return None
        xs = [p.x for p in pts]; ys = [p.y for p in pts]; rs = [p.rssi for p in pts]
        if max(xs) - min(xs) < min_span or max(ys) - min(ys) < min_span:
            return None
        n = len(pts)
        mx, my, mr = sum(xs) / n, sum(ys) / n, sum(rs) / n
        sxx = sum((x - mx) ** 2 for x in xs); syy = sum((y - my) ** 2 for y in ys)
        sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        sxr = sum((x - mx) * (r - mr) for x, r in zip(xs, rs)); syr = sum((y - my) * (r - mr) for y, r in zip(ys, rs))
        det = sxx * syy - sxy * sxy
        if abs(det) < 1e-9:
            return None
        a = (sxr * syy - syr * sxy) / det
        b = (syr * sxx - sxr * sxy) / det
        ss_tot = sum((r - mr) ** 2 for r in rs)
        ss_res = sum((r - mr - a * (x - mx) - b * (y - my)) ** 2 for x, y, r in zip(xs, ys, rs))
        r2 = 0.0 if ss_tot == 0 else max(0.0, 1 - ss_res / ss_tot)
        return a, b, r2

    def best(self):
        pts = [p for p in self.points if p.rssi is not None]
        return max(pts, key=lambda p: p.rssi) if pts else None

    def close(self):
        if self._fh:
            self._fh.close()
