"""Cable-free link: the DK rebroadcasts its target measurement; the laptop's Bluetooth reads it.

Same surface as NordicSerial. Manufacturer data (company 0xFFFF), a BATCH per advertisement because
BlueZ surfaces only ~1 update per 2 s per device:
  b'SH' seq(u8) idx(u16 LE, running count = index of newest sample) n(u8) age_ds(u8) n x int8 newest-first
The RSSI we track is the DK's measurement of the PHONE (payload), never the laptop's RSSI of the DK.
"""

import asyncio
import struct
import threading
import time

from signalhound.radio.filter import RssiFilter
from signalhound.radio.scanner_protocol import Line

COMPANY = 0xFFFF
MAGIC = b"SH"


def parse_batch(md, last_idx):
    """Return (new_samples_oldest_first, idx, age_ds) or None. Dedups against last_idx (mod 65536)."""
    if not md or not md.startswith(MAGIC) or len(md) < 7:
        return None
    seq, idx, n, age = struct.unpack("<BHBB", md[2:7])
    vals = list(struct.unpack(f"<{n}b", md[7:7 + n])) if n and len(md) >= 7 + n else []
    if last_idx is None:
        fresh = min(len(vals), 5)  # first contact: take a few recent ones, not the whole history
    else:
        fresh = min(len(vals), (idx - last_idx) % 65536)
    return list(reversed(vals[:fresh])), idx, age


class BleLink:
    def __init__(self, cfg, on_line=None):
        self.cfg = cfg
        self.on_line = on_line
        self.filter = RssiFilter(cfg.rssi_window, cfg.rssi_min_samples, cfg.rssi_ema_alpha, cfg.rssi_stale_seconds)
        self.lock = threading.Lock()
        self.connected = False
        self.port = "ble"
        self.last_heartbeat = None
        self.last_idx = None
        self.link_rssi = None
        self.dk_count = None
        self.dk_age = None
        self.target_seen = 0
        self.errors = 0
        self.last_line = ""
        self.others = {}
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, name="ble-link", daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()

    def _run(self):
        asyncio.run(self._scan())

    async def _scan(self):
        from bleak import BleakScanner

        def cb(device, adv):
            md = adv.manufacturer_data.get(COMPANY)
            parsed = parse_batch(md, self.last_idx)
            if parsed is None:
                return
            fresh, idx, age = parsed
            now = time.time()
            with self.lock:
                self.connected = True
                self.last_heartbeat = now
                self.link_rssi = adv.rssi
                self.dk_count, self.dk_age = idx, age
                self.last_idx = idx
                self.last_line = f"SH idx={idx} new={len(fresh)} age={age} vals={fresh}"
                if age == 255:
                    return
                base = now - age / 10.0
                for k, v in enumerate(fresh):
                    self.filter.add(float(v), base - 0.5 * (len(fresh) - 1 - k))
                    self.target_seen += 1
            if self.on_line:
                for v in fresh:
                    self.on_line(Line("TARGET", self.cfg.target_name, float(v), "via-dk-ble"))

        while not self._stop.is_set():
            try:
                scanner = BleakScanner(cb, scanning_mode="active", bluez={"filters": {"DuplicateData": True}})
                await scanner.start()
                while not self._stop.is_set():
                    await asyncio.sleep(0.2)
                    if self.last_heartbeat and time.time() - self.last_heartbeat > 5:
                        self.connected = False
                await scanner.stop()
            except Exception:
                self.errors += 1
                self.connected = False
                await asyncio.sleep(1.0)

    # ---- same accessors as NordicSerial ----------------------------------
    def get_raw_rssi(self):
        with self.lock:
            return self.filter.get_raw_rssi()

    def get_filtered_rssi(self):
        with self.lock:
            return self.filter.get_filtered_rssi()

    def get_signal_quality(self):
        with self.lock:
            return self.filter.get_signal_quality()

    def snapshot(self):
        with self.lock:
            f = self.filter
            return {
                "port": f"ble (link {self.link_rssi} dBm)",
                "connected": self.connected,
                "raw": f.get_raw_rssi(),
                "filtered": f.get_filtered_rssi(),
                "median": f.median(),
                "stdev": round(f.stdev(), 2),
                "samples": f.count(),
                "total": f.total,
                "age": None if f.age() is None else round(f.age(), 2),
                "status": f.status(),
                "heartbeat_age": None if self.last_heartbeat is None else round(time.time() - self.last_heartbeat, 1),
                "others": {},
            }

    def wait_for_samples(self, n, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.lock:
                if self.filter.count() >= n and not self.filter.is_stale():
                    return True
            time.sleep(0.05)
        return False

    def reset_window(self):
        with self.lock:
            self.filter.reset()
