"""2D simulated Go2 + radio field for algorithm development. No hardware."""

import math
import random
import time


class MockRobot:
    """Integrates bursts instantly; exposes the same surface as Go2Robot."""

    def __init__(self, x=0.0, y=0.0, yaw=0.0, realtime=False):
        self.x, self.y, self.yaw = x, y, yaw
        self.realtime = realtime
        self.connected = False
        self.stops = 0
        self.bursts = []
        self.obstacle = [9.9, 9.9, 9.9, 9.9]

    async def connect(self):
        self.connected = True

    async def disconnect(self):
        self.connected = False

    async def burst(self, vx, vyaw, seconds):
        self.bursts.append((vx, vyaw, seconds))
        if self.realtime:
            import asyncio

            await asyncio.sleep(seconds)
        self.yaw = (self.yaw + vyaw * seconds + math.pi) % (2 * math.pi) - math.pi
        self.x += vx * seconds * math.cos(self.yaw)
        self.y += vx * seconds * math.sin(self.yaw)

    async def stop(self):
        self.stops += 1

    async def get_yaw(self):
        return self.yaw

    async def get_position(self):
        return (self.x, self.y)

    async def get_obstacle_ranges(self):
        return list(self.obstacle)

    def status(self):
        return {"connected": self.connected, "x": self.x, "y": self.y, "yaw": self.yaw}


class RadioField:
    """Synthetic RSSI: C - 10*n*log10(d) + noise, optional body-shadow + dropouts."""

    def __init__(self, tx, ty, c=-40.0, n=2.2, noise_db=2.5, dropout=0.0, seed=1):
        self.tx, self.ty, self.c, self.n, self.noise_db, self.dropout = tx, ty, c, n, noise_db, dropout
        self.rng = random.Random(seed)

    def rssi_at(self, x, y):
        if self.dropout and self.rng.random() < self.dropout:
            return None
        d = math.hypot(self.tx - x, self.ty - y)
        return self.c - 10 * self.n * math.log10(d + 0.3) + self.rng.gauss(0, self.noise_db)


class MockRadio:
    """Feeds a RssiFilter from the field at the mock robot's position. Mimics NordicSerial."""

    def __init__(self, cfg, robot, field, samples_per_read=6):
        from signalhound.radio.filter import RssiFilter

        self.cfg, self.robot, self.field = cfg, robot, field
        self.filter = RssiFilter(cfg.rssi_window, cfg.rssi_min_samples, cfg.rssi_ema_alpha, cfg.rssi_stale_seconds)
        self.samples_per_read = samples_per_read
        self.connected = True

    def sample(self, n=None):
        for _ in range(n or self.samples_per_read):
            r = self.field.rssi_at(self.robot.x, self.robot.y)
            if r is not None:
                self.filter.add(r, time.time())

    def wait_for_samples(self, n, timeout):
        self.sample(n)
        return self.filter.count() >= min(n, self.filter.window)

    def reset_window(self):
        self.filter.reset()

    def get_filtered_rssi(self):
        return self.filter.get_filtered_rssi()

    def get_raw_rssi(self):
        return self.filter.get_raw_rssi()

    def get_signal_quality(self):
        return self.filter.get_signal_quality()

    def snapshot(self):
        f = self.filter
        return {"connected": True, "raw": f.get_raw_rssi(), "filtered": f.get_filtered_rssi(), "median": f.median(),
                "stdev": round(f.stdev(), 2), "samples": f.count(), "total": f.total, "age": f.age(),
                "status": f.status(), "heartbeat_age": 0, "others": {}, "port": "mock"}

    def start(self):
        return self

    def stop(self):
        pass
