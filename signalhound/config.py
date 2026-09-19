"""All tunables in one place. Every value can be overridden from the environment / .env."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _f(name, default):
    return float(os.getenv(name, default))


def _i(name, default):
    return int(os.getenv(name, default))


@dataclass
class Config:
    # Target beacon (BLE local name advertised by nRF Connect on the phone)
    target_name: str = field(default_factory=lambda: os.getenv("TARGET_NAME", "Galaxy S25"))
    # Serial link to the Nordic DK (auto-detect SEGGER J-Link VCOM when empty)
    serial_port: str = field(default_factory=lambda: os.getenv("NORDIC_SERIAL_PORT", ""))
    serial_baud: int = field(default_factory=lambda: _i("NORDIC_SERIAL_BAUD", 115200))
    # RSSI filtering
    rssi_window: int = field(default_factory=lambda: _i("RSSI_WINDOW", 10))
    rssi_min_samples: int = field(default_factory=lambda: _i("RSSI_MIN_SAMPLES", 5))
    rssi_ema_alpha: float = field(default_factory=lambda: _f("RSSI_EMA_ALPHA", 0.4))
    rssi_stale_seconds: float = field(default_factory=lambda: _f("RSSI_STALE_SECONDS", 6.0))
    # Homing decisions (dB). Larger RSSI (less negative) = stronger.
    rssi_improvement_db: float = field(default_factory=lambda: _f("RSSI_IMPROVEMENT_DB", 3.0))
    rssi_worsen_db: float = field(default_factory=lambda: _f("RSSI_WORSEN_DB", 3.0))
    target_rssi_threshold: float = field(default_factory=lambda: _f("TARGET_RSSI_THRESHOLD", -45))
    target_rssi_hold_seconds: float = field(default_factory=lambda: _f("TARGET_RSSI_HOLD_SECONDS", 2.0))
    measure_timeout_seconds: float = field(default_factory=lambda: _f("MEASURE_TIMEOUT_SECONDS", 8.0))
    settle_seconds: float = field(default_factory=lambda: _f("SETTLE_SECONDS", 1.5))
    # Motion bursts (robot.py enforces the caps; these are the defaults)
    move_speed: float = field(default_factory=lambda: _f("MOVE_SPEED", 0.3))
    move_step_seconds: float = field(default_factory=lambda: _f("MOVE_STEP_SECONDS", 1.5))
    rotate_speed: float = field(default_factory=lambda: _f("ROTATE_SPEED", 0.8))
    rotate_step_seconds: float = field(default_factory=lambda: _f("ROTATE_STEP_SECONDS", 2.0))
    max_move_speed: float = 0.5
    max_rotate_speed: float = 1.0
    max_burst_seconds: float = 2.0
    # Search limits
    search_timeout_seconds: float = field(default_factory=lambda: _f("SEARCH_TIMEOUT_SECONDS", 180))
    max_moves: int = field(default_factory=lambda: _i("MAX_MOVES", 60))
    probe_patience: int = field(default_factory=lambda: _i("PROBE_PATIENCE", 4))
    trend_db: float = field(default_factory=lambda: _f("TREND_DB", 1.5))
    obstacle_stop_m: float = field(default_factory=lambda: _f("OBSTACLE_STOP_M", 0.6))
    # Go2 connection (secrets come from env only; never committed)
    go2_ip: str = field(default_factory=lambda: os.getenv("GO2_IP", "192.168.12.1"))
    go2_aes_key: str = field(default_factory=lambda: os.getenv("GO2_AES_KEY", ""))
    go2_ssid: str = field(default_factory=lambda: os.getenv("GO2_SSID", ""))
