"""Terminal status display. Redraws in place; no curses so it survives any terminal."""

import math
import sys
import time

ARROWS = {"IMPROVED": "↑", "WORSENED": "↓"}


def fmt(v, unit="", digits=1):
    return "  n/a" if v is None else f"{v:.{digits}f}{unit}"


def render(cfg, radio, robot, ctl, extra=""):
    s = radio.snapshot()
    st = robot.status()
    yaw = st.get("yaw")
    trend = ""
    if ctl and ctl.best_rssi is not None and s["filtered"] is not None:
        trend = f"{s['filtered'] - ctl.best_rssi:+.1f} dB vs best"
    elapsed = ctl.elapsed() if ctl else 0
    lines = [
        "SIGNALHOUND  ·  radio homing on a Unitree Go2  ·  Ctrl+C = STOP",
        "=" * 64,
        f"TARGET   {cfg.target_name}   ({'serial ' + str(s['port']) if s['connected'] else 'SERIAL NOT CONNECTED'})",
        "",
        "RADIO",
        f"  Raw RSSI:       {fmt(s['raw'], ' dBm', 0)}",
        f"  Filtered RSSI:  {fmt(s['filtered'], ' dBm')}",
        f"  Median/σ:       {fmt(s['median'])} / {s['stdev']}",
        f"  Samples:        {s['samples']} (total {s['total']})   status: {s['status']}   {trend}",
        "",
        "ROBOT",
        f"  Connected:      {'YES' if st.get('connected') else 'NO'}   telemetry: {'fresh' if st.get('telemetry_fresh', True) else 'STALE'}",
        f"  x / y:          {fmt(st.get('x'), '', 2)} / {fmt(st.get('y'), '', 2)}",
        f"  yaw:            {fmt(None if yaw is None else math.degrees(yaw), '°', 0)}",
        f"  obstacle:       {st.get('range_obstacle')}",
        "",
        "SEARCH",
        f"  State:          {ctl.state if ctl else '-'}",
        f"  Best RSSI:      {fmt(ctl.best_rssi if ctl else None, ' dBm')}",
        f"  Elapsed:        {int(elapsed)//60:02d}:{int(elapsed)%60:02d}    Moves: {ctl.moves if ctl else 0}",
        "",
        f"Decision:  {ctl.decision if ctl else ''}",
        extra,
    ]
    out = "\x1b[H\x1b[J" + "\n".join(lines) + "\n"
    sys.stdout.write(out)
    sys.stdout.flush()


class Ticker:
    def __init__(self, period=0.3):
        self.period = period
        self.last = 0

    def due(self):
        now = time.time()
        if now - self.last >= self.period:
            self.last = now
            return True
        return False
