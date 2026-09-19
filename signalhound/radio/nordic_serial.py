"""Serial link to the Nordic DK: auto-detect, reconnect, parse, timestamp, filter."""

import glob
import threading
import time

from signalhound.radio.filter import RssiFilter
from signalhound.radio.scanner_protocol import parse_line


def candidate_ports(preferred=""):
    """Ordered list of ports to try. The nRF7002-DK's J-Link OB exposes two CDC ports and which one
    carries the nRF5340 console depends on the OB firmware/enumeration, so we probe them all."""
    if preferred:
        return [preferred]
    ports = sorted(glob.glob("/dev/serial/by-id/usb-SEGGER_J-Link_*"))
    return ports or sorted(glob.glob("/dev/ttyACM*"))


def find_port(preferred=""):
    ports = candidate_ports(preferred)
    return ports[0] if ports else None


def probe_port(port, baud, seconds=2.5):
    """True if the port emits SignalHound protocol lines within `seconds`."""
    import serial

    try:
        with serial.Serial(port, baud, timeout=0.3) as ser:
            ser.dtr = True
            deadline = time.time() + seconds
            while time.time() < deadline:
                line = ser.readline().decode("utf-8", "replace")
                if line and parse_line(line) is not None:
                    return True
    except Exception:
        return False
    return False


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
            port = None
            for candidate in candidate_ports(self.cfg.serial_port):
                if self.cfg.serial_port or probe_port(candidate, self.cfg.serial_baud):
                    port = candidate
                    break
            if not port:
                self.connected = False
                time.sleep(1.0)
                continue
            try:
                with serial.Serial(port, self.cfg.serial_baud, timeout=1.0) as ser:
                    ser.dtr = True
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
            if line.kind in ("TARGET", "ADV") and (not line.name or line.name == self.cfg.target_name):
                self.filter.add(line.rssi, now)
                self.target_seen += 1
            elif line.kind in ("TARGET", "ADV"):
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
