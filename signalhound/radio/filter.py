"""RSSI is a noisy scalar. This module turns raw samples into something a controller can trust.

Rolling median over the last `window` samples, then an exponential moving average.
Larger (less negative) dBm = stronger signal.
"""

import statistics
import time
from collections import deque
from dataclasses import dataclass


@dataclass
class Sample:
    timestamp: float
    rssi: float


class RssiFilter:
    def __init__(self, window=10, min_samples=5, alpha=0.4, stale_seconds=3.0, clock=time.time):
        self.window = window
        self.min_samples = min_samples
        self.alpha = alpha
        self.stale_seconds = stale_seconds
        self.clock = clock
        self.samples = deque(maxlen=window)
        self.total = 0
        self.ema = None
        self.last_time = None

    def add(self, rssi, timestamp=None):
        ts = self.clock() if timestamp is None else timestamp
        self.samples.append(Sample(ts, float(rssi)))
        self.total += 1
        self.last_time = ts
        med = self.median()
        self.ema = med if self.ema is None else self.alpha * med + (1 - self.alpha) * self.ema
        return self.ema

    def reset(self):
        self.samples.clear()
        self.ema = None
        self.last_time = None

    # ---- accessors -------------------------------------------------------
    def get_raw_rssi(self):
        return self.samples[-1].rssi if self.samples else None

    def median(self):
        return statistics.median(s.rssi for s in self.samples) if self.samples else None

    def mean(self):
        return statistics.fmean(s.rssi for s in self.samples) if self.samples else None

    def stdev(self):
        return statistics.pstdev([s.rssi for s in self.samples]) if len(self.samples) > 1 else 0.0

    def get_filtered_rssi(self):
        return self.ema

    def count(self):
        return len(self.samples)

    def age(self):
        return None if self.last_time is None else self.clock() - self.last_time

    def is_stale(self):
        age = self.age()
        return age is None or age > self.stale_seconds

    def ready(self):
        return len(self.samples) >= self.min_samples and not self.is_stale()

    def get_signal_quality(self):
        """0..1: enough fresh samples with low spread."""
        if not self.samples or self.is_stale():
            return 0.0
        fill = min(1.0, len(self.samples) / max(1, self.min_samples))
        spread = 1.0 / (1.0 + self.stdev() / 4.0)
        return round(fill * spread, 3)

    def status(self):
        if self.last_time is None:
            return "waiting"
        if self.is_stale():
            return "lost"
        if len(self.samples) < self.min_samples:
            return "acquiring"
        return "tracking"
