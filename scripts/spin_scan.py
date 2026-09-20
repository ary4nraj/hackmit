"""ONE spin scan on the real dog: rotate through N headings, print RSSI per heading and the contrast.
Use it to check the reflector before a demo run: you want >= 8 dB between the best and worst heading.
  ./scripts/sh-python.sh scripts/spin_scan.py [--headings 6] [--yes]
"""
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1]))
import argparse
import asyncio
import math

from signalhound.config import Config
from signalhound.homing import scan as scanmod
from signalhound.homing.controller import HomingController
from signalhound.radio import make_radio
from signalhound.robot.go2 import Go2Robot
from signalhound.robot.safety import MotionGuard


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--headings", type=int, default=6)
    p.add_argument("--yes", action="store_true")
    a = p.parse_args()
    cfg = Config()
    cfg.search_timeout_seconds = 600
    cfg.max_moves = 200
    radio = make_radio(cfg).start()
    robot = Go2Robot(cfg)
    await robot.connect()
    guard = MotionGuard(robot, cfg)
    ctl = HomingController(cfg, radio, robot, guard)
    ctl.on_update = lambda c: print(f"  [{c.state}] {c.decision}", flush=True)
    try:
        await asyncio.sleep(1.0)
        if not robot.status()["telemetry_fresh"]:
            print("no fresh telemetry; abort")
            return
        print("waiting for beacon...")
        while radio.get_filtered_rssi() is None:
            await asyncio.to_thread(radio.wait_for_samples, 1, 1.0)
        base = await ctl._measure("baseline")
        print(f"baseline {base} dBm (n={ctl.last_measure_n}) at yaw {scanmod.deg(await robot.get_yaw())}°")
        if not a.yes and input("Spin the dog in place through the headings? type YES: ").strip() != "YES":
            return
        await robot.stand_up()
        ctl.started = ctl.clock()
        readings = await scanmod.spin_scan(ctl, a.headings)
        print("\nRESULT")
        for y, r, n in readings:
            print(f"  yaw {scanmod.deg(y):5d}°  rssi {'n/a' if r is None else f'{r:6.1f}'} dBm  (n={n})")
        c = scanmod.contrast(readings)
        y, r = scanmod.best_heading(readings)
        print(f"  contrast {c} dB  best heading {scanmod.deg(y)}°")
        print("  verdict:", "GOOD (>= 6 dB): set HOMING_MODE=scan" if c and c >= 6 else "WEAK (< 6 dB): stay on HOMING_MODE=climb")
    finally:
        await guard.stop()
        await robot.stop()
        radio.stop()
        await robot.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
