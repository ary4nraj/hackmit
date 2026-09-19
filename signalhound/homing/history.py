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

    def best(self):
        pts = [p for p in self.points if p.rssi is not None]
        return max(pts, key=lambda p: p.rssi) if pts else None

    def close(self):
        if self._fh:
            self._fh.close()
