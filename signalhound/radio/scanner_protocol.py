"""Line protocol between the Nordic DK and the laptop. One line per event, comma separated.

  TARGET,<name>,<rssi_dbm>,<addr>      target beacon seen (this is what steering uses)
  ADV,<name>,<rssi_dbm>,<addr>         any other named advertiser (rate limited); the laptop may treat one of these as the target
  SCAN,<packets_total>,<target_total>  1 Hz heartbeat proving the board is alive
  BOOT,<version>                       firmware started
"""

from dataclasses import dataclass


@dataclass
class Line:
    kind: str
    name: str = ""
    rssi: float | None = None
    addr: str = ""
    extra: tuple = ()


def parse_line(raw: str):
    text = raw.strip().lstrip("\x00")
    if not text or "," not in text:
        return None
    parts = text.split(",")
    kind = parts[0].strip().upper()
    try:
        if kind == "TARGET" and len(parts) >= 3:
            return Line("TARGET", parts[1].strip(), float(parts[2]), parts[3].strip() if len(parts) > 3 else "")
        if kind in ("SEEN", "ADV") and len(parts) >= 3:
            return Line("ADV", parts[1].strip(), float(parts[2]), parts[3].strip() if len(parts) > 3 else "")
        if kind == "RSSI" and len(parts) >= 2:  # bare form, name unknown
            return Line("TARGET", "", float(parts[1]))
        if kind == "SCAN":
            return Line("SCAN", extra=tuple(int(p) for p in parts[1:3]))
        if kind == "BOOT":
            return Line("BOOT", parts[1].strip() if len(parts) > 1 else "")
    except ValueError:
        return None
    return None
