"""Serial link to the Nordic DK: auto-detect, reconnect, parse, timestamp, filter."""

import glob
import threading
import time

from signalhound.radio.filter import RssiFilter
from signalhound.radio.scanner_protocol import parse_line


def find_port(preferred=""):
    if preferred:
        return preferred
    # SEGGER J-Link OB on the nRF7002-DK exposes two CDC ports; the first is the nRF5340 console.
    for pattern in ("/dev/serial/by-id/usb-SEGGER_J-Link_*-if00", "/dev/serial/by-id/usb-SEGGER_J-Link_*"):
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[0]
    hits = sorted(glob.glob("/dev/ttyACM*"))
    return hits[0] if hits else None


class NordicSerial:
    """Background reader thread. Thread-safe accessors; safe to poll from asyncio."""

    def __init__(self, cfg, on_line=None):
        self.cfg = cfg
        self.on_line = on_line
        self.filter = RssiFilter(cfg.rssi_window, cfg.rssi_min_samples, cfg.rssi_ema_alpha, cfg.rssi_stale_seconds)
        self.lock = threading.Lock()
        self.port = None
        self.connected = False
        self.last_line = ""
        self.last_heartbeat = None
        self.target_seen = 0
        self.others = {}
        self.errors = 0
        self._stop = threading.Event()
        self._thread = None

    # ---- lifecycle -------------------------------------------------------
    def start(self):
        self._thread = threading.Thread(target=self._run, name="nordic-serial", daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()

    def _run(self):
        import serial

        while not self._stop.is_set():
            port = find_port(self.cfg.serial_port)
            if not port:
                self.connected = False
                time.sleep(1.0)
                continue
            try:
                with serial.Serial(port, self.cfg.serial_baud, timeout=1.0) as ser:
                    self.port = port
                    self.connected = True
                    ser.reset_input_buffer()
                    while not self._stop.is_set():
                        raw = ser.readline()
                        if not raw:
                            continue
                        self._handle(raw.decode("utf-8", "replace"))
            except Exception:
                self.errors += 1
                self.connected = False
                time.sleep(1.0)

    # ---- parsing ---------------------------------------------------------
    def _handle(self, text):
        line = parse_line(text)
        self.last_line = text.strip()
        if line is None:
            return
        now = time.time()
        with self.lock:
            if line.kind == "TARGET" and (not line.name or line.name == self.cfg.target_name):
                self.filter.add(line.rssi, now)
                self.target_seen += 1
            elif line.kind in ("TARGET", "SEEN"):
                self.others[line.name] = (line.rssi, now)
            elif line.kind == "SCAN":
                self.last_heartbeat = now
        if self.on_line:
            self.on_line(line)

    # ---- accessors -------------------------------------------------------
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
                "port": self.port,
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
                "others": {k: v[0] for k, v in self.others.items() if time.time() - v[1] < 5},
            }

    def wait_for_samples(self, n, timeout):
        """Block until n fresh samples are in the window (or timeout). Returns True on success."""
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
